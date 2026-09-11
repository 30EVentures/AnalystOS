"""Tests for L0 store + retrieve.

One test per "Done when" check in specs/slice-2/spec.md (store) and
specs/slice-3/spec.md (retrieve).
"""

import hashlib
import tempfile
import unittest
from pathlib import Path

from analystos.l0.store import retrieve, store


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

    def test_stored_bytes_are_encrypted_not_plaintext(self):  # Slice 43 - Done when #1
        # Slice 2's original version of this test asserted the opposite -
        # that the on-disk bytes matched the plaintext exactly. Slice 43
        # (evidence encryption at rest) makes that assertion wrong by
        # design; the round trip through retrieve() (below) is what now
        # proves correctness, not raw on-disk equality.
        digest = store(self.source, self.evidence)
        stored = (self.evidence / digest).read_bytes()
        original = self.source.read_bytes()
        self.assertNotEqual(stored, original)
        self.assertNotIn(original, stored)  # not just reordered - not present at all

    def test_hash_is_really_sha256_of_the_contents(self):  # sanity check
        digest = store(self.source, self.evidence)
        self.assertEqual(digest, hashlib.sha256(b"hello analyst\n").hexdigest())

    def test_missing_file_raises(self):  # guard rail
        with self.assertRaises(FileNotFoundError):
            store(self.tmp / "nope.txt", self.evidence)

    # --- retrieve (slice 3) ---

    def test_retrieve_returns_the_original_bytes(self):  # Done when #1
        digest = store(self.source, self.evidence)
        self.assertEqual(retrieve(digest, self.evidence), self.source.read_bytes())

    def test_retrieve_unknown_hash_raises(self):  # Done when #2
        with self.assertRaises(FileNotFoundError):
            retrieve("0" * 64, self.evidence)

    def test_store_then_retrieve_roundtrip_on_binary(self):  # not just text
        blob = self.tmp / "pic.bin"
        blob.write_bytes(bytes(range(256)) * 8)
        digest = store(blob, self.evidence)
        self.assertEqual(retrieve(digest, self.evidence), blob.read_bytes())


if __name__ == "__main__":
    unittest.main()
