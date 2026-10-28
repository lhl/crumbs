"""Export reconstructed data in the shape spike/map-globe consumes:
a GeoJSON FeatureCollection of photo points (with visit/trip ids, category
from the latest classification when present) plus visit and trip summaries.
The spike keeps working with zero classifications; labels join when they exist.
"""

import json

from . import db


def export_geojson(conn) -> dict:
    rows = conn.execute(
        """SELECT m.id, m.rel_path, m.captured_at, m.gps_lat, m.gps_lon,
                  vm.visit_id, tv.trip_id,
                  (SELECT json_extract(c.labels_json, '$.category')
                     FROM classifications c WHERE c.media_id = m.id
                     ORDER BY c.id DESC LIMIT 1) AS category,
                  (SELECT json_extract(c.labels_json, '$.evidence_types')
                     FROM classifications c WHERE c.media_id = m.id
                     ORDER BY c.id DESC LIMIT 1) AS evidence_types
           FROM media_items m
           LEFT JOIN visit_media vm ON vm.media_id = m.id
           LEFT JOIN trip_visits tv ON tv.visit_id = vm.visit_id
           WHERE m.gps_lat IS NOT NULL ORDER BY m.captured_at"""
    ).fetchall()
    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["gps_lon"], r["gps_lat"]]},
            "properties": {
                "media_id": r["id"], "rel_path": r["rel_path"], "captured_at": r["captured_at"],
                "visit_id": r["visit_id"], "trip_id": r["trip_id"],
                "category": r["category"] or "unclassified",
                "evidence_types": json.loads(r["evidence_types"]) if r["evidence_types"] else [],
            },
        })
    visits = [dict(r) for r in conn.execute("SELECT * FROM visits ORDER BY started_at")]
    trips = [dict(r) for r in conn.execute("SELECT * FROM trips ORDER BY started_at")]
    return {"type": "FeatureCollection", "features": features, "visits": visits, "trips": trips}
