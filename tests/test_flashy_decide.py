"""Slice 104 - the prepared-not-executed decision-records script. Tests only
build_request(), parse_state() and main()'s dry-run path; send_request() (the
only function that touches the network) is never called from this file - no
test in this repository ever calls api.flashyos.com for real, and sending a
real decision is an outward action that needs the owner's explicit yes each
time regardless of whether a token exists. See ops/README.md.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from ops.flashy_decide import build_request, parse_state

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "flashy_decide.py"


class BuildRequestTest(unittest.TestCase):
    def test_request_shape_matches_the_sdks_own_endpoint(self):
        req = build_request("analystos", "analystos-agent", "deploy the charter", "MEDIUM", "", "secret-token")
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["url"], "https://api.flashyos.com/api/v1/orgs/analystos/decisions")
        self.assertEqual(req["body"]["orgId"], "analystos")
        self.assertEqual(req["body"]["agentName"], "analystos-agent")
        self.assertEqual(req["body"]["summary"], "deploy the charter")
        self.assertEqual(req["body"]["impact"], "MEDIUM")

    def test_an_owner_is_folded_into_the_summary_like_the_sdk_does(self):
        req = build_request("analystos", "analystos-agent", "wire funds", "CRITICAL", "@mara", "t")
        self.assertEqual(req["body"]["summary"], "wire funds (owner: @mara)")

    def test_the_token_itself_never_appears_in_the_built_request(self):
        req = build_request("x", "y", "a", "LOW", "", "a-very-real-looking-secret-token")
        self.assertNotIn("a-very-real-looking-secret-token", json.dumps(req))
        self.assertIn("redacted", req["body"]["token"])


class ParseStateTest(unittest.TestCase):
    """Mirrors @flashyos/agent@0.21.0's own STATUS_TO_STATE mapping exactly."""

    def test_auto_approved_maps_to_auto(self):
        self.assertEqual(parse_state({"decision": {"id": "d1", "status": "AUTO_APPROVED"}})["state"], "auto")

    def test_pending_maps_to_pending(self):
        self.assertEqual(parse_state({"decision": {"id": "d1", "status": "PENDING"}})["state"], "pending")

    def test_approved_and_rejected_both_map_to_reviewed(self):
        self.assertEqual(parse_state({"decision": {"id": "d1", "status": "APPROVED"}})["state"], "reviewed")
        self.assertEqual(parse_state({"decision": {"id": "d1", "status": "REJECTED"}})["state"], "reviewed")

    def test_a_malformed_response_is_pending_and_unrecorded_not_a_crash(self):
        self.assertEqual(parse_state({}), {"id": None, "state": "pending", "status": None, "recorded": False})
        self.assertEqual(parse_state({"decision": {}}), {"id": None, "state": "pending", "status": None, "recorded": False})


class CliDryRunTest(unittest.TestCase):
    """Runs the real CLI, but always without --execute, so no network call
    is ever possible from this test."""

    def test_dry_run_prints_the_request_and_touches_no_network(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "deploy the charter", "--tier", "2",
             "--org-id", "cmtkurcbs00je12tigb1rc6t1", "--agent-name", "analystos-agent", "--token", "fake-token-for-testing"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("dry run", result.stdout)
        self.assertIn("does not block", result.stdout)
        self.assertNotIn("fake-token-for-testing", result.stdout)

    def test_no_token_given_refuses_cleanly(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "FLASHYOS_AGENT_TOKEN"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "deploy", "--org-id", "x", "--agent-name", "y"],
            capture_output=True, text=True, timeout=15, env=env,
        )
        self.assertEqual(result.returncode, 2)

    def test_tier_one_is_low_impact(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "read a public page", "--tier", "1",
             "--org-id", "cmtkurcbs00je12tigb1rc6t1", "--agent-name", "analystos-agent", "--token", "fake-token-for-testing"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"impact": "LOW"', result.stdout)


class ExecuteFlagTest(unittest.TestCase):
    """--execute must reach send_request() - proven in-process with
    send_request() mocked out, never by actually calling api.flashyos.com.
    This session makes no real call to that host under any test."""

    def test_execute_calls_send_request_exactly_once_with_the_built_request(self):
        from unittest.mock import patch

        import ops.flashy_decide as mod

        with patch.object(mod, "send_request", return_value={"status": 200, "body": {"decision": {"id": "d1", "status": "PENDING"}}}) as mock_send:
            code = mod.main([
                "deploy the charter", "--tier", "2",
                "--org-id", "cmtkurcbs00je12tigb1rc6t1", "--agent-name", "analystos-agent",
                "--token", "fake-token-for-testing", "--execute",
            ])
        self.assertEqual(code, 0)
        mock_send.assert_called_once()
        sent_request, sent_token = mock_send.call_args[0]
        self.assertEqual(sent_token, "fake-token-for-testing")
        self.assertEqual(sent_request["body"]["impact"], "MEDIUM")

    def test_without_execute_send_request_is_never_called(self):
        from unittest.mock import patch

        import ops.flashy_decide as mod

        with patch.object(mod, "send_request") as mock_send:
            code = mod.main([
                "deploy the charter",
                "--org-id", "cmtkurcbs00je12tigb1rc6t1", "--agent-name", "analystos-agent",
                "--token", "fake-token-for-testing",
            ])
        self.assertEqual(code, 0)
        mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
