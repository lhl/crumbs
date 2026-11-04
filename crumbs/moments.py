"""Moments: finer-grained evidence inside a visit, for multi-step recall.

A visit is often a whole day of photos. A "moment" is a run of photos with
no gap longer than MOMENT_GAP_MIN, which is usually one meal or one stop.
Everything here is read from stored extractions (photo text, dish names);
nothing is inferred beyond grouping by time.
"""

import re

from .ask import _food_media, _in_scope

MOMENT_GAP_MIN = 20
_NORM = re.compile(r"[\s\-‐'’`·.,:/()]+")


def norm(s: str) -> str:
    """Lowercase and drop spaces/punctuation so 'Kinkaku-ji' matches 'Kinkakuji'."""
    return _NORM.sub("", (s or "").lower())


def _minutes(ts: str) -> int:
    h, m = int(ts[11:13]), int(ts[14:16])
    return h * 60 + m


def _photo_text(data: dict) -> tuple[list[str], str, list[dict]]:
    names = [p.get("name") for p in data.get("place_name_candidates") or [] if p.get("name")]
    text = (data.get("visible_text") or "").strip()
    dishes = [d for d in data.get("dish_candidates") or [] if (d.get("name") or "").strip()]
    return names, text, dishes


def visit_moments(conn, visit_id: int, ex: dict) -> list[dict]:
    """Split a visit's photos into moments by time gaps."""
    rows = conn.execute(
        "SELECT m.id, m.captured_at FROM visit_media vm JOIN media_items m ON m.id = vm.media_id "
        "WHERE vm.visit_id = ? AND m.captured_at IS NOT NULL ORDER BY m.captured_at", (visit_id,)).fetchall()
    food = _food_media(conn, visit_id)
    moments, cur, last = [], None, None
    for mid, ts in rows:
        t = _minutes(ts)
        if cur is None or t - last > MOMENT_GAP_MIN:
            cur = {"visit_id": visit_id, "date": ts[:10], "start": ts[11:16], "end": ts[11:16],
                   "media": [], "food": [], "names": [], "texts": [], "dishes": []}
            moments.append(cur)
        last = t
        cur["end"] = ts[11:16]
        cur["media"].append(mid)
        if mid in food:
            cur["food"].append(mid)
        names, text, dishes = _photo_text(ex.get(mid, {}))
        for n in names:
            if n not in cur["names"]:
                cur["names"].append(n)
        line = text.splitlines()[0].strip()[:40] if text else ""
        if line and line not in cur["texts"] and not any(norm(line) == norm(n) for n in cur["names"] + names):
            cur["texts"].append(line)
        for d in dishes:
            if d["name"] not in [x["name"] for x in cur["dishes"]]:
                cur["dishes"].append({"name": d["name"], "basis": d.get("basis") or "seen", "media_id": mid})
    for m in moments:
        dish_photos = [d["media_id"] for d in m["dishes"] if d["media_id"] in m["food"]]
        named = [mid for mid in m["media"] if _photo_text(ex.get(mid, {}))[0]]
        m["photo_id"] = (dish_photos or m["food"] or named or m["media"])[0]
    return moments


def moment_line(m: dict) -> dict:
    """Compact form for the model: small enough for many moments in 8k context."""
    out = {"photo_id": m["photo_id"], "time": f"{m['start']}-{m['end']}", "photos": len(m["media"]),
           "food_photos": len(m["food"])}
    if m["names"]:
        out["photo_text_names"] = m["names"][:3]
    if m["texts"]:
        out["photo_text"] = m["texts"][:2]
    if m["dishes"]:
        out["dishes"] = [d["name"][:50] for d in m["dishes"][:3]]
    return out


def find_photos(conn, ex: dict, query: str, area=None, window=None, limit=8) -> list[dict]:
    """Photos whose read text (signs, place names, dishes) matches a name or word."""
    q = norm(query)
    if len(q) < 2:
        return []
    tokens = [norm(t) for t in re.split(r"\s+", query) if len(norm(t)) >= 4]
    media_visit = dict(conn.execute("SELECT media_id, visit_id FROM visit_media").fetchall())
    visits = {}
    scored = []
    for mid, data in ex.items():
        vid = media_visit.get(mid)
        if vid is None:
            continue
        names, text, dishes = _photo_text(data)
        hay = norm(" ".join(names) + " " + text + " " + " ".join(d["name"] for d in dishes))
        score = 10 if q in hay else sum(t in hay for t in tokens)
        if not score:
            continue
        if vid not in visits:
            visits[vid] = conn.execute("SELECT * FROM visits WHERE id = ?", (vid,)).fetchone()
        if not _in_scope(visits[vid], area, window):
            continue
        scored.append((score, mid, vid, names, text))
    scored.sort(key=lambda s: -s[0])
    out, seen_visits = [], set()
    ts = dict(conn.execute("SELECT id, captured_at FROM media_items").fetchall())
    for score, mid, vid, names, text in scored:
        if vid in seen_visits and len(out) >= 3:
            continue  # spread hits across visits before repeating one
        seen_visits.add(vid)
        when = ts.get(mid) or ""
        out.append({"photo_id": mid, "visit_id": vid, "date": when[:10] or None, "time": when[11:16] or None,
                    "photo_text": (names[:2] or [text.splitlines()[0][:60] if text else ""])})
        if len(out) >= limit:
            break
    return out


def day_visits(conn, date: str) -> list[int]:
    return [r[0] for r in conn.execute(
        "SELECT id FROM visits WHERE substr(started_at, 1, 10) <= ? AND substr(ended_at, 1, 10) >= ? "
        "ORDER BY started_at", (date, date))]


def moment_card(conn, ex: dict, photo_id: int):
    """Evidence card for the moment containing one photo (or None)."""
    row = conn.execute("SELECT visit_id FROM visit_media WHERE media_id = ?", (photo_id,)).fetchone()
    if not row:
        return None
    for m in visit_moments(conn, row[0], ex):
        if photo_id in m["media"]:
            food_first = list(dict.fromkeys([photo_id] + [d["media_id"] for d in m["dishes"]] + m["food"]))
            return {
                "visit_id": m["visit_id"], "date": m["date"], "moment": f"{m['start']}–{m['end']}",
                "photo_id": photo_id,
                "place": {"name": None, "place_id": None, "source": None, "status": None, "rejected": None},
                "text_names": (m["names"] + m["texts"])[:2],
                "dishes": [{"name": d["name"], "basis": d["basis"]} for d in m["dishes"][:6]],
                "media": food_first[:4], "food_photos": len(m["food"]), "match": None, "review": None,
            }
    return None
