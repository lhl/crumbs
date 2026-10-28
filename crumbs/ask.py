"""Ask engine (AGT v1): answers the demo query families by composing the
local index tools over records only.

Rules (AGT-04): every factual claim in an answer is assembled from tool
results (visits, candidates, extractions, stays); unknown is a designed
outcome. This v1 uses deterministic intent parsing — a Glimmer tool-calling
front-end can replace the parser later without changing the tools or the
answer contract.

Families:
  A. "what did I have / order / eat at <place>?"     -> visits whose place
     candidates match the name; dishes from those visits' extractions.
  B. "what was the <kind> place near <anchor> (that week / in <month year>)?"
     -> anchor resolution (place registry or known public area), visits in
     the window within radius, their ranked candidates.
  C. "what did I have last time I was here?" (with current location)
     -> nearest past food visits to the given coordinates.
  D. keyword fallback over extraction text / categories.
"""

import json
import re
from datetime import datetime

from .places import haversine_m, search_name

# Public city/area centers (geography, not personal data) for name anchors
# that are areas rather than venues.
AREAS = {
    "kyoto": (35.0116, 135.7681), "arashiyama": (35.0094, 135.6668),
    "tokyo": (35.6762, 139.6503), "taipei": (25.0330, 121.5654),
    "seattle": (47.6062, -122.3321), "sapporo": (43.0618, 141.3545),
    "okinawa": (26.2124, 127.6809),
}
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}


def _window_from_query(q: str):
    m = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})", q)
    if m:
        y, mo = int(m.group(2)), MONTHS[m.group(1)]
        return (f"{y}-{mo:02d}-01", f"{y}-{mo:02d}-31")
    m = re.search(r"\b(20\d{2})\b", q)
    if m:
        return (f"{m.group(1)}-01-01", f"{m.group(1)}-12-31")
    return None


def _find_place_in_query(conn, q: str):
    """Longest registry place name appearing in the query (if any)."""
    best = None
    for p in conn.execute("SELECT id, name, lat, lon, kind FROM places"):
        name = p["name"]
        if len(name) >= 3 and name.lower() in q and (best is None or len(name) > len(best["name"])):
            best = dict(p)
    return best


def _visits_in_window(conn, frm, to):
    return conn.execute(
        "SELECT * FROM visits WHERE center_lat IS NOT NULL AND started_at >= ? AND started_at <= ? ORDER BY started_at",
        (frm + " 00:00:00", to + " 23:59:59"),
    ).fetchall()


def _visit_candidates(conn, visit_id, limit=5):
    return [dict(r) for r in conn.execute(
        """SELECT p.name, p.kind, vc.distance_m, vc.evidence FROM visit_place_candidates vc
           JOIN places p ON p.id = vc.place_id WHERE vc.visit_id = ? ORDER BY vc.distance_m LIMIT ?""",
        (visit_id, limit))]


def _visit_dishes(conn, visit_id):
    dishes = []
    for (data_json,) in conn.execute(
        """SELECT e.data_json FROM extractions e JOIN visit_media vm ON vm.media_id = e.media_id
           WHERE vm.visit_id = ?""", (visit_id,)):
        for d in json.loads(data_json).get("dish_candidates", []):
            if d["name"] not in dishes:
                dishes.append(d["name"])
    return dishes


