"""Slice 59 - the files a FlashyOS Level 1/2 check reads are present, valid,
consistent, and make no claim the product cannot back. See
specs/slice-59/spec.md."""

import json
import re
import unittest
from pathlib import Path

from analystos.aao.validate import validate_charter

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CHARTER_PATH = SITE / ".well-known" / "flashyos-charter.json"
LEGACY_PATH = SITE / "flashyos.roles.json"
HANDSHAKE_PATH = SITE / ".well-known" / "flashyos.json"

CHARTER = json.loads(CHARTER_PATH.read_text(encoding="utf-8"))
HANDSHAKE = json.loads(HANDSHAKE_PATH.read_text(encoding="utf-8"))


class CharterTest(unittest.TestCase):
    def test_passes_the_checker_with_no_errors_and_no_warnings(self):
        self.assertEqual([p.to_dict() for p in validate_charter(CHARTER)], [])

    def test_both_paths_serve_identical_bytes(self):
        self.assertEqual(CHARTER_PATH.read_bytes(), LEGACY_PATH.read_bytes())

    def test_it_is_analystos_with_a_reachable_human(self):
        self.assertEqual(CHARTER["slug"], "analystos")
        self.assertRegex(CHARTER["accountableTo"], r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        self.assertNotIn("example.com", CHARTER["accountableTo"])

    def test_every_measure_names_a_numerator_and_a_denominator(self):
        for role in CHARTER["roles"]:
            with self.subTest(role=role["name"]):
                self.assertRegex(role["measure"], r" as a share of ")

    def test_no_role_claims_a_capability_the_product_lacks(self):
        claimed = {c for role in CHARTER["roles"] for c in role["capabilities"]}
        self.assertEqual(claimed, {"extract", "analyze", "cite", "verify", "refuse", "seal", "publish", "reverify"})

    def test_escalation_names_a_real_role(self):
        self.assertIn(CHARTER["escalation"], [r["name"] for r in CHARTER["roles"]])


class HandshakeTest(unittest.TestCase):
    """The documented flashyos/1 shape: required mesh + org{slug,name<=120,
    profile?}; optional capabilities (<=32 kebab-case), wants, api, join."""

    def test_required_fields(self):
        self.assertEqual(HANDSHAKE["mesh"], "flashyos/1")
        org = HANDSHAKE["org"]
        self.assertEqual(org["slug"], CHARTER["slug"])
        self.assertTrue(0 < len(org["name"]) <= 120)
        self.assertTrue(org["profile"].startswith("https://"))

    def test_it_declares_no_capabilities_until_something_is_callable(self):
        self.assertNotIn("capabilities", HANDSHAKE)

    def test_any_url_it_carries_is_https(self):
        for key in ("api", "join", "wants"):
            if key in HANDSHAKE:
                self.assertTrue(str(HANDSHAKE[key]).startswith("https://"))

    def test_capabilities_if_ever_added_would_be_kebab_case(self):
        for cap in HANDSHAKE.get("capabilities", []):
            self.assertRegex(cap, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(HANDSHAKE.get("capabilities", [])), 32)


class VercelHeadersTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))

    def test_both_paths_get_json_and_cors_headers(self):
        by_source = {h["source"]: {x["key"]: x["value"] for x in h["headers"]} for h in self.config["headers"]}
        for source in ("/.well-known/flashyos.json", "/.well-known/flashyos-charter.json", "/flashyos.roles.json"):
            with self.subTest(source=source):
                headers = by_source[source]
                self.assertTrue(headers["Content-Type"].startswith("application/json"))
                self.assertEqual(headers["Access-Control-Allow-Origin"], "*")

    def test_the_function_exclusions_are_untouched(self):
        self.assertIn("api/**/*.py", self.config["functions"])  # covers api/v1/ too (Slice 61)

    def test_no_secret_shaped_string_in_any_published_file(self):
        for path in (CHARTER_PATH, LEGACY_PATH, HANDSHAKE_PATH):
            self.assertIsNone(re.search(r"sk-[A-Za-z0-9]{10,}|token|password", path.read_text().lower()), path)


if __name__ == "__main__":
    unittest.main()
