"""Ask cards, dish search, and review answers over a synthetic store.

All records are invented: places, dishes, and coordinates are synthetic
(coordinates are public city centers, not anyone's visits)."""
import json
from pathlib import Path
import tempfile
import unittest

from crumbs import db
from crumbs.ask import ask, visit_place
from crumbs.review import answer_question, open_questions

KYOTO = (35.0116, 135.7681)
TAIPEI = (25.0330, 121.5654)


def build_store(c):
    """Insert the synthetic fixture into an initialized store."""
    c.execute("INSERT INTO source_imports (kind,scope,source_ref) VALUES ('photos','synthetic','synthetic')")
    c.execute("INSERT INTO places (id,external_id,name,kind,lat,lon,source) VALUES "
              "(1,'synthetic:1','Synthetic Grill','restaurant',?,?,'synthetic')", KYOTO)
    visits = [  # id, date, center, dishes, visible text, place-name text
        (1, "2025-11-24", KYOTO, [("grilled fish", "seen"), ("miso soup", "read_on_menu")], "", "Synthetic Grill"),
        (2, "2025-11-25", KYOTO, [("matcha parfait", "read_on_menu")], "MATCHA HOUSE", "Synthetic Tea"),
        (3, "2026-01-20", TAIPEI, [("soup dumplings", "read_on_menu")], "", ""),
    ]
    for vid, day, (lat, lon), dishes, text, pname in visits:
        c.execute("INSERT INTO visits (id,started_at,ended_at,center_lat,center_lon,photo_count,created_by) "
                  "VALUES (?,?,?,?,?,1,'synthetic')", (vid, f"{day} 12:00:00", f"{day} 13:00:00", lat, lon))
        c.execute("INSERT INTO media_items (id,content_hash,source_path,rel_path,captured_at,import_id) "
                  "VALUES (?,?,'synthetic','synthetic.jpg',?,1)", (vid, f"hash{vid}", f"{day} 12:10:00"))
        c.execute("INSERT INTO visit_media VALUES (?,?)", (vid, vid))
        c.execute("INSERT INTO classifications (media_id,model,checkpoint,labels_json) VALUES (?,'synthetic','synthetic',?)",
                  (vid, json.dumps({"category": "food"})))
        data = {"visible_text": text, "dish_candidates": [{"name": n, "basis": b} for n, b in dishes],
                "place_name_candidates": [{"name": pname, "basis": "sign"}] if pname else []}
        c.execute("INSERT INTO extractions (media_id,model,checkpoint,data_json) VALUES (?,'synthetic','synthetic',?)",
                  (vid, json.dumps(data)))
    c.execute("INSERT INTO visit_place_candidates (visit_id,place_id,distance_m,evidence,score,created_by) "
              "VALUES (1,1,40,'gps',17,'synthetic')")
    c.execute("INSERT INTO visit_resolutions (visit_id,top_place_id,status,tier,reasons_json,created_by) "
              "VALUES (1,1,'candidate-weak','medium',?,'reconcile-synthetic')",
              (json.dumps({"ranked": [{"place_id": 1, "why": ["gps 40 m (+17)"]}]}),))
    c.execute("INSERT INTO review_questions (id,visit_id,question,created_by) VALUES "
              "(10,1,'Was this Synthetic Grill?','reconcile-synthetic'), (11,2,'Do you remember the place?','reconcile-synthetic')")
    c.commit()


class AskReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.temp.name) / "crumbs.db")
        db.init_schema(self.conn)
        build_store(self.conn)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_dish_search_returns_evidence_cards(self):
        r = ask(self.conn, "where did I have grilled fish?")
        self.assertEqual(r["status"], "answered")
        self.assertEqual([c["visit_id"] for c in r["results"]], [1])
        card = r["results"][0]
        self.assertEqual(card["place"]["name"], "Synthetic Grill")
        self.assertEqual(card["place"]["source"], "nearby (GPS)")
        self.assertEqual(card["dishes"][0]["name"], "grilled fish")
        self.assertEqual(card["media"], [1])
        self.assertEqual(card["review"]["question_id"], 10)

    def test_area_scope_and_plurals(self):
        self.assertEqual([c["visit_id"] for c in ask(self.conn, "where did I have dumplings in Taipei?")["results"]], [3])
        self.assertEqual(ask(self.conn, "where did I have dumplings in Kyoto?")["status"], "unknown")

    def test_area_food_visits_and_text_names(self):
        r = ask(self.conn, "what did I eat in Kyoto?")
        self.assertEqual(sorted(c["visit_id"] for c in r["results"]), [1, 2])
        tea = next(c for c in r["results"] if c["visit_id"] == 2)
        self.assertIsNone(tea["place"]["name"])
        self.assertEqual(tea["text_names"], ["Synthetic Tea"])

    def test_unknown_is_designed(self):
        r = ask(self.conn, "have I been to Paris?")
        self.assertEqual(r["status"], "unknown")
        self.assertIn("paris", r["answer"])
        self.assertEqual(r["results"], [])

    def test_confirm_appends_user_row_and_keeps_model_row(self):
        out = answer_question(self.conn, 10, "confirm")
        self.assertEqual(out["visit"]["place"]["status"], "confirmed")
        self.assertIsNone(out["visit"]["review"])
        rows = self.conn.execute("SELECT created_by, status FROM visit_resolutions WHERE visit_id = 1 ORDER BY id").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("reconcile-synthetic", "candidate-weak"), ("user", "confirmed")])
        self.assertEqual([q["question_id"] for q in open_questions(self.conn)], [11])
        card = ask(self.conn, "what did I have at synthetic grill?")["results"][0]
        self.assertEqual(card["place"]["source"], "you confirmed")

    def test_reject_hides_candidate_and_later_answer_replaces_it(self):
        answer_question(self.conn, 10, "reject")
        p = visit_place(self.conn, 1)
        self.assertIsNone(p["name"])
        self.assertEqual(p["rejected"], "Synthetic Grill")
        answer_question(self.conn, 10, "confirm")
        self.assertEqual(visit_place(self.conn, 1)["status"], "confirmed")
        (n,) = self.conn.execute("SELECT COUNT(*) FROM visit_resolutions WHERE created_by = 'user'").fetchone()
        self.assertEqual(n, 1)

    def test_name_and_invalid_answers(self):
        with self.assertRaises(ValueError):
            answer_question(self.conn, 11, "confirm")  # visit 2 has no candidate place
        with self.assertRaises(ValueError):
            answer_question(self.conn, 11, "name", "  ")
        with self.assertRaises(ValueError):
            answer_question(self.conn, 11, "maybe")
        out = answer_question(self.conn, 11, "name", "Synthetic Tea House")
        self.assertEqual(out["visit"]["place"], {"name": "Synthetic Tea House", "place_id": None,
                                                 "source": "you named it", "status": "confirmed", "rejected": None})


if __name__ == "__main__":
    unittest.main()
