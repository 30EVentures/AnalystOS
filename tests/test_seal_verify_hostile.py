"""Slice 87 - a stranger's malformed bundle is refused, never crashes the verifier or the public
POST /api/v1/verify endpoint, and an empty bundle never verifies vacuously. Each case here was found
by conformance/seal-1.json (see docs/decisions.md)."""

import copy
import os
import unittest
from unittest.mock import patch

from analystos.l4.seal import build_bundle
from analystos.l4.seal_verify import verify_bundle
from api.analyze import app

TRACE = {"tier": "plain", "segments": [{"type": "prose", "text": "a"}, {"type": "prose", "text": "b"}],
         "report": None, "document_text": "t", "source_hash": "a" * 64}


def bundle():
    return build_bundle(copy.deepcopy(TRACE), created="2026-10-01T00:00:00Z", nonce="0011223344556677")


def hostile():
    out = {}
    b = bundle(); b["facts"][0]["key"] = 5; out["numeric key"] = b
    b = bundle(); b["facts"][0]["key"] = ["fact/000000"]; out["list key"] = b
    b = bundle(); b["facts"][0]["key"] = {"k": 1}; out["object key"] = b
    b = bundle(); b["facts"][1]["record"] = "a string"; out["string record"] = b
    b = bundle(); b["facts"][1]["record"] = None; out["null record"] = b
    for name, value in (("string", "deadbeef"), ("list", ["x"]), ("number", 7), ("true", True), ("empty string", ""), ("empty list", [])):
        b = bundle(); b["signature"] = value; out[f"{name} signature"] = b
    b = bundle(); b["facts"] = []; b["payload"].update(entries=0, root=None); out["no facts, null root"] = b
    return out


class HostileBundleTest(unittest.TestCase):
    def test_each_is_refused_not_raised(self):
        for name, b in hostile().items():
            with self.subTest(name):
                self.assertFalse(verify_bundle(b)["ok"])
                self.assertFalse(verify_bundle(b, public_key="A" * 43, source_text="t")["ok"])

    def test_an_empty_bundle_does_not_verify_vacuously(self):
        b = bundle()
        b["facts"] = []
        b["payload"].update(entries=0, root=None)
        outcome = verify_bundle(b)
        self.assertFalse(outcome["ok"])
        self.assertEqual([c["name"] for c in outcome["checks"] if c["status"] == "fail"], ["structure"])

    def test_the_honest_bundle_still_verifies_and_null_signature_is_unsigned(self):
        outcome = verify_bundle(bundle())
        self.assertTrue(outcome["ok"])
        self.assertFalse(outcome["authentic"])

    def test_the_public_endpoint_answers_instead_of_failing(self):
        with patch.dict(os.environ, {"ANALYSTOS_RATE_LIMIT_MAX": "100000"}):
            client = app.test_client()
            for name, b in hostile().items():
                with self.subTest(name):
                    response = client.post("/api/v1/verify", json={"bundle": b})
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(response.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
