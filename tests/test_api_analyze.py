"""Tests for the /api/analyze endpoint - one per "Done when" in specs/slice-20/spec.md.

Uses Flask's own test client, which drives the real Flask ``app`` object
through a real HTTP-shaped request/response (multipart upload included) with
no server process and no network - the same thing a live deployment runs,
minus Vercel's own infrastructure, which can only be verified by deploying.
"""

import glob
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from api.analyze import _ACCESS_CODE_ENV_VAR, app

_TEST_ACCESS_CODE = "test-access-code"


def _csv_bytes(text):
    return io.BytesIO(text.encode("utf-8"))


class AnalyzeEndpointTest(unittest.TestCase):
    """Access gating itself (Slice 22) is covered by test_api_access.py - every
    request here carries the correct code so these tests keep verifying the
    Slice 20 pipeline behavior the gating check now sits in front of."""

    def setUp(self):
        self.client = app.test_client()
        os.environ[_ACCESS_CODE_ENV_VAR] = _TEST_ACCESS_CODE

    def tearDown(self):
        os.environ.pop(_ACCESS_CODE_ENV_VAR, None)

    def _post(self, data):
        return self.client.post(
            "/api/analyze",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Access-Code": _TEST_ACCESS_CODE},
        )

    def test_well_formed_upload_returns_a_cited_report(self):  # Done when #1
        data = {
            "file": (_csv_bytes("period,revenue\nFY2023,26974\nFY2024,60922\n"), "data.csv"),
            "schema": json.dumps({"period": "text", "revenue": "number"}),
            "template": "income_statement",
            "currency_unit": "actual",
        }
        resp = self._post(data)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("FY2024 revenue was $60.9K.", body["section"])
        self.assertIn("<!doctype html>", body["html"])
        self.assertIn("computed from:", body["section"])  # the growth ask ran too

    def test_missing_file_is_a_clean_400(self):  # Done when #2
        resp = self._post({"schema": json.dumps({"period": "text"})})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("file", resp.get_json()["error"])

    def test_unsupported_file_type_is_a_clean_400(self):  # Done when #3
        data = {
            "file": (io.BytesIO(b"hello"), "data.txt"),
            "schema": json.dumps({"period": "text"}),
        }
        resp = self._post(data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(".txt", resp.get_json()["error"])

    def test_pdf_is_still_rejected(self):  # Slice 23: not wired into the API yet, on purpose
        data = {
            "file": (io.BytesIO(b"%PDF-1.4 not a real pdf"), "data.pdf"),
            "schema": json.dumps({"period": "text"}),
        }
        resp = self._post(data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(".pdf", resp.get_json()["error"])

    def test_missing_schema_is_a_clean_400(self):  # Done when #4
        data = {"file": (_csv_bytes("period\nFY2024\n"), "data.csv")}
        resp = self._post(data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("schema", resp.get_json()["error"])

    def test_invalid_schema_json_is_a_clean_400(self):  # Done when #4
        data = {
            "file": (_csv_bytes("period\nFY2024\n"), "data.csv"),
            "schema": "not json",
        }
        resp = self._post(data)
        self.assertEqual(resp.status_code, 400)

    def test_a_pipeline_error_becomes_a_400_not_a_500(self):  # Done when #5
        # "revenue" column doesn't exist in the CSV - extract_table raises
        data = {
            "file": (_csv_bytes("period\nFY2024\n"), "data.csv"),
            "schema": json.dumps({"period": "text", "revenue": "number"}),
            "template": "income_statement",
        }
        resp = self._post(data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("revenue", resp.get_json()["error"])

    def test_nothing_persists_after_the_request(self):  # Done when #6
        before = set(glob.glob(str(Path(tempfile.gettempdir()) / "analystos-*")))
        data = {
            "file": (_csv_bytes("period,revenue\nFY2024,100\n"), "data.csv"),
            "schema": json.dumps({"period": "text", "revenue": "number"}),
            "template": "income_statement",
        }
        resp = self._post(data)
        self.assertEqual(resp.status_code, 200)
        after = set(glob.glob(str(Path(tempfile.gettempdir()) / "analystos-*")))
        self.assertEqual(after - before, set())  # no new temp dir left behind

    def test_nothing_persists_even_when_the_request_fails(self):  # Done when #6
        before = set(glob.glob(str(Path(tempfile.gettempdir()) / "analystos-*")))
        data = {
            "file": (_csv_bytes("period\nFY2024\n"), "data.csv"),
            "schema": json.dumps({"period": "text", "revenue": "number"}),
            "template": "income_statement",
        }
        self._post(data)
        after = set(glob.glob(str(Path(tempfile.gettempdir()) / "analystos-*")))
        self.assertEqual(after - before, set())


if __name__ == "__main__":
    unittest.main()
