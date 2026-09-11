"""Tests for the per-IP rate limiter in front of /api/analyze and
/api/extract - specs/slice-41/spec.md. Defense in depth on top of the
existing access-code gate (Slice 22), which explicitly deferred this.
Uses Flask's own test client, same approach as test_api_access.py.
"""

import io
import json
import os
import unittest

from api.analyze import (
    _ACCESS_CODE_ENV_VAR,
    _RATE_LIMIT_MAX_ENV_VAR,
    _RATE_LIMIT_WINDOW_ENV_VAR,
    _rate_limit_buckets,
    app,
)

_REAL_CODE = "correct-code"
_ENV_VARS = (_ACCESS_CODE_ENV_VAR, _RATE_LIMIT_MAX_ENV_VAR, _RATE_LIMIT_WINDOW_ENV_VAR)


def _valid_form():
    # Explicit template: no real API call needed, keeping these tests fast
    # and offline - same reasoning as test_api_access.py.
    return {
        "file": (io.BytesIO(b"period,revenue\nFY2024,100\n"), "data.csv"),
        "schema": json.dumps({"period": "text", "revenue": "number"}),
        "template": "income_statement",
    }


class RateLimitTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self._env_backup = {k: os.environ.get(k) for k in _ENV_VARS}
        os.environ[_ACCESS_CODE_ENV_VAR] = _REAL_CODE
        # Isolate from any other test file's requests against the same
        # module-level buckets - state persists for the life of the test
        # process, not just this TestCase.
        _rate_limit_buckets.clear()

    def tearDown(self):
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _rate_limit_buckets.clear()

    def test_exceeding_the_limit_returns_a_clean_429_not_a_500(self):  # Done when #1
        os.environ[_RATE_LIMIT_MAX_ENV_VAR] = "2"
        os.environ[_RATE_LIMIT_WINDOW_ENV_VAR] = "60"
        for _ in range(2):
            resp = self.client.post(
                "/api/analyze", data=_valid_form(), content_type="multipart/form-data",
                headers={"X-Access-Code": _REAL_CODE},
            )
            self.assertEqual(resp.status_code, 200)  # still within budget

        resp = self.client.post(
            "/api/analyze", data=_valid_form(), content_type="multipart/form-data",
            headers={"X-Access-Code": _REAL_CODE},
        )
        self.assertEqual(resp.status_code, 429)
        self.assertNotEqual(resp.status_code, 500)
        self.assertIn("too many requests", resp.get_json()["error"].lower())

    def test_normal_usage_under_the_limit_is_unaffected(self):  # Done when #3
        os.environ[_RATE_LIMIT_MAX_ENV_VAR] = "5"
        os.environ[_RATE_LIMIT_WINDOW_ENV_VAR] = "60"
        for _ in range(5):
            resp = self.client.post(
                "/api/analyze", data=_valid_form(), content_type="multipart/form-data",
                headers={"X-Access-Code": _REAL_CODE},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertIn("FY2024 revenue was $100.", resp.get_json()["section"])

    def test_the_limit_is_configurable_via_env_var(self):  # Done when #2
        os.environ[_RATE_LIMIT_MAX_ENV_VAR] = "1"
        os.environ[_RATE_LIMIT_WINDOW_ENV_VAR] = "60"
        resp = self.client.post(
            "/api/analyze", data=_valid_form(), content_type="multipart/form-data",
            headers={"X-Access-Code": _REAL_CODE},
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(
            "/api/analyze", data=_valid_form(), content_type="multipart/form-data",
            headers={"X-Access-Code": _REAL_CODE},
        )
        self.assertEqual(resp.status_code, 429)

        # Raise the ceiling and confirm it actually takes effect, not just
        # the default - proves the env var is really read, not ignored.
        os.environ[_RATE_LIMIT_MAX_ENV_VAR] = "100"
        _rate_limit_buckets.clear()
        resp = self.client.post(
            "/api/analyze", data=_valid_form(), content_type="multipart/form-data",
            headers={"X-Access-Code": _REAL_CODE},
        )
        self.assertEqual(resp.status_code, 200)

    def test_a_wrong_code_still_counts_toward_the_same_budget(self):
        # The actual point of gating this endpoint: brute-forcing the
        # shared code must also be throttled, not just successful use.
        os.environ[_RATE_LIMIT_MAX_ENV_VAR] = "2"
        os.environ[_RATE_LIMIT_WINDOW_ENV_VAR] = "60"
        for _ in range(2):
            resp = self.client.post(
                "/api/analyze", data=_valid_form(), content_type="multipart/form-data",
                headers={"X-Access-Code": "guess"},
            )
            self.assertEqual(resp.status_code, 401)

        resp = self.client.post(
            "/api/analyze", data=_valid_form(), content_type="multipart/form-data",
            headers={"X-Access-Code": "guess"},
        )
        self.assertEqual(resp.status_code, 429)

    def test_the_rate_limiter_also_covers_api_extract(self):
        os.environ[_RATE_LIMIT_MAX_ENV_VAR] = "1"
        os.environ[_RATE_LIMIT_WINDOW_ENV_VAR] = "60"
        resp = self.client.post(
            "/api/extract", data=_valid_form(), content_type="multipart/form-data",
            headers={"X-Access-Code": _REAL_CODE},
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(
            "/api/extract", data=_valid_form(), content_type="multipart/form-data",
            headers={"X-Access-Code": _REAL_CODE},
        )
        self.assertEqual(resp.status_code, 429)

    def test_default_limit_is_generous_enough_for_normal_test_traffic(self):
        # No env var override - the shipped default must not itself be so
        # tight that ordinary use (or the rest of this suite) trips it.
        for _ in range(10):
            resp = self.client.post(
                "/api/analyze", data=_valid_form(), content_type="multipart/form-data",
                headers={"X-Access-Code": _REAL_CODE},
            )
            self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
