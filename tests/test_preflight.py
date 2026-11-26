"""Slice 135 - preflight: the same checks as a hire, with no model call, no reservation
and no access code. Preflight and hire share one intake path, so they cannot disagree."""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import jsonify

from analystos.api_v2 import blueprint as v2
from analystos.api_v2 import receipt as receipts
from analystos.packs import consulting
from analystos.packs.replay import ReplayClient
from api.analyze import app
from tests.isolation import reset_rate_limits
from tests.test_api_v2 import CLIENT, CODE, RESPONSE, ROOT, body


class PreflightTest(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {"ANALYSTOS_ACCESS_CODE": CODE})
        patcher.start()
        self.addCleanup(patcher.stop)
        reset_rate_limits(self)
        self.clients = []

        def factory():
            client = ReplayClient([RESPONSE])
            self.clients.append(client)
            return client

        original = v2.client_factory
        v2.client_factory = factory
        self.addCleanup(lambda: setattr(v2, "client_factory", original))
        self.http = app.test_client()

    def preflight(self, payload, path="/api/v2/engagements/preflight"):
        return self.http.post(path, json=payload)  # no access code, ever

    def hire(self, payload):
        return self.http.post("/api/v2/engagements", json=payload, headers={"X-Access-Code": CODE})

    def test_a_ready_hire_is_ready_and_is_taken_on(self):
        response = self.preflight(body())
        self.assertEqual(response.status_code, 200)
        doc = response.get_json()
        self.assertEqual(doc["format"], "analystos-preflight/1")
        self.assertTrue(doc["ready"])
        self.assertEqual((doc["problems"], doc["open_questions"]), ([], []))
        self.assertEqual((doc["pricing"], doc["model_calls_made"]), ("tbd", 0))
        self.assertEqual(doc["deliverable"]["format"], "deck")
        self.assertEqual(self.clients, [])  # no model client was even made
        self.assertEqual(self.hire(body()).status_code, 200)

    def test_first_call_is_what_the_hire_actually_sends(self):
        first = self.preflight(body()).get_json()["first_call"]
        self.assertEqual(self.hire(body()).status_code, 200)
        sent = self.clients[0].requests[0]
        self.assertEqual(first["system_characters"], len(sent["system"]))
        self.assertEqual(first["message_characters"], len(sent["messages"][0]["content"]))
        self.assertEqual(sent["tools"][0], consulting.TOOL)
        self.assertEqual(first["tool_definition_characters"],
                         len(json.dumps(consulting.TOOL, ensure_ascii=False, separators=(",", ":"))))

    def test_every_refusal_is_the_hires_refusal(self):
        missing = {k: v for k, v in CLIENT["answers"].items() if k != "consulting.success"}
        cases = [body(role="astrologer"), body(requested_by={"kind": "robot", "ref": "x"}),
                 body(answers={"insurance.file": "x"}), body(problem=""), body(answers=missing),
                 body(budget={"max_model_calls": 3}), body(budget={"max_dollars": 1})]
        for payload in cases:
            with self.subTest(payload=str(payload)[:80]):
                doc = self.preflight(payload).get_json()
                error = self.hire(payload).get_json()["error"]
                self.assertFalse(doc["ready"])
                self.assertIsNone(doc["first_call"])
                if error["code"] == "refused":
                    self.assertEqual(doc["problems"], [error["message"]])
                elif error["code"] == "bad_budget":
                    self.assertEqual(doc["problems"], error["problems"])
                else:
                    self.assertEqual(error["code"], "not_accepted")
                    self.assertEqual(doc["open_questions"], error["open_questions"])
                    self.assertIn("consulting.success", doc["open_questions"])
                    self.assertEqual(doc["problems"], error["problems"])
        self.assertEqual(self.clients, [])

    def test_a_bad_budget_and_open_questions_are_reported_together(self):
        missing = {k: v for k, v in CLIENT["answers"].items() if k != "consulting.success"}
        doc = self.preflight(body(answers=missing, budget={"max_model_calls": 3})).get_json()
        self.assertTrue(any("max_model_calls" in p for p in doc["problems"]))
        self.assertIn("consulting.success", doc["open_questions"])
        self.assertIsNone(doc["worst_case"])

    def test_a_bad_budget_is_reported_with_a_bad_role(self):
        doc = self.preflight(body(role="astrologer", budget={"max_model_calls": 3})).get_json()
        self.assertEqual(len(doc["problems"]), 2, doc["problems"])
        self.assertTrue(any("max_model_calls" in p for p in doc["problems"]))
        self.assertEqual(self.hire(body(role="astrologer", budget={"max_model_calls": 3})).get_json()["error"]["code"],
                         "bad_budget")  # the hire checks the budget first

    def test_it_reports_nothing_but_its_published_fields(self):
        doc = self.preflight(body()).get_json()
        self.assertEqual(set(doc), {"format", "ready", "role", "problems", "open_questions", "budget", "limits",
                                    "worst_case", "deliverable", "first_call", "pricing", "model_calls_made", "note"})
        self.assertEqual(set(doc["first_call"]), {"system_characters", "message_characters", "tool_definition_characters"})
        self.assertTrue(all(isinstance(v, int) for v in doc["first_call"].values()))

    def test_the_default_requester_and_blank_answers_match_the_hire(self):
        no_requester = {k: v for k, v in body().items() if k != "requested_by"}
        self.assertTrue(self.preflight(no_requester).get_json()["ready"])
        receipt = self.hire(no_requester)
        self.assertEqual(receipt.status_code, 200)
        blank = body(answers=dict(CLIENT["answers"], **{"consulting.success": "   "}))
        doc = self.preflight(blank).get_json()
        self.assertFalse(doc["ready"])
        self.assertIn("consulting.success", doc["open_questions"])
        self.assertEqual(self.hire(blank).get_json()["error"]["open_questions"], doc["open_questions"])

    def test_only_preflight_true_selects_it(self):
        response = self.http.post("/api/v2/engagements?preflight=false", json=body())
        self.assertEqual(response.status_code, 401)  # an ordinary hire, which needs the code

    def test_worst_case_follows_the_budget(self):
        doc = self.preflight(body()).get_json()
        self.assertEqual(doc["worst_case"], {"model_calls": 2, "output_tokens": 2 * consulting.MAX_TOKENS})
        self.assertEqual(doc["limits"], receipts.LIMITS)
        doc = self.preflight(body(budget={"max_model_calls": 1, "max_output_tokens_per_call": 5000})).get_json()
        self.assertEqual(doc["worst_case"], {"model_calls": 1, "output_tokens": 5000})
        self.assertEqual(doc["budget"], {"max_model_calls": 1, "max_output_tokens_per_call": 5000})

    def test_each_role_names_its_deliverable(self):
        case = ROOT / "fixtures" / "roles" / "finance-modeling"
        client = json.loads((case / "client.json").read_text())
        doc = self.preflight({"role": client["roles"][0], "problem": client["problem"],
                              "answers": dict(client["answers"]), "requested_by": client["requested_by"]}).get_json()
        self.assertTrue(doc["ready"], doc["problems"])
        self.assertEqual(doc["deliverable"]["extension"], "xlsx")

    def test_the_vercel_route_reaches_the_same_preflight(self):
        routed = self.preflight(body(), path="/api/v2/engagements?preflight=true").get_json()
        direct = self.preflight(body()).get_json()
        self.assertEqual(routed, direct)
        rewrites = json.loads((ROOT / "vercel.json").read_text())["rewrites"]
        self.assertIn({"source": "/api/v2/engagements/preflight",
                       "destination": "/api/v2/engagements?preflight=true"}, rewrites)
        self.assertEqual(self.clients, [])

    def test_malformed_and_oversized_requests_are_refused(self):
        self.assertEqual(self.http.post("/api/v2/engagements/preflight", data="not json").status_code, 400)
        self.assertEqual(self.preflight(body(answers=["x"])).status_code, 400)
        self.assertEqual(self.preflight(["a"]).status_code, 400)
        self.assertEqual(self.preflight(body(problem="x" * 70000)).status_code, 413)

    def test_it_is_rate_limited(self):
        limited = lambda: (jsonify(error="too many requests"), 429)  # noqa: E731
        with patch.object(v2, "_rate_limit", limited), app.test_request_context():
            self.assertEqual(self.preflight(body()).status_code, 429)
            self.assertEqual(self.preflight(body(), path="/api/v2/engagements?preflight=true").status_code, 429)


class PreflightDocsTest(unittest.TestCase):
    def test_it_is_documented_where_agents_look(self):
        guide = (ROOT / "docs" / "hiring-api.md").read_text(encoding="utf-8")
        self.assertIn("POST /api/v2/engagements/preflight", guide)
        self.assertIn('"format": "analystos-preflight/1"', guide)
        llms = (ROOT / "site" / "llms.txt").read_text(encoding="utf-8")
        self.assertIn("POST https://analystos.dev/api/v2/engagements/preflight", llms)
        glossary = (ROOT / "site" / "glossary.html").read_text(encoding="utf-8")
        self.assertIn('<div class="g-term" id="preflight">', glossary)


if __name__ == "__main__":
    unittest.main()
