"""Slice 133 - metered hiring: a budget that only narrows, measured usage, and a receipt
for every engagement taken on. Every model call is a ReplayClient; no
test can reach the paid API."""

import base64
import hashlib
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from analystos.api_v2 import blueprint as v2
from analystos.api_v2 import receipt as receipts
from analystos.packs import consulting
from analystos.packs.replay import ReplayClient
from api.analyze import app
from tests.isolation import reset_rate_limits
from tests.test_api_v2 import CLIENT, CODE, RESPONSE, body

BAD = dict(RESPONSE, answer="Churn went up to 7% so do retention.")


class _Reporting:
    """A ReplayClient whose replies carry the token counts a real model reports."""

    def __init__(self, responses, usages):
        self.replay = ReplayClient(responses)
        self.requests = self.replay.requests
        self.usages = list(usages)
        self.messages = self

    def create(self, **kwargs):
        reply = self.replay.messages.create(**kwargs)
        reply.usage = SimpleNamespace(**self.usages.pop(0))
        return reply


class MeteredHiringTest(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {"ANALYSTOS_ACCESS_CODE": CODE})
        patcher.start()
        self.addCleanup(patcher.stop)
        reset_rate_limits(self)
        self.clients = []
        self.make = lambda: ReplayClient([RESPONSE])

        def factory():
            client = self.make()
            self.clients.append(client)
            return client

        original = v2.client_factory
        v2.client_factory = factory
        self.addCleanup(lambda: setattr(v2, "client_factory", original))
        self.http = app.test_client()

    def post(self, payload, query=""):
        return self.http.post("/api/v2/engagements" + query, json=payload, headers={"X-Access-Code": CODE})

    # -- the budget only narrows ------------------------------------------------------------

    def test_a_budget_above_the_limits_is_refused_before_any_call(self):
        for budget in ({"max_model_calls": 3}, {"max_output_tokens_per_call": consulting.MAX_TOKENS + 1},
                       {"max_model_calls": 0}, {"max_model_calls": True}, {"max_model_calls": 1.0},
                       {"max_model_calls": "1"}, {"max_dollars": 5}, [1], "cheap"):
            with self.subTest(budget=budget):
                self.clients.clear()
                response = self.post(body(budget=budget))
                self.assertEqual(response.status_code, 422, budget)
                error = response.get_json()["error"]
                self.assertEqual(error["code"], "bad_budget")
                self.assertEqual(error["limits"], {"max_model_calls": 2, "max_output_tokens_per_call": consulting.MAX_TOKENS})
                self.assertEqual(self.clients, [])  # refused before a client was even made

    def test_one_call_means_no_repair(self):
        self.make = lambda: ReplayClient([BAD, RESPONSE])
        response = self.post(body(budget={"max_model_calls": 1}))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(len(self.clients[0].requests), 1)
        error = response.get_json()["error"]
        self.assertIn("the budget allowed no repair attempt (max_model_calls 1)", error["problems"])
        self.assertEqual(error["receipt"]["usage"]["model_calls"], 1)

    def test_the_default_still_allows_exactly_one_repair(self):
        self.make = lambda: ReplayClient([BAD, RESPONSE])
        response = self.post(body(), query="?format=json")
        self.assertEqual(response.status_code, 200, response.get_data()[:300])
        self.assertEqual(len(self.clients[0].requests), 2)
        self.assertEqual(response.get_json()["receipt"]["usage"]["model_calls"], 2)

    def test_the_token_budget_is_what_each_call_asks_for(self):
        self.make = lambda: ReplayClient([BAD, RESPONSE])
        self.post(body(budget={"max_output_tokens_per_call": 6000}))
        self.assertEqual([r["max_tokens"] for r in self.clients[0].requests], [6000, 6000])
        self.clients.clear()
        self.make = lambda: ReplayClient([RESPONSE])
        self.post(body())
        self.assertEqual(self.clients[0].requests[0]["max_tokens"], consulting.MAX_TOKENS)

    def test_the_pipeline_refuses_a_wider_budget_itself(self):
        from analystos.catalog import load_catalog
        from analystos.l3 import engagement as eng
        cat = load_catalog()
        record = eng.new_engagement(engagement_id=eng.new_id(), created="2026-11-26T00:00:00Z",
                                    requested_by=CLIENT["requested_by"], problem=CLIENT["problem"],
                                    roles=CLIENT["roles"][:1], catalog=cat)
        for qid, text in CLIENT["answers"].items():
            record = eng.answer(record, qid, text)
        accepted, problems = eng.accept(record, cat)
        self.assertIsNotNone(accepted, problems)
        consulting.build_deck_spec(accepted, cat, client=ReplayClient([RESPONSE]))  # the same engagement works
        for kwargs in ({"max_model_calls": 3}, {"max_tokens": consulting.MAX_TOKENS + 1}, {"max_model_calls": False},
                       {"max_model_calls": 0}, {"max_tokens": 2.0}):
            replay = ReplayClient([RESPONSE, RESPONSE, RESPONSE])
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, "must be 1 to"):
                    consulting.build_deck_spec(accepted, cat, client=replay, **kwargs)
                self.assertEqual(replay.requests, [])

    # -- usage is measured, never guessed ---------------------------------------------------

    def test_usage_is_what_the_model_reported(self):
        self.make = lambda: _Reporting([BAD, RESPONSE], [{"input_tokens": 5000, "output_tokens": 3100},
                                                          {"input_tokens": 9000, "output_tokens": 3300}])
        usage = self.post(body(), query="?format=json").get_json()["receipt"]["usage"]
        self.assertEqual((usage["model_calls"], usage["input_tokens"], usage["output_tokens"]), (2, 14000, 6400))
        self.assertEqual([c["output_tokens"] for c in usage["calls"]], [3100, 3300])

    def test_cached_input_counts_as_input(self):
        self.make = lambda: _Reporting([RESPONSE], [{"input_tokens": 100, "output_tokens": 3000,
                                                    "cache_creation_input_tokens": 4000, "cache_read_input_tokens": 900}])
        usage = self.post(body(), query="?format=json").get_json()["receipt"]["usage"]
        self.assertEqual(usage["input_tokens"], 5000)
        self.make = lambda: _Reporting([RESPONSE], [{"input_tokens": 100, "output_tokens": 3000,
                                                    "cache_creation_input_tokens": None, "cache_read_input_tokens": None}])
        self.assertEqual(self.post(body(), query="?format=json").get_json()["receipt"]["usage"]["input_tokens"], 100)

    def test_an_unreported_count_makes_the_total_unknown(self):
        self.make = lambda: _Reporting([BAD, RESPONSE], [{"input_tokens": 5000, "output_tokens": 3100},
                                                          {"input_tokens": 9000}])
        usage = self.post(body(), query="?format=json").get_json()["receipt"]["usage"]
        self.assertEqual(usage["input_tokens"], 14000)
        self.assertIsNone(usage["output_tokens"])
        self.make = lambda: ReplayClient([RESPONSE])
        replayed = self.post(body(), query="?format=json").get_json()["receipt"]["usage"]
        self.assertEqual(replayed["model_calls"], 1)
        self.assertIsNone(replayed["input_tokens"])  # a replay reports nothing, so nothing is claimed

    # -- the receipt --------------------------------------------------------------------------

    def test_the_receipt_binds_the_file_that_was_delivered(self):
        response = self.post(body(requested_by={"kind": "agent", "ref": "buyer-agent-7"}))
        self.assertEqual(response.status_code, 200)
        raw = response.headers["X-AnalystOS-Receipt"]
        receipt = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        self.assertEqual(receipt["format"], "analystos-receipt/1")
        self.assertEqual(receipt["outcome"], "delivered")
        self.assertEqual(receipt["output"]["sha256"], hashlib.sha256(response.get_data()).hexdigest())
        self.assertEqual(receipt["output"]["bytes"], len(response.get_data()))
        self.assertEqual(receipt["spec_sha256"], response.headers["X-AnalystOS-Spec-Sha256"])
        self.assertEqual(receipt["engagement_id"], response.headers["X-AnalystOS-Engagement"])
        self.assertEqual(receipt["requested_by"], {"kind": "agent", "ref": "buyer-agent-7"})
        self.assertEqual(response.headers["X-AnalystOS-Receipt-Sha256"], receipts.digest(receipt))
        self.assertEqual((receipt["pricing"], receipt["charged_cents"], receipt["signed"]), ("tbd", 0, False))
        self.assertEqual(receipt["budget"], receipts.LIMITS)

    def test_the_json_receipt_matches_the_base64_output(self):
        doc = self.post(body(budget={"max_output_tokens_per_call": 7000}), query="?format=json").get_json()
        data = base64.b64decode(doc["output"]["base64"])
        self.assertEqual(doc["receipt"]["output"]["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(doc["receipt"]["spec_sha256"], doc["spec_sha256"])
        self.assertEqual(doc["receipt_sha256"], receipts.digest(doc["receipt"]))
        self.assertEqual(doc["receipt"]["budget"]["max_output_tokens_per_call"], 7000)

    def test_the_digest_keeps_non_ascii_as_utf8(self):
        doc = self.post(body(requested_by={"kind": "agent", "ref": "achats-équipe"}), query="?format=json").get_json()
        canonical = receipts.canonical(doc["receipt"])
        self.assertIn("achats-équipe".encode("utf-8"), canonical)
        self.assertNotIn(b"\\u00e9", canonical)
        self.assertEqual(doc["receipt_sha256"], hashlib.sha256(canonical).hexdigest())
        self.assertNotEqual(doc["receipt_sha256"], hashlib.sha256(
            json.dumps(doc["receipt"], sort_keys=True, separators=(",", ":")).encode()).hexdigest())

    def test_failures_get_a_receipt_with_no_output(self):
        self.make = lambda: ReplayClient([BAD, BAD])
        error = self.post(body()).get_json()["error"]
        self.assertEqual(error["receipt"]["outcome"], "not_verified")
        self.assertIsNone(error["receipt"]["output"])
        self.assertEqual(error["receipt"]["usage"]["model_calls"], 2)
        self.assertEqual(error["receipt_sha256"], receipts.digest(error["receipt"]))

    def test_a_call_that_failed_after_sending_is_metered_as_unknown(self):
        def failed(*args, **kwargs):
            raise ValueError("analysis is temporarily unavailable - please try again shortly")
        with patch.object(consulting, "_create_message", failed):
            response = self.post(body())
        self.assertEqual(response.status_code, 503)
        receipt = response.get_json()["error"]["receipt"]
        self.assertEqual(receipt["outcome"], "unavailable")
        self.assertEqual(receipt["usage"]["model_calls"], 1)
        self.assertIsNone(receipt["usage"]["input_tokens"])

    def test_a_call_the_spend_ceiling_refuses_is_not_metered(self):
        from analystos.l2 import analyze
        for ceiling, responses, calls in (("0", [RESPONSE], 0), ("1", [BAD, RESPONSE], 1)):
            self.make = lambda responses=responses: ReplayClient(list(responses))
            self.clients.clear()
            with self.subTest(ceiling=ceiling), patch.dict(os.environ, {"ANALYSTOS_MAX_API_CALLS": ceiling}), \
                    patch.object(analyze, "_api_call_count", 0):
                response = self.post(body())
                self.assertEqual(response.status_code, 503)
                receipt = response.get_json()["error"]["receipt"]
                self.assertEqual(receipt["usage"]["model_calls"], calls)
                self.assertEqual(len(self.clients[0].requests), calls)  # what was metered is what was sent

    def test_an_unaccepted_engagement_makes_no_call_and_no_receipt(self):
        response = self.post(body(answers={}))
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("receipt", response.get_json()["error"])
        self.assertEqual(self.clients, [])

    def test_a_receipt_names_an_output_exactly_when_delivered(self):
        record = {"id": "e1", "roles": ["r"], "created": "2026-11-26T00:00:00Z"}
        with self.assertRaises(ValueError):
            receipts.build(record, "not_verified", receipts.LIMITS, [], "t", output=b"x",
                           fmt={"name": "deck", "media_type": "m"})
        with self.assertRaises(ValueError):
            receipts.build(record, "delivered", receipts.LIMITS, [], "t")
        with self.assertRaises(ValueError):
            receipts.build(record, "charged", receipts.LIMITS, [], "t")


class HiringDocsTest(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self.root = Path(__file__).resolve().parents[1]
        self.guide = (self.root / "docs" / "hiring-api.md").read_text(encoding="utf-8")

    def test_the_guide_states_the_real_limits_and_is_served(self):
        self.assertIn(f"| `max_model_calls` | {consulting.MAX_MODEL_CALLS} |", self.guide)
        self.assertIn(f"| `max_output_tokens_per_call` | {consulting.MAX_TOKENS} |", self.guide)
        self.assertIn("**Receipts are not signed yet**", self.guide)
        self.assertIn("Price: to be determined.", self.guide)
        self.assertEqual((self.root / "site" / "docs" / "hiring-api.md").read_text(encoding="utf-8"), self.guide)
        llms = (self.root / "site" / "llms.txt").read_text(encoding="utf-8")
        self.assertIn("https://analystos.dev/docs/hiring-api.md", llms)
        self.assertIn(f"({consulting.MAX_MODEL_CALLS} model calls, {consulting.MAX_TOKENS} output tokens per call)", llms)

    def test_the_guide_names_every_receipt_field(self):
        record = {"id": "e1", "roles": ["r"], "created": "t"}
        for field in receipts.build(record, "not_verified", receipts.LIMITS, [], "t"):
            self.assertIn(f'"{field}"', self.guide)

    def test_agents_and_readers_can_find_it(self):
        import sys
        sys.path.insert(0, str(self.root / "tools"))
        import studio_chrome
        self.assertIn('href="/docs/hiring-api.md"', studio_chrome.render_nav())
        glossary = (self.root / "site" / "glossary.html").read_text(encoding="utf-8")
        for term in ("budget", "receipt"):
            self.assertIn(f'<div class="g-term" id="{term}">', glossary)


if __name__ == "__main__":
    unittest.main()
