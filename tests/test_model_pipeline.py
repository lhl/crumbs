"""Synthetic model-server contract and resumability checks; no model/GPU needed."""

import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from crumbs import classify, config, db, extract


EVIDENCE = {"visible_text": "Synthetic Cafe", "dish_candidates": [],
            "place_name_candidates": [], "cannot_determine": False}
TRIAGE = {"category": "food", "evidence_types": ["dish"], "confidence": "high"}


class ModelHandler(BaseHTTPRequestHandler):
    bodies = []
    unavailable = False

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.bodies.append(body)
        if self.unavailable:
            self.send_error(503, "Synthetic model unavailable")
            return
        schema = body["response_format"]
        schema = schema.get("schema") or schema["json_schema"]["schema"]
        parsed = TRIAGE if "category" in schema["properties"] else EVIDENCE
        raw = json.dumps({"choices": [{"message": {"content": json.dumps(parsed)}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "crumbs.db"
        self.analysis = self.root / "analysis"
        self.analysis.mkdir()
        self.conn = db.connect(self.path)
        db.init_schema(self.conn)
        self.conn.execute("INSERT INTO source_imports (kind, scope, source_ref) "
                          "VALUES ('photos', 'synthetic', 'synthetic')")
        for i in range(1, 6):
            self.conn.execute("INSERT INTO media_items (id, content_hash, source_path, rel_path, import_id) "
                              "VALUES (?, ?, 'synthetic', 'synthetic.jpg', 1)", (i, f"hash{i}"))
            (self.analysis / f"hash{i}.jpg").write_bytes(b"synthetic image for fake server")
            self.conn.execute("INSERT INTO classifications (media_id, model, checkpoint, labels_json) "
                              "VALUES (?, ?, 'synthetic-triage', ?)",
                              (i, classify.MODEL, json.dumps(TRIAGE)))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_truncated_extraction_retries_without_accepting_prefix(self):
        requests = []

        def response(request, timeout):
            requests.append(json.loads(request.data))
            content = json.dumps(EVIDENCE)
            # Even syntactically complete JSON must not mask a token-cap stop.
            reason = "length" if len(requests) == 1 else "stop"
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": content},
                                                      "finish_reason": reason}]}).encode())

        with patch.object(extract.urllib.request, "urlopen", response):
            result = extract.extract_one(self.analysis / "hash1.jpg")
        self.assertEqual(result["parsed"], EVIDENCE)
        self.assertEqual([r["max_tokens"] for r in requests], [1100, 4096])
        self.assertEqual(requests[1]["temperature"], 0.2)

    def test_repeated_invalid_output_remains_a_failure(self):
        raw = json.dumps({"choices": [{"message": {"content": '{"visible_text": "unfinished'},
                                      "finish_reason": "length"}]}).encode()
        with patch.object(extract.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(raw)) as send:
            with self.assertRaisesRegex(ValueError, "token budget"):
                extract.extract_one(self.analysis / "hash1.jpg")
        self.assertEqual(send.call_count, 2)

    def test_extraction_field_validation(self):
        invalid = [{}, {**EVIDENCE, "cannot_determine": "false"},
                   {**EVIDENCE, "visible_text": []}, {**EVIDENCE, "dish_candidates": "dish"},
                   {**EVIDENCE, "dish_candidates": [{"name": "dish", "basis": "guessed"}]},
                   {**EVIDENCE, "place_name_candidates": [{"name": 123, "basis": "signage"}]}]
        for parsed in invalid:
            with self.subTest(parsed=parsed), self.assertRaises(ValueError):
                extract.validate_extraction(parsed)
        self.assertEqual(extract.validate_extraction(EVIDENCE), EVIDENCE)

    def test_request_dialects(self):
        for model in ("", "synthetic-fp8"):
            with self.subTest(model=model), patch.object(config, "GLIMMER_MODEL", model):
                body = config.glimmer_body([], 100, extract.SCHEMA)
                if model:
                    self.assertEqual(body["model"], model)
                    self.assertEqual(body["response_format"]["json_schema"]["schema"], extract.SCHEMA)
                else:
                    self.assertNotIn("model", body)
                    self.assertEqual(body["response_format"]["schema"], extract.SCHEMA)

    def test_extraction_commits_before_next_model_wait_and_resumes(self):
        other = sqlite3.connect(self.path, timeout=0.1, check_same_thread=False)
        calls = []

        def read(path):
            # A separate writer must succeed between every pair of model calls.
            other.execute("INSERT INTO labels (media_id, field, value) VALUES (1, 'category', 'food')")
            other.commit()
            calls.append(path)
            return {"parsed": EVIDENCE, "content": json.dumps(EVIDENCE)}

        try:
            with patch.object(extract, "extract_one", read), contextlib.redirect_stdout(io.StringIO()):
                result = extract.extract_all(self.conn, workers=1)
                resumed = extract.extract_all(self.conn, workers=1)
            self.assertEqual(result["extracted"], 5)
            self.assertEqual(result["failed"], 0)
            self.assertEqual(resumed["targets"], 0)
            self.assertEqual(len(calls), 5)
        finally:
            other.close()

    def test_invalid_workers(self):
        with self.assertRaisesRegex(ValueError, "at least 1"):
            extract.extract_all(self.conn, workers=0)

    def test_classification_commits_before_next_model_wait(self):
        self.conn.execute("DELETE FROM classifications")
        self.conn.commit()
        other = sqlite3.connect(self.path, timeout=0.1, check_same_thread=False)

        def read(path):
            other.execute("INSERT INTO labels (media_id, field, value) VALUES (1, 'category', 'food')")
            other.commit()
            return {"parsed": TRIAGE, "raw": {}, "content": json.dumps(TRIAGE)}

        try:
            with patch.object(classify, "classify_one", read), contextlib.redirect_stdout(io.StringIO()):
                result = classify.classify_all(self.conn, workers=1)
            self.assertEqual(result["classified"], 5)
            self.assertEqual(result["failed"], 0)
        finally:
            other.close()

    def test_cli_http_failure_resume_and_checkpoint(self):
        ModelHandler.bodies = []
        ModelHandler.unavailable = True
        server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env = dict(os.environ, CRUMBS_DATA_DIR=str(self.root), CRUMBS_DB=str(self.path),
                   GLIMMER_URL=f"http://127.0.0.1:{server.server_port}", GLIMMER_MODEL="synthetic-fp8")
        command = [sys.executable, "-m", "crumbs.cli", "extract", "--workers", "2"]
        try:
            failed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(failed.returncode, 1, failed.stderr)
            self.assertIn("'unattempted': 3", failed.stdout)
            self.assertEqual(len(ModelHandler.bodies), 2)
            ModelHandler.unavailable = False
            passed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertIn("'extracted': 5", passed.stdout)
            resumed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn("'targets': 0", resumed.stdout)
            self.assertEqual(self.conn.execute("SELECT DISTINCT checkpoint FROM extractions").fetchall()[0][0],
                             "synthetic-fp8")
            self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM extractions").fetchone()[0], 5)
            for body in ModelHandler.bodies:
                self.assertEqual(body["model"], "synthetic-fp8")
                self.assertIn("json_schema", body["response_format"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            ModelHandler.unavailable = False

    def test_real_http_contract_both_dialects(self):
        ModelHandler.bodies = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(config, "GLIMMER_URL", f"http://127.0.0.1:{server.server_port}"):
                for model in ("", "synthetic-fp8"):
                    with self.subTest(model=model), patch.object(config, "GLIMMER_MODEL", model):
                        image = self.analysis / "hash1.jpg"
                        self.assertEqual(extract.extract_one(image)["parsed"], EVIDENCE)
                        self.assertEqual(classify.classify_one(image)["parsed"]["category"], "food")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
