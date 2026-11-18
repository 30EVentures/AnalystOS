"""Slice 92 - hardening: a size cap before the paid call, no upload text in the audit log,
a logged verifier fault. See specs/slice-92/spec.md."""

import contextlib
import io
import json
import unittest
from unittest.mock import MagicMock, patch

from analystos.l2 import analyze
from analystos.l2.prompt_safety import MAX_TITLE_CHARS
from analystos.l4 import seal_verify
from tests.test_api_v1 import ApiTestCase

_LEAK = "SECRETCELL-4471"


class DocumentCapTest(unittest.TestCase):
    def test_an_over_cap_document_is_refused_before_any_model_call(self):
        client = MagicMock()
        text = "x" * (analyze.MAX_DOCUMENT_CHARS + 1)
        with self.assertRaises(ValueError) as caught:
            analyze.analyze_document(text, "t", client=client)
        client.messages.create.assert_not_called()
        self.assertIn(f"{analyze.MAX_DOCUMENT_CHARS:,}", str(caught.exception))
        self.assertNotIn("xxxx", str(caught.exception))

    def test_the_cap_is_checked_before_the_client_is_even_resolved(self):
        with patch.object(analyze, "_resolve_client", side_effect=AssertionError("resolved")):
            with self.assertRaises(ValueError):
                analyze.analyze_document("x" * (analyze.MAX_DOCUMENT_CHARS + 1), "t")

    def test_a_document_at_the_cap_is_still_sent(self):
        with patch.object(analyze, "_request_report", return_value=([], False)) as sent, \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(ValueError):  # no segments: fails on content, not on size
                analyze.analyze_document("x" * analyze.MAX_DOCUMENT_CHARS, "t", client=MagicMock())
        self.assertTrue(sent.called)


class JobAuditTest(ApiTestCase):
    def submit(self, **form):
        data = {"file": (io.BytesIO(b"a,b\n1,2\n"), "report.csv"), **form}
        return self.client.post("/api/v1/jobs", headers=self.h(), content_type="multipart/form-data", data=data)

    def test_a_failed_job_audit_line_carries_no_text_from_the_document(self):
        job = self.submit().get_json()
        error = ValueError(f"row 3, column 'X': '{_LEAK}' is not a number")
        with patch("analystos.api_v1.blueprint.build_report", side_effect=error):
            response = self.client.post(f"/api/v1/jobs/{job['id']}/run", headers=self.h())
        self.assertEqual(response.get_json()["status"], "failed")
        audit_text = (self.store.root / "audit.jsonl").read_text()
        self.assertNotIn(_LEAK, audit_text)
        failed = [e for e in self.store.read_audit() if e["type"] == "job_failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["error_type"], "ValueError")
        self.assertTrue(failed[0]["error"])

    def test_a_config_failure_keeps_its_message_in_the_audit_line(self):
        job = self.submit().get_json()
        with patch("analystos.api_v1.blueprint.code_version", side_effect=ValueError("ANALYSTOS_CODE_VERSION is malformed")):
            self.client.post(f"/api/v1/jobs/{job['id']}/run", headers=self.h())
        failed = [e for e in self.store.read_audit() if e["type"] == "job_failed"]
        self.assertIn("ANALYSTOS_CODE_VERSION", failed[0]["error"])


class TitleCapTest(ApiTestCase):
    def test_an_overlong_title_is_a_400_on_analyses_and_on_jobs(self):
        long_title = "t" * (MAX_TITLE_CHARS + 1)
        response = self.analyze(title=long_title)
        self.assertEqual(response.status_code, 400, response.get_data(as_text=True)[:200])
        self.assertEqual(response.get_json()["error"]["code"], "bad_request")
        job = self.client.post("/api/v1/jobs", headers=self.h(), content_type="multipart/form-data",
                               data={"file": (io.BytesIO(b"a,b\n1,2\n"), "report.csv"), "title": long_title})
        self.assertEqual(job.status_code, 400, job.get_data(as_text=True)[:200])

    def test_a_title_at_the_cap_still_works(self):
        title = "t" * MAX_TITLE_CHARS
        self.assertEqual(self.analyze(title=title).status_code, 201)
        job = self.client.post("/api/v1/jobs", headers=self.h(), content_type="multipart/form-data",
                               data={"file": (io.BytesIO(b"a,b\n1,2\n"), "report.csv"), "title": title})
        self.assertEqual(job.status_code, 202)


class VerifierFaultLogTest(unittest.TestCase):
    def test_an_internal_verifier_fault_logs_the_exception_type_and_still_fails_closed(self):
        class _Boom(Exception):
            pass

        err = io.StringIO()
        with patch.object(seal_verify, "_verify_bundle", side_effect=_Boom(f"carries {_LEAK}")), \
                contextlib.redirect_stderr(err):
            out = seal_verify.verify_bundle({"format": "x"})
        self.assertFalse(out["ok"] or out["authentic"] or out["content_checked"])
        logged = err.getvalue()
        self.assertIn("_Boom", logged)
        self.assertNotIn(_LEAK, logged)
        self.assertEqual(len(logged.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
