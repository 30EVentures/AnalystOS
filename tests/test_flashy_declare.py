"""Slice 102 - the prepared-not-executed capability/offer declaration script.
Tests only build_requests() and main()'s dry-run path; send_request() (the
only function that touches the network) is never called from this file -
there is no valid token in this session and this is an outward action that
needs the owner's explicit yes regardless of whether a token exists. See
ops/README.md.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from ops.flashy_declare import build_requests

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "flashy_declare.py"


class BuildRequestTest(unittest.TestCase):
    """Shapes from the published @flashyos/agent@0.21.0 client, after the first
    live call (2026-11-26) answered 400 to the old {"capabilities": [...]} body."""

    def test_capabilities_are_one_request_each_with_a_description(self):
        reqs = build_requests("capabilities", "cmtkurcbs00je12tigb1rc6t1", "analysis",
                              ["document-analysis", "analytics"], "secret-token",
                              {"document-analysis": "Reads one source document."})
        self.assertEqual([r["method"] for r in reqs], ["POST", "POST"])
        for req in reqs:
            self.assertEqual(req["url"], "https://api.flashyos.com/api/v1/orgs/cmtkurcbs00je12tigb1rc6t1/agents/analysis/capabilities")
        self.assertEqual([r["body"] for r in reqs], [
            {"capability": "analytics", "description": "analytics"},  # no description known: the slug, as the client does
            {"capability": "document-analysis", "description": "Reads one source document."},
        ])

    def test_offers_are_one_org_level_request(self):
        reqs = build_requests("offers", "cmtkurcbs00je12tigb1rc6t1", "analysis", ["b-offer", "a-offer", "a-offer"], "t")
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0]["url"], "https://api.flashyos.com/api/v1/orgs/cmtkurcbs00je12tigb1rc6t1/offers")
        self.assertEqual(reqs[0]["body"], {"offers": ["a-offer", "b-offer"]})

    def test_duplicate_values_are_deduplicated(self):
        reqs = build_requests("capabilities", "x", "y", ["a", "a", "b"], "t")
        self.assertEqual([r["body"]["capability"] for r in reqs], ["a", "b"])

    def test_the_charter_purpose_is_the_description(self):
        from ops.mesh_ids import capability_descriptions
        descriptions = capability_descriptions()
        self.assertTrue(descriptions["document-analysis"].startswith("Reads one source document"))
        self.assertTrue(all(descriptions.values()))

    def test_the_token_itself_never_appears_in_the_built_request(self):
        # The headers only ever hold a redacted placeholder - the real token is
        # injected later, only inside send_request(), which this suite never calls.
        reqs = build_requests("capabilities", "x", "y", ["a"], "a-very-real-looking-secret-token")
        self.assertNotIn("a-very-real-looking-secret-token", json.dumps(reqs))
        self.assertIn("redacted", reqs[0]["headers"]["x-join-grant"])


class CliDryRunTest(unittest.TestCase):
    """Runs the real CLI, but always without --execute, so no network call
    is ever possible from this test."""

    def test_dry_run_prints_the_request_and_touches_no_network(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "capabilities", "analysis", "evidence",
             "--org-id", "cmtkurcbs00je12tigb1rc6t1", "--agent-name", "analystos-agent", "--token", "fake-token-for-testing"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("dry run", result.stdout)
        self.assertNotIn("fake-token-for-testing", result.stdout)

    def test_offers_dry_run_targets_the_organisation_not_an_agent(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "offers", "document-analysis",
             "--org-id", "cmtkurcbs00je12tigb1rc6t1", "--agent-name", "analystos-agent", "--token", "fake-token-for-testing"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("/orgs/cmtkurcbs00je12tigb1rc6t1/offers", result.stdout)
        self.assertNotIn("/agents/", result.stdout)

    def test_no_token_given_refuses_cleanly(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "FLASHY_JOIN_GRANT_TOKEN"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "capabilities", "analysis", "--org-id", "x", "--agent-name", "y"],
            capture_output=True, text=True, timeout=15, env=env,
        )
        self.assertEqual(result.returncode, 2)

class ExecuteFlagTest(unittest.TestCase):
    """--execute must reach send_request() - proven in-process with
    send_request() mocked out, never by actually calling api.flashyos.com.
    This session makes no real call to that host under any test."""

    def test_execute_calls_send_request_exactly_once_with_the_built_request(self):
        from unittest.mock import patch

        import ops.flashy_declare as mod

        with patch.object(mod, "send_request", return_value={"status": 200, "body": {"ok": True}}) as mock_send:
            code = mod.main([
                "capabilities", "analysis", "evidence",
                "--org-id", "cmtkurcbs00je12tigb1rc6t1", "--agent-name", "analystos-agent",
                "--token", "fake-token-for-testing", "--execute",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(mock_send.call_count, 2)  # one request per capability
        sent = [c[0] for c in mock_send.call_args_list]
        self.assertEqual({tok for _, tok in sent}, {"fake-token-for-testing"})
        self.assertEqual([r["body"]["capability"] for r, _ in sent], ["analysis", "evidence"])

    def test_execute_stops_at_the_first_refusal(self):
        import io
        import urllib.error
        from unittest.mock import patch

        import ops.flashy_declare as mod

        refusal = urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(b'{"error":"no"}'))
        with patch.object(mod, "send_request", side_effect=refusal) as mock_send:
            code = mod.main(["capabilities", "analysis", "evidence", "--org-id", "cmtkurcbs00je12tigb1rc6t1",
                             "--agent-name", "analysis", "--token", "t", "--execute"])
        self.assertEqual(code, 1)
        mock_send.assert_called_once()

    def test_without_execute_send_request_is_never_called(self):
        from unittest.mock import patch

        import ops.flashy_declare as mod

        with patch.object(mod, "send_request") as mock_send:
            code = mod.main([
                "capabilities", "analysis",
                "--org-id", "cmtkurcbs00je12tigb1rc6t1", "--agent-name", "analystos-agent",
                "--token", "fake-token-for-testing",
            ])
        self.assertEqual(code, 0)
        mock_send.assert_not_called()


class GuardTest(unittest.TestCase):
    """Slice 132: the two mistakes Flashy measured are refused before anything is built."""

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--agent-name", "analysis",
                               "--token", "fake-token-for-testing"], cwd=ROOT, capture_output=True, text=True, timeout=30)

    def test_the_slug_is_refused_as_an_org_id(self):
        done = self.run_script("capabilities", "document-analysis", "--org-id", "analystos")
        self.assertEqual(done.returncode, 2)
        self.assertIn("cmtkurcbs00je12tigb1rc6t1", done.stdout)
        self.assertNotIn("api.flashyos.com", done.stdout)

    def test_a_capability_the_charter_does_not_answer_for_is_refused(self):
        done = self.run_script("capabilities", "document-analysys", "--org-id", "cmtkurcbs00je12tigb1rc6t1")
        self.assertEqual(done.returncode, 2)
        self.assertIn("document-analysys", done.stdout)
        self.assertNotIn("api.flashyos.com", done.stdout)

    def test_a_non_slug_is_refused(self):
        done = self.run_script("offers", "Document Analysis", "--org-id", "cmtkurcbs00je12tigb1rc6t1")
        self.assertEqual(done.returncode, 2)

    def test_every_charter_x_capability_passes(self):
        from ops.mesh_ids import charter_capabilities, value_problems
        caps = charter_capabilities()
        for slug in ("document-analysis", "figure-verification", "sealed-report", "analytics", "analysis"):
            self.assertIn(slug, caps)
        self.assertEqual(value_problems("capabilities", sorted(caps)), [])

    def test_anything_not_shaped_like_an_org_id_is_refused(self):
        from ops.mesh_ids import org_id_problem
        self.assertIsNone(org_id_problem("cmtkurcbs00je12tigb1rc6t1"))
        for bad in ("analystos", "Analystos", "org/analystos", "", "../x", "cmtkurcbs00je12tigb1rc6t1/../x"):
            self.assertIsNotNone(org_id_problem(bad), bad)

    def test_an_agent_name_with_a_path_character_is_refused(self):
        done = self.run_script("capabilities", "analysis", "--org-id", "cmtkurcbs00je12tigb1rc6t1")
        self.assertEqual(done.returncode, 0, done.stdout)  # "analysis" is a valid agent name
        bad = subprocess.run([sys.executable, str(SCRIPT), "capabilities", "analysis", "--org-id",
                              "cmtkurcbs00je12tigb1rc6t1", "--agent-name", "../admin", "--token", "t"],
                             cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(bad.returncode, 2)
        self.assertNotIn("api.flashyos.com", bad.stdout)

    def test_more_than_twenty_offers_is_refused(self):
        from ops.mesh_ids import value_problems
        self.assertTrue(value_problems("offers", [f"offer-{i}" for i in range(21)]))


if __name__ == "__main__":
    unittest.main()
