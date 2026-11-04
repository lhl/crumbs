"""Glimmer agent loop with a scripted fake model over the synthetic store."""
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error

from crumbs import db
from crumbs.agent import run_agent
from test_ask_review import build_store


def call(tool, **args):
    return {"id": f"call-{tool}", "type": "function", "function": {"name": tool, "arguments": json.dumps(args)}}


class FakeGlimmer:
    """Returns scripted messages in order and records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.sent = []

    def __call__(self, messages, tools, tool_choice="auto", timeout=180):
        self.sent.append({"messages": json.loads(json.dumps(messages)), "tool_choice": tool_choice,
                          "tools": [t["function"]["name"] for t in tools]})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.temp.name) / "crumbs.db")
        db.init_schema(self.conn)
        build_store(self.conn)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_tool_call_then_cited_answer(self):
        fake = FakeGlimmer({"content": "", "tool_calls": [call("search_dishes", terms="soup dumpling", city="Taipei")]},
                           {"content": "You had soup dumplings on 2026-01-20 at an unnamed place [v3]."})
        r = run_agent(self.conn, "where did I have soup dumplings in Taipei?", chat=fake)
        self.assertEqual(r["status"], "answered")
        self.assertEqual([c["visit_id"] for c in r["results"]], [3])
        self.assertEqual(r["agent"]["grounding"], {"cited": [3], "cited_photos": [], "unsupported_removed": [],
                                                   "unsupported_photos_removed": []})
        tool_msg = fake.sent[1]["messages"][-1]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertEqual(json.loads(tool_msg["content"])["visits"][0]["visit_id"], 3)
        self.assertNotIn("visits_near_me", fake.sent[0]["tools"])  # no location, no location tool

    def test_uncited_or_invented_visits_are_removed(self):
        fake = FakeGlimmer({"content": "", "tool_calls": [call("food_visits_in_city", city="Kyoto")]},
                           {"content": "You ate grilled fish [v1] and also at a famous place [v999]."})
        r = run_agent(self.conn, "what did I eat in Kyoto?", chat=fake)
        self.assertEqual(r["agent"]["grounding"]["unsupported_removed"], [999])
        self.assertNotIn("[v999]", r["answer"])
        self.assertEqual([c["visit_id"] for c in r["results"]], [1])

    def test_no_tool_results_is_unknown(self):
        fake = FakeGlimmer({"content": "", "tool_calls": [call("search_dishes", terms="croissant")]},
                           {"content": "Your history has no record of croissants."})
        r = run_agent(self.conn, "where did I have croissants?", chat=fake)
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(r["results"], [])

    def test_unknown_city_tool_error_reaches_the_model(self):
        fake = FakeGlimmer({"content": "", "tool_calls": [call("food_visits_in_city", city="Synthville")]},
                           {"content": "No record."})
        run_agent(self.conn, "what did I eat in Synthville?", chat=fake)
        self.assertIn("cannot resolve", json.loads(fake.sent[1]["messages"][-1]["content"])["error"])

    def test_place_lookup_uses_registry_then_photo_text(self):
        fake = FakeGlimmer({"content": "", "tool_calls": [call("visits_at_place", name="Synthetic Tea")]},
                           {"content": "Photo text reads Synthetic Tea [v2]."})
        r = run_agent(self.conn, "what did I have at Synthetic Tea?", chat=fake)
        self.assertEqual([c["visit_id"] for c in r["results"]], [2])
        self.assertIn("unverified", json.loads(fake.sent[1]["messages"][-1]["content"])["note"])

    def test_retry_on_server_error_and_empty_answer(self):
        err = urllib.error.HTTPError("http://synthetic", 500, "synthetic", {}, None)
        fake = FakeGlimmer(err, {"content": "", "tool_calls": [call("search_dishes", terms="grilled fish")]},
                           {"content": ""}, {"content": "Grilled fish on 2025-11-24 [v1]."})
        r = run_agent(self.conn, "grilled fish?", chat=fake)
        self.assertEqual(r["answer"], "Grilled fish on 2025-11-24 [v1].")
        self.assertEqual(fake.sent[-1]["tool_choice"], "none")
        self.assertEqual(fake.sent[-1]["tools"], [])  # answer-only turns offer no tools (llama.cpp 500s otherwise)

    def test_offline_glimmer_falls_back_to_parser(self):
        fake = FakeGlimmer(urllib.error.URLError("synthetic connection refused"))
        r = run_agent(self.conn, "where did I have grilled fish?", chat=fake)
        self.assertFalse(r["agent"]["used"])
        self.assertIn("deterministic parser", r["agent"]["error"])
        self.assertEqual([c["visit_id"] for c in r["results"]], [1])

    def test_tools_found_cards_survive_a_mid_loop_failure(self):
        err = urllib.error.URLError("synthetic drop")
        fake = FakeGlimmer({"content": "", "tool_calls": [call("search_dishes", terms="matcha")]}, err)
        r = run_agent(self.conn, "matcha?", chat=fake)
        self.assertTrue(r["agent"]["used"])
        self.assertIn("did not finish", r["answer"])
        self.assertEqual([c["visit_id"] for c in r["results"]], [2])


def add_synthetic_day(c):
    """Visit 4: one synthetic Kyoto day with an anchor, a lunch, and a dessert stop."""
    c.execute("INSERT INTO visits (id,started_at,ended_at,center_lat,center_lon,photo_count,created_by) "
              "VALUES (4,'2025-11-26 10:00:00','2025-11-26 16:45:00',35.0116,135.7681,5,'synthetic')")
    photos = [  # id, time, food, data
        (41, "10:00", False, {"visible_text": "SYNTHETIC GARDEN admission", "place_name_candidates": [{"name": "Synthetic-Garden"}]}),
        (42, "12:46", False, {"visible_text": "SYNTH EEL", "place_name_candidates": [{"name": "SYNTH EEL"}]}),
        (43, "13:02", True, {"dish_candidates": [{"name": "grilled eel rice bowl", "basis": "seen"}]}),
        (44, "16:40", True, {"dish_candidates": [{"name": "shaved ice", "basis": "seen"}]}),
        (45, "16:41", True, {}),
    ]
    for mid, hm, food, data in photos:
        c.execute("INSERT INTO media_items (id,content_hash,source_path,rel_path,captured_at,import_id) "
                  "VALUES (?,?,'synthetic','synthetic.jpg',?,1)", (mid, f"hash{mid}", f"2025-11-26 {hm}:00"))
        c.execute("INSERT INTO visit_media VALUES (4,?)", (mid,))
        c.execute("INSERT INTO classifications (media_id,model,checkpoint,labels_json) VALUES (?,'synthetic','synthetic',?)",
                  (mid, json.dumps({"category": "food" if food else "other"})))
        if data:
            c.execute("INSERT INTO extractions (media_id,model,checkpoint,data_json) VALUES (?,'synthetic','synthetic',?)",
                      (mid, json.dumps(data)))
    c.commit()


class AnchoredRecallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.temp.name) / "crumbs.db")
        db.init_schema(self.conn)
        build_store(self.conn)
        add_synthetic_day(self.conn)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_anchor_then_day_then_meal_moment(self):
        fake = FakeGlimmer({"content": "", "tool_calls": [call("find_photos", text="Synthetic Garden")]},
                           {"content": "", "tool_calls": [call("day_timeline", date="2025-11-26")]},
                           {"content": "That lunch was where the photo text reads SYNTH EEL [p43] [p99999]."})
        r = run_agent(self.conn, "the eel place the day I went to the synthetic garden?", chat=fake)
        anchor = json.loads(fake.sent[1]["messages"][-1]["content"])
        self.assertEqual(anchor["photos"][0]["photo_id"], 41)  # 'Synthetic Garden' matches 'Synthetic-Garden'
        timeline = json.loads(fake.sent[2]["messages"][-1]["content"])["moments"]
        self.assertEqual([m["time"] for m in timeline], ["10:00-10:00", "12:46-13:02", "16:40-16:41"])
        self.assertEqual(timeline[1]["photo_id"], 43)
        self.assertEqual(timeline[1]["text_photo_ids"], [42])  # the sign, offered for a closer look
        self.assertEqual(r["agent"]["grounding"]["unsupported_photos_removed"], [99999])
        self.assertNotIn("[p99999]", r["answer"])
        card = r["results"][0]
        self.assertEqual((card["moment"], card["text_names"], card["media"][0]), ("12:46–13:02", ["SYNTH EEL"], 43))
        self.assertIsNone(card["place"]["name"])  # a photo-text name is never promoted to a verified place
        self.assertIn("recall a meal", fake.sent[0]["messages"][0]["content"])  # the skill is in the prompt

    def test_look_at_photos_only_for_returned_photos(self):
        looked = []

        def vision(conn, media_id, question):
            looked.append(media_id)
            return "a bowl of shaved ice"
        fake = FakeGlimmer({"content": "", "tool_calls": [call("look_at_photos", photo_ids=[44], question="ice?")]},
                           {"content": "", "tool_calls": [call("day_timeline", date="2025-11-26")]},
                           {"content": "", "tool_calls": [call("look_at_photos", photo_ids=[44], question="ice?")]},
                           {"content": "Shaved ice [p44]."})
        r = run_agent(self.conn, "the shaved ice that day?", chat=fake, vision=vision)
        self.assertIn("only photo_id or text_photo_ids", json.loads(fake.sent[1]["messages"][-1]["content"])["error"])
        self.assertEqual(looked, [44])
        self.assertIn({"step": "look", "seen": ["a bowl of shaved ice"]}, r["agent"]["trace"])
        self.assertEqual(r["results"][0]["photo_id"], 44)

    def test_name_check_looks_at_the_sign_photo_itself(self):
        looked = []

        def vision(conn, media_id, question):
            looked.append(media_id)
            return "SYNTH EEL HOUSE"
        fake = FakeGlimmer({"content": "", "tool_calls": [call("day_timeline", date="2025-11-26")]},
                           {"content": "", "tool_calls": [call("look_at_photos", photo_ids=[42], question="name?")]},
                           {"content": "A closer look reads SYNTH EEL HOUSE [p42]."})
        r = run_agent(self.conn, "the eel place that day?", chat=fake, vision=vision)
        self.assertEqual(looked, [42])  # the text photo, not the moment's food photo
        self.assertEqual(fake.sent[-1]["tools"], [])  # after a look, the next turn only answers
        self.assertEqual(r["results"][0]["moment"], "12:46–13:02")


if __name__ == "__main__":
    unittest.main()
