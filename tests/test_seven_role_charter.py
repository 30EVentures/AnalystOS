"""Slice 95 - the draft seven-role team charter in drafts/ (not served; see
drafts/README.md) is well-formed, internally consistent, and passes the real
published FlashyOS validators. This does not test anything this repo serves;
it tests a decision the owner has not made yet, so that decision can be made
with real evidence instead of a guess.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT_PATH = ROOT / "drafts" / "flashyos-charter.team.json"
LIVE_CHARTER_PATH = ROOT / "site" / ".well-known" / "flashyos-charter.json"
NODE_MODULES = ROOT / "tools" / "flashyos-check" / "node_modules"

DRAFT = json.loads(DRAFT_PATH.read_text())


class DraftLocationTest(unittest.TestCase):
    """The structural safeguard drafts/README.md describes: this file must
    never be inside site/, which Vercel serves verbatim on deploy."""

    def test_the_draft_is_not_under_the_served_site_directory(self):
        self.assertFalse(str(DRAFT_PATH).startswith(str(ROOT / "site")))

    def test_nothing_under_site_references_the_draft_filename(self):
        site_dir = ROOT / "site"
        for path in site_dir.rglob("*"):
            if path.is_file():
                self.assertNotIn("flashyos-charter.team", path.read_text(errors="ignore"), path)


class DraftShapeTest(unittest.TestCase):
    """Same checks tests/test_mesh_identity.py runs on the live charter."""

    def test_seven_roles_present_once_each(self):
        names = [r["name"] for r in DRAFT["roles"]]
        self.assertEqual(
            sorted(names),
            ["analysis", "client-delivery", "coordination", "evidence", "research", "synthesis", "verification"],
        )
        self.assertEqual(len(names), len(set(names)))

    def test_it_is_still_analystos_with_a_reachable_human(self):
        self.assertEqual(DRAFT["slug"], "analystos")
        self.assertRegex(DRAFT["accountableTo"], r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def test_every_measure_names_a_numerator_and_a_denominator(self):
        for role in DRAFT["roles"]:
            with self.subTest(role=role["name"]):
                self.assertRegex(role["measure"], r" as a share of ")

    def test_escalation_names_a_real_role(self):
        self.assertIn(DRAFT["escalation"], [r["name"] for r in DRAFT["roles"]])

    def test_role_names_fit_the_published_length_and_word_rules(self):
        # Mirrors aao.ROLE_NAME_MIN/MAX/MAX_WORDS (3, 24, 3) without importing Node;
        # RealValidatorTest below checks the actual package agrees.
        for role in DRAFT["roles"]:
            name = role["name"]
            with self.subTest(role=name):
                self.assertTrue(3 <= len(name) <= 24, name)
                self.assertLessEqual(len(name.split("-")), 3, name)
                self.assertRegex(name, r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", name)

    def test_families_are_in_the_published_closed_set(self):
        closed = {
            "growth", "revenue", "product", "engineering",
            "operations", "data", "finance", "risk", "governance", "support",
        }
        for role in DRAFT["roles"]:
            with self.subTest(role=role["name"]):
                self.assertIn(role["family"], closed)

    def test_analytics_capability_is_kept_on_the_analysis_role(self):
        # drafts/README.md's reason: removing it would unlist the org from the
        # one capability it is already discoverable under on the live network.
        analysis = next(r for r in DRAFT["roles"] if r["name"] == "analysis")
        self.assertIn("analytics", analysis["x-capability"])


class DraftVsLiveTest(unittest.TestCase):
    def test_the_three_live_roles_are_a_subset_of_the_draft(self):
        live = json.loads(LIVE_CHARTER_PATH.read_text())
        live_names = {r["name"] for r in live["roles"]}
        draft_names = {r["name"] for r in DRAFT["roles"]}
        self.assertTrue(live_names.issubset(draft_names), live_names - draft_names)

    def test_the_three_shared_roles_keep_the_same_gate_and_family(self):
        live = json.loads(LIVE_CHARTER_PATH.read_text())
        live_by_name = {r["name"]: r for r in live["roles"]}
        draft_by_name = {r["name"]: r for r in DRAFT["roles"]}
        for name in live_by_name:
            with self.subTest(role=name):
                self.assertEqual(live_by_name[name]["family"], draft_by_name[name]["family"])
                self.assertEqual(
                    live_by_name[name]["humanApprovalAtOrAbove"],
                    draft_by_name[name]["humanApprovalAtOrAbove"],
                )


@unittest.skipUnless(NODE_MODULES.is_dir(), "run: cd tools/flashyos-check && npm install --ignore-scripts")
class RealValidatorTest(unittest.TestCase):
    def _run_node(self, script: str) -> dict:
        result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_zero_validator_errors(self):
        out = self._run_node(
            """
            const aao = require('./tools/flashyos-check/node_modules/@flashyos/aao');
            const fs = require('fs');
            const charter = JSON.parse(fs.readFileSync('drafts/flashyos-charter.team.json'));
            console.log(JSON.stringify({errors: aao.validateCharterDocument(charter)}));
            """
        )
        self.assertEqual(out["errors"], [])

    def test_all_five_static_conformance_checks_pass(self):
        out = self._run_node(
            """
            const aao = require('./tools/flashyos-check/node_modules/@flashyos/aao');
            const fs = require('fs');
            const charter = JSON.parse(fs.readFileSync('drafts/flashyos-charter.team.json'));
            console.log(JSON.stringify(aao.runStaticConformance(charter)));
            """
        )
        static_checks = [c for c in out if c["kind"] == "static"]
        self.assertEqual(len(static_checks), 5)
        for check in static_checks:
            with self.subTest(check=check["id"]):
                self.assertEqual(check["status"], "pass")

    def test_audit_property_reaches_level_2_with_every_discovery_slug_declared(self):
        # Simulates the state this charter would need to be served in (every
        # x-capability deployed and declared) - not the half-declared state
        # that drafts/README.md explains is the wrong thing to publish today.
        out = self._run_node(
            """
            const conf = require('./tools/flashyos-check/node_modules/@flashyos/conformance');
            const fs = require('fs');
            const charter = JSON.parse(fs.readFileSync('drafts/flashyos-charter.team.json'));
            const caps = [...new Set([
              ...charter.roles.map(r => r.name),
              ...charter.roles.flatMap(r => r['x-capability'] || []),
            ])];
            const handshake = {
              mesh: 'flashyos/1',
              org: {slug: charter.slug, name: charter.name, profile: charter.repositories[0].url},
              capabilities: caps,
            };
            console.log(JSON.stringify(conf.auditProperty({charter, handshake, manifest: charter})));
            """
        )
        self.assertEqual(out, {"ok": True, "issues": [], "level": 2})


if __name__ == "__main__":
    unittest.main()
