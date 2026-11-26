"""Slice 132 - the public signing keys as a JWKS (Flashy plan C-ID-6)."""

import base64
import json
import unittest
from pathlib import Path

from tools.build_jwks import JWKS_PATH, build, jwk_for

ROOT = Path(__file__).resolve().parents[1]
SEAL_KEY = json.loads((ROOT / "site" / ".well-known" / "analystos-seal-key.json").read_text())
JWKS = json.loads(JWKS_PATH.read_text())


class JwksTest(unittest.TestCase):
    def test_the_served_file_is_what_the_tool_builds(self):
        self.assertEqual(JWKS_PATH.read_text(), build())

    def test_every_active_seal_key_is_published_with_the_same_id(self):
        active = {k["key_id"]: k["public_key"] for k in SEAL_KEY["keys"] if k["status"] == "active"}
        self.assertTrue(active)
        self.assertEqual({k["kid"]: k["x"] for k in JWKS["keys"]}, active)

    def test_each_key_is_a_standard_ed25519_jwk_with_no_private_part(self):
        for key in JWKS["keys"]:
            self.assertEqual(set(key), {"kty", "crv", "x", "kid", "use", "alg"})
            self.assertEqual((key["kty"], key["crv"], key["use"], key["alg"]), ("OKP", "Ed25519", "sig", "EdDSA"))
            self.assertNotIn("d", key)
            self.assertEqual(len(base64.urlsafe_b64decode(key["x"] + "=" * (-len(key["x"]) % 4))), 32)

    def test_key_ids_are_unique(self):
        kids = [k["kid"] for k in JWKS["keys"]]
        self.assertEqual(len(kids), len(set(kids)))

    def test_a_wrong_length_or_algorithm_is_refused(self):
        with self.assertRaises(ValueError):
            jwk_for({"key_id": "k", "algorithm": "ed25519", "public_key": "AAAA"})
        with self.assertRaises(ValueError):
            jwk_for({"key_id": "k", "algorithm": "p256", "public_key": "x"})

    def test_it_is_served_as_json_with_cors(self):
        vercel = json.loads((ROOT / "vercel.json").read_text())
        block = next(h for h in vercel["headers"] if h["source"] == "/.well-known/jwks.json")
        headers = {h["key"]: h["value"] for h in block["headers"]}
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")


if __name__ == "__main__":
    unittest.main()
