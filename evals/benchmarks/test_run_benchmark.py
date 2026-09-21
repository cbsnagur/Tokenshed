import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BENCH_DIR)

import run_benchmark  # noqa: E402
from estimate_tokens import estimate_tokens  # noqa: E402


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        answer = "- Defines a Calculator class\n- add(a, b) returns a + b\n- divide raises ValueError when b is 0"
        body = json.dumps({"choices": [{"message": {"content": answer}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


class EstimateTokensTests(unittest.TestCase):
    def test_nonempty_text_has_positive_estimate(self):
        self.assertGreater(estimate_tokens("x" * 400), 0)

    def test_longer_text_estimates_more_tokens(self):
        self.assertGreater(estimate_tokens("x" * 4000), estimate_tokens("x" * 40))

    def test_empty_text_still_returns_at_least_one(self):
        self.assertEqual(estimate_tokens(""), 1)


class RunBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.cache_dir = tempfile.mkdtemp()
        os.environ["TOKENSHED_MODEL"] = "test-model"
        os.environ["TOKENSHED_API_BASE"] = f"http://127.0.0.1:{self.port}"
        os.environ["TOKENSHED_CACHE_DIR"] = self.cache_dir

    def tearDown(self):
        shutil.rmtree(self.cache_dir, ignore_errors=True)
        for var in ("TOKENSHED_MODEL", "TOKENSHED_API_BASE", "TOKENSHED_CACHE_DIR"):
            os.environ.pop(var, None)

    def test_loads_the_example_task(self):
        tasks = run_benchmark.load_tasks(os.path.join(BENCH_DIR, "tasks"))
        ids = [t["id"] for t in tasks]
        self.assertIn("example-summarize", ids)

    def test_example_task_runs_end_to_end_against_stub_worker(self):
        tasks = run_benchmark.load_tasks(os.path.join(BENCH_DIR, "tasks"))
        task = next(t for t in tasks if t["id"] == "example-summarize")
        result = run_benchmark.run_task(task)
        self.assertNotIn("error", result)
        self.assertGreater(result["baseline_tokens"], result["delegated_tokens"])
        self.assertGreater(result["pct_saved"], 0)
        self.assertIn("Calculator", result["answer"])

    def test_missing_fixture_reports_error_not_a_crash(self):
        task = {
            "id": "broken",
            "paths": ["fixtures/does_not_exist.py"],
            "question": "q",
            "answer_key": [],
        }
        result = run_benchmark.run_task(task)
        self.assertIn("error", result)

    def test_main_fails_cleanly_without_model_configured(self):
        del os.environ["TOKENSHED_MODEL"]
        code = run_benchmark.main([])
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
