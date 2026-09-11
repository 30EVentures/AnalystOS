"""Tests for the in-code spend safety net in _create_message -
specs/slice-42/spec.md. A second, in-code hard-stop ceiling alongside the
existing account-level Anthropic spend cap (docs/decisions.md, 2026-09-05).
Uses a mocked Anthropic client throughout: no real API call, no cost.
"""

import os
import unittest
from types import SimpleNamespace

from analystos.l2 import analyze
from analystos.l2.analyze import _MAX_API_CALLS_ENV_VAR, _create_message


def _counting_client(segments=None):
    """A minimal stand-in for anthropic.Anthropic() that also records how
    many times .messages.create was actually invoked - proving a blocked
    call never reached it, not just that it raised."""
    calls = {"n": 0}

    def _create(**kwargs):
        calls["n"] += 1
        tool_use_block = SimpleNamespace(type="tool_use", input={"segments": segments or []})
        return SimpleNamespace(content=[tool_use_block], stop_reason="tool_use")

    client = SimpleNamespace(messages=SimpleNamespace(create=_create))
    return client, calls


class SpendBudgetTest(unittest.TestCase):
    def setUp(self):
        self._env_backup = os.environ.get(_MAX_API_CALLS_ENV_VAR)
        os.environ.pop(_MAX_API_CALLS_ENV_VAR, None)
        # Isolate from any other test file's calls through the same shared
        # choke point - the counter is process-lifetime, not per-test.
        analyze._api_call_count = 0

    def tearDown(self):
        if self._env_backup is None:
            os.environ.pop(_MAX_API_CALLS_ENV_VAR, None)
        else:
            os.environ[_MAX_API_CALLS_ENV_VAR] = self._env_backup
        analyze._api_call_count = 0

    def test_once_the_ceiling_is_exceeded_the_next_call_never_reaches_the_client(self):  # Done when #1
        os.environ[_MAX_API_CALLS_ENV_VAR] = "2"
        client, calls = _counting_client()
        _create_message(client, model="x", max_tokens=1, messages=[])
        _create_message(client, model="x", max_tokens=1, messages=[])
        self.assertEqual(calls["n"], 2)  # both within budget

        with self.assertRaises(ValueError) as cm:
            _create_message(client, model="x", max_tokens=1, messages=[])
        self.assertIn("temporarily unavailable", str(cm.exception))
        # the real proof: the mock's create() was never invoked a 3rd time -
        # the block happened before any API call was made, not after a
        # failed one.
        self.assertEqual(calls["n"], 2)

    def test_the_ceiling_is_configurable_via_env_var(self):  # Done when #2
        os.environ[_MAX_API_CALLS_ENV_VAR] = "1"
        client, calls = _counting_client()
        _create_message(client, model="x", max_tokens=1, messages=[])
        with self.assertRaises(ValueError):
            _create_message(client, model="x", max_tokens=1, messages=[])
        self.assertEqual(calls["n"], 1)

        # Raise the ceiling and confirm the new value actually takes
        # effect - proves the env var is really read, not a fixed internal
        # default.
        os.environ[_MAX_API_CALLS_ENV_VAR] = "5"
        _create_message(client, model="x", max_tokens=1, messages=[])
        self.assertEqual(calls["n"], 2)

    def test_a_call_under_the_ceiling_is_completely_unaffected(self):  # Done when #3
        os.environ[_MAX_API_CALLS_ENV_VAR] = "100"
        client, calls = _counting_client()
        response = _create_message(client, model="x", max_tokens=1, messages=[])
        self.assertEqual(calls["n"], 1)
        self.assertIsNotNone(response)

    def test_unset_env_var_means_no_internal_ceiling(self):
        # A second layer on top of the account-level cap, not a
        # replacement forced on everyone by default.
        os.environ.pop(_MAX_API_CALLS_ENV_VAR, None)
        client, calls = _counting_client()
        for _ in range(50):
            _create_message(client, model="x", max_tokens=1, messages=[])
        self.assertEqual(calls["n"], 50)

    def test_an_unparseable_env_var_falls_back_to_no_ceiling_not_a_crash(self):
        os.environ[_MAX_API_CALLS_ENV_VAR] = "not-a-number"
        client, calls = _counting_client()
        _create_message(client, model="x", max_tokens=1, messages=[])
        self.assertEqual(calls["n"], 1)

    def test_the_error_matches_the_shape_a_real_api_failure_already_produces(self):
        os.environ[_MAX_API_CALLS_ENV_VAR] = "0"
        client, calls = _counting_client()
        with self.assertRaises(ValueError) as cm:
            _create_message(client, model="x", max_tokens=1, messages=[])
        self.assertIn("temporarily unavailable", str(cm.exception))
        self.assertEqual(calls["n"], 0)


if __name__ == "__main__":
    unittest.main()
