import contextlib
import io
import os
import shutil
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import _stats  # noqa: E402
import report  # noqa: E402

DAY = 86400


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._env_backup = {
            k: os.environ.get(k)
            for k in ("TOKENSHED_CACHE_DIR", "TOKENSHED_STATS", "TOKENSHED_SESSION")
        }
        os.environ["TOKENSHED_CACHE_DIR"] = self.tmpdir
        os.environ.pop("TOKENSHED_STATS", None)
        os.environ["TOKENSHED_SESSION"] = "sess-a"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _run(self, *argv):
        """Run report.main() capturing (exit_code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = report.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def _seed(self, ts=None):
        ts = ts if ts is not None else int(time.time())
        _stats.record(
            ts=ts, session="sess-a", kind="block", script="read",
            file="x.py", bytes=120000, avoided_tokens=30000,
        )
        _stats.record(
            ts=ts, session="sess-a", kind="worker", script="bulk_read",
            model="m", spent_tokens=1000,
        )
        _stats.record(
            ts=ts, session="sess-b", kind="block", script="bash",
            file="y.py", bytes=40000, avoided_tokens=10000,
        )

    def test_empty_ledger_is_friendly(self):
        code, out, _ = self._run()
        self.assertEqual(code, 0)
        self.assertIn("no events recorded yet", out)

    def test_current_session_and_lifetime(self):
        self._seed()
        code, out, _ = self._run()
        self.assertEqual(code, 0)
        self.assertIn("Session sess-a (current):", out)
        self.assertIn("Lifetime totals:", out)
        # sess-a: 30,000 avoided - 1,000 spent. Lifetime adds sess-b's 10,000.
        self.assertIn("~29,000", out)
        self.assertIn("~39,000", out)
        self.assertIn("1,000", out)

    def test_session_filter_excludes_lifetime(self):
        self._seed()
        code, out, _ = self._run("--session", "sess-b")
        self.assertEqual(code, 0)
        self.assertIn("Session sess-b:", out)
        self.assertNotIn("Lifetime totals:", out)
        self.assertIn("~10,000", out)

    def test_unknown_session_does_not_crash(self):
        self._seed()
        code, out, _ = self._run("--session", "nope")
        self.assertEqual(code, 0)
        self.assertIn("no events recorded for session nope", out)

    def test_since_drops_older_events(self):
        self._seed(ts=int(time.time()) - 10 * DAY)
        cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - DAY))
        code, out, _ = self._run("--since", cutoff)
        self.assertEqual(code, 0)
        self.assertIn("no events recorded yet", out)

    def test_since_keeps_newer_events(self):
        self._seed()
        cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - DAY))
        code, out, _ = self._run("--since", cutoff)
        self.assertEqual(code, 0)
        self.assertIn("~29,000", out)

    def test_bad_since_exits_nonzero(self):
        code, _, err = self._run("--since", "last-tuesday")
        self.assertEqual(code, 2)
        self.assertIn("YYYY-MM-DD", err)

    def test_corrupt_ledger_does_not_crash(self):
        self._seed()
        with open(_stats.ledger_path(), "a", encoding="utf-8") as fh:
            fh.write("{not json at all\n")
        code, out, _ = self._run()
        self.assertEqual(code, 0)
        self.assertIn("~29,000", out)


if __name__ == "__main__":
    unittest.main()
