"""Overnight round 1 - a bad upload is a 4xx with a JSON body, never a 500, and never
leaves a job stuck. The model is never called: every file here is rejected while it
is being read, before any model step. See STATE.md (round 1).

Found by running the routes with production error handling on:
  * a file that is not really an .xlsx/.docx/.pptx/.pdf raised zipfile.BadZipFile or
    a pdfminer error out of the route (HTTP 500, an HTML page);
  * a filename over the filesystem's 255-byte limit raised OSError from ``save`` (500);
  * an unexpected error while running a stored job left it ``running`` forever with
    its upload still on disk (the upload is meant to be dropped as soon as it has run);
  * a docx/xlsx/pptx is a zip, and nothing bounded how large it expands.
"""

import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from analystos.l1 import guard
from analystos.l1.detect import extract_any
from analystos.l1.document_text import extract_document_text
from api.analyze import _ACCESS_CODE_ENV_VAR, app
from tests.test_api_v1 import ApiTestCase

_CODE = "test-access-code"
_JUNK = b"this is not really a document"
_BINARY = (".xlsx", ".docx", ".pptx", ".pdf")


class LegacyRoutesTest(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {_ACCESS_CODE_ENV_VAR: _CODE, "ANALYSTOS_RATE_LIMIT_MAX": "100000"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = app.test_client()

    def post(self, route, name, data, **form):
        return self.client.post(
            route, data={"file": (io.BytesIO(data), name), **form},
            headers={"X-Access-Code": _CODE}, content_type="multipart/form-data",
        )

    def test_extract_reports_a_damaged_file_as_a_400_with_json(self):
        for ext in _BINARY:
            for data in (_JUNK, b""):
                with self.subTest(ext=ext, size=len(data)):
                    response = self.post("/api/extract", "report" + ext, data)
                    self.assertEqual(response.status_code, 400, response.get_data(as_text=True)[:200])
                    self.assertIn("error", response.get_json())

    def test_analyze_reports_a_damaged_file_as_a_400_on_both_paths(self):
        for ext in _BINARY:
            with self.subTest(ext=ext, path="narrated default"):
                response = self.post("/api/analyze", "report" + ext, _JUNK)
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True)[:200])
                self.assertIn("error", response.get_json())
            with self.subTest(ext=ext, path="table template"):
                response = self.post("/api/analyze", "report" + ext, _JUNK, template="income_statement",
                                     schema='{"period": "text"}', pdf_confirmed="true")
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True)[:200])

    def test_the_error_does_not_name_server_paths_or_libraries(self):
        response = self.post("/api/extract", "report.xlsx", _JUNK)
        self.assertEqual(response.status_code, 400)  # not a 500 page, which would also name nothing
        text = response.get_data(as_text=True)
        for leak in ("zipfile", "BadZipFile", "Traceback", "/var/", "analystos-", "openpyxl"):
            self.assertNotIn(leak, text)

    def test_an_overlong_filename_is_a_400_not_a_500(self):
        for route in ("/api/extract", "/api/analyze"):
            with self.subTest(route=route):
                response = self.post(route, "a" * 300 + ".csv", b"a,b\n1,2\n")
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True)[:200])
                self.assertIn("error", response.get_json())

    def test_a_filename_at_the_limit_still_works(self):
        response = self.post("/api/extract", "a" * 200 + ".csv", b"a,b\n1,2\n")
        self.assertEqual(response.status_code, 200)


class V1RoutesTest(ApiTestCase):
    def test_analyses_reports_a_damaged_file_as_a_422_with_the_error_envelope(self):
        for ext in _BINARY:
            with self.subTest(ext=ext):
                response = self.analyze(name="report" + ext, content=_JUNK.decode())
                self.assertEqual(response.status_code, 422, response.get_data(as_text=True)[:200])
                self.assertIn("error", response.get_json())

    def test_an_overlong_filename_is_refused_on_analyses_and_on_job_creation(self):
        response = self.analyze(name="a" * 300 + ".csv")
        self.assertEqual(response.status_code, 400, response.get_data(as_text=True)[:200])
        job = self.client.post("/api/v1/jobs", headers=self.h(), content_type="multipart/form-data",
                               data={"file": (io.BytesIO(b"a,b\n1,2\n"), "a" * 300 + ".csv")})
        self.assertEqual(job.status_code, 400, job.get_data(as_text=True)[:200])

    def submitted(self, name="report.csv", content=b"a,b\n1,2\n"):
        response = self.client.post("/api/v1/jobs", headers=self.h(), content_type="multipart/form-data",
                                    data={"file": (io.BytesIO(content), name)})
        self.assertEqual(response.status_code, 202, response.get_data(as_text=True))
        return response.get_json()

    def run_job(self, job):
        return self.client.post(f"/api/v1/jobs/{job['id']}/run", headers=self.h())

    def test_a_damaged_upload_fails_the_job_and_drops_the_upload(self):
        job = self.submitted("report.xlsx", _JUNK)
        failed = self.run_job(job).get_json()
        self.assertEqual(failed["status"], "failed", failed)
        self.assertIn("damaged or not really", failed["error"])  # the guard's message, not the catch-all's
        self.assertIsNone(self.store.job_upload(job["id"]))

    def test_an_unexpected_error_fails_the_job_instead_of_leaving_it_running(self):
        job = self.submitted()
        with patch("analystos.api_v1.blueprint.build_report", side_effect=RuntimeError("boom /srv/secret/path")):
            response = self.run_job(job)
        body = response.get_json()
        self.assertEqual(body["status"], "failed", body)
        self.assertNotIn("boom", response.get_data(as_text=True))
        self.assertNotIn("/srv/secret", response.get_data(as_text=True))
        self.assertIsNone(self.store.job_upload(job["id"]))
        self.assertEqual(self.client.get(f"/api/v1/jobs/{job['id']}", headers=self.h()).get_json()["status"], "failed")


class ArchiveSizeTest(unittest.TestCase):
    def zip_of(self, size, name="word/document.xml"):
        path = Path(self._tmp.name) / "bomb.docx"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            with archive.open(name, "w") as entry:
                for _ in range(size // 65536):
                    entry.write(b"\0" * 65536)
        return path

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_an_archive_that_expands_past_the_cap_is_refused_before_it_is_parsed(self):
        path = self.zip_of(3 * 1024 * 1024)
        with patch.object(guard, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1024 * 1024):
            for read in (lambda: extract_any(path), lambda: extract_document_text(path)):
                with self.assertRaises(ValueError) as caught:
                    read()
                self.assertIn("expands", str(caught.exception))

    def test_an_archive_with_too_many_entries_is_refused(self):
        path = Path(self._tmp.name) / "many.xlsx"
        with zipfile.ZipFile(path, "w") as archive:
            for i in range(30):
                archive.writestr(f"x/{i}.xml", "<a/>")
        with patch.object(guard, "MAX_ARCHIVE_ENTRIES", 10):
            with self.assertRaises(ValueError) as caught:
                extract_any(path)
        self.assertIn("entries", str(caught.exception))

    def test_a_pdf_is_not_treated_as_an_archive(self):
        self.assertIsNone(guard.check_archive(Path("whatever.pdf")))


if __name__ == "__main__":
    unittest.main()
