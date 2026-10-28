"""Demo manifest builder (DEM-01 draft): selects the concrete records that
carry each demo beat from the current store and writes them to a LOCAL
manifest (data/demo/manifest.json, ignored — it names the owner's real
visits). The committed demo script (demo/DEMO.md) refers to beats
generically; this manifest is what the presenter actually clicks through.

Also emits a sufficiency report: can this corpus carry the demo, or does
it need a fresher sync first?
"""

import json
from pathlib import Path

from . import config


def build_demo_manifest(conn) -> dict:
    def one(sql, args=()):
        r = conn.execute(sql, args).fetchone()
        return dict(r) if r else None

    beats = {}
    beats["globe_hero"] = {
        "gps_photos": conn.execute("SELECT COUNT(*) FROM media_items WHERE gps_lat IS NOT NULL").fetchone()[0],
        "visits": conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0],
        "trips": conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0],
    }
    beats["extraction_hero"] = one(
        """SELECT e.media_id, substr(e.data_json, 1, 220) AS preview FROM extractions e
           WHERE json_array_length(json_extract(e.data_json, '$.dish_candidates')) >= 2
           ORDER BY e.id LIMIT 1""")
    beats["anchor_visit"] = one(
        """SELECT vr.visit_id, p.name AS top_candidate FROM visit_resolutions vr
           LEFT JOIN places p ON p.id = vr.top_place_id
           WHERE vr.visit_id IN (SELECT visit_id FROM visit_place_candidates GROUP BY visit_id HAVING COUNT(*) >= 4)
           ORDER BY vr.visit_id LIMIT 1""")
    beats["signage_strong"] = [dict(r) for r in conn.execute(
        """SELECT vr.visit_id, p.name FROM visit_resolutions vr JOIN places p ON p.id = vr.top_place_id
           WHERE vr.status = 'candidate-strong'""")]
    beats["review_question"] = one("SELECT visit_id, question FROM review_questions WHERE status = 'open' LIMIT 1")
    beats["categories"] = {r[0]: r[1] for r in conn.execute(
        "SELECT json_extract(labels_json, '$.category'), COUNT(*) FROM classifications GROUP BY 1")}
    beats["unlabeled_for_scoring"] = conn.execute(
        "SELECT COUNT(*) FROM media_items WHERE NOT EXISTS (SELECT 1 FROM labels WHERE media_id = media_items.id AND field = 'category')"
    ).fetchone()[0]

    japan_visits = conn.execute(
        "SELECT COUNT(*) FROM visits WHERE center_lat BETWEEN 30 AND 46 AND center_lon BETWEEN 129 AND 146").fetchone()[0]
    verdict = {
        "sample_photos": beats["globe_hero"]["gps_photos"],
        "japan_visits": japan_visits,
        "can_demo_pipeline_end_to_end": bool(beats["extraction_hero"] and beats["signage_strong"] and beats["review_question"]),
        "public_video_ready": False,
        "gaps": [
            "No user labels yet — no accuracy numbers can be shown until the labeler pass happens.",
            "Trips over-merge at sample sparsity (14 'trips', some spanning weeks/cities): demo should feature specific visits, not whole-trip narratives, until a fuller import exists.",
            "Public video may only show a consented subset (owner decision) or the synthetic set; this manifest names real visits and stays local.",
            "A fresher iPhone/iCloud sync would add complete recent trips (better story arc) but is not required for the pipeline demo.",
        ],
    }
    out = {"beats": beats, "verdict": verdict}
    dest = config.DATA_DIR.parent / "demo"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "manifest.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out
