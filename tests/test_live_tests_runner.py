"""Tests for live_tests/run_live_tests.py's own logic - cost tracking,
price table, and the hard ceiling - specs/slice-51/spec.md, Done when #2
and #3. Entirely mocked: no real API call, no cost, no network
dependency, exactly like every other test in tests/. This file proves
the runner's logic is correct BEFORE it is ever pointed at the real
API - the real-API proof itself (Done when #4) is a live run, not
something a mocked test can substitute for.
"""

import unittest
from types import SimpleNamespace

from live_tests.run_live_tests import (
    DEGRADED, DOCUMENTS, FAIL, PASS, BudgetExceeded, CostTrackingClient, _price, evaluate, exit_status,
)


def _usage_response(input_tokens, output_tokens):
    return SimpleNamespace(usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens))


class PriceTableTest(unittest.TestCase):
    def test_a_known_model_prices_input_and_output_tokens_correctly(self):
        cost = _price("claude-sonnet-5", 1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 2.00 + 10.00)

    def test_zero_tokens_costs_nothing(self):
        self.assertEqual(_price("claude-sonnet-5", 0, 0), 0.0)

    def test_an_unrecognized_model_raises_rather_than_silently_undercounting(self):
        with self.assertRaises(ValueError) as cm:
            _price("some-future-model", 1000, 1000)
        self.assertIn("some-future-model", str(cm.exception))


class CostTrackingClientTest(unittest.TestCase):
    def test_a_call_records_real_usage_and_computes_real_cost(self):
        real = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: _usage_response(1000, 500)))
        client = CostTrackingClient(real, ceiling_dollars=1.0)

        client.messages.create(model="claude-sonnet-5")

        self.assertEqual(len(client.calls), 1)
        expected = (1000 / 1_000_000) * 2.00 + (500 / 1_000_000) * 10.00
        self.assertAlmostEqual(client.total_cost, expected)
        self.assertAlmostEqual(client.calls[0]["cost"], expected)
        self.assertEqual(client.calls[0]["input_tokens"], 1000)
        self.assertEqual(client.calls[0]["output_tokens"], 500)

    def test_cost_accumulates_across_multiple_calls(self):
        real = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: _usage_response(100_000, 0)))
        client = CostTrackingClient(real, ceiling_dollars=1.0)

        client.messages.create(model="claude-sonnet-5")
        client.messages.create(model="claude-sonnet-5")

        self.assertEqual(len(client.calls), 2)
        self.assertAlmostEqual(client.total_cost, 2 * (100_000 / 1_000_000) * 2.00)

    def test_once_the_ceiling_is_reached_the_next_call_is_refused_before_dispatch(self):
        dispatched = []
        real = SimpleNamespace(messages=SimpleNamespace(
            create=lambda **kw: dispatched.append(1) or _usage_response(1_000_000, 0)
        ))
        client = CostTrackingClient(real, ceiling_dollars=1.0)

        client.messages.create(model="claude-sonnet-5")  # costs $2.00 - ceiling now exceeded
        self.assertEqual(len(dispatched), 1)

        with self.assertRaises(BudgetExceeded):
            client.messages.create(model="claude-sonnet-5")
        # the refused call must never have reached the real client at all
        self.assertEqual(len(dispatched), 1)

    def test_a_run_that_never_reaches_the_ceiling_is_never_refused(self):
        real = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: _usage_response(1000, 500)))
        client = CostTrackingClient(real, ceiling_dollars=1.0)
        for _ in range(5):
            client.messages.create(model="claude-sonnet-5")
        self.assertEqual(len(client.calls), 5)

DOC = "Revenue was $498.0 million. Net income was $22.4 million, then $19.6 million."
SEGS = [
    {"type": "quote", "label": "Revenue", "value": 498000000.0, "format": "usd", "citation": "$498.0 million"},
    {"type": "quote", "label": "NI", "value": 22400000.0, "format": "usd", "citation": "$22.4 million"},
    {"type": "quote", "label": "NI2", "value": 19600000.0, "format": "usd", "citation": "$19.6 million"},
]


def _trace(tier="written", segments=None, verified=None, reason=None, text=DOC):
    segments = SEGS if segments is None else segments
    return {"tier": tier, "segments": segments, "report": None if tier == "plain" else {"title": "T", "executive_summary": [{"text": "See {{0}}."}]},
            "document_text": text, "source_hash": "c" * 64, "fallback_reason": reason,
            "analysis": {"proposed": len(segments), "verified": len(segments) if verified is None else verified, "dropped": 0}}


class EvaluateTest(unittest.TestCase):  # Slice 67
    WRITTEN = {"tier": "written", "min_verified": 3}

    def test_a_good_written_run_passes(self):
        outcome, detail = evaluate(self.WRITTEN, _trace())
        self.assertEqual(outcome, PASS, detail)

    def test_a_fallback_is_degraded_not_a_pass(self):
        for tier in ("deterministic", "plain"):
            with self.subTest(tier=tier):
                outcome, detail = evaluate(self.WRITTEN, _trace(tier=tier, reason="Gate 2 did not pass"))
                self.assertEqual(outcome, DEGRADED)
                self.assertIn("Gate 2 did not pass", detail)

    def test_too_few_verified_facts_fails_even_at_the_right_tier(self):
        outcome, detail = evaluate({"tier": "written", "min_verified": 4}, _trace())
        self.assertEqual(outcome, FAIL)
        self.assertIn("3 verified", detail)

    def test_a_seal_that_does_not_verify_fails(self):
        bad = [dict(SEGS[0], value=999.0)] + SEGS[1:]
        outcome, detail = evaluate(self.WRITTEN, _trace(segments=bad))
        self.assertEqual(outcome, FAIL)
        self.assertIn("values_match_citations", detail)

    def test_a_citation_that_is_not_in_the_document_text_fails(self):
        outcome, detail = evaluate(self.WRITTEN, _trace(text="Something else entirely."))
        self.assertEqual(outcome, FAIL)
        self.assertIn("citations_in_text", detail)

    def test_no_trace_and_no_facts_fail(self):
        self.assertEqual(evaluate(self.WRITTEN, {})[0], FAIL)
        self.assertEqual(evaluate({"tier": "written", "min_verified": 0}, _trace(segments=[], verified=0))[0], FAIL)

    def test_the_table_path_expects_the_table_tier_and_no_seal(self):
        self.assertEqual(evaluate({"tier": "table", "min_verified": 0}, {"tier": "table", "segments": []})[0], PASS)
        self.assertEqual(evaluate({"tier": "table", "min_verified": 0}, _trace())[0], FAIL)

    def test_every_document_declares_a_gradeable_expectation(self):
        for doc in DOCUMENTS:
            with self.subTest(doc=doc["name"]):
                self.assertIn(doc["expect"]["tier"], ("table", "written"))
                self.assertGreaterEqual(doc["expect"]["min_verified"], 0)
        self.assertEqual([d["expect"]["tier"] for d in DOCUMENTS].count("table"), 1)


class ExitStatusTest(unittest.TestCase):  # Slice 67
    def test_exit_codes(self):
        ok = [("a", PASS)]
        self.assertEqual(exit_status(ok, False), 0)
        self.assertEqual(exit_status([("a", PASS), ("b", DEGRADED)], False), 0)
        self.assertEqual(exit_status([("a", PASS), ("b", DEGRADED)], False, strict=True), 1)
        self.assertEqual(exit_status([("a", FAIL)], False), 1)
        self.assertEqual(exit_status(ok, True), 1)


if __name__ == "__main__":
    unittest.main()
