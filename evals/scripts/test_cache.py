import os
import shutil
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import _cache  # noqa: E402


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_store_then_load_hits(self):
        key = _cache.compute_key("q", "model", "v1", [["a.py", "hash1"]])
        _cache.store_entry(self.tmpdir, key, "the answer")
        self.assertEqual(_cache.load_entry(self.tmpdir, key), "the answer")

    def test_miss_on_unknown_key(self):
        self.assertIsNone(_cache.load_entry(self.tmpdir, "nonexistent"))

    def test_key_changes_when_file_hash_changes(self):
        key_a = _cache.compute_key("q", "model", "v1", [["a.py", "hash1"]])
        key_b = _cache.compute_key("q", "model", "v1", [["a.py", "hash2"]])
        self.assertNotEqual(key_a, key_b)

    def test_key_changes_when_model_changes(self):
        key_a = _cache.compute_key("q", "model-a", "v1", [["a.py", "hash1"]])
        key_b = _cache.compute_key("q", "model-b", "v1", [["a.py", "hash1"]])
        self.assertNotEqual(key_a, key_b)

    def test_key_changes_when_prompt_version_changes(self):
        key_a = _cache.compute_key("q", "model", "v1", [["a.py", "hash1"]])
        key_b = _cache.compute_key("q", "model", "v2", [["a.py", "hash1"]])
        self.assertNotEqual(key_a, key_b)

    def test_key_stable_regardless_of_file_order(self):
        key_a = _cache.compute_key(
            "q", "model", "v1", [["a.py", "h1"], ["b.py", "h2"]]
        )
        key_b = _cache.compute_key(
            "q", "model", "v1", [["b.py", "h2"], ["a.py", "h1"]]
        )
        self.assertEqual(key_a, key_b)

    def test_expired_entry_is_evicted_on_load(self):
        key = _cache.compute_key("q", "model", "v1", [["a.py", "hash1"]])
        _cache.store_entry(self.tmpdir, key, "old answer")
        path = _cache._entry_path(self.tmpdir, key)
        old_time = time.time() - (_cache.MAX_AGE_DAYS + 1) * 86400
        os.utime(path, (old_time, old_time))
        self.assertIsNone(_cache.load_entry(self.tmpdir, key))
        self.assertFalse(os.path.exists(path))

    def test_prune_removes_oldest_first_above_size_cap(self):
        answers_dir = os.path.join(self.tmpdir, "answers")
        os.makedirs(answers_dir, exist_ok=True)
        # Three ~20MB-ish entries so the total clears the 50MB cap.
        chunk = "x" * (20 * 1024 * 1024)
        keys = ["k1", "k2", "k3"]
        now = time.time()
        for i, k in enumerate(keys):
            _cache.store_entry(self.tmpdir, k, chunk)
            path = _cache._entry_path(self.tmpdir, k)
            # Stagger mtimes so k1 is oldest, k3 is newest.
            stamp = now - (len(keys) - i) * 10
            os.utime(path, (stamp, stamp))
        _cache._maintain(answers_dir)
        # Oldest (k1) should be gone; newest (k3) should remain.
        self.assertFalse(os.path.exists(_cache._entry_path(self.tmpdir, "k1")))
        self.assertTrue(os.path.exists(_cache._entry_path(self.tmpdir, "k3")))

    def test_cache_enabled_env_var(self):
        os.environ["TOKENSHED_CACHE"] = "off"
        try:
            self.assertFalse(_cache.cache_enabled())
        finally:
            del os.environ["TOKENSHED_CACHE"]
        self.assertTrue(_cache.cache_enabled())

    def test_default_cache_dir_not_inside_repo(self):
        os.environ.pop("TOKENSHED_CACHE_DIR", None)
        cache_dir = _cache.default_cache_dir()
        self.assertNotIn(REPO_ROOT, cache_dir)

    def test_cache_dir_override(self):
        os.environ["TOKENSHED_CACHE_DIR"] = "/tmp/custom-tokenshed-cache"
        try:
            self.assertEqual(_cache.default_cache_dir(), "/tmp/custom-tokenshed-cache")
        finally:
            del os.environ["TOKENSHED_CACHE_DIR"]


if __name__ == "__main__":
    unittest.main()
