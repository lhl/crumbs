"""Location-history import, stay derivation, and photo cross-correlation.

Input: a Wanderings GeoJSON export (epoch-ms points with accuracy). Points
are stored raw and `observed`; everything derived (stays, visit matches) is
versioned `inferred` with the algorithm in `created_by`.

Best uses of this source, in order:
1. Corroborate photo visits (a dwell at the same time/place is independent
   evidence a visit happened, and the dwell center is usually a better
   position than a sampled photo's GPS).
2. Surface "dark visits" — stays with no photos — so recommendations are
   not limited to what was photographed.
3. Anchor timezone inference (IMP-03): photo EXIF times are camera-local,
   this track is UTC; matching photo positions against the track over
   candidate UTC offsets recovers the camera offset per trip (probe later;
   the data model keeps both clocks explicit until then).
"""

import json
import math
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

ACC_MAX_M = 200.0          # points worse than this are stored but not used for stays
STAY_RADIUS_M = 150.0
STAY_MIN_MINUTES = 20
STAY_ALGO = "stay-v1(r=150m,min=20min,acc<=200m)"


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def import_wanderings(conn, path: Path) -> dict:
    data = json.loads(path.read_text())
    feats = data["features"]
    cur = conn.execute(
        "INSERT INTO source_imports (kind, scope, source_ref) VALUES ('wanderings', ?, ?)",
        (f"Wanderings locations export ({len(feats)} points)", str(path)),
    )
    import_id = cur.lastrowid
    rows = []
    for f in feats:
        lon, lat = f["geometry"]["coordinates"]
        p = f["properties"]
        rows.append((int(p["ts"]), _iso(int(p["ts"])), lat, lon, p.get("acc"), import_id))
    conn.executemany(
        "INSERT INTO location_records (ts_ms, recorded_at, lat, lon, accuracy_m, import_id, source) "
        "VALUES (?, ?, ?, ?, ?, ?, 'wanderings')",
        rows,
    )
    conn.commit()
    return {"points": len(rows), "import_id": import_id}


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371000.0 * 2 * math.asin(math.sqrt(h))


def derive_stays(conn) -> dict:
    """Greedy dwell clustering over accuracy-filtered points in time order:
    a stay grows while points stay within STAY_RADIUS_M of its running center;
    it is kept when it spans at least STAY_MIN_MINUTES."""
    conn.execute("DELETE FROM visit_stays")
    conn.execute("DELETE FROM stays WHERE created_by = ?", (STAY_ALGO,))
    pts = conn.execute(
        "SELECT ts_ms, lat, lon FROM location_records WHERE accuracy_m IS NULL OR accuracy_m <= ? ORDER BY ts_ms",
        (ACC_MAX_M,),
    ).fetchall()
    stays, current = [], []
    center = None
    for ts, lat, lon in pts:
        if center is not None and haversine_m(center[0], center[1], lat, lon) <= STAY_RADIUS_M:
            current.append((ts, lat, lon))
            n = len(current)
            center = (sum(p[1] for p in current) / n, sum(p[2] for p in current) / n)
        else:
            if current:
                stays.append(current)
            current, center = [(ts, lat, lon)], (lat, lon)
    if current:
        stays.append(current)
    kept = 0
    for s in stays:
        span_min = (s[-1][0] - s[0][0]) / 60000.0
        if span_min < STAY_MIN_MINUTES:
            continue
        n = len(s)
        conn.execute(
            "INSERT INTO stays (started_at, ended_at, center_lat, center_lon, point_count, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_iso(s[0][0]), _iso(s[-1][0]), sum(p[1] for p in s) / n, sum(p[2] for p in s) / n, n, STAY_ALGO),
        )
        kept += 1
    conn.commit()
    return {"raw_clusters": len(stays), "stays_kept": kept, "points_used": len(pts)}


def _track(conn):
    return conn.execute(
        "SELECT ts_ms, lat, lon FROM location_records WHERE accuracy_m IS NULL OR accuracy_m <= ? ORDER BY ts_ms",
        (ACC_MAX_M,),
    ).fetchall()


def track_position_at(track, ts_list, ts_ms):
    """Linear-interpolated track position at a UTC instant (None outside range)."""
    i = bisect_left(ts_list, ts_ms)
    if i == 0 or i >= len(track):
        return None
    (t0, la0, lo0), (t1, la1, lo1) = track[i - 1], track[i]
    if t1 == t0:
        return la0, lo0
    f = (ts_ms - t0) / (t1 - t0)
    return la0 + (la1 - la0) * f, lo0 + (lo1 - lo0) * f


TZ_ALGO = "tz-v1(track-match,hourly)"


