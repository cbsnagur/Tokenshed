import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOKS_DIR = os.path.join(REPO_ROOT, "hooks")
sys.path.insert(0, HOOKS_DIR)

import read_hook  # noqa: E402


def _read_ledger_events(base_dir):
    """Walk the isolated cache dir for any *.jsonl ledger and return all
    parsed events, without hardcoding the ledger's exact filename/subpath."""
    events = []
    for root, _, files in os.walk(base_dir):
        for name in files:
            if name.endswith(".jsonl"):
                with open(os.path.join(root, name), "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            events.append(json.loads(line))
    return events


class ReadHookEvaluateTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.stats_dir = tempfile.mkdtemp()
        os.environ.pop("TOKENSHED_MIN_LINES", None)
        os.environ.pop("TOKENSHED_ALLOWLIST", None)
        os.environ.pop("TOKENSHED_STATS", None)
        os.environ["TOKENSHED_CACHE_DIR"] = self.stats_dir

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.stats_dir, ignore_errors=True)
        os.environ.pop("TOKENSHED_CACHE_DIR", None)

    def _write(self, name, lines):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(f"line {i}" for i in range(lines)) + "\n")
        return path

    def _data(self, path, **extra_input):
        tool_input = {"file_path": path}
        tool_input.update(extra_input)
        return {"tool_name": "Read", "tool_input": tool_input, "cwd": self.tmpdir}

    def test_small_file_allowed(self):
        path = self._write("small.py", 10)
        self.assertIsNone(read_hook.evaluate(self._data(path)))

    def test_large_file_blocked_with_r3_content(self):
        path = self._write("big.py", 500)
        reason = read_hook.evaluate(self._data(path))
        self.assertIsNotNone(reason)
        self.assertIn(path, reason)
        self.assertIn("bulk_read.py", reason)
        self.assertIn("grep -n", reason)
        self.assertIn("500 lines", reason)

    def test_file_at_exact_threshold_allowed(self):
        path = self._write("edge.py", 350)
        self.assertIsNone(read_hook.evaluate(self._data(path)))

    def test_file_one_over_threshold_blocked(self):
        path = self._write("edge.py", 351)
        self.assertIsNotNone(read_hook.evaluate(self._data(path)))

    def test_partial_read_with_offset_allowed(self):
        path = self._write("big.py", 500)
        self.assertIsNone(read_hook.evaluate(self._data(path, offset=100)))

    def test_partial_read_with_limit_allowed(self):
        path = self._write("big.py", 500)
        self.assertIsNone(read_hook.evaluate(self._data(path, limit=50)))

    def test_missing_file_allowed_through(self):
        path = os.path.join(self.tmpdir, "nope.py")
        self.assertIsNone(read_hook.evaluate(self._data(path)))

    def test_binary_file_allowed(self):
        path = os.path.join(self.tmpdir, "big.bin")
        with open(path, "wb") as fh:
            fh.write(b"\x00PNG" + os.urandom(20000))
        self.assertIsNone(read_hook.evaluate(self._data(path)))

    def test_allowlisted_path_allowed(self):
        path = self._write("package.lock", 500)
        claude_dir = os.path.join(self.tmpdir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        with open(os.path.join(claude_dir, "tokenshed-allow.txt"), "w") as fh:
            fh.write("# generated files\n*.lock\n")
        self.assertIsNone(read_hook.evaluate(self._data(path)))

    def test_non_read_tool_ignored(self):
        data = {"tool_name": "Write", "tool_input": {"file_path": "whatever"}, "cwd": self.tmpdir}
        self.assertIsNone(read_hook.evaluate(data))

    def test_custom_threshold_env_var(self):
        path = self._write("medium.py", 50)
        os.environ["TOKENSHED_MIN_LINES"] = "10"
        try:
            self.assertIsNotNone(read_hook.evaluate(self._data(path)))
        finally:
            del os.environ["TOKENSHED_MIN_LINES"]

    def test_invalid_threshold_env_var_falls_back_to_default(self):
        path = self._write("medium.py", 50)
        os.environ["TOKENSHED_MIN_LINES"] = "not-a-number"
        try:
            self.assertIsNone(read_hook.evaluate(self._data(path)))
        finally:
            del os.environ["TOKENSHED_MIN_LINES"]

    def test_relative_path_resolved_against_cwd(self):
        self._write("big.py", 500)
        data = {"tool_name": "Read", "tool_input": {"file_path": "big.py"}, "cwd": self.tmpdir}
        self.assertIsNotNone(read_hook.evaluate(data))

    def test_latency_under_100ms_on_10000_line_file(self):
        path = self._write("huge.py", 10000)
        data = self._data(path)
        start = time.perf_counter()
        read_hook.evaluate(data)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 100, f"read hook evaluate() took {elapsed_ms:.1f}ms")

    def test_deny_records_block_event(self):
        path = self._write("big.py", 500)
        reason = read_hook.evaluate(self._data(path))
        self.assertIsNotNone(reason)
        events = _read_ledger_events(self.stats_dir)
        self.assertEqual(len(events), 1, f"expected exactly one ledger event, got {events}")
        event = events[0]
        self.assertEqual(event["kind"], "block")
        self.assertEqual(event["script"], "read")
        self.assertEqual(event["file"], path)
        self.assertEqual(event["bytes"], os.path.getsize(path))
        self.assertEqual(event["avoided_tokens"], os.path.getsize(path) // 4)

    def test_allow_records_no_event(self):
        path = self._write("small.py", 10)
        reason = read_hook.evaluate(self._data(path))
        self.assertIsNone(reason)
        self.assertEqual(_read_ledger_events(self.stats_dir), [])


class ReadHookSubprocessTests(unittest.TestCase):
    """End-to-end checks of the real CLI contract: stdin JSON in,
    exit-code + hookSpecificOutput JSON out, and fail-open on garbage
    input."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.stats_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.stats_dir, ignore_errors=True)

    def _run(self, payload: str):
        env = dict(os.environ, TOKENSHED_CACHE_DIR=self.stats_dir)
        return subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "read_hook.py")],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

    def test_end_to_end_block(self):
        path = os.path.join(self.tmpdir, "big.py")
        with open(path, "w") as fh:
            fh.write("\n".join(f"line {i}" for i in range(500)) + "\n")
        payload = json.dumps(
            {"tool_name": "Read", "tool_input": {"file_path": path}, "cwd": self.tmpdir}
        )
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        parsed = json.loads(result.stdout)
        self.assertEqual(
            parsed["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_end_to_end_allow(self):
        path = os.path.join(self.tmpdir, "small.py")
        with open(path, "w") as fh:
            fh.write("print('hi')\n")
        payload = json.dumps(
            {"tool_name": "Read", "tool_input": {"file_path": path}, "cwd": self.tmpdir}
        )
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_malformed_input_fails_open(self):
        result = self._run("not json at all")
        self.assertEqual(result.returncode, 0)

    def test_empty_input_fails_open(self):
        result = self._run("")
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
