"""Tests for the /api/extract preview endpoint - one per "Done when" in
specs/slice-25/spec.md.
"""

import io
import os
import tempfile
import unittest
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from api.analyze import _ACCESS_CODE_ENV_VAR, app

_TEST_ACCESS_CODE = "test-access-code"


def _csv_bytes(text):
    return io.BytesIO(text.encode("utf-8"))


def _make_pdf_bytes(rows):
    buf = io.BytesIO()
    data = [[str(v) for v in row] for row in rows]
    t = Table(data)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(buf, pagesize=letter).build([t])
    buf.seek(0)
    return buf


class ExtractEndpointTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        os.environ[_ACCESS_CODE_ENV_VAR] = _TEST_ACCESS_CODE

    def tearDown(self):
        os.environ.pop(_ACCESS_CODE_ENV_VAR, None)

    def _post(self, data):
        return self.client.post(
            "/api/extract",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Access-Code": _TEST_ACCESS_CODE},
        )

    def test_csv_returns_a_guessed_schema_and_preview_rows(self):
        data = {"file": (_csv_bytes("period,revenue\nFY2023,1000000\nFY2024,1250000\n"), "data.csv")}
        resp = self._post(data)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["schema"], {"period": "text", "revenue": "number"})
        self.assertEqual(
            body["preview"],
            [
                {"row": 2, "cells": {"period": "FY2023", "revenue": 1000000.0}},
                {"row": 3, "cells": {"period": "FY2024", "revenue": 1250000.0}},
            ],
        )
        self.assertIsNone(body["warning"])

    def test_pdf_returns_a_warning(self):
        data = {"file": (_make_pdf_bytes([["period", "revenue"], ["FY2024", "4200000"]]), "data.pdf")}
        resp = self._post(data)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["schema"], {"period": "text", "revenue": "number"})
        self.assertIsNotNone(body["warning"])
        self.assertIn("PDF", body["warning"])

    def test_missing_file_is_a_clean_400(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("file", resp.get_json()["error"])

    def test_unsupported_file_type_is_a_clean_400(self):
        data = {"file": (io.BytesIO(b"hello"), "data.txt")}
        resp = self._post(data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(".txt", resp.get_json()["error"])

    def test_wrong_access_code_is_a_clean_401(self):
        data = {"file": (_csv_bytes("period\nFY2024\n"), "data.csv")}
        resp = self.client.post(
            "/api/extract",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Access-Code": "wrong"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_nothing_persists_after_the_request(self):
        import glob

        before = set(glob.glob(str(Path(tempfile.gettempdir()) / "analystos-*")))
        data = {"file": (_csv_bytes("period,revenue\nFY2024,100\n"), "data.csv")}
        resp = self._post(data)
        self.assertEqual(resp.status_code, 200)
        after = set(glob.glob(str(Path(tempfile.gettempdir()) / "analystos-*")))
        self.assertEqual(after - before, set())


if __name__ == "__main__":
    unittest.main()
