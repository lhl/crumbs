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
        self.assertEqual(r["agent"]["grounding"], {"cited": [3], "unsupported_removed": []})
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


if __name__ == "__main__":
    unittest.main()
