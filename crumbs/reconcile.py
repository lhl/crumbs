"""Visit reconciliation (REC-02 v1): deterministic evidence scoring.

For each visit, every place candidate is scored from independent evidence
kinds, strongest first (PLAN triangulation order):
  signage-text match (name read from the visit's own photos) .... +50
  dwell stay overlapping the visit, candidate near its center ... +25/+15
  location track present within 250 m during the visit ......... +10
  GPS proximity of candidate to visit center ................... 0..20
  visit has food evidence ...................................... +5
Nothing here *confirms* a place: the best outcome is `candidate-strong`.
Confirmation comes from a check-in, a signage match the user accepts, or
the user — REC-03's rules, enforced by construction in this scoring.
Visits that stay weak/unknown produce exactly one review question each.
Every score is stored with its reasons so the decision is auditable.
"""

import json
from datetime import datetime, timedelta, timezone
from statistics import median

from .locations import _track, haversine_m, track_position_at

ALGO = "reconcile-v1(evidence-score)"


def _visit_offsets(conn):
    offs = {}
    for vid, off in conn.execute(
        "SELECT vm.visit_id, tz.offset_hours FROM visit_media vm JOIN tz_estimates tz ON tz.media_id = vm.media_id"
    ):
        offs.setdefault(vid, []).append(off)
    return {k: median(v) for k, v in offs.items()}


def _track_near_visit(track, ts_list, v, off_hours) -> float:
    """Minimum distance (m) from the visit center to the track during the
    (tz-corrected) visit window, sampled every 5 min; inf if no coverage."""
    t0 = datetime.fromisoformat(v["started_at"]) - timedelta(hours=float(off_hours))
    t1 = datetime.fromisoformat(v["ended_at"]) - timedelta(hours=float(off_hours))
    a = int(t0.replace(tzinfo=timezone.utc).timestamp() * 1000) - 1800_000
    b = int(t1.replace(tzinfo=timezone.utc).timestamp() * 1000) + 1800_000
    best = float("inf")
    t = a
    while t <= b:
        pos = track_position_at(track, ts_list, t)
        if pos:
            best = min(best, haversine_m(v["center_lat"], v["center_lon"], pos[0], pos[1]))
        t += 300_000
    return best


def reconcile_all(conn) -> dict:
    track = _track(conn)
    ts_list = [p[0] for p in track]
    offsets = _visit_offsets(conn)
    conn.execute("DELETE FROM visit_resolutions WHERE created_by = ?", (ALGO,))
    conn.execute("DELETE FROM review_questions WHERE created_by = ? AND status = 'open'", (ALGO,))

    visits = conn.execute("SELECT * FROM visits ORDER BY started_at").fetchall()
    stats = {"visits": 0, "candidate-strong": 0, "candidate-weak": 0, "unknown": 0, "questions": 0}
    for v in visits:
        stats["visits"] += 1
        reasons = []
        if v["center_lat"] is None:
            conn.execute(
                "INSERT OR REPLACE INTO visit_resolutions (visit_id, status, tier, reasons_json, created_by) "
                "VALUES (?, 'unknown', 'weak', ?, ?)",
                (v["id"], json.dumps(["no GPS center"]), ALGO),
            )
            stats["unknown"] += 1
            continue

        cands = conn.execute(
            """SELECT vc.place_id, vc.distance_m, vc.evidence, p.name FROM visit_place_candidates vc
               JOIN places p ON p.id = vc.place_id WHERE vc.visit_id = ?""", (v["id"],)).fetchall()
        stay = conn.execute(
            """SELECT s.center_lat, s.center_lon, vs.time_relation FROM visit_stays vs
               JOIN stays s ON s.id = vs.stay_id WHERE vs.visit_id = ? ORDER BY vs.center_distance_m LIMIT 1""",
            (v["id"],)).fetchone()
        track_d = _track_near_visit(track, ts_list, v, offsets.get(v["id"], 0))
        (food_n,) = conn.execute(
            """SELECT COUNT(*) FROM visit_media vm JOIN classifications c ON c.media_id = vm.media_id
               WHERE vm.visit_id = ? AND json_extract(c.labels_json, '$.category') = 'food'""", (v["id"],)).fetchone()

        scored = {}
        for c in cands:
            s = scored.setdefault(c["place_id"], {"place_id": c["place_id"], "name": c["name"], "score": 0.0, "why": []})
            if c["evidence"] == "signage-text":
                s["score"] += 50; s["why"].append("signage-text name match")
            if c["evidence"] == "gps":
                pts = max(0.0, 20.0 - c["distance_m"] / 15.0)
                s["score"] += pts; s["why"].append(f"gps {c['distance_m']:.0f} m (+{pts:.0f})")
            if stay is not None:
                (plat, plon) = conn.execute("SELECT lat, lon FROM places WHERE id = ?", (c["place_id"],)).fetchone()
                d_stay = haversine_m(stay["center_lat"], stay["center_lon"], plat, plon)
                if d_stay <= 150:
                    pts = 25 if stay["time_relation"] == "overlap" else 15
                    s["score"] += pts; s["why"].append(f"dwell stay {stay['time_relation']} (+{pts})")
            if track_d <= 250:
                s["score"] += 10; s["why"].append("track present <=250 m (+10)")
        if food_n:
            for s in scored.values():
                s["score"] += 5; s["why"].append("food photo in visit (+5)")
        ranked = sorted(scored.values(), key=lambda x: -x["score"])
        top = ranked[0] if ranked else None
        second = ranked[1]["score"] if len(ranked) > 1 else 0.0

        if top and top["score"] >= 45 and top["score"] - second >= 10:
            status, tier = "candidate-strong", "strong"
        elif top and top["score"] >= 30:
            status, tier = "candidate-weak", "medium"
        else:
            status, tier = "unknown", "weak"
        stats[status] += 1
        reasons = ranked[:3]
        conn.execute(
            "INSERT OR REPLACE INTO visit_resolutions (visit_id, top_place_id, status, tier, reasons_json, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (v["id"], top["place_id"] if top else None, status, tier,
             json.dumps({"ranked": reasons, "track_min_distance_m": None if track_d == float("inf") else round(track_d)}, ensure_ascii=False), ALGO),
        )
        if status != "candidate-strong" and food_n:
            q = (f"Was this {top['name']} ({ranked[0]['why'][0] if ranked and ranked[0]['why'] else 'nearby candidate'}), "
                 "another nearby place, or somewhere else?") if top else \
                "You took food photos here, but no restaurant nearby is known. Do you remember the place?"
            conn.execute(
                "INSERT OR IGNORE INTO review_questions (visit_id, question, created_by) VALUES (?, ?, ?)",
                (v["id"], q, ALGO),
            )
            stats["questions"] += 1
    conn.commit()
    return stats
