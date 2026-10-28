"""Place registry + visit triangulation, v1 (REC-07).

Populates a locally cached registry of named food/drink places around
GPS-bearing, food-bearing visits, and records ranked PlaceCandidates per
visit. Evidence discipline (PLAN section 4, use case 8): GPS proximity only
ever creates *candidates* with their distance shown; confirmation needs a
check-in, a signage-text match, or the user.

Dev-stage lookup source is the Overpass API (OSM). That is a `lookup`
network call and it reveals the queried *area* (a visit centroid) to the
Overpass operator — acceptable for development on the lead's own data, and
NOT the product default: the shipped path reads POIs from locally held
PMTiles extracts (Kyoto/Taipei/Lisbon already; per-trip extracts at import)
so no coordinate ever leaves the device. Results are cached in SQLite, so
each area is fetched at most once.
"""

import json
import math
import time
import urllib.parse
import urllib.request

# Public Overpass instances rate-limit and 504 under load; rotate + retry.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]
AMENITIES = "restaurant|cafe|bar|fast_food|food_court|pub|bakery|ice_cream|biergarten"
ALGO = "places-v1(overpass)"


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371000.0 * 2 * math.asin(math.sqrt(h))


def overpass_around(lat: float, lon: float, radius_m: int) -> list[dict]:
    ql = (
        f"[out:json][timeout:30];"
        f'(node["amenity"~"{AMENITIES}"]["name"](around:{radius_m},{lat},{lon});'
        f'way["amenity"~"{AMENITIES}"]["name"](around:{radius_m},{lat},{lon}););'
        f"out center 60;"
    )
    last_err = None
    for attempt in range(3 * len(OVERPASS_URLS)):
        url = OVERPASS_URLS[attempt % len(OVERPASS_URLS)]
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode({"data": ql}).encode(),
            headers={"User-Agent": "crumbs-dev/0.1 (local place-registry prototype)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
            break
        except Exception as e:  # 504/429/timeout: back off and try the next mirror
            last_err = e
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"all Overpass mirrors failed: {last_err}")
    out = []
    for el in data.get("elements", []):
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plon = el.get("lon") or (el.get("center") or {}).get("lon")
        tags = el.get("tags", {})
        if plat is None or not tags.get("name"):
            continue
        out.append({
            "external_id": f"osm:{el['type']}/{el['id']}",
            "name": tags["name"], "kind": tags.get("amenity"),
            "cuisine": tags.get("cuisine"), "lat": plat, "lon": plon,
        })
    return out


def food_visits(conn):
    return conn.execute(
        """SELECT v.id, v.center_lat, v.center_lon FROM visits v
           WHERE v.center_lat IS NOT NULL AND EXISTS (
             SELECT 1 FROM visit_media vm JOIN classifications c ON c.media_id = vm.media_id
             WHERE vm.visit_id = v.id
               AND json_extract(c.labels_json, '$.category') = 'food')
           ORDER BY v.started_at"""
    ).fetchall()


def fetch_candidates(conn, radius_m: int = 300, pause_s: float = 1.1) -> dict:
    visits = food_visits(conn)
    done_ids = {r[0] for r in conn.execute(
        "SELECT DISTINCT visit_id FROM visit_place_candidates WHERE created_by = ?", (ALGO,))}
    stats = {"visits_queried": 0, "places_seen": 0, "candidates": 0, "visits_with_candidates": 0,
             "skipped_done": 0, "failed": 0}
    for v in visits:
        if v["id"] in done_ids:
            stats["skipped_done"] += 1
            continue
        try:
            found = overpass_around(v["center_lat"], v["center_lon"], radius_m)
        except Exception as e:
            stats["failed"] += 1
            print(f"visit {v['id']}: FAILED {e}", flush=True)
            time.sleep(pause_s)
            continue
        stats["visits_queried"] += 1
        got = 0
        for p in found:
            conn.execute(
                "INSERT OR IGNORE INTO places (external_id, name, kind, cuisine, lat, lon, source) "
                "VALUES (?, ?, ?, ?, ?, ?, 'osm-overpass')",
                (p["external_id"], p["name"], p["kind"], p["cuisine"], p["lat"], p["lon"]),
            )
            (pid,) = conn.execute("SELECT id FROM places WHERE external_id = ?", (p["external_id"],)).fetchone()
            d = haversine_m(v["center_lat"], v["center_lon"], p["lat"], p["lon"])
            cur = conn.execute(
                "INSERT OR IGNORE INTO visit_place_candidates (visit_id, place_id, distance_m, evidence, score, created_by) "
                "VALUES (?, ?, ?, 'gps', ?, ?)",
                (v["id"], pid, round(d, 1), round(1.0 / (1.0 + d / 100.0), 4), ALGO),
            )
            stats["candidates"] += cur.rowcount
            got += cur.rowcount
        stats["places_seen"] += len(found)
        if got:
            stats["visits_with_candidates"] += 1
        conn.commit()
        print(f"visit {v['id']}: {len(found)} places, {got} candidates", flush=True)
        time.sleep(pause_s)
    return stats


def nearby(conn, lat: float, lon: float, radius_m: int = 500, kind: str = None) -> list[dict]:
    q = "SELECT * FROM places"
    rows = conn.execute(q).fetchall()
    out = []
    for r in rows:
        d = haversine_m(lat, lon, r["lat"], r["lon"])
        if d <= radius_m and (kind is None or r["kind"] == kind):
            out.append({**dict(r), "distance_m": round(d, 1)})
    return sorted(out, key=lambda x: x["distance_m"])


def search_name(conn, text: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM places WHERE name LIKE ? ORDER BY name LIMIT 30", (f"%{text}%",)
    ).fetchall()
    return [dict(r) for r in rows]
