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

from live_tests.run_live_tests import BudgetExceeded, CostTrackingClient, _price


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


if __name__ == "__main__":
    unittest.main()
