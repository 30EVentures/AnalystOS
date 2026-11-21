"""Slice 97 - the document-analysis engagement playbook and its acceptance
criteria, checked for real: against the published @flashyos/playbook package
for structure, and against this repo's own running Flask app and seal
verifier for the claims that reference them. See drafts/README.md.
"""

import copy
import json
import subprocess
import unittest
from pathlib import Path

from analystos.l4.acceptance import CRITERIA, document_analysis_acceptance
from analystos.l4.seal import build_bundle
from analystos.l4.seal_verify import canonical_bytes, sha256_hex
from tests.test_l4_seal import trace
from api.analyze import app

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = ROOT / "drafts" / "playbook-document-analysis.json"
NODE_MODULES = ROOT / "tools" / "flashyos-check" / "node_modules"

PLAYBOOK = json.loads(PLAYBOOK_PATH.read_text())
STEPS_BY_ID = {s["id"]: s for s in PLAYBOOK["steps"]}


class PlaybookLocationTest(unittest.TestCase):
    def test_not_under_the_served_site_directory(self):
        self.assertFalse(str(PLAYBOOK_PATH).startswith(str(ROOT / "site")))


class PlaybookShapeTest(unittest.TestCase):
    """Checks that do not need Node - the shape any @flashyos/playbook
    consumer would read."""

    def test_every_role_in_a_step_is_declared_at_the_top(self):
        for step in PLAYBOOK["steps"]:
            self.assertIn(step["role"], PLAYBOOK["roles"], step["id"])

    def test_every_role_is_a_name_in_the_live_or_draft_charter(self):
        charter = json.loads((ROOT / "site" / ".well-known" / "flashyos-charter.json").read_text())
        draft_charter = json.loads((ROOT / "drafts" / "flashyos-charter.team.json").read_text())
        known_roles = {r["name"] for r in charter["roles"]} | {r["name"] for r in draft_charter["roles"]}
        for role in PLAYBOOK["roles"]:
            self.assertIn(role, known_roles, role)

    def test_every_after_reference_names_a_real_step(self):
        for step in PLAYBOOK["steps"]:
            for ref in step.get("after", []):
                self.assertIn(ref, STEPS_BY_ID, f"{step['id']} -> {ref}")

    def test_the_dependency_graph_has_no_cycle(self):
        # A plain depth-first walk; this playbook is a line, but the test
        # does not assume that - the next step added might not be.
        visiting, visited = set(), set()

        def visit(step_id, path):
            if step_id in visited:
                return
            self.assertNotIn(step_id, visiting, f"cycle: {' -> '.join(path + [step_id])}")
            visiting.add(step_id)
            for ref in STEPS_BY_ID[step_id].get("after", []):
                visit(ref, path + [step_id])
            visiting.discard(step_id)
            visited.add(step_id)

        for step_id in STEPS_BY_ID:
            visit(step_id, [])

    def test_exactly_one_step_per_charter_role(self):
        roles_used = [s["role"] for s in PLAYBOOK["steps"]]
        self.assertEqual(sorted(roles_used), sorted(PLAYBOOK["roles"]))

    def test_the_seal_step_evidence_kind_matches_the_evidence_module(self):
        # If analystos/l4/acceptance.py's criteria ever stop mentioning the
        # seal, this step's evidence kind should be revisited too.
        self.assertIn("seal", CRITERIA[0].lower())
        self.assertEqual(STEPS_BY_ID["seal-the-report"]["evidence"], "sealed")


@unittest.skipUnless(NODE_MODULES.is_dir(), "run: cd tools/flashyos-check && npm install --ignore-scripts")
class RealPlaybookValidatorTest(unittest.TestCase):
    def _run_node(self, script: str):
        result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_is_a_well_formed_playbook_with_zero_validation_errors(self):
        out = self._run_node(
            """
            const pb = require('./tools/flashyos-check/node_modules/@flashyos/playbook');
            const fs = require('fs');
            const doc = JSON.parse(fs.readFileSync('drafts/playbook-document-analysis.json'));
            console.log(JSON.stringify({isPlaybook: pb.isPlaybook(doc), errors: pb.validate(doc)}));
            """
        )
        self.assertTrue(out["isPlaybook"])
        self.assertEqual(out["errors"], [])

    def test_a_well_formed_claim_for_every_step_has_zero_findings(self):
        out = self._run_node(
            """
            const pb = require('./tools/flashyos-check/node_modules/@flashyos/playbook');
            const fs = require('fs');
            const doc = JSON.parse(fs.readFileSync('drafts/playbook-document-analysis.json'));
            const byId = {}; doc.steps.forEach(s => byId[s.id] = s);
            const ctx = {participants: ['org/analystos', 'org/example-client']};
            const claims = {
              'accept-engagement-scope': {kind:'attested', statement:'We agree the scope.', by:'org/example-client'},
              'gather-and-record-sources': {kind:'attested', statement:'We confirm the sources.', by:'org/example-client'},
              'draft-the-cited-report': {kind:'endpoint', url:'https://analystos.dev/api/v1/verify', expect:{status:200}},
              'recompute-and-refuse': {kind:'endpoint', url:'https://analystos.dev/api/v1/verify', expect:{status:200, contains:'content_checked'}},
              'seal-the-report': {kind:'sealed', entryId:'ship/analystos/8f2a1c4d9b0e', digest:'a'.repeat(64)},
              'deliver-and-answer-questions': {kind:'url', url:'https://analystos.dev/r/abc123'},
            };
            const findings = {};
            for (const [id, claim] of Object.entries(claims)) {
              findings[id] = pb.checkClaim({...byId[id], orgId:'org/analystos'}, claim, ctx);
            }
            console.log(JSON.stringify(findings));
            """
        )
        for step_id, findings in out.items():
            with self.subTest(step=step_id):
                self.assertEqual(findings, [], f"{step_id}: {findings}")

    def test_an_organisation_cannot_attest_its_own_step(self):
        # Proves the check above is not vacuous: the real validator does
        # refuse a bad claim, not just accept whatever shape is handed in.
        out = self._run_node(
            """
            const pb = require('./tools/flashyos-check/node_modules/@flashyos/playbook');
            const fs = require('fs');
            const doc = JSON.parse(fs.readFileSync('drafts/playbook-document-analysis.json'));
            const step = doc.steps.find(s => s.id === 'accept-engagement-scope');
            const claim = {kind:'attested', statement:'x', by:'org/analystos'};
            const ctx = {participants: ['org/analystos', 'org/example-client']};
            console.log(JSON.stringify(pb.checkClaim({...step, orgId:'org/analystos'}, claim, ctx)));
            """
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["rule"], "attested")

    def test_sealed_evidence_with_no_verifier_is_honestly_unverified(self):
        # No shipped/1 fan-in exists yet (Track C), so a "sealed" claim is
        # correctly unverified today, not falsely passed or failed.
        out = self._run_node(
            """
            const pb = require('./tools/flashyos-check/node_modules/@flashyos/playbook');
            (async () => {
              const step = {id:'seal-the-report', role:'evidence', evidence:'sealed', orgId:'org/analystos'};
              const claim = {kind:'sealed', entryId:'ship/analystos/8f2a1c4d9b0e', digest:'a'.repeat(64)};
              console.log(JSON.stringify(await pb.verifyEvidence(step, claim, {})));
            })();
            """
        )
        self.assertEqual(out["state"], "unverified")


