import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import doctor  # noqa: E402
from _api import ApiError  # noqa: E402


def _git(cwd, *args):
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        for var in ("TOKENSHED_MODEL", "TOKENSHED_API_KEY", "TOKENSHED_API_BASE"):
            os.environ.pop(var, None)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        for var in ("TOKENSHED_MODEL", "TOKENSHED_API_KEY", "TOKENSHED_API_BASE"):
            os.environ.pop(var, None)

    def _run(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = doctor.main(cwd=self.tmpdir)
        return code, out.getvalue()

    def test_missing_model_fails(self):
        code, out = self._run()
        self.assertNotEqual(code, 0)
        self.assertIn("[FAIL] TOKENSHED_MODEL is not set", out)

    def test_worker_check_skipped_without_model(self):
        code, out = self._run()
        self.assertIn("[SKIP] worker API check", out)

    def test_all_pass_when_model_set_and_worker_reachable(self):
        os.environ["TOKENSHED_MODEL"] = "test-model"
        with mock.patch.object(doctor, "chat_completion", return_value="OK"):
            code, out = self._run()
        self.assertEqual(code, 0)
        self.assertIn("[PASS] TOKENSHED_MODEL is set", out)
        self.assertIn("[PASS] worker API reachable", out)
        self.assertIn("All checks passed.", out)

    def test_worker_failure_reported(self):
        os.environ["TOKENSHED_MODEL"] = "test-model"
        with mock.patch.object(
            doctor, "chat_completion", side_effect=ApiError("could not reach x")
        ):
            code, out = self._run()
        self.assertNotEqual(code, 0)
        self.assertIn("[FAIL] worker API check failed", out)

    def test_key_leak_scan_skipped_without_git_repo(self):
        os.environ["TOKENSHED_API_KEY"] = "sk-super-secret-value"
        code, out = self._run()
        self.assertIn("[SKIP] key-leak scan", out)

    def test_key_leak_detected_in_tracked_file(self):
        os.environ["TOKENSHED_API_KEY"] = "sk-super-secret-value"
        _git(self.tmpdir, "init", "-q")
        leaked = os.path.join(self.tmpdir, "settings.local.json")
        with open(leaked, "w") as fh:
            fh.write('{"key": "sk-super-secret-value"}\n')
        _git(self.tmpdir, "add", "settings.local.json")
        _git(self.tmpdir, "commit", "-q", "-m", "oops")

        code, out = self._run()
        self.assertNotEqual(code, 0)
        self.assertIn("[FAIL] TOKENSHED_API_KEY value appears to be committed", out)
        self.assertIn("settings.local.json", out)
        # The key's actual value must never be printed.
        self.assertNotIn("sk-super-secret-value", out)

    def test_no_leak_when_key_not_present_in_tracked_files(self):
        os.environ["TOKENSHED_API_KEY"] = "sk-super-secret-value"
        _git(self.tmpdir, "init", "-q")
        clean = os.path.join(self.tmpdir, "README.md")
        with open(clean, "w") as fh:
            fh.write("hello\n")
        _git(self.tmpdir, "add", "README.md")
        _git(self.tmpdir, "commit", "-q", "-m", "init")

        code, out = self._run()
        self.assertIn("[PASS] no tracked file contains the TOKENSHED_API_KEY value", out)


if __name__ == "__main__":
    unittest.main()
