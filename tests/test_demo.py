"""Manifest coverage and provenance checks over synthetic records."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crumbs import config, db
from crumbs.demo import build_demo_manifest


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.conn = db.connect(self.root / "crumbs.db")
        db.init_schema(self.conn)
        self.conn.execute("INSERT INTO source_imports (kind,scope,source_ref) VALUES ('photos','synthetic','synthetic')")
        for mid in (1, 2):
            self.conn.execute("INSERT INTO media_items (id,content_hash,source_path,rel_path,import_id) "
                              "VALUES (?,?,'synthetic','synthetic.jpg',1)", (mid, str(mid)))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def build(self):
        with patch.object(config, "DATA_DIR", self.root / "crumbs"):
            return build_demo_manifest(self.conn)

    def test_one_latest_category_per_photo_and_only_user_labels(self):
        for model, category in (("old-model", "trip"), ("new-model", "food")):
            self.conn.execute("INSERT INTO classifications (media_id,model,checkpoint,labels_json) "
                              "VALUES (1,?,'synthetic',?)", (model, json.dumps({"category": category})))
        self.conn.execute("INSERT INTO labels (media_id,field,value,source) VALUES (1,'category','food','model')")
        self.conn.execute("INSERT INTO labels (media_id,field,value,source) VALUES (2,'category','other','user')")
        self.conn.commit()
        out = self.build()
        self.assertEqual(out["beats"]["categories"], {"food": 1, "unclassified": 1})
        self.assertEqual(out["beats"]["unlabeled_for_scoring"], 1)
        self.assertTrue(any("1 photos" in gap for gap in out["verdict"]["gaps"]))
        self.assertTrue((self.root / "demo" / "manifest.json").exists())
        self.assertFalse(out["verdict"]["public_video_ready"])

    def test_strong_resolution_requires_text_for_signage_beat(self):
        self.conn.execute("INSERT INTO places (id,external_id,name,lat,lon,source) "
                          "VALUES (1,'synthetic:1','Synthetic Cafe',0,0,'synthetic')")
        for vid, evidence in ((1, "gps"), (2, "signage-text")):
            self.conn.execute("INSERT INTO visits (id,created_by) VALUES (?,'synthetic')", (vid,))
            self.conn.execute("INSERT INTO visit_place_candidates "
                              "(visit_id,place_id,distance_m,evidence,score,created_by) "
                              "VALUES (?,1,0,?,1,'synthetic')", (vid, evidence))
            self.conn.execute("INSERT INTO visit_resolutions "
                              "(visit_id,top_place_id,status,tier,reasons_json,created_by) "
                              "VALUES (?,1,'candidate-strong','strong','[]','synthetic')", (vid,))
        self.conn.commit()
        out = self.build()
        self.assertEqual([r["visit_id"] for r in out["beats"]["signage_strong"]], [2])
        self.assertFalse(out["verdict"]["can_demo_pipeline_end_to_end"])


if __name__ == "__main__":
    unittest.main()
