"""API access-control checks using an empty synthetic evidence store."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from crumbs import api


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = None
        self.thread = None

    def tearDown(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=5)
        self.temp.cleanup()

    def start_server(self, host="127.0.0.1"):
        ready = queue.Queue()
        real_server = api.HTTPServer

        def make_server(address, handler):
            server = real_server(address, handler)
            ready.put(server)
            return server

        def run():
            with patch.dict(os.environ, {"CRUMBS_API_TOKEN": "synthetic-test-token"}), \
                    patch.object(api.config, "DB_PATH", self.root / "synthetic.db"), \
                    patch.object(api, "HTTPServer", side_effect=make_server):
                api.serve(host=host, port=0)

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        self.server = ready.get(timeout=5)
        return f"http://127.0.0.1:{self.server.server_port}"

    def test_non_loopback_requires_nonblank_token_before_connect(self):
        for host in ("0.0.0.0", "", "192.0.2.1", "demo-host"):
            for token in ("", "   "):
                with self.subTest(host=host, token=token), \
                        patch.dict(os.environ, {"CRUMBS_API_TOKEN": token}), \
                        patch.object(api.db, "connect") as connect:
                    with self.assertRaisesRegex(ValueError, "CRUMBS_API_TOKEN is required"):
                        api.serve(host=host, port=0)
                    connect.assert_not_called()

    def test_loopback_defaults_remain_available(self):
        for host in ("127.0.0.1", "localhost"):
            with self.subTest(host=host), patch.dict(os.environ, {"CRUMBS_API_TOKEN": ""}), \
                    patch.object(api.db, "connect"), patch.object(api, "HTTPServer") as server:
                api.serve(host=host, port=0)
                server.assert_called_once()
                self.assertEqual(server.call_args.args[0], (host, 0))
                server.return_value.__enter__.return_value.serve_forever.assert_called_once()

    def test_bearer_auth_cannot_be_disabled_by_later_environment_change(self):
        base = self.start_server()
        with patch.dict(os.environ, {"CRUMBS_API_TOKEN": ""}):
            for token in (None, "wrong-synthetic-token"):
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                req = urllib.request.Request(base + "/v1/search", headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as err:
                    urllib.request.urlopen(req, timeout=3)
                self.assertEqual(err.exception.code, 401)
            req = urllib.request.Request(base + "/v1/search", headers={
                "Authorization": "Bearer synthetic-test-token"})
            with urllib.request.urlopen(req, timeout=3) as response:
                self.assertEqual(json.load(response), {"results": []})
        with urllib.request.urlopen(base + "/v1/health", timeout=3) as response:
            self.assertEqual(json.load(response)["status"], "ok")

    def test_browser_preflight_does_not_authorize_the_following_request(self):
        base = self.start_server()
        req = urllib.request.Request(base + "/v1/ask", method="OPTIONS", headers={
            "Origin": "http://synthetic-ui.invalid", "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization"})
        with urllib.request.urlopen(req, timeout=3) as response:
            self.assertEqual(response.status, 204)
            self.assertIn("Authorization", response.headers["Access-Control-Allow-Headers"])
        with self.assertRaises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(base + "/v1/ask?q=synthetic", timeout=3)
        self.assertEqual(err.exception.code, 401)

    def test_real_wildcard_bind_rejects_unauthenticated_requests(self):
        base = self.start_server(host="0.0.0.0")
        self.assertEqual(self.server.server_address[0], "0.0.0.0")
        with self.assertRaises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(base + "/v1/search", timeout=3)
        self.assertEqual(err.exception.code, 401)
        req = urllib.request.Request(base + "/v1/search", headers={
            "Authorization": "Bearer synthetic-test-token"})
        with urllib.request.urlopen(req, timeout=3) as response:
            self.assertEqual(json.load(response), {"results": []})

    def test_review_and_preview_routes_on_empty_store(self):
        base = self.start_server()
        auth = {"Authorization": "Bearer synthetic-test-token", "Content-Type": "application/json"}
        req = urllib.request.Request(base + "/v1/review/999", method="POST", headers=auth,
                                     data=json.dumps({"answer": "confirm"}).encode())
        with self.assertRaises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req, timeout=3)
        self.assertEqual(err.exception.code, 400)
        self.assertIn("no such question", json.load(err.exception)["error"])
        with self.assertRaises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(urllib.request.Request(base + "/v1/media/999/preview", headers=auth), timeout=3)
        self.assertEqual(err.exception.code, 404)
        with urllib.request.urlopen(urllib.request.Request(base + "/v1/review", headers=auth), timeout=3) as r:
            self.assertEqual(json.load(r), {"questions": []})

    def test_agent_token_is_read_only_and_capped_at_tier_1(self):
        import sqlite3
        from crumbs import db

        conn = sqlite3.connect(self.root / "synthetic.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        db.init_schema(conn)
        conn.execute("INSERT INTO source_imports (kind,scope,source_ref) VALUES ('photos','synthetic','synthetic')")
        conn.execute("INSERT INTO media_items (id,content_hash,source_path,rel_path,captured_at,gps_lat,gps_lon,import_id) "
                     "VALUES (1,'h1','synthetic','synthetic/a.jpg','2025-01-01 12:00:00',35.011634,135.768134,1)")
        conn.execute("INSERT INTO classifications (media_id,model,checkpoint,labels_json) VALUES "
                     "(1,'synthetic','synthetic','{\"category\": \"food\"}')")
        conn.commit()
        env = {"CRUMBS_API_TOKEN": "synthetic-owner", "CRUMBS_AGENT_TOKEN": "synthetic-agent"}
        with patch.dict(os.environ, env):
            server = api.HTTPServer(("127.0.0.1", 0), api.make_handler(conn))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def get(path, tok):
            req = urllib.request.Request(base + path, headers={"Authorization": f"Bearer {tok}"})
            with urllib.request.urlopen(req, timeout=3) as r:
                return json.load(r)
        try:
            owner = get("/v1/search?category=food&tier=2", "synthetic-owner")["results"][0]
            agent = get("/v1/search?category=food&tier=2", "synthetic-agent")["results"][0]
            self.assertEqual((owner["lat"], owner["rel_path"]), (35.011634, "synthetic/a.jpg"))
            self.assertEqual(agent["lat"], 35.01)  # rounded: tier capped at 1
            self.assertNotIn("rel_path", agent)
            with patch("crumbs.agent.run_agent", return_value={
                    "status": "answered", "answer": "synthetic", "results": [{"visit_id": i} for i in range(15)],
                    "agent": {"used": True, "latency_s": 1.0, "error": None,
                              "trace": [{"step": "tool", "tool": "search_dishes"}, {"step": "answer"}]}}):
                a = get("/v1/ask?q=synthetic&agent=1&near=current", "synthetic-agent")
                o = get("/v1/ask?q=synthetic&agent=1", "synthetic-owner")
            self.assertEqual((len(a["results"]), a["agent"]), (10, {"used": True, "latency_s": 1.0, "error": None, "lookups": 1}))
            self.assertEqual(a["current_location"], {"as_of": None, "age_s": None})  # phone never posted
            self.assertEqual((len(o["results"]), len(o["agent"]["trace"])), (15, 2))
            for path in ("/v1/review/1", "/v1/current"):
                req = urllib.request.Request(base + path, method="POST", data=b'{"lat": 1, "lon": 2}',
                                             headers={"Authorization": "Bearer synthetic-agent"})
                with self.subTest(path=path):
                    with self.assertRaises(urllib.error.HTTPError) as err:
                        urllib.request.urlopen(req, timeout=3)
                    self.assertEqual(err.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            conn.close()

    def test_agent_docs_are_served_without_auth(self):
        base = self.start_server()
        with urllib.request.urlopen(base + "/v1/openapi.json", timeout=3) as r:
            self.assertIn("/v1/ask", json.load(r)["paths"])
        with urllib.request.urlopen(base + "/v1/skill", timeout=3) as r:
            self.assertIn("Always check health first", r.read().decode())

    def test_tokenless_writes_refuse_foreign_origins(self):
        import sqlite3
        from crumbs import db

        conn = sqlite3.connect(self.root / "synthetic.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        db.init_schema(conn)
        with patch.dict(os.environ, {"CRUMBS_API_TOKEN": ""}):
            server = api.HTTPServer(("127.0.0.1", 0), api.make_handler(conn))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for origin, code in (("http://synthetic-site.invalid", 403), ("http://127.0.0.1:5173", 400)):
                req = urllib.request.Request(base + "/v1/review/1", method="POST", data=b'{"answer": "confirm"}',
                                             headers={"Origin": origin, "Content-Type": "application/json"})
                with self.subTest(origin=origin):
                    with self.assertRaises(urllib.error.HTTPError) as err:
                        urllib.request.urlopen(req, timeout=3)
                    self.assertEqual(err.exception.code, code)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            conn.close()

    def test_cli_rejects_unauthenticated_lan_bind(self):
        env = dict(os.environ, CRUMBS_DB=str(self.root / "cli.db"), CRUMBS_API_TOKEN="")
        result = subprocess.run([sys.executable, "-m", "crumbs.cli", "serve", "--host", "0.0.0.0", "--port", "0"],
                                env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn("CRUMBS_API_TOKEN is required", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.root / "cli.db").exists())


if __name__ == "__main__":
    unittest.main()
