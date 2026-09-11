"""Tests for the L0 evidence retention/expiry cleanup pass -
specs/slice-43/spec.md, "Done when" #3.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

from analystos.l0.store import (
    _RETENTION_DAYS_ENV_VAR,
    purge_expired_evidence,
    retrieve,
    store,
)


class RetentionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.evidence = self.tmp / "evidence"
        self.source = self.tmp / "source.txt"
        self.source.write_bytes(b"hello analyst\n")
        self._env_backup = os.environ.get(_RETENTION_DAYS_ENV_VAR)
        os.environ.pop(_RETENTION_DAYS_ENV_VAR, None)

    def tearDown(self):
        if self._env_backup is None:
            os.environ.pop(_RETENTION_DAYS_ENV_VAR, None)
        else:
            os.environ[_RETENTION_DAYS_ENV_VAR] = self._env_backup
        self._tmp.cleanup()

    def _backdate(self, digest, days_old):
        stored_path = self.evidence / digest
        old_time = time.time() - (days_old * 86400)
        os.utime(stored_path, (old_time, old_time))

    def test_a_file_past_its_retention_window_is_removed_on_the_next_cleanup_run(self):  # Done when #3
        digest = store(self.source, self.evidence)
        self.assertTrue((self.evidence / digest).is_file())

        self._backdate(digest, days_old=45)  # older than the 30-day window below

        removed = purge_expired_evidence(self.evidence, max_age_days=30)

        self.assertIn(digest, removed)
        self.assertFalse((self.evidence / digest).is_file())
        with self.assertRaises(FileNotFoundError):
            retrieve(digest, self.evidence)

    def test_a_file_within_the_retention_window_survives_a_cleanup_run(self):
        digest = store(self.source, self.evidence)
        self._backdate(digest, days_old=5)  # well within a 30-day window

        removed = purge_expired_evidence(self.evidence, max_age_days=30)

        self.assertEqual(removed, [])
        self.assertTrue((self.evidence / digest).is_file())
        self.assertEqual(retrieve(digest, self.evidence), self.source.read_bytes())

    def test_retention_days_is_configurable_via_env_var(self):
        os.environ[_RETENTION_DAYS_ENV_VAR] = "1"
        digest = store(self.source, self.evidence)
        self._backdate(digest, days_old=2)  # older than the 1-day env-configured window

        removed = purge_expired_evidence(self.evidence)  # no explicit max_age_days - reads the env var

        self.assertIn(digest, removed)
        self.assertFalse((self.evidence / digest).is_file())

    def test_unset_retention_means_no_expiry_is_enforced(self):
        digest = store(self.source, self.evidence)
        self._backdate(digest, days_old=9999)  # ancient - would expire under any real window

        removed = purge_expired_evidence(self.evidence)  # no env var, no max_age_days -> opt-in default

        self.assertEqual(removed, [])
        self.assertTrue((self.evidence / digest).is_file())

    def test_store_itself_triggers_cleanup_of_other_expired_files(self):
        # store() runs the cleanup pass as a side effect (best-effort), so
        # retention is actually enforced over time without an external
        # scheduler - see the spec's "Done when" #3 framing ("on the next
        # cleanup run").
        old_digest = store(self.source, self.evidence)
        self._backdate(old_digest, days_old=45)

        os.environ[_RETENTION_DAYS_ENV_VAR] = "30"
        other_source = self.tmp / "other.txt"
        other_source.write_bytes(b"a different file\n")
        store(other_source, self.evidence)  # unrelated store call

        self.assertFalse((self.evidence / old_digest).is_file())


if __name__ == "__main__":
    unittest.main()