def ask(conn, question: str, lat=None, lon=None) -> dict:
    q = " " + question.lower().strip() + " "
    evidence = {"visits": [], "places": [], "media": []}

    # Family C: last time I was here
    if ("last time" in q or "was here" in q or "near me" in q) and lat is not None:
        rows = []
        for v in conn.execute("SELECT * FROM visits WHERE center_lat IS NOT NULL ORDER BY started_at DESC"):
            d = haversine_m(lat, lon, v["center_lat"], v["center_lon"])
            if d <= 1000:
                cands = _visit_candidates(conn, v["id"], 3)
                rows.append((d, v, cands))
                if len(rows) >= 5:
                    break
        if not rows:
            return {"status": "unknown", "answer": "No past visits found within 1 km of your current location.", "evidence": evidence}
        lines = ["Your past visits near here:"]
        for d, v, cands in rows:
            evidence["visits"].append(v["id"])
            names = ", ".join(f"{c['name']} ({c['distance_m']:.0f} m from photo cluster)" for c in cands) or "unnamed place"
            dishes = _visit_dishes(conn, v["id"])
            lines.append(f"- {v['started_at'][:10]}: {names}" + (f" — dishes seen: {', '.join(dishes[:4])}" if dishes else ""))
        return {"status": "answered", "answer": "\n".join(lines), "evidence": evidence}

    place = _find_place_in_query(conn, question.lower())
    area = next(((name, c) for name, c in AREAS.items() if f" {name} " in q or f" {name}?" in q), None)

    # Family A: what did I have at <place>
    if place and any(w in q for w in (" have ", " had ", " order", " eat ", " ate ")):
        visits = conn.execute(
            """SELECT DISTINCT v.id, v.started_at FROM visit_place_candidates vc
               JOIN visits v ON v.id = vc.visit_id WHERE vc.place_id = ? ORDER BY v.started_at""",
            (place["id"],)).fetchall()
        if not visits:
            return {"status": "unknown", "answer": f"No visits are linked to {place['name']} yet.", "evidence": evidence}
        lines = [f"Visits where {place['name']} is a nearby place candidate (candidate, not confirmed — confirm in the review queue):"]
        for v in visits:
            evidence["visits"].append(v["id"])
            dishes = _visit_dishes(conn, v["id"])
            lines.append(f"- {v['started_at'][:10]}" + (f": {', '.join(dishes[:6])}" if dishes else ": no dish extraction for this visit"))
        evidence["places"].append(place["id"])
        return {"status": "answered", "answer": "\n".join(lines), "evidence": evidence}

    # Family B: anchor + window restaurant recall
    anchor = None
    if place:
        anchor = (place["name"], place["lat"], place["lon"])
    elif area:
        anchor = (area[0].title(), area[1][0], area[1][1])
    if anchor and any(w in q for w in ("restaurant", "place", "eat", "food", "dashi", "tempura", "ramen", "cafe", "near", "week", "trip", "else", "other")):
        window = _window_from_query(q)
        visits = _visits_in_window(conn, *(window or ("0000-01-01", "9999-12-31")))
        picked = []
        for v in visits:
            d = haversine_m(anchor[1], anchor[2], v["center_lat"], v["center_lon"])
            if d <= 2000:
                picked.append((d, v))
        if not picked:
            return {"status": "unknown",
                    "answer": f"No visits found within 2 km of {anchor[0]}" + (f" in {window[0][:7]}" if window else "") + ".",
                    "evidence": evidence}
        lines = [f"Visits near {anchor[0]}" + (f" ({window[0][:7]})" if window else "") + ":"]
        for d, v in picked[:8]:
            evidence["visits"].append(v["id"])
            cands = _visit_candidates(conn, v["id"], 4)
            names = ", ".join(f"{c['name']} ({c['distance_m']:.0f} m)" for c in cands) or "no known restaurant nearby (unnamed)"
            lines.append(f"- {v['started_at'][:10]} ({d:.0f} m from anchor): {names}")
        return {"status": "answered", "answer": "\n".join(lines), "evidence": evidence}

    # Family D: keyword fallback across extraction text + categories
    words = [w for w in re.findall(r"[a-z]{4,}", q) if w not in
             ("what", "where", "when", "have", "that", "this", "with", "from", "were", "been")]
    hits = []
    if words:
        for (mid, data_json, cat) in conn.execute(
            """SELECT m.id, e.data_json, json_extract(c.labels_json, '$.category')
               FROM media_items m
               LEFT JOIN extractions e ON e.id = (SELECT MAX(id) FROM extractions WHERE media_id = m.id)
               LEFT JOIN classifications c ON c.id = (SELECT MAX(id) FROM classifications WHERE media_id = m.id)"""):
            hay = (data_json or "").lower()
            if any(w in hay for w in words):
                hits.append(mid)
    if hits:
        evidence["media"] = hits[:10]
        return {"status": "answered",
                "answer": f"Found {len(hits)} photos whose extracted text/dishes match ({', '.join(words[:3])}). Media ids: {hits[:10]}.",
                "evidence": evidence}
    return {"status": "unknown",
            "answer": "I don't have records that answer that yet. Try naming a place, a month/year, or a dish.",
            "evidence": evidence}
