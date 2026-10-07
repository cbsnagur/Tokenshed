import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import _stats  # noqa: E402


class StatsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._env_backup = {
            k: os.environ.get(k)
            for k in ("TOKENSHED_CACHE_DIR", "TOKENSHED_STATS", "TOKENSHED_SESSION")
        }
        os.environ["TOKENSHED_CACHE_DIR"] = self.tmpdir

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_record_then_read_round_trip(self):
        _stats.record(kind="block", script="read", avoided_tokens=100)
        events = _stats.read_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "block")
        self.assertEqual(events[0]["avoided_tokens"], 100)
        self.assertIn("ts", events[0])
        self.assertIn("session", events[0])

    def test_summarize_totals(self):
        os.environ["TOKENSHED_SESSION"] = "s1"
        _stats.record(kind="block", avoided_tokens=1000)
        _stats.record(kind="worker", spent_tokens=200)
        summary = _stats.summarize(_stats.read_events())
        self.assertEqual(
            summary["lifetime"],
            {"blocks": 1, "avoided_tokens": 1000, "spent_tokens": 200, "saved_tokens": 800},
        )
        self.assertEqual(summary["sessions"]["s1"], summary["lifetime"])

    def test_per_session_grouping(self):
        os.environ["TOKENSHED_SESSION"] = "s1"
        _stats.record(kind="block", avoided_tokens=500)
        os.environ["TOKENSHED_SESSION"] = "s2"
        _stats.record(kind="worker", spent_tokens=100)
        summary = _stats.summarize(_stats.read_events())
        self.assertEqual(set(summary["sessions"]), {"s1", "s2"})
        self.assertEqual(summary["sessions"]["s1"]["avoided_tokens"], 500)
        self.assertEqual(summary["sessions"]["s2"]["spent_tokens"], 100)
        self.assertEqual(summary["lifetime"]["avoided_tokens"], 500)
        self.assertEqual(summary["lifetime"]["spent_tokens"], 100)

    def test_session_id_env_beats_marker(self):
        _stats.stamp_session("marker-sid")
        os.environ["TOKENSHED_SESSION"] = "env-sid"
        self.assertEqual(_stats.session_id(), "env-sid")

    def test_session_id_uses_marker_when_env_unset(self):
        os.environ.pop("TOKENSHED_SESSION", None)
        _stats.stamp_session("marker-sid")
        self.assertEqual(_stats.session_id(), "marker-sid")

    def test_session_id_unknown_when_neither_set(self):
        os.environ.pop("TOKENSHED_SESSION", None)
        self.assertEqual(_stats.session_id(), "unknown")

    def test_read_events_missing_ledger_returns_empty(self):
        self.assertEqual(_stats.read_events(), [])

    def test_read_events_skips_corrupt_lines(self):
        os.makedirs(self.tmpdir, exist_ok=True)
        with open(_stats.ledger_path(), "w", encoding="utf-8") as fh:
            fh.write('{"kind": "block", "avoided_tokens": 10}\n')
            fh.write("not json at all\n")
            fh.write("\n")
            fh.write("[1, 2, 3]\n")  # valid JSON, but not an object
            fh.write('{"kind": "worker", "spent_tokens": 5}\n')
        events = _stats.read_events()
        self.assertEqual(len(events), 2)

    def test_stats_disabled_records_nothing(self):
        os.environ["TOKENSHED_STATS"] = "off"
        self.assertFalse(_stats.stats_enabled())
        _stats.record(kind="block", avoided_tokens=100)
        self.assertEqual(_stats.read_events(), [])
        self.assertFalse(os.path.exists(_stats.ledger_path()))

    def test_stamp_session_noop_when_disabled(self):
        os.environ["TOKENSHED_STATS"] = "off"
        _stats.stamp_session("some-sid")
        self.assertFalse(os.path.exists(_stats.marker_path()))

    def test_estimate_tokens(self):
        self.assertEqual(_stats.estimate_tokens(400), 100)
        self.assertEqual(_stats.estimate_tokens(0), 0)
        self.assertEqual(_stats.estimate_tokens(-50), 0)

    def test_record_swallows_open_errors(self):
        with mock.patch("builtins.open", side_effect=OSError("boom")):
            try:
                _stats.record(kind="block", avoided_tokens=1)
            except Exception as exc:  # pragma: no cover - must never happen
                self.fail(f"record() raised {exc!r}")

    def test_record_swallows_unwritable_cache_dir(self):
        os.environ["TOKENSHED_CACHE_DIR"] = os.path.join(
            self.tmpdir, "a-file-not-a-dir"
        )
        with open(os.environ["TOKENSHED_CACHE_DIR"], "w", encoding="utf-8") as fh:
            fh.write("blocking file")
        try:
            _stats.record(kind="block", avoided_tokens=1)
        except Exception as exc:  # pragma: no cover - must never happen
            self.fail(f"record() raised {exc!r}")


if __name__ == "__main__":
    unittest.main()
