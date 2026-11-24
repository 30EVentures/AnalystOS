"""Slice 118 - /api/v2: the public catalog, and hiring a role for one engagement.

Every model call here is a ReplayClient replaying a worked example; no test can
reach the paid API (the blueprint's client factory is replaced for every test)."""

import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from pptx import Presentation

from analystos.api_v2 import blueprint as v2
from analystos.packs.replay import ReplayClient
from api.analyze import app
from tests.isolation import reset_rate_limits

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "fixtures" / "consulting" / "churn-clinics"
CLIENT = json.loads((CASE / "client.json").read_text())
RESPONSE = json.loads((CASE / "response.json").read_text())
CODE = "test-access-code"


def body(**changes):
    out = {"role": CLIENT["roles"][0], "problem": CLIENT["problem"], "answers": dict(CLIENT["answers"]),
           "requested_by": CLIENT["requested_by"]}
    out.update(changes)
    return out


class ApiV2Test(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {"ANALYSTOS_ACCESS_CODE": CODE})
        patcher.start()
        self.addCleanup(patcher.stop)
        reset_rate_limits(self)
        self.replays = []

        def factory():
            replay = ReplayClient(list(self.responses))
            self.replays.append(replay)
            return replay

        self.responses = [RESPONSE]
        original = v2.client_factory
        v2.client_factory = factory
        self.addCleanup(lambda: setattr(v2, "client_factory", original))
        self.client = app.test_client()

    def post(self, payload, code=CODE, query=""):
        headers = {"X-Access-Code": code} if code is not None else {}
        return self.client.post("/api/v2/engagements" + query, json=payload, headers=headers)

    def test_the_catalog_is_public_and_complete(self):
        response = self.client.get("/api/v2/catalog")
        self.assertEqual(response.status_code, 200)
        doc = response.get_json()
        self.assertEqual(doc["format"], "analystos-v2-catalog/1")
        self.assertEqual(len(doc["roles"]), 73)
        self.assertIn("to be determined", doc["pricing"])
        for role in doc["roles"]:
            self.assertEqual(role["pricing"], "tbd")
            self.assertIn(role["tested"], ("mock", "mock-family"))
            self.assertTrue(any(q["id"] == "common.decision" for q in role["questions"]))
        tested = {r["id"]: r["tested"] for r in doc["roles"]}
        self.assertEqual(tested["management-consulting-analyst"], "mock")
        self.assertEqual(tested["financial-equity-research-analyst"], "mock-family")
        self.assertEqual(sum(v == "mock" for v in tested.values()), 23)  # Slice 127: 10 work examples

    def test_hiring_returns_a_verified_deck(self):
        response = self.post(body())
        self.assertEqual(response.status_code, 200, response.get_data()[:300])
        self.assertEqual(response.mimetype, v2.PPTX)
        self.assertRegex(response.headers["X-AnalystOS-Spec-Sha256"], r"^[0-9a-f]{64}$")
        prs = Presentation(io.BytesIO(response.get_data()))
        self.assertGreaterEqual(len(prs.slides), 12)
        self.assertEqual(len(self.replays[0].requests), 1)

    def test_each_role_gets_its_family_format(self):  # Slice 124
        from docx import Document
        from openpyxl import load_workbook
        for family, mime, opener in (("legal-contracts-procurement", "wordprocessingml", Document),
                                     ("finance-modeling", "spreadsheetml", load_workbook)):
            case = ROOT / "fixtures" / "roles" / family
            client = json.loads((case / "client.json").read_text())
            self.responses = [json.loads((case / "response.json").read_text())]
            with self.subTest(family=family):
                response = self.post({"role": client["roles"][0], "problem": client["problem"],
                                      "answers": dict(client["answers"]), "requested_by": client["requested_by"]})
                self.assertEqual(response.status_code, 200, response.get_data()[:300])
                self.assertIn(mime, response.mimetype)
                self.assertEqual(response.headers["X-AnalystOS-Format"], "memo" if family.startswith("legal") else "workbook")
                self.assertIn(".docx" if family.startswith("legal") else ".xlsx", response.headers["Content-Disposition"])
                opener(io.BytesIO(response.get_data()))
                json_response = self.post({"role": client["roles"][0], "problem": client["problem"],
                                           "answers": dict(client["answers"]), "requested_by": client["requested_by"]},
                                          query="?format=json")
                output = json_response.get_json()["output"]
                self.assertEqual(output["format"], "memo" if family.startswith("legal") else "workbook")
                self.assertNotIn("deck_base64", json_response.get_json())
                opener(io.BytesIO(__import__("base64").b64decode(output["base64"])))

    def test_agents_can_ask_for_the_spec(self):
        response = self.post(body(requested_by={"kind": "agent", "ref": "buyer-agent-7"}), query="?format=json")
        self.assertEqual(response.status_code, 200)
        doc = response.get_json()
        self.assertEqual(doc["engagement"]["requested_by"]["kind"], "agent")
        self.assertEqual(doc["engagement"]["state"], "accepted")
        self.assertEqual(doc["spec"]["role"], "management-consulting-analyst")
        Presentation(io.BytesIO(__import__("base64").b64decode(doc["deck_base64"])))

    def test_the_access_code_is_required(self):
        self.assertEqual(self.post(body(), code=None).status_code, 401)
        self.assertEqual(self.post(body(), code="wrong").status_code, 401)
        with patch.dict(os.environ, {"ANALYSTOS_ACCESS_CODE": ""}):
            self.assertEqual(self.post(body()).status_code, 500)
        self.assertEqual(self.replays, [])  # no model call was even prepared

    def test_unanswered_scoping_questions_are_refused_before_any_call(self):
        answers = {k: v for k, v in CLIENT["answers"].items() if k != "consulting.success"}
        response = self.post(body(answers=answers))
        self.assertEqual(response.status_code, 422)
        self.assertIn("consulting.success", response.get_json()["error"]["open_questions"])
        self.assertEqual(self.replays, [])

    def test_bad_input_is_refused(self):
        cases = ((body(role="astrologer"), 422), (body(problem=""), 422), (body(answers=["x"]), 400),
                 (body(answers={"insurance.file": "x"}), 422), (body(requested_by={"kind": "robot", "ref": "x"}), 422))
        for payload, status in cases:
            with self.subTest(payload=str(payload)[:60]):
                self.assertEqual(self.post(payload).status_code, status)
        self.assertEqual(self.client.post("/api/v2/engagements", data="not json",
                                          headers={"X-Access-Code": CODE}).status_code, 400)
        big = body(problem="x" * 70000)
        self.assertEqual(self.post(big).status_code, 413)
        self.assertEqual(self.replays, [])

    def test_unverifiable_work_is_never_delivered(self):
        bad = dict(RESPONSE, answer="Churn went up to 7% so do retention.")
        self.responses = [bad, bad]
        response = self.post(body())
        self.assertEqual(response.status_code, 502)
        error = response.get_json()["error"]
        self.assertIn("nothing was delivered", error["message"])
        self.assertTrue(error["problems"])  # the full list, so a failure can be diagnosed
        self.assertTrue(any("write numbers only as figure tags" in p for p in error["problems"]))
        self.assertEqual(len(self.replays[0].requests), 2)  # one repair retry, never a third call


if __name__ == "__main__":
    unittest.main()
