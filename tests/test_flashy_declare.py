"""Slice 102 - the prepared-not-executed capability/offer declaration script.
Tests only build_request() and main()'s dry-run path; send_request() (the
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

from ops.flashy_declare import build_request

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "flashy_declare.py"


class BuildRequestTest(unittest.TestCase):
    def test_capabilities_request_shape(self):
        req = build_request("capabilities", "analystos", "analystos-agent", ["evidence", "analysis"], "secret-token")
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["url"], "https://api.flashyos.com/api/v1/orgs/analystos/agents/analystos-agent/capabilities")
        self.assertEqual(req["body"], {"capabilities": ["analysis", "evidence"]})  # sorted, deduplicated

    def test_offers_request_shape(self):
        req = build_request("offers", "analystos", "analystos-agent", ["document-analysis"], "secret-token")
        self.assertTrue(req["url"].endswith("/offers"))
        self.assertEqual(req["body"], {"offers": ["document-analysis"]})

    def test_duplicate_values_are_deduplicated(self):
        req = build_request("capabilities", "x", "y", ["a", "a", "b"], "t")
        self.assertEqual(req["body"]["capabilities"], ["a", "b"])

    def test_the_token_itself_never_appears_in_the_built_request(self):
        # build_request's headers only ever hold a redacted placeholder - the
        # real token is injected later, only inside send_request(), which
        # this test suite never calls.
        req = build_request("capabilities", "x", "y", ["a"], "a-very-real-looking-secret-token")
        self.assertNotIn("a-very-real-looking-secret-token", json.dumps(req))
        self.assertIn("redacted", req["headers"]["x-join-grant"])


class CliDryRunTest(unittest.TestCase):
    """Runs the real CLI, but always without --execute, so no network call
    is ever possible from this test."""

    def test_dry_run_prints_the_request_and_touches_no_network(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "capabilities", "analysis", "evidence",
             "--org-id", "analystos", "--agent-name", "analystos-agent", "--token", "fake-token-for-testing"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("dry run", result.stdout)
        self.assertNotIn("fake-token-for-testing", result.stdout)

    def test_offers_dry_run_warns_the_path_is_unconfirmed(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "offers", "document-analysis",
             "--org-id", "analystos", "--agent-name", "analystos-agent", "--token", "fake-token-for-testing"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("own guess", result.stdout)

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
                "--org-id", "analystos", "--agent-name", "analystos-agent",
                "--token", "fake-token-for-testing", "--execute",
            ])
        self.assertEqual(code, 0)
        mock_send.assert_called_once()
        sent_request, sent_token = mock_send.call_args[0]
        self.assertEqual(sent_token, "fake-token-for-testing")
        self.assertEqual(sent_request["body"], {"capabilities": ["analysis", "evidence"]})

    def test_without_execute_send_request_is_never_called(self):
        from unittest.mock import patch

        import ops.flashy_declare as mod

        with patch.object(mod, "send_request") as mock_send:
            code = mod.main([
                "capabilities", "analysis",
                "--org-id", "analystos", "--agent-name", "analystos-agent",
                "--token", "fake-token-for-testing",
            ])
        self.assertEqual(code, 0)
        mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
