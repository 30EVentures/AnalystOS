"""Overnight round 5 - API robustness. Found by driving the routes with production
error handling (an unhandled exception is an HTML 500):

  * ``GET /api/v1/reports/<id>?exp=..&sig=<non-ASCII>`` (no authentication) -> 500:
    ``hmac.compare_digest`` refuses non-ASCII *strings*;
  * the legacy ``X-Access-Code`` header with a non-ASCII value -> 500 instead of 401, same cause;
  * ``POST /api/v1/reports/<id>/review`` with a JSON body that is not an object -> 500;
  * the per-IP rate-limit table only ever grew (one entry per distinct client key, never evicted);
  * a job that was submitted and never run kept its uploaded document on disk forever (the docs
    promise the upload is kept only until the job runs); finished jobs' records were never removed;
  * two concurrent ``run`` calls for one pending job could both pass the "is it pending?" check.
"""

import contextlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from analystos.api_v1 import links, store as store_mod
from api import analyze as legacy
from tests.test_api_v1 import ApiTestCase


class SignatureComparisonTest(unittest.TestCase):
    def test_a_non_ascii_signature_is_invalid_not_an_exception(self):
        for sig in ("é", "�", "a" * 10 + "é", "𝔘"):
            with self.subTest(sig=sig):
                self.assertEqual(links.check("secret", "a" * 64, "html", 9999999999, sig, now=1), "invalid")

    def test_a_real_signature_still_checks(self):
        exp, sig = links.sign("secret", "a" * 64, "html", 3600, now=1000)
        self.assertEqual(links.check("secret", "a" * 64, "html", exp, sig, now=1001), "ok")
        self.assertEqual(links.check("secret", "a" * 64, "html", exp, sig, now=exp + 1), "expired")


class V1RouteTest(ApiTestCase):
    def test_a_link_with_a_non_ascii_signature_is_a_403_not_a_500(self):
        digest = self.created()["id"]
        response = self.client.get(f"/api/v1/reports/{digest}?format=html&exp=9999999999&sig=%C3%A9")
        self.assertEqual(response.status_code, 403, response.get_data(as_text=True)[:120])
        self.assertEqual(response.get_json()["error"]["code"], "link_invalid")

    def review(self, digest, data=None):
        kwargs = {} if data is None else {"data": data, "content_type": "application/json"}
        return self.client.post(f"/api/v1/reports/{digest}/review", headers=self.h(), **kwargs)

    def test_a_review_body_that_is_not_an_object_is_a_400(self):
        digest = self.created()["id"]
        for body in ("[1]", '"text"', "5", "true"):
            with self.subTest(body=body):
                response = self.review(digest, body)
                self.assertIn(response.status_code, (400,), response.get_data(as_text=True)[:120])

    def test_a_review_with_no_body_or_an_object_still_works(self):
        digest = self.created()["id"]
        self.assertEqual(self.review(digest).status_code, 200)
        self.assertEqual(self.review(digest, json.dumps({"approved": True})).status_code, 200)
        self.assertEqual(self.review(digest, json.dumps({"approved": "yes"})).status_code, 400)


