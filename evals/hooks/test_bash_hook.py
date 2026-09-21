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

import bash_hook  # noqa: E402


class BashHookEvaluateTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.environ.pop("TOKENSHED_MIN_LINES", None)
        os.environ.pop("TOKENSHED_ALLOWLIST", None)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, name, lines):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(f"line {i}" for i in range(lines)) + "\n")
        return path

    def _data(self, command):
        return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": self.tmpdir}

    # B1: cat/less/more over threshold
    def test_cat_small_file_allowed(self):
        path = self._write("small.py", 10)
        self.assertIsNone(bash_hook.evaluate(self._data(f"cat {path}")))

    def test_cat_large_file_blocked(self):
        path = self._write("big.py", 500)
        reason = bash_hook.evaluate(self._data(f"cat {path}"))
        self.assertIsNotNone(reason)
        self.assertIn(path, reason)

    def test_less_large_file_blocked(self):
        path = self._write("big.py", 500)
        self.assertIsNotNone(bash_hook.evaluate(self._data(f"less {path}")))

    def test_more_large_file_blocked(self):
        path = self._write("big.py", 500)
        self.assertIsNotNone(bash_hook.evaluate(self._data(f"more {path}")))

    # B2: pipes and redirects always pass through
    def test_cat_large_file_piped_allowed(self):
        path = self._write("big.py", 500)
        self.assertIsNone(bash_hook.evaluate(self._data(f"cat {path} | grep foo")))

    def test_cat_large_file_redirected_allowed(self):
        path = self._write("big.py", 500)
        out = os.path.join(self.tmpdir, "out.txt")
        self.assertIsNone(bash_hook.evaluate(self._data(f"cat {path} > {out}")))

    def test_non_read_command_allowed(self):
        self.assertIsNone(bash_hook.evaluate(self._data("git log --oneline -5")))

    # B3: relative paths resolved against hook cwd
    def test_relative_path_resolved_against_cwd(self):
        self._write("big.py", 500)
        self.assertIsNotNone(bash_hook.evaluate(self._data("cat big.py")))

    # B4: head/tail only blocked when asked for more than the threshold
    def test_head_default_allowed(self):
        path = self._write("big.py", 500)
        self.assertIsNone(bash_hook.evaluate(self._data(f"head {path}")))

    def test_head_small_n_allowed(self):
        path = self._write("big.py", 500)
        self.assertIsNone(bash_hook.evaluate(self._data(f"head -n 20 {path}")))

    def test_head_large_n_blocked(self):
        path = self._write("big.py", 500)
        self.assertIsNotNone(bash_hook.evaluate(self._data(f"head -n 5000 {path}")))

    def test_tail_large_n_blocked(self):
        path = self._write("big.py", 500)
        self.assertIsNotNone(bash_hook.evaluate(self._data(f"tail -n 5000 {path}")))

    def test_tail_large_n_equals_form_blocked(self):
        path = self._write("big.py", 500)
        self.assertIsNotNone(bash_hook.evaluate(self._data(f"tail --lines=5000 {path}")))

    # sequential (non-piped) commands are each checked
    def test_sequential_commands_second_one_blocked(self):
        small = self._write("small.py", 10)
        big = self._write("big.py", 500)
        self.assertIsNotNone(bash_hook.evaluate(self._data(f"cat {small}; cat {big}")))

    def test_sequential_commands_all_small_allowed(self):
        a = self._write("a.py", 10)
        b = self._write("b.py", 10)
        self.assertIsNone(bash_hook.evaluate(self._data(f"cat {a} && cat {b}")))

    # R4-equivalent allow-list applies to bash too
    def test_allowlisted_path_allowed(self):
        path = self._write("package.lock", 500)
        claude_dir = os.path.join(self.tmpdir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        with open(os.path.join(claude_dir, "tokenshed-allow.txt"), "w") as fh:
            fh.write("*.lock\n")
        self.assertIsNone(bash_hook.evaluate(self._data(f"cat {path}")))

    def test_missing_file_allowed(self):
        path = os.path.join(self.tmpdir, "nope.py")
        self.assertIsNone(bash_hook.evaluate(self._data(f"cat {path}")))

    def test_unparseable_command_fails_open(self):
        # Unbalanced quote: shlex raises ValueError internally.
        self.assertIsNone(bash_hook.evaluate(self._data("cat 'unterminated")))

    def test_latency_under_100ms_on_10000_line_file(self):
        path = self._write("huge.py", 10000)
        start = time.perf_counter()
        bash_hook.evaluate(self._data(f"cat {path}"))
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 100, f"bash hook evaluate() took {elapsed_ms:.1f}ms")


class BashHookSubprocessTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, payload: str):
        return subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "bash_hook.py")],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_end_to_end_block(self):
        path = os.path.join(self.tmpdir, "big.py")
        with open(path, "w") as fh:
            fh.write("\n".join(f"line {i}" for i in range(500)) + "\n")
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": f"cat {path}"}, "cwd": self.tmpdir}
        )
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_end_to_end_allow(self):
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "echo hi"}, "cwd": self.tmpdir}
        )
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_malformed_input_fails_open(self):
        result = self._run("not json at all")
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
