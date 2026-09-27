"""Slice 72 - the evidence store says once, out loud, when it uses the public
development key. See specs/slice-72/spec.md."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from analystos.l0 import store as store_mod
from analystos.l0.store import retrieve, store


class KeyWarningTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.source = self.tmp / "s.txt"
        self.source.write_bytes(b"hello analyst\n")
        self.evidence = self.tmp / "ev"
        patcher = patch.object(store_mod, "_warned_fallback", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_store(self, env):
        err = io.StringIO()
        with patch.dict(os.environ, env, clear=False), contextlib.redirect_stderr(err):
            digest = store(self.source, self.evidence)
            body = retrieve(digest, self.evidence)
        return err.getvalue(), digest, body

    def test_the_fallback_warns_exactly_once_per_process(self):
        env = {store_mod._EVIDENCE_KEY_ENV_VAR: ""}
        first, _, _ = self.run_store(env)
        second, _, _ = self.run_store(env)
        self.assertEqual(first.count("development key"), 1)
        self.assertEqual(second, "")

    def test_the_warning_names_the_variable_and_says_the_key_is_public(self):
        text, _, _ = self.run_store({store_mod._EVIDENCE_KEY_ENV_VAR: ""})
        self.assertIn("ANALYSTOS_EVIDENCE_KEY", text)
        self.assertIn("public", text)
        self.assertIn("casual reading", text)

    def test_a_configured_key_prints_nothing(self):
        text, _, body = self.run_store({store_mod._EVIDENCE_KEY_ENV_VAR: Fernet.generate_key().decode()})
        self.assertEqual(text, "")
        self.assertEqual(body, b"hello analyst\n")

    def test_behaviour_is_otherwise_unchanged_files_round_trip_under_the_fallback(self):
        _, digest, body = self.run_store({store_mod._EVIDENCE_KEY_ENV_VAR: ""})
        self.assertEqual(body, b"hello analyst\n")
        stored = next((self.evidence).rglob(digest))
        self.assertNotIn(b"hello analyst", stored.read_bytes())  # still never plaintext


if __name__ == "__main__":
    unittest.main()
