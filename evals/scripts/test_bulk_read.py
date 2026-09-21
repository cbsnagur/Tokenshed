import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import bulk_read  # noqa: E402
from _api import ApiError  # noqa: E402


class BulkReadTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache_dir = tempfile.mkdtemp()
        os.environ["TOKENSHED_MODEL"] = "test-model"
        os.environ["TOKENSHED_CACHE_DIR"] = self.cache_dir
        os.environ.pop("TOKENSHED_CACHE", None)
        os.environ.pop("TOKENSHED_MAX_BYTES", None)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.cache_dir, ignore_errors=True)
        for var in ("TOKENSHED_MODEL", "TOKENSHED_CACHE_DIR", "TOKENSHED_CACHE", "TOKENSHED_MAX_BYTES"):
            os.environ.pop(var, None)

    def _write(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = bulk_read.main(argv)
        except SystemExit as exc:
            code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_missing_file_errors_clearly(self):
        code, out, err = self._run(
            ["--question", "what is this", "--paths", "/no/such/file.py"]
        )
        self.assertNotEqual(code, 0)
        self.assertIn("not found", err)

    def test_oversized_request_refused(self):
        path = self._write("big.txt", "x" * 1000)
        os.environ["TOKENSHED_MAX_BYTES"] = "10"
        code, out, err = self._run(["--question", "q", "--paths", path])
        self.assertNotEqual(code, 0)
        self.assertIn("byte", err)

    def test_calls_worker_and_prints_only_answer(self):
        path = self._write("a.py", "def f():\n    return 1\n")
        with mock.patch.object(bulk_read, "chat_completion", return_value="- does X") as m:
            code, out, err = self._run(["--question", "what does it do", "--paths", path])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "- does X")
        self.assertEqual(err, "")
        m.assert_called_once()
        # BR2: the wrapped file (with line numbers) went into the prompt.
        user_prompt = m.call_args[0][1]
        self.assertIn(f'<file path="{path}">', user_prompt)
        self.assertIn("1: def f():", user_prompt)

    def test_repeat_question_hits_cache_without_calling_worker(self):
        path = self._write("a.py", "def f():\n    return 1\n")
        with mock.patch.object(bulk_read, "chat_completion", return_value="- does X") as m:
            self._run(["--question", "what does it do", "--paths", path])
            code, out, err = self._run(["--question", "what does it do", "--paths", path])
        self.assertEqual(code, 0)
        self.assertIn("(cached)", out)
        self.assertIn("does X", out)
        m.assert_called_once()  # second call was served from cache

    def test_no_cache_flag_forces_fresh_call(self):
        path = self._write("a.py", "def f():\n    return 1\n")
        with mock.patch.object(bulk_read, "chat_completion", return_value="- does X") as m:
            self._run(["--question", "what does it do", "--paths", path])
            code, out, err = self._run(
                ["--question", "what does it do", "--paths", path, "--no-cache"]
            )
        self.assertEqual(code, 0)
        self.assertNotIn("(cached)", out)
        self.assertEqual(m.call_count, 2)

    def test_editing_file_invalidates_cache(self):
        path = self._write("a.py", "def f():\n    return 1\n")
        with mock.patch.object(bulk_read, "chat_completion", return_value="- v1") as m:
            self._run(["--question", "q", "--paths", path])
        self._write("a.py", "def f():\n    return 2\n")
        with mock.patch.object(bulk_read, "chat_completion", return_value="- v2") as m:
            code, out, err = self._run(["--question", "q", "--paths", path])
        self.assertNotIn("(cached)", out)
        self.assertIn("v2", out)

    def test_worker_failure_prints_clear_stderr_and_nonzero_exit(self):
        path = self._write("a.py", "x = 1\n")
        with mock.patch.object(
            bulk_read, "chat_completion", side_effect=ApiError("could not reach http://x")
        ):
            code, out, err = self._run(["--question", "q", "--paths", path])
        self.assertNotEqual(code, 0)
        self.assertIn("could not reach", err)
        self.assertEqual(out, "")

    def test_missing_model_env_errors(self):
        del os.environ["TOKENSHED_MODEL"]
        path = self._write("a.py", "x = 1\n")
        code, out, err = self._run(["--question", "q", "--paths", path])
        self.assertNotEqual(code, 0)
        self.assertIn("TOKENSHED_MODEL", err)


if __name__ == "__main__":
    unittest.main()