def estimate_timezones(conn) -> dict:
    """IMP-03 via the track: for each GPS+time photo, find the whole-hour UTC
    offset that puts the interpolated track position closest to the photo's
    own GPS. Stores per-photo estimates; visits use their median."""
    from collections import Counter

    track = _track(conn)
    ts_list = [p[0] for p in track]
    photos = conn.execute(
        "SELECT id, captured_at, gps_lat, gps_lon FROM media_items "
        "WHERE gps_lat IS NOT NULL AND captured_at IS NOT NULL"
    ).fetchall()
    conn.execute("DELETE FROM tz_estimates WHERE created_by = ?", (TZ_ALGO,))
    hist, within = Counter(), 0
    for p in photos:
        base_ms = int(datetime.fromisoformat(p["captured_at"]).replace(tzinfo=timezone.utc).timestamp() * 1000)
        best_h, best_d = None, float("inf")
        for h in range(-12, 15):
            pos = track_position_at(track, ts_list, base_ms - h * 3600_000)
            if pos is None:
                continue
            d = haversine_m(p["gps_lat"], p["gps_lon"], pos[0], pos[1])
            if d < best_d:
                best_h, best_d = h, d
        if best_h is None:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO tz_estimates (media_id, offset_hours, track_distance_m, created_by) VALUES (?, ?, ?, ?)",
            (p["id"], best_h, round(best_d, 1), TZ_ALGO),
        )
        hist[best_h] += 1
        if best_d <= 1000:
            within += 1
    conn.commit()
    return {"photos": len(photos), "within_1km_at_best_offset": within, "offset_histogram": dict(sorted(hist.items()))}


def correlate(conn) -> dict:
    """Match photo visits to stays (time overlap or within 2h, centers within
    1 km) and measure photo/track agreement. Visit times are camera-local,
    stay times UTC — a constant per-trip offset therefore *understates*
    matches until IMP-03 lands; the report says so instead of hiding it."""
    track = _track(conn)
    ts_list = [p[0] for p in track]
    visits = conn.execute(
        "SELECT id, started_at, ended_at, center_lat, center_lon FROM visits WHERE center_lat IS NOT NULL"
    ).fetchall()
    stays = conn.execute("SELECT id, started_at, ended_at, center_lat, center_lon FROM stays").fetchall()

    def parse(s):
        return datetime.fromisoformat(s)

    # Convert each visit's camera-local window to UTC using its photos'
    # median tz estimate (fallback: face value, which understates matches).
    offsets = {}
    for vid, off in conn.execute(
        "SELECT vm.visit_id, tz.offset_hours FROM visit_media vm JOIN tz_estimates tz ON tz.media_id = vm.media_id"
    ):
        offsets.setdefault(vid, []).append(off)
    from statistics import median as _median

    conn.execute("DELETE FROM visit_stays")
    matched_visits, matched_stays = set(), set()
    links = 0
    for v in visits:
        off = _median(offsets[v["id"]]) if v["id"] in offsets else 0
        from datetime import timedelta

        vs = parse(v["started_at"]) - timedelta(hours=float(off))
        ve = parse(v["ended_at"]) - timedelta(hours=float(off))
        for s in stays:
            ss, se = parse(s["started_at"]), parse(s["ended_at"])
            overlap = not (ve < ss or vs > se)
            near = not overlap and (abs((ss - ve).total_seconds()) <= 7200 or abs((vs - se).total_seconds()) <= 7200)
            if not (overlap or near):
                continue
            d = haversine_m(v["center_lat"], v["center_lon"], s["center_lat"], s["center_lon"])
            if d <= 1000:
                conn.execute(
                    "INSERT OR IGNORE INTO visit_stays (visit_id, stay_id, center_distance_m, time_relation) VALUES (?, ?, ?, ?)",
                    (v["id"], s["id"], round(d, 1), "overlap" if overlap else "near"),
                )
                matched_visits.add(v["id"]); matched_stays.add(s["id"]); links += 1
    conn.commit()

    photos = conn.execute(
        "SELECT m.captured_at, m.gps_lat, m.gps_lon, tz.offset_hours FROM media_items m "
        "LEFT JOIN tz_estimates tz ON tz.media_id = m.id "
        "WHERE m.gps_lat IS NOT NULL AND m.captured_at IS NOT NULL"
    ).fetchall()
    agree = within = 0
    for p in photos:
        off = p["offset_hours"] or 0
        base_ms = int(datetime.fromisoformat(p["captured_at"]).replace(tzinfo=timezone.utc).timestamp() * 1000)
        pos = track_position_at(track, ts_list, base_ms - off * 3600_000)
        if pos is None:
            continue
        within += 1
        if haversine_m(p["gps_lat"], p["gps_lon"], pos[0], pos[1]) <= 1000:
            agree += 1
    return {
        "visits": len(visits), "visits_matched_to_stay": len(matched_visits), "links": links,
        "stays": len(stays), "stays_without_visit": len(stays) - len(matched_stays),
        "photos_with_track_position": within, "photos_agreeing_within_1km": agree,
        "note": "times tz-corrected per photo (tz-v1); dwell stays are the specific subset - track-presence within the visit window is the broader corroboration",
    }
