"""Tests for L0 store - one per "Done when" check in specs/slice-2/spec.md."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from analystos.l0.store import store


class StoreTest(unittest.TestCase):
    def setUp(self):
        # a throwaway working area for each test; removed in tearDown
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.evidence = self.tmp / "evidence"
        self.source = self.tmp / "source.txt"
        self.source.write_bytes(b"hello analyst\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_returns_64_char_hex(self):  # Done when #1
        digest = store(self.source, self.evidence)
        self.assertEqual(len(digest), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in digest))

    def test_copy_exists_named_by_hash(self):  # Done when #2
        digest = store(self.source, self.evidence)
        self.assertTrue((self.evidence / digest).is_file())

    def test_same_file_twice_is_idempotent(self):  # Done when #3
        first = store(self.source, self.evidence)
        second = store(self.source, self.evidence)
        self.assertEqual(first, second)
        self.assertEqual(len(list(self.evidence.iterdir())), 1)

    def test_one_byte_change_changes_the_hash(self):  # Done when #4
        first = store(self.source, self.evidence)
        self.source.write_bytes(b"hello analyst!")  # different contents
        second = store(self.source, self.evidence)
        self.assertNotEqual(first, second)

    def test_stored_bytes_match_the_original(self):  # Done when #5
        digest = store(self.source, self.evidence)
        stored = (self.evidence / digest).read_bytes()
        self.assertEqual(stored, self.source.read_bytes())

    def test_hash_is_really_sha256_of_the_contents(self):  # sanity check
        digest = store(self.source, self.evidence)
        self.assertEqual(digest, hashlib.sha256(b"hello analyst\n").hexdigest())

    def test_missing_file_raises(self):  # guard rail
        with self.assertRaises(FileNotFoundError):
            store(self.tmp / "nope.txt", self.evidence)


if __name__ == "__main__":
    unittest.main()