class AcceptanceCriteriaTest(unittest.TestCase):
    """analystos/l4/acceptance.py, built entirely on the real, already-tested
    verify_bundle - never a second, parallel notion of "verified"."""

    def _real_bundle(self, **override_trace):
        return build_bundle(trace(**override_trace))

    def test_a_genuinely_sealed_report_is_accepted(self):
        bundle = self._real_bundle()
        reasons = document_analysis_acceptance(bundle, source_text=trace()["document_text"])
        self.assertEqual(reasons, [], reasons)

    def test_without_the_source_text_content_is_not_checked_and_that_is_a_failure(self):
        bundle = self._real_bundle()
        reasons = document_analysis_acceptance(bundle, source_text=None)
        self.assertTrue(any("no source text was supplied" in r for r in reasons), reasons)

    def test_a_tampered_bundle_is_refused(self):
        bundle = copy.deepcopy(self._real_bundle())
        bundle["facts"][0]["record"]["value"] = "999999999999"
        reasons = document_analysis_acceptance(bundle, source_text=trace()["document_text"])
        self.assertTrue(any("does not verify" in r for r in reasons), reasons)

    def test_never_raises_on_a_hostile_bundle(self):
        for hostile in (None, {}, {"payload": None}, "not a bundle", 12345, {"payload": {"tier": object()}}):
            with self.subTest(hostile=repr(hostile)[:40]):
                reasons = document_analysis_acceptance(hostile, source_text="x")
                self.assertIsInstance(reasons, list)
                self.assertTrue(reasons)

    def test_criteria_are_documented_and_match_the_playbook_brief(self):
        self.assertEqual(len(CRITERIA), 3)
        seal_step_brief = STEPS_BY_ID["seal-the-report"]["brief"].lower()
        self.assertIn("seal", seal_step_brief)


class EndpointEvidenceAgainstTheRealAppTest(unittest.TestCase):
    """The 'draft-the-cited-report' and 'recompute-and-refuse' steps both
    close against POST /api/v1/verify. This proves the claims' expectations
    (status 200; the body containing content_checked) are actually true of
    the running app, not merely well-shaped JSON."""

    def setUp(self):
        self.client = app.test_client()

    def test_verifying_a_genuine_bundle_returns_200_and_content_checked_true(self):
        bundle = build_bundle(trace())
        response = self.client.post("/api/v1/verify", json={"bundle": bundle, "text": trace()["document_text"]})
        self.assertEqual(response.status_code, 200)  # the "draft-the-cited-report" step's expect.status
        body = response.get_data(as_text=True)
        self.assertIn("content_checked", body)  # the "recompute-and-refuse" step's expect.contains
        self.assertTrue(response.get_json()["content_checked"])

    def test_the_same_endpoint_fails_closed_on_a_tampered_bundle(self):
        bundle = copy.deepcopy(build_bundle(trace()))
        bundle["facts"][0]["record"]["value"] = "999999999999"
        response = self.client.post("/api/v1/verify", json={"bundle": bundle, "text": trace()["document_text"]})
        self.assertEqual(response.status_code, 200)  # verify never 500s - it answers, with ok: false
        self.assertFalse(response.get_json()["ok"])

    def test_an_unauthenticated_caller_can_reach_this_endpoint(self):
        # Both playbook steps assume this; if it ever needs auth, the
        # playbook's evidence kind for these steps needs revisiting too.
        bundle = build_bundle(trace())
        response = self.client.post("/api/v1/verify", json={"bundle": bundle})
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
