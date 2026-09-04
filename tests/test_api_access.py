"""Tests for /api/analyze's access gating - one per "Done when" in
specs/slice-22/spec.md. Uses Flask's own test client, same approach as
test_api_analyze.py.
"""

import io
import json
import os
import unittest

from api.analyze import _ACCESS_CODE_ENV_VAR, app

_REAL_CODE = "correct-code"


def _valid_form():
    return {
        "file": (io.BytesIO(b"period,revenue\nFY2024,100\n"), "data.csv"),
        "schema": json.dumps({"period": "text", "revenue": "number"}),
    }


class AccessGatingTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self._had_env = _ACCESS_CODE_ENV_VAR in os.environ
        self._prior_value = os.environ.get(_ACCESS_CODE_ENV_VAR)

    def tearDown(self):
        if self._had_env:
            os.environ[_ACCESS_CODE_ENV_VAR] = self._prior_value
        else:
            os.environ.pop(_ACCESS_CODE_ENV_VAR, None)

    def test_no_header_is_a_clean_401(self):  # Done when #1
        os.environ[_ACCESS_CODE_ENV_VAR] = _REAL_CODE
        resp = self.client.post(
            "/api/analyze", data=_valid_form(), content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 401)
        self.assertIn("access code", resp.get_json()["error"])

    def test_wrong_code_is_a_clean_401(self):  # Done when #1
        os.environ[_ACCESS_CODE_ENV_VAR] = _REAL_CODE
        resp = self.client.post(
            "/api/analyze",
            data=_valid_form(),
            content_type="multipart/form-data",
            headers={"X-Access-Code": "not-it"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertIn("access code", resp.get_json()["error"])

    def test_wrong_code_never_touches_the_file(self):  # Done when #1
        # An unsupported extension would normally be a 400 - if gating ran
        # after the file check, this would leak that instead of a 401.
        os.environ[_ACCESS_CODE_ENV_VAR] = _REAL_CODE
        resp = self.client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(b"x"), "data.txt")},
            content_type="multipart/form-data",
            headers={"X-Access-Code": "not-it"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_correct_code_proceeds_normally(self):  # Done when #2
        os.environ[_ACCESS_CODE_ENV_VAR] = _REAL_CODE
        resp = self.client.post(
            "/api/analyze",
            data=_valid_form(),
            content_type="multipart/form-data",
            headers={"X-Access-Code": _REAL_CODE},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("FY2024 revenue was $100.", resp.get_json()["section"])

    def test_unset_env_var_fails_closed(self):  # Done when #3
        os.environ.pop(_ACCESS_CODE_ENV_VAR, None)
        resp = self.client.post(
            "/api/analyze",
            data=_valid_form(),
            content_type="multipart/form-data",
            headers={"X-Access-Code": "anything"},
        )
        self.assertEqual(resp.status_code, 500)
        self.assertIn("not configured", resp.get_json()["error"])

    def test_error_never_echoes_the_supplied_code(self):  # Done when #4
        os.environ[_ACCESS_CODE_ENV_VAR] = _REAL_CODE
        secret_guess = "super-secret-guess-12345"
        resp = self.client.post(
            "/api/analyze",
            data=_valid_form(),
            content_type="multipart/form-data",
            headers={"X-Access-Code": secret_guess},
        )
        self.assertNotIn(secret_guess, resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
