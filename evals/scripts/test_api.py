import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import _api  # noqa: E402


class _Behavior:
    """Mutable box so the handler class (fixed at server-creation time)
    can look up the current test's desired response."""

    mode = "ok"


def _make_handler():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # keep test output quiet

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            self.received_body = body
            self.received_auth = self.headers.get("Authorization")

            if _Behavior.mode == "ok":
                payload = json.loads(body)
                answer = f"echo:{payload['messages'][1]['content'][:20]}"
                response = json.dumps(
                    {"choices": [{"message": {"content": answer}}]}
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response)
            elif _Behavior.mode == "with_usage":
                payload = json.loads(body)
                answer = f"echo:{payload['messages'][1]['content'][:20]}"
                response = json.dumps(
                    {
                        "choices": [{"message": {"content": answer}}],
                        "usage": {"total_tokens": 1290},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response)
            elif _Behavior.mode == "unauthorized":
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error": "bad key"}')
            elif _Behavior.mode == "server_error":
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"internal error")
            elif _Behavior.mode == "bad_shape":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"unexpected": true}')

    return Handler


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _make_handler())
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def setUp(self):
        _Behavior.mode = "ok"
        self.base_url = f"http://127.0.0.1:{self.port}"

    def _config(self, api_key="secret-test-key"):
        return _api.Config(
            model="test-model",
            api_base=self.base_url,
            api_key=api_key,
            timeout=5,
            temperature=0.2,
        )

    def test_successful_call_returns_content(self):
        answer, usage = _api.chat_completion("sys", "hello world", config=self._config())
        self.assertTrue(answer.startswith("echo:"))

    def test_no_usage_key_returns_empty_dict(self):
        answer, usage = _api.chat_completion("sys", "hi", config=self._config())
        self.assertEqual(usage, {})

    def test_usage_surfaced_from_response(self):
        _Behavior.mode = "with_usage"
        answer, usage = _api.chat_completion("sys", "hi", config=self._config())
        self.assertEqual(usage, {"total_tokens": 1290})

    def test_unauthorized_maps_to_clear_message_without_leaking_key(self):
        _Behavior.mode = "unauthorized"
        with self.assertRaises(_api.ApiError) as ctx:
            _api.chat_completion("sys", "hi", config=self._config(api_key="super-secret"))
        message = str(ctx.exception)
        self.assertIn("authentication failed", message)
        self.assertNotIn("super-secret", message)

    def test_server_error_includes_status_code(self):
        _Behavior.mode = "server_error"
        with self.assertRaises(_api.ApiError) as ctx:
            _api.chat_completion("sys", "hi", config=self._config())
        self.assertIn("500", str(ctx.exception))

    def test_unreachable_host_raises_clear_error(self):
        config = _api.Config(
            model="test-model",
            api_base="http://127.0.0.1:1",  # nothing listens here
            api_key="",
            timeout=2,
            temperature=0.2,
        )
        with self.assertRaises(_api.ApiError) as ctx:
            _api.chat_completion("sys", "hi", config=config)
        self.assertIn("could not reach", str(ctx.exception))

    def test_unexpected_response_shape_raises_clear_error(self):
        _Behavior.mode = "bad_shape"
        with self.assertRaises(_api.ApiError):
            _api.chat_completion("sys", "hi", config=self._config())

    def test_missing_model_env_raises(self):
        os.environ.pop("TOKENSHED_MODEL", None)
        with self.assertRaises(_api.ApiError):
            _api.get_config()

    def test_temperature_none_omits_field(self):
        os.environ["TOKENSHED_MODEL"] = "m"
        os.environ["TOKENSHED_TEMPERATURE"] = "none"
        try:
            config = _api.get_config()
            self.assertIsNone(config.temperature)
        finally:
            del os.environ["TOKENSHED_MODEL"]
            del os.environ["TOKENSHED_TEMPERATURE"]

    def test_default_temperature(self):
        os.environ["TOKENSHED_MODEL"] = "m"
        os.environ.pop("TOKENSHED_TEMPERATURE", None)
        try:
            config = _api.get_config()
            self.assertEqual(config.temperature, 0.2)
        finally:
            del os.environ["TOKENSHED_MODEL"]


if __name__ == "__main__":
    unittest.main()
