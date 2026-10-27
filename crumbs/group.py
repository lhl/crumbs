"""Deterministic pre-grouping (REC-01): candidate visits and trips from
time gaps and GPS jumps. No model involved; REC-02 reconciliation (Glimmer)
refines these later. Derived rows are regenerated per run (created_by marks
the algorithm version), never edited in place.

Rules v1:
- Order photos by captured_at (photos without a time cannot be grouped and
  are reported, not silently dropped).
- New visit when the gap from the previous photo exceeds GAP_HOURS, or the
  GPS distance from the previous GPS-bearing photo exceeds JUMP_KM.
- New trip when the gap between consecutive visits exceeds TRIP_GAP_DAYS.
Times are camera-local (IMP-03 timezone inference outstanding), so grouping
is only trustworthy within a continuous travel stretch until then.
"""

import math
from datetime import datetime

from . import db

GAP_HOURS = 6
JUMP_KM = 50
TRIP_GAP_DAYS = 4
ALGO = f"group-v1(gap={GAP_HOURS}h,jump={JUMP_KM}km)"


def haversine_km(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def group_all(conn) -> dict:
    rows = conn.execute(
        "SELECT id, captured_at, gps_lat, gps_lon FROM media_items "
        "WHERE captured_at IS NOT NULL ORDER BY captured_at, id"
    ).fetchall()
    untimed = conn.execute("SELECT COUNT(*) FROM media_items WHERE captured_at IS NULL").fetchone()[0]

    conn.execute("DELETE FROM trip_visits WHERE trip_id IN (SELECT id FROM trips WHERE created_by = ?)", (ALGO,))
    conn.execute("DELETE FROM trips WHERE created_by = ?", (ALGO,))
    conn.execute("DELETE FROM visit_media WHERE visit_id IN (SELECT id FROM visits WHERE created_by = ?)", (ALGO,))
    conn.execute("DELETE FROM visits WHERE created_by = ?", (ALGO,))

    visits: list[list] = []
    current: list = []
    prev = None
    for r in rows:
        t = datetime.fromisoformat(r["captured_at"])
        split = False
        if prev is not None:
            gap_h = (t - prev[0]).total_seconds() / 3600
            if gap_h > GAP_HOURS:
                split = True
            elif (
                r["gps_lat"] is not None and prev[1] is not None
                and haversine_km((r["gps_lat"], r["gps_lon"]), prev[1]) > JUMP_KM
            ):
                split = True
        if split and current:
            visits.append(current)
            current = []
        current.append(r)
        prev = (t, (r["gps_lat"], r["gps_lon"]) if r["gps_lat"] is not None else (prev[1] if prev else None))
    if current:
        visits.append(current)

    visit_ids = []
    for v in visits:
        lats = [r["gps_lat"] for r in v if r["gps_lat"] is not None]
        lons = [r["gps_lon"] for r in v if r["gps_lon"] is not None]
        cur = conn.execute(
            "INSERT INTO visits (started_at, ended_at, center_lat, center_lon, photo_count, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (v[0]["captured_at"], v[-1]["captured_at"],
             _median(lats) if lats else None, _median(lons) if lons else None, len(v), ALGO),
        )
        vid = cur.lastrowid
        visit_ids.append((vid, v))
        conn.executemany("INSERT INTO visit_media (visit_id, media_id) VALUES (?, ?)",
                         [(vid, r["id"]) for r in v])

    # trips: split on long gaps between consecutive visits
    trips = 0
    current_trip: list[int] = []
    prev_end = None
    def flush():
        nonlocal trips
        if not current_trip:
            return
        cur = conn.execute(
            "INSERT INTO trips (name, started_at, ended_at, created_by) VALUES (NULL, ?, ?, ?)",
            (conn.execute("SELECT started_at FROM visits WHERE id = ?", (current_trip[0],)).fetchone()[0],
             conn.execute("SELECT ended_at FROM visits WHERE id = ?", (current_trip[-1],)).fetchone()[0], ALGO),
        )
        conn.executemany("INSERT INTO trip_visits (trip_id, visit_id) VALUES (?, ?)",
                         [(cur.lastrowid, vid) for vid in current_trip])
        trips += 1
    for vid, v in visit_ids:
        start = datetime.fromisoformat(v[0]["captured_at"])
        if prev_end is not None and (start - prev_end).days >= TRIP_GAP_DAYS:
            flush()
            current_trip = []
        current_trip.append(vid)
        prev_end = datetime.fromisoformat(v[-1]["captured_at"])
    flush()
    conn.commit()
    sizes = [len(v) for _, v in visit_ids]
    return {
        "visits": len(visits), "trips": trips, "untimed_photos": untimed,
        "visit_size_median": _median(sizes) if sizes else 0,
        "visit_size_max": max(sizes) if sizes else 0,
        "single_photo_visits": sum(1 for s in sizes if s == 1),
    }
