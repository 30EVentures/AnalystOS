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
        # Slice 103 (owner's decision, 2026-11-21): switched the live charter to
        # the seven-role team charter drafted in Slice 95. The three original
        # roles' capabilities are unchanged (spec-95 #4); the four new roles'
        # capabilities are governance permissions for a team this codebase does
        # not yet run as live agents - drafts/README.md's former "why it is not
        # the live charter" section documented this plainly before the switch,
        # and ROADMAP.md's Blocked list now carries what making them real needs
        # (re-minted join-grant token, six live agents, four new endpoints). This
        # test's job is only to catch a role quietly claiming something beyond
        # that known, disclosed set - not to force the charter back to three.
        claimed = {c for role in CHARTER["roles"] for c in role["capabilities"]}
        original = {"extract", "analyze", "cite", "verify", "refuse", "seal", "publish", "reverify"}
        self.assertLessEqual(original, claimed)
        self.assertEqual(claimed, original | {
            "accept", "assign", "schedule", "escalate",   # coordination
            "gather", "catalogue", "provenance",            # research
            "compare", "synthesise", "draft",               # synthesis
            "deliver", "brief", "answer",                   # client-delivery
        })

    def test_escalation_names_a_real_role(self):
        self.assertIn(CHARTER["escalation"], [r["name"] for r in CHARTER["roles"]])


class HandshakeTest(unittest.TestCase):
    """The documented flashyos/1 shape: required mesh + org{slug,name<=120,
    profile?}; optional capabilities (<=32 kebab-case), wants, api, join.

    Slice 94 (2026-11-21): the Flashy estate's 21 Nov reply resolved the open
    question that used to sit here. A charter *role name* restates a
    governance fact the charter already publishes and claims nothing
    callable; declaring it took their own auditProperty from level 1
    ("declares nothing it can do") to level 2 with zero issues when they ran
    it. So the handshake now declares exactly the charter's role names - and
    only those, never the x-capability discovery slugs (document-analysis,
    figure-verification, ...), which still wait on docs/mesh-identity.md's
    rule: an endpoint deployed and a token minted. tools/build_flashyos_handshake.py
    is the only thing that writes this array; test_build_flashyos_handshake.py
    checks nobody hand-edits it out of step with the charter.
    """

    def test_required_fields(self):
        self.assertEqual(HANDSHAKE["mesh"], "flashyos/1")
        org = HANDSHAKE["org"]
        self.assertEqual(org["slug"], CHARTER["slug"])
        self.assertTrue(0 < len(org["name"]) <= 120)
        self.assertTrue(org["profile"].startswith("https://"))

    def test_capabilities_are_the_role_names_and_their_discovery_slugs(self):
        # Owner's decision 2026-11-26 (Slice 132, Flashy plan C-MESH-6): advertise the
        # x-capability slugs beside the role names, one vocabulary everywhere.
        self.assertIn("capabilities", HANDSHAKE)
        names = {r["name"] for r in CHARTER["roles"]}
        slugs = {c for role in CHARTER["roles"] for c in role.get("x-capability", [])}
        self.assertEqual(len(slugs), 8)
        self.assertEqual(set(HANDSHAKE["capabilities"]), names | slugs)

    def test_every_advertised_capability_is_answered_for_by_a_role(self):
        answered = {r["name"] for r in CHARTER["roles"]} | {
            c for role in CHARTER["roles"] for c in role.get("x-capability", [])}
        self.assertEqual(set(HANDSHAKE["capabilities"]) - answered, set())

    def test_any_url_it_carries_is_https(self):
        for key in ("api", "join", "wants"):
            if key in HANDSHAKE:
                self.assertTrue(str(HANDSHAKE[key]).startswith("https://"))

    def test_capabilities_are_kebab_case_and_within_the_count_limit(self):
        for cap in HANDSHAKE.get("capabilities", []):
            self.assertRegex(cap, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(HANDSHAKE.get("capabilities", [])), 32)


class VercelHeadersTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))

    def test_both_paths_get_json_and_cors_headers(self):
        by_source = {h["source"]: {x["key"]: x["value"] for x in h["headers"]} for h in self.config["headers"]}
        for source in ("/.well-known/flashyos.json", "/.well-known/flashyos-charter.json", "/flashyos.roles.json",
                       "/.well-known/devlog.fragment.json",
                       "/.well-known/shiplog.json", "/.well-known/checkpoint.json"):
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
