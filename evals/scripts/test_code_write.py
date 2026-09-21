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

import code_write  # noqa: E402
from _api import ApiError  # noqa: E402


class CodeWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.environ["TOKENSHED_MODEL"] = "test-model"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        os.environ.pop("TOKENSHED_MODEL", None)

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

    def test_missing_reference_file_errors(self):
        code, out, err = self._run(
            ["--spec", "write tests", "--reference", "/no/such/file.py"]
        )
        self.assertNotEqual(code, 0)
        self.assertIn("not found", err)

    def test_strips_fenced_code_block(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        raw = "```python\ndef g():\n    return 2\n```"
        with mock.patch.object(code_write, "chat_completion", return_value=raw):
            code, out, err = self._run(
                ["--spec", "write g like f", "--reference", reference]
            )
        self.assertEqual(code, 0)
        self.assertEqual(out, "def g():\n    return 2\n")
        self.assertNotIn("```", out)

    def test_without_target_prints_code_to_stdout(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        with mock.patch.object(code_write, "chat_completion", return_value="def g():\n    return 2\n"):
            code, out, err = self._run(
                ["--spec", "write g", "--reference", reference]
            )
        self.assertEqual(code, 0)
        self.assertIn("def g():", out)

    def test_with_target_writes_file_and_prints_only_summary(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        target = os.path.join(self.tmpdir, "out.py")
        with mock.patch.object(code_write, "chat_completion", return_value="def g():\n    return 2\n"):
            code, out, err = self._run(
                ["--spec", "write g", "--reference", reference, "--target", target]
            )
        self.assertEqual(code, 0)
        self.assertNotIn("def g", out)  # code never reaches stdout
        self.assertIn("wrote", out)
        self.assertIn(target, out)
        with open(target) as fh:
            self.assertEqual(fh.read(), "def g():\n    return 2\n")

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
        with mock.patch.object(code_write, "chat_completion", return_value="def g():\n    return 2\n"):
            code, out, err = self._run(
                ["--spec", "write g", "--reference", reference, "--target", target, "--force"]
            )
        self.assertEqual(code, 0)
        with open(target) as fh:
            self.assertEqual(fh.read(), "def g():\n    return 2\n")

    def test_creates_missing_target_directory(self):
        reference = self._write("ref.py", "def f():\n    return 1\n")
        target = os.path.join(self.tmpdir, "nested", "dir", "out.py")
        with mock.patch.object(code_write, "chat_completion", return_value="code\n"):
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
