import io
import json
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

import code_write  # noqa: E402
from _api import ApiError  # noqa: E402


class CodeWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache_dir = tempfile.mkdtemp()
        os.environ["TOKENSHED_MODEL"] = "test-model"
        os.environ["TOKENSHED_CACHE_DIR"] = self.cache_dir

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.cache_dir, ignore_errors=True)
        os.environ.pop("TOKENSHED_MODEL", None)
        os.environ.pop("TOKENSHED_CACHE_DIR", None)

    def _write(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = code_write.main(argv)
        except SystemExit as exc:
            code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def _worker_events(self):
        ledger = os.path.join(self.cache_dir, "stats.jsonl")
        if not os.path.isfile(ledger):
            return []
        with open(ledger, encoding="utf-8") as fh:
            events = [json.loads(line) for line in fh if line.strip()]
        return [e for e in events if e.get("kind") == "worker"]

    def test_missing_reference_file_errors(self):
        code, out, err = self._run(
            ["--spec", "write tests", "--reference", "/no/such/file.py"]
        )
        self.assertNotEqual(code, 0)
        self.assertIn("not found", err)

    def test_strips_fenced_code_block(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        raw = "```python\ndef g():\n    return 2\n```"
        with mock.patch.object(
            code_write, "chat_completion", return_value=(raw, {"total_tokens": 1290})
        ):
            code, out, err = self._run(
                ["--spec", "write g like f", "--reference", reference]
            )
        self.assertEqual(code, 0)
        self.assertEqual(out, "def g():\n    return 2\n")
        self.assertNotIn("```", out)

    def test_without_target_prints_code_to_stdout(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        with mock.patch.object(
            code_write,
            "chat_completion",
            return_value=("def g():\n    return 2\n", {"total_tokens": 1290}),
        ):
            code, out, err = self._run(
                ["--spec", "write g", "--reference", reference]
            )
        self.assertEqual(code, 0)
        self.assertIn("def g():", out)

    def test_with_target_writes_file_and_prints_only_summary(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        target = os.path.join(self.tmpdir, "out.py")
        with mock.patch.object(
            code_write,
            "chat_completion",
            return_value=("def g():\n    return 2\n", {"total_tokens": 1290}),
        ):
            code, out, err = self._run(
                ["--spec", "write g", "--reference", reference, "--target", target]
            )
        self.assertEqual(code, 0)
        self.assertNotIn("def g", out)  # code never reaches stdout
        self.assertIn("wrote", out)
        self.assertIn(target, out)
        with open(target) as fh:
            self.assertEqual(fh.read(), "def g():\n    return 2\n")

    def test_worker_event_recorded_on_successful_generation(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        with mock.patch.object(
            code_write,
            "chat_completion",
            return_value=("def g():\n    return 2\n", {"total_tokens": 1290}),
        ):
            self._run(["--spec", "write g", "--reference", reference])
        events = self._worker_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["script"], "code_write")
        self.assertEqual(events[0]["model"], "test-model")
        self.assertEqual(events[0]["spent_tokens"], 1290)

    def test_refuses_to_overwrite_without_force(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        target = self._write("out.py", "existing content\n")
        code, out, err = self._run(
            ["--spec", "write g", "--reference", reference, "--target", target]
        )
        self.assertNotEqual(code, 0)
        self.assertIn("already exists", err)
        with open(target) as fh:
            self.assertEqual(fh.read(), "existing content\n")

    def test_force_allows_overwrite(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        target = self._write("out.py", "existing content\n")
        with mock.patch.object(
            code_write,
            "chat_completion",
            return_value=("def g():\n    return 2\n", {"total_tokens": 1290}),
        ):
            code, out, err = self._run(
                ["--spec", "write g", "--reference", reference, "--target", target, "--force"]
            )
        self.assertEqual(code, 0)
        with open(target) as fh:
            self.assertEqual(fh.read(), "def g():\n    return 2\n")

    def test_creates_missing_target_directory(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        target = os.path.join(self.tmpdir, "nested", "dir", "out.py")
        with mock.patch.object(
            code_write, "chat_completion", return_value=("code\n", {"total_tokens": 1290})
        ):
            code, out, err = self._run(
                ["--spec", "write g", "--reference", reference, "--target", target]
            )
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(target))

    def test_worker_failure_reports_clear_error(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        with mock.patch.object(
            code_write, "chat_completion", side_effect=ApiError("authentication failed")
        ):
            code, out, err = self._run(
                ["--spec", "write g", "--reference", reference]
            )
        self.assertNotEqual(code, 0)
        self.assertIn("authentication failed", err)


if __name__ == "__main__":
    unittest.main()
