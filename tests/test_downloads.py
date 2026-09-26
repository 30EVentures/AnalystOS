"""Slice 63 - results are handed back as files for the reader's own Downloads
folder; nothing is kept on the server. See specs/slice-63/spec.md."""

import base64
import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from analystos.l4.seal import generate_key
from analystos.l4.seal_verify import verify_bundle
from api.analyze import _ACCESS_CODE_ENV_VAR, app

REPO = Path(__file__).resolve().parents[1]
CODE = "downloads-test-code"


def narrated_client():
    tool_use = SimpleNamespace(type="tool_use", input={"segments": [{
        "type": "quote", "display": "inline", "label": "Revenue", "exact_text": "4200000",
        "has_value": True, "value": 4200000.0, "sentence": "Revenue was {value}.", "format": "usd"}]})
    response = SimpleNamespace(content=[tool_use])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response))


class HostedPageDownloadsTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        patcher = patch.dict(os.environ, {_ACCESS_CODE_ENV_VAR: CODE, "ANALYSTOS_RATE_LIMIT_MAX": "100000"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, data):
        with contextlib.redirect_stderr(io.StringIO()):
            return self.client.post("/api/analyze", data=data, content_type="multipart/form-data",
                                    headers={"X-Access-Code": CODE})

    def test_a_narrated_run_returns_a_real_pdf_and_a_verifying_seal(self):
        with patch("analystos.l2.analyze.anthropic.Anthropic", return_value=narrated_client()):
            body = self.post({"file": (io.BytesIO(b"period,revenue\nFY2024,4200000\n"), "data.csv")}).get_json()
        self.assertIn("Revenue was $4.2M.", body["section"])  # unchanged fields
        self.assertIn("<!doctype html>", body["html"].lower())
        self.assertTrue(base64.b64decode(body["pdf_base64"]).startswith(b"%PDF"))
        self.assertEqual(body["seal"]["format"], "analystos-seal/1")
        out = verify_bundle(body["seal"])
        self.assertTrue(out["ok"], out)
        self.assertIsNone(body["seal"]["signature"])  # no key configured -> unsigned, and it says so

    def test_a_configured_seal_key_signs_it(self):
        priv, pub = generate_key()
        with patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": priv}), \
                patch("analystos.l2.analyze.anthropic.Anthropic", return_value=narrated_client()):
            body = self.post({"file": (io.BytesIO(b"period,revenue\nFY2024,4200000\n"), "data.csv")}).get_json()
        self.assertTrue(verify_bundle(body["seal"], public_key=pub)["authentic"])

    def test_a_malformed_seal_key_does_not_lose_the_report(self):
        with patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": "garbage"}), \
                patch("analystos.l2.analyze.anthropic.Anthropic", return_value=narrated_client()):
            resp = self.post({"file": (io.BytesIO(b"period,revenue\nFY2024,4200000\n"), "data.csv")})
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("seal", body)
        self.assertIn("Revenue was $4.2M.", body["section"])

    def test_the_table_path_has_a_pdf_but_no_seal(self):
        body = self.post({
            "file": (io.BytesIO(b"period,revenue\nFY2023,26974\nFY2024,60922\n"), "data.csv"),
            "schema": '{"period": "text", "revenue": "number"}', "template": "income_statement",
        }).get_json()
        self.assertTrue(base64.b64decode(body["pdf_base64"]).startswith(b"%PDF"))
        self.assertNotIn("seal", body)

    def test_nothing_is_written_to_the_server(self):
        before = set(Path(tempfile.gettempdir()).glob("analystos-*"))
        with patch("analystos.l2.analyze.anthropic.Anthropic", return_value=narrated_client()):
            self.post({"file": (io.BytesIO(b"period,revenue\nFY2024,4200000\n"), "data.csv")})
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("analystos-*")) - before, set())


class UploadPageTest(unittest.TestCase):
    PAGE = (REPO / "site" / "upload.html").read_text(encoding="utf-8")

    def test_three_download_controls_exist(self):
        for control in ("download-pdf-btn", "download-html-btn", "download-seal-btn"):
            self.assertIn(f'id="{control}"', self.PAGE)

    def test_downloads_use_the_download_attribute_and_the_response_fields(self):
        self.assertIn("a.download = filename", self.PAGE)
        for field in ("data.pdf_base64", "data.seal", "data.html"):
            self.assertIn(field, self.PAGE)
        self.assertIn(".seal.json", self.PAGE)
        self.assertIn("Downloads folder", self.PAGE)

    def test_the_print_fallback_is_kept_for_a_response_without_a_pdf(self):
        self.assertIn("frame.contentWindow.print()", self.PAGE)

    def test_the_seal_button_stays_hidden_unless_a_seal_came_back(self):
        self.assertIn('id="download-seal-btn" hidden', self.PAGE)
        self.assertIn("downloadSealBtn.hidden = !latest.seal", self.PAGE)


class ApiV1IncludePdfTest(unittest.TestCase):
    def test_include_pdf_flag(self):
        from tests.test_api_v1 import ApiTestCase  # reuse the mocked-model harness

        class Inner(ApiTestCase):
            def runTest(self):  # pragma: no cover - driven below
                pass

        case = Inner()
        case.setUp()
        try:
            plain = case.created()
            self.assertNotIn("pdf_base64", plain)
            with_pdf = case.created(include_pdf="true")
            self.assertTrue(base64.b64decode(with_pdf["pdf_base64"]).startswith(b"%PDF"))
        finally:
            case.doCleanups()


class StatelessDefaultIsDocumentedTest(unittest.TestCase):
    def test_docs_state_the_default(self):
        api = (REPO / "docs" / "api.md").read_text()
        self.assertIn("keeps no reports on a server by default", api)
        self.assertIn("include_pdf", api)
        self.assertIn("evidenceUrl", api)
        self.assertTrue(re.search(r"30E Ventures", (REPO / "docs" / "mesh-identity.md").read_text()))


if __name__ == "__main__":
    unittest.main()