class LegacyAccessCodeTest(unittest.TestCase):
    def test_a_non_ascii_access_code_header_is_a_401(self):
        with patch.dict(os.environ, {legacy._ACCESS_CODE_ENV_VAR: "right-code", "ANALYSTOS_RATE_LIMIT_MAX": "100000"}):
            client = legacy.app.test_client()
            for code in ("é", "right-codé", "Ã©"):
                with self.subTest(code=code):
                    response = client.post("/api/extract", headers={"X-Access-Code": code},
                                           data={"file": (io.BytesIO(b"a,b\n1,2\n"), "x.csv")},
                                           content_type="multipart/form-data")
                    self.assertEqual(response.status_code, 401, response.get_data(as_text=True)[:120])

    def test_the_right_code_still_works(self):
        with patch.dict(os.environ, {legacy._ACCESS_CODE_ENV_VAR: "right-code", "ANALYSTOS_RATE_LIMIT_MAX": "100000"}):
            response = legacy.app.test_client().post(
                "/api/extract", headers={"X-Access-Code": "right-code"},
                data={"file": (io.BytesIO(b"a,b\n1,2\n"), "x.csv")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)


class RateLimitTableTest(unittest.TestCase):
    def setUp(self):
        legacy._rate_limit_buckets.clear()
        self.addCleanup(legacy._rate_limit_buckets.clear)

    def test_the_table_does_not_grow_without_bound(self):
        with patch.dict(os.environ, {"ANALYSTOS_RATE_LIMIT_MAX": "5", "ANALYSTOS_RATE_LIMIT_WINDOW_SECONDS": "60"}):
            with legacy.app.test_request_context("/api/extract", method="POST"):
                clock = [1000.0]
                with patch.object(legacy.time, "time", lambda: clock[0]):
                    for i in range(legacy._MAX_RATE_LIMIT_CLIENTS + 500):
                        with patch.object(legacy, "_client_key", lambda i=i: f"10.{i >> 16}.{(i >> 8) & 255}.{i & 255}"):
                            legacy._rate_limit_denied()
                    self.assertLessEqual(len(legacy._rate_limit_buckets), legacy._MAX_RATE_LIMIT_CLIENTS)
                    clock[0] += 61  # every window has now expired
                    with patch.object(legacy, "_client_key", lambda: "203.0.113.9"):
                        legacy._rate_limit_denied()
                    # once the table is over its cap, expired windows are what gets dropped first
                    self.assertLessEqual(len(legacy._rate_limit_buckets), legacy._MAX_RATE_LIMIT_CLIENTS)

    def test_limiting_still_works(self):
        with patch.dict(os.environ, {"ANALYSTOS_RATE_LIMIT_MAX": "2", "ANALYSTOS_RATE_LIMIT_WINDOW_SECONDS": "60"}):
            with legacy.app.test_request_context("/api/extract", method="POST", environ_base={"REMOTE_ADDR": "198.51.100.7"}):
                self.assertIsNone(legacy._rate_limit_denied())
                self.assertIsNone(legacy._rate_limit_denied())
                self.assertEqual(legacy._rate_limit_denied()[1], 429)


class JobRetentionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = store_mod.FileStore(Path(self._tmp.name) / "store")

    def job(self, job_id, created_ts, status="pending"):
        meta = {"caller": "agent-a", "status": status, "created": store_mod.iso(created_ts), "title": "T"}
        self.store.create_job(job_id, meta, "report.csv", b"a,b\n1,2\n")

    def test_a_job_that_was_never_run_is_removed_with_its_upload_after_the_retention_period(self):
        now = 10_000_000.0
        ttl = 30 * 86400
        old, fresh = "a" * 32, "b" * 32
        self.job(old, now - ttl - 60)
        self.job(fresh, now - 60)
        self.store.purge_expired(now=now)
        self.assertIsNone(self.store.job_upload(old))
        self.assertIsNone(self.store.job_meta(old))
        self.assertIsNotNone(self.store.job_upload(fresh))

    def test_a_finished_jobs_record_is_removed_too(self):
        now = 10_000_000.0
        self.job("c" * 32, now - 31 * 86400, status="done")
        self.store.delete_job_upload("c" * 32)
        self.store.purge_expired(now=now)
        self.assertIsNone(self.store.job_meta("c" * 32))

    def test_reports_are_still_purged_by_their_own_expiry(self):
        digest = "d" * 64
        self.store.put(digest, {"expires_ts": 5.0}, "<html></html>", None, {"x": 1})
        self.assertEqual(self.store.purge_expired(now=10.0), 1)
        self.assertIsNone(self.store.meta(digest))


class JobClaimTest(ApiTestCase):
    def test_exactly_one_of_many_concurrent_claims_wins(self):
        job_id = "e" * 32
        self.store.create_job(job_id, {"caller": "agent-a", "status": "pending", "created": store_mod.iso(time.time())},
                              "report.csv", b"a,b\n1,2\n")
        wins, barrier = [], threading.Barrier(8)

        def attempt():
            barrier.wait()
            wins.append(self.store.claim_job(job_id))

        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(wins.count(True), 1, wins)

    def test_a_run_that_loses_the_claim_does_not_run_the_pipeline(self):
        response = self.client.post("/api/v1/jobs", headers=self.h(), content_type="multipart/form-data",
                                    data={"file": (io.BytesIO(b"a,b\n1,2\n"), "report.csv")})
        job_id = response.get_json()["id"]
        self.assertTrue(self.store.claim_job(job_id))  # another worker got there first
        with patch("analystos.api_v1.blueprint.build_report", side_effect=AssertionError("must not run twice")):
            with contextlib.redirect_stderr(io.StringIO()):
                again = self.client.post(f"/api/v1/jobs/{job_id}/run", headers=self.h())
        self.assertEqual(again.status_code, 200, again.get_data(as_text=True)[:200])
        self.assertIn(again.get_json()["status"], ("pending", "running"))


if __name__ == "__main__":
    unittest.main()
