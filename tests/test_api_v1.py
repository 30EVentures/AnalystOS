"""Slice 61 - the agent-callable /api/v1. See specs/slice-61/spec.md and
docs/api.md. The model is always mocked: no network, no cost."""

import contextlib
import copy
import io
import json
import os
import re
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from analystos.api_v1 import auth, links, store as store_mod
from analystos.api_v1.audit import measures
from analystos.api_v1.__main__ import main as cli_main
from analystos.api_v1.openapi import build_openapi
from analystos.l4.seal import generate_key
from analystos.l4.seal_verify import verify_bundle
from analystos.pipeline import build_report as real_build_report
from api.analyze import app

REPO = Path(__file__).resolve().parents[1]
CSV = "metric,value\nq3_2025_revenue,402000000\nq4_2025_revenue,410000000\nq1_2026_revenue,432000000\nq2_2026_revenue,455000000\nq3_2026_revenue,498000000\n"
SECRET_WORDS = "PROJECT-NIGHTINGALE-CONFIDENTIAL"


def fake_client(narrative_ok=False):
    def quote(label, text, value):
        return {"type": "quote", "display": "stat", "label": label, "exact_text": text, "has_value": True,
                "value": value, "sentence": "{value} was reported.", "format": "usd"}
    raw = [quote("Q3 2025 Revenue", "402000000", 402e6), quote("Q4 2025 Revenue", "410000000", 410e6),
           quote("Q1 2026 Revenue", "432000000", 432e6), quote("Q2 2026 Revenue", "455000000", 455e6),
           quote("Q3 2026 Revenue", "498000000", 498e6),
           {"type": "quote", "display": "stat", "label": "Invented", "exact_text": "777777777", "has_value": True,
            "value": 777777777.0, "sentence": "{value}.", "format": "usd"}]
    report = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"segments": raw})])
    broken = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"segments": []})])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: broken if kw["tool_choice"]["name"] == "write_narrative" else report))


def mocked_build_report(*args, **kwargs):
    return real_build_report(*args, llm_client=fake_client(), **kwargs)


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raw_a, entry_a = auth.new_key("agent-a")
        self.raw_b, entry_b = auth.new_key("agent-b")
        self.seal_priv, self.seal_pub = generate_key()
        env = {
            auth.KEYS_ENV: f"{entry_a},{entry_b}", store_mod.STORE_ENV: str(Path(self._tmp.name) / "store"),
            links.SECRET_ENV: "link-secret-for-tests", "ANALYSTOS_SEAL_KEY": self.seal_priv,
            "ANALYSTOS_RATE_LIMIT_MAX": "100000", store_mod.TTL_ENV: "30",
        }
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        build_patch = patch("analystos.api_v1.blueprint.build_report", mocked_build_report)
        build_patch.start()
        self.addCleanup(build_patch.stop)
        self.client = app.test_client()
        self.store = store_mod.FileStore.from_env()

    def h(self, key=None):
        return {"Authorization": f"Bearer {key or self.raw_a}"}

    def analyze(self, key=None, name="report.csv", content=CSV, **form):
        data = {"file": (io.BytesIO(content.encode()), name), **form}
        with contextlib.redirect_stderr(io.StringIO()):
            return self.client.post("/api/v1/analyses", data=data, headers=self.h(key), content_type="multipart/form-data")

    def created(self, **kw):
        response = self.analyze(**kw)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()


class CreateAnalysisTest(ApiTestCase):
    def test_creates_a_sealed_stored_report(self):
        body = self.created()
        self.assertRegex(body["id"], r"^[0-9a-f]{64}$")
        self.assertEqual(body["tier"], "deterministic")
        self.assertEqual(body["counts"], {"proposed": 6, "verified": 5, "dropped": 1})
        self.assertTrue(body["stored"] and body["signed"])
        self.assertEqual(body["links"]["report"], f"/api/v1/reports/{body['id']}")
        self.assertTrue(body["html"].lower().startswith("<!doctype html"))
        self.assertNotIn("777777777", json.dumps(body))

    def test_the_response_seal_verifies_with_the_standalone_verifier(self):
        body = self.created()
        out = verify_bundle(body["seal"], public_key=self.seal_pub)
        self.assertTrue(out["ok"] and out["authentic"], out)

    def test_location_header_and_pdf_are_stored(self):
        response = self.analyze()
        body = response.get_json()
        self.assertEqual(response.headers["Location"], body["links"]["report"])
        pdf = self.client.get(body["links"]["pdf"], headers=self.h())
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.get_data().startswith(b"%PDF"))

    def test_without_a_store_the_report_and_seal_are_still_inline(self):
        with patch.dict(os.environ, {store_mod.STORE_ENV: ""}):
            body = self.created()
            self.assertFalse(body["stored"])
            self.assertIsNone(body["links"])
            self.assertTrue(verify_bundle(body["seal"])["ok"])
            self.assertEqual(self.client.get(f"/api/v1/reports/{body['id']}", headers=self.h()).status_code, 503)
            self.assertEqual(self.client.get(f"/api/v1/verify/{body['id']}").status_code, 503)

    def test_a_bad_seal_key_config_is_refused_not_downgraded(self):
        with patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": "garbage"}):
            response = self.analyze()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "unavailable")

    def test_no_seal_key_means_an_unsigned_seal_that_says_so(self):
        with patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": ""}):
            body = self.created()
        self.assertFalse(body["signed"])
        self.assertIsNone(body["seal"]["signature"])

    def test_input_errors(self):
        no_file = self.client.post("/api/v1/analyses", data={}, headers=self.h(), content_type="multipart/form-data")
        self.assertEqual((no_file.status_code, no_file.get_json()["error"]["code"]), (400, "bad_request"))
        bad_type = self.analyze(name="malware.exe")
        self.assertEqual((bad_type.status_code, bad_type.get_json()["error"]["code"]), (415, "unsupported_media"))

    def test_a_pipeline_valueerror_is_a_422_with_its_message(self):
        with patch("analystos.api_v1.blueprint.build_report", side_effect=ValueError("nothing verifiable")):
            response = self.analyze()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"], {"code": "unprocessable", "message": "nothing verifiable"})


class AsyncJobsTest(ApiTestCase):
    """Its own X-Forwarded-For so these extra requests don't push the shared
    per-IP rate-limit counter into other tests' way (see AuthTest etc., which
    share the default IP and stay well under the per-test-raised ceiling
    only as long as nothing here adds to their count)."""

    IP = "203.0.113.204"

    def h(self, key=None):
        return {**super().h(key), "X-Forwarded-For": self.IP}

    def submit(self, key=None, name="report.csv", content=CSV, **form):
        data = {"file": (io.BytesIO(content.encode()), name), **form}
        with contextlib.redirect_stderr(io.StringIO()):
            return self.client.post("/api/v1/jobs", data=data, headers=self.h(key), content_type="multipart/form-data")

    def submitted(self, **kw):
        response = self.submit(**kw)
        self.assertEqual(response.status_code, 202, response.get_data(as_text=True))
        return response.get_json()

    def run_job(self, job, key=None):
        with contextlib.redirect_stderr(io.StringIO()):
            return self.client.post(f"/api/v1/jobs/{job['id']}/run", headers=self.h(key))

    def poll(self, job, key=None):
        return self.client.get(f"/api/v1/jobs/{job['id']}", headers=self.h(key))

    def test_create_is_fast_and_pending(self):
        job = self.submitted()
        self.assertEqual(job["status"], "pending")
        self.assertRegex(job["id"], r"^[0-9a-f]{32}$")

    def test_polling_never_runs_it(self):
        job = self.submitted()
        for _ in range(3):
            self.assertEqual(self.poll(job).get_json()["status"], "pending")
        self.assertIsNotNone(self.store.job_upload(job["id"]))

    def test_run_produces_the_same_report_analyses_would(self):
        job = self.submitted()
        done = self.run_job(job).get_json()
        self.assertEqual(done["status"], "done")
        seal = self.client.get(done["links"]["seal"], headers=self.h()).get_json()
        self.assertEqual(seal["payload"]["tier"], "deterministic")
        polled = self.poll(job).get_json()
        self.assertEqual(polled, done)

    def test_run_is_idempotent_and_never_reruns(self):
        job = self.submitted()
        first = self.run_job(job).get_json()
        second = self.run_job(job).get_json()
        self.assertEqual(first, second)
        analyses = [e for e in self.store.read_audit() if e["type"] == "analysis"]
        self.assertEqual(len(analyses), 1)
        self.assertEqual(analyses[0]["via"], "job")

    def test_upload_is_deleted_once_run(self):
        job = self.submitted()
        self.assertIsNotNone(self.store.job_upload(job["id"]))
        self.run_job(job)
        self.assertIsNone(self.store.job_upload(job["id"]))

    def test_a_pipeline_failure_marks_the_job_failed_and_drops_the_upload(self):
        job = self.submitted()
        with patch("analystos.api_v1.blueprint.build_report", side_effect=ValueError("nothing verifiable")):
            failed = self.run_job(job).get_json()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"], "nothing verifiable")
        self.assertIsNone(self.store.job_upload(job["id"]))
        self.assertEqual(self.poll(job).get_json(), failed)

    def test_a_bad_seal_key_marks_the_job_failed(self):
        job = self.submitted()
        with patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": "garbage"}):
            failed = self.run_job(job).get_json()
        self.assertEqual(failed["status"], "failed")
        self.assertIn("key", failed["error"].lower())

    def test_only_the_creator_can_run_or_poll(self):
        job = self.submitted()
        self.assertEqual(self.run_job(job, key=self.raw_b).status_code, 404)
        self.assertEqual(self.poll(job, key=self.raw_b).status_code, 404)

    def test_unknown_job_is_404(self):
        fake = {"id": "a" * 32}
        self.assertEqual(self.run_job(fake).status_code, 404)
        self.assertEqual(self.poll(fake).status_code, 404)

    def test_input_errors_match_analyses(self):
        no_file = self.client.post("/api/v1/jobs", data={}, headers=self.h(), content_type="multipart/form-data")
        self.assertEqual((no_file.status_code, no_file.get_json()["error"]["code"]), (400, "bad_request"))
        bad_type = self.submit(name="malware.exe")
        self.assertEqual((bad_type.status_code, bad_type.get_json()["error"]["code"]), (415, "unsupported_media"))

    def test_query_form_used_behind_vercel_rewrites(self):
        job = self.submitted()
        run = self.client.post(f"/api/v1/jobs?id={job['id']}&run=true", headers=self.h())
        self.assertEqual(run.get_json()["status"], "done")
        polled = self.client.get(f"/api/v1/jobs?id={job['id']}", headers=self.h())
        self.assertEqual(polled.get_json()["status"], "done")

    def test_jobs_are_audited(self):
        job = self.submitted()
        self.run_job(job)
        types = [e["type"] for e in self.store.read_audit()]
        self.assertEqual(types, ["job_created", "analysis"])

    def test_no_store_configured_is_503(self):
        with patch.dict(os.environ, {store_mod.STORE_ENV: ""}):
            r = self.submit()
        self.assertEqual((r.status_code, r.get_json()["error"]["code"]), (503, "store_not_configured"))


class AuthTest(ApiTestCase):
    def test_missing_and_wrong_keys_are_refused(self):
        for headers in ({}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer "}):
            with self.subTest(headers=headers):
                r = self.client.post("/api/v1/analyses", data={"file": (io.BytesIO(b"x"), "a.csv")}, headers=headers,
                                     content_type="multipart/form-data")
                self.assertEqual((r.status_code, r.get_json()["error"]["code"]), (401, "unauthorized"))

    def test_no_configured_keys_fails_closed(self):
        with patch.dict(os.environ, {auth.KEYS_ENV: ""}):
            r = self.client.post("/api/v1/analyses", headers=self.h(), data={}, content_type="multipart/form-data")
        self.assertEqual((r.status_code, r.get_json()["error"]["code"]), (503, "unavailable"))

    def test_another_callers_report_looks_missing(self):
        body = self.created()
        theirs = self.client.get(body["links"]["report"], headers=self.h(self.raw_b))
        missing = self.client.get(f"/api/v1/reports/{'0' * 64}", headers=self.h(self.raw_b))
        self.assertEqual(theirs.status_code, 404)
        self.assertEqual(theirs.get_json(), missing.get_json())

    def test_key_helpers(self):
        raw, entry = auth.new_key("abc")
        name, digest = entry.split(":")
        self.assertEqual(digest, auth.hash_key(raw))
        self.assertEqual(auth.load_keys({auth.KEYS_ENV: entry + ",bad,x:short,BAD NAME:" + digest}), {"abc": digest})
        with self.assertRaises(ValueError):
            auth.new_key("Bad Name")


class ReportAccessTest(ApiTestCase):
    def test_the_creator_can_fetch_each_format(self):
        body = self.created()
        html = self.client.get(body["links"]["report"], headers=self.h())
        self.assertEqual(html.status_code, 200)
        self.assertIn("text/html", html.headers["Content-Type"])
        self.assertIn("default-src 'none'", html.headers["Content-Security-Policy"])
        self.assertEqual(html.headers["Cache-Control"], "private, no-store")
        seal = self.client.get(body["links"]["seal"], headers=self.h()).get_json()
        self.assertEqual(seal["payload"], body["seal"]["payload"])
        self.assertEqual(self.client.get(body["links"]["report"] + "?format=exe", headers=self.h()).status_code, 400)

    def test_no_credentials_is_401_not_a_leak(self):
        body = self.created()
        self.assertEqual(self.client.get(body["links"]["report"]).status_code, 401)

    def test_query_form_used_behind_vercel_rewrites(self):
        body = self.created()
        r = self.client.get(f"/api/v1/reports?digest={body['id']}&format=seal", headers=self.h())
        self.assertEqual(r.status_code, 200)

    def test_malformed_ids_are_404_never_a_path(self):
        for bad in ("../../etc/passwd", "short", "Z" * 64):
            with self.subTest(bad=bad):
                self.assertEqual(self.client.get(f"/api/v1/reports?digest={bad}", headers=self.h()).status_code, 404)

    def test_views_are_audited(self):
        body = self.created()
        self.client.get(body["links"]["report"], headers=self.h())
        views = [e for e in self.store.read_audit() if e["type"] == "view"]
        self.assertEqual([(v["via"], v["caller"]) for v in views], [("key", "agent-a")])


class ReviewTest(ApiTestCase):
    """Its own X-Forwarded-For (like VercelDoorsTest's rate-limit test) so these
    extra requests don't push the shared per-IP counter into other tests' way."""

    IP = "203.0.113.202"

    def h(self, key=None):
        return {**super().h(key), "X-Forwarded-For": self.IP}

    def get(self, path):
        return self.client.get(path, headers={"X-Forwarded-For": self.IP})

    def review(self, body, key=None, **payload):
        return self.client.post(f"/api/v1/reports/{body['id']}/review", json=payload, headers=self.h(key))

    def test_creator_can_review_and_it_shows_up_at_verify(self):
        body = self.created()
        r = self.review(body, approved=True)
        self.assertEqual(r.status_code, 200)
        reviewed = r.get_json()["reviewed"]
        self.assertEqual((reviewed["caller"], reviewed["approved"]), ("agent-a", True))
        meta = self.get(f"/api/v1/verify/{body['id']}").get_json()
        self.assertEqual(meta["reviewed"], reviewed)

    def test_unreviewed_is_null(self):
        body = self.created()
        meta = self.get(f"/api/v1/verify/{body['id']}").get_json()
        self.assertIsNone(meta["reviewed"])

    def test_reviewing_again_overwrites(self):
        body = self.created()
        self.review(body, approved=False)
        second = self.review(body, approved=True).get_json()["reviewed"]
        meta = self.get(f"/api/v1/verify/{body['id']}").get_json()
        self.assertEqual(meta["reviewed"], second)
        self.assertTrue(second["approved"])

    def test_approved_is_optional_and_defaults_to_null(self):
        body = self.created()
        reviewed = self.review(body).get_json()["reviewed"]
        self.assertIsNone(reviewed["approved"])

    def test_approved_must_be_a_boolean(self):
        body = self.created()
        self.assertEqual(self.review(body, approved="yes").status_code, 400)

    def test_only_the_creator_can_review(self):
        body = self.created()
        self.assertEqual(self.review(body, key=self.raw_b).status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/reports/{body['id']}/review",
                                           headers={"X-Forwarded-For": self.IP}).status_code, 401)

    def test_unknown_report_is_404(self):
        self.assertEqual(self.client.post(f"/api/v1/reports/{'a' * 64}/review", headers=self.h()).status_code, 404)

    def test_query_form_used_behind_vercel_rewrites(self):
        body = self.created()
        r = self.client.post(f"/api/v1/reports?digest={body['id']}&review=true", json={"approved": True}, headers=self.h())
        self.assertEqual(r.status_code, 200)

    def test_expired_report_cannot_be_reviewed(self):
        body = self.created()
        with patch("analystos.api_v1.blueprint.time.time", return_value=time.time() + 40 * 86400):
            r = self.review(body)
        self.assertEqual(r.status_code, 410)

    def test_reviews_are_audited(self):
        body = self.created()
        self.review(body, approved=True)
        reviews = [e for e in self.store.read_audit() if e["type"] == "review"]
        self.assertEqual([(e["caller"], e["approved"]) for e in reviews], [("agent-a", True)])


class LinksTest(ApiTestCase):
    def link(self, body, key=None, **payload):
        payload = {"id": body["id"], **payload}
        return self.client.post("/api/v1/links", json=payload, headers=self.h(key))

    def test_a_signed_link_works_without_a_key(self):
        body = self.created()
        made = self.link(body, format="html", ttl_seconds=3600)
        self.assertEqual(made.status_code, 201)
        url = made.get_json()["url"]
        self.assertTrue(url.startswith("http://localhost/api/v1/reports/"))
        path = url[len("http://localhost"):]
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"<!doctype html", r.get_data().lower())
        self.assertEqual([e["via"] for e in self.store.read_audit() if e["type"] == "view"], ["link"])

    def test_a_link_is_scoped_to_its_format_and_report(self):
        one, two = self.created(), self.created()
        path = self.link(one, format="html")
        path = path.get_json()["url"][len("http://localhost"):]
        self.assertEqual(self.client.get(path.replace("format=html", "format=pdf")).status_code, 403)
        self.assertEqual(self.client.get(path.replace(one["id"], two["id"])).status_code, 403)
        self.assertEqual(self.client.get(path[:-1] + ("0" if path[-1] != "0" else "1")).status_code, 403)

    def test_expired_links_are_refused(self):
        body = self.created()
        path = self.link(body, format="seal", ttl_seconds=60).get_json()["url"][len("http://localhost"):]
        with patch("analystos.api_v1.links.time.time", return_value=time.time() + 3600):
            r = self.client.get(path)
        self.assertEqual((r.status_code, r.get_json()["error"]["code"]), (410, "link_expired"))

    def test_link_ttl_is_bounded_and_capped_to_the_reports_life(self):
        body = self.created()
        self.assertEqual(self.link(body, ttl_seconds=5).status_code, 400)
        self.assertEqual(self.link(body, ttl_seconds=10**9).status_code, 400)
        self.assertEqual(self.link(body, format="zip").status_code, 400)
        with patch.dict(os.environ, {store_mod.TTL_ENV: "0.001"}):
            short = self.created()
        made = self.link(short, ttl_seconds=604800).get_json()
        exp = int(re.search(r"exp=(\d+)", made["url"]).group(1))
        self.assertLessEqual(exp, int(self.store.meta(short["id"])["expires_ts"]))

    def test_only_the_creator_can_issue_a_link_and_a_secret_is_required(self):
        body = self.created()
        self.assertEqual(self.link(body, key=self.raw_b).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/links", json={"id": body["id"]}).status_code, 401)
        with patch.dict(os.environ, {links.SECRET_ENV: ""}):
            self.assertEqual(self.link(body).status_code, 503)
            path = f"/api/v1/reports/{body['id']}?format=html&exp=9999999999&sig=abc"
            self.assertEqual(self.client.get(path).status_code, 503)

    def test_public_base_url_override(self):
        body = self.created()
        with patch.dict(os.environ, {"ANALYSTOS_PUBLIC_BASE_URL": "https://analystos.dev/"}):
            url = self.link(body).get_json()["url"]
        self.assertTrue(url.startswith("https://analystos.dev/api/v1/reports/"))

    def test_bad_bodies(self):
        self.assertEqual(self.client.post("/api/v1/links", data="nope", headers=self.h()).status_code, 400)
        self.assertEqual(self.client.post("/api/v1/links", json={"id": "x" * 64}, headers=self.h()).status_code, 404)

    def test_link_primitives(self):
        exp, sig = links.sign("k", "d" * 64, "html", 60, now=1000)
        self.assertEqual(links.check("k", "d" * 64, "html", exp, sig, now=1001), "ok")
        self.assertEqual(links.check("k", "d" * 64, "html", exp, sig, now=1060), "expired")
        self.assertEqual(links.check("k", "d" * 64, "pdf", exp, sig, now=1001), "invalid")
        self.assertEqual(links.check("other", "d" * 64, "html", exp, sig, now=1001), "invalid")
        self.assertEqual(links.check("k", "d" * 64, "html", "abc", sig), "invalid")
        self.assertEqual(links.check("k", "d" * 64, "html", exp, None), "invalid")


class VerifyTest(ApiTestCase):
    def test_public_metadata_only(self):
        body = self.created()
        r = self.client.get(f"/api/v1/verify/{body['id']}")
        meta = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(meta["payload"], body["seal"]["payload"])
        self.assertEqual(meta["signature"]["public_key"], self.seal_pub)
        text = json.dumps(meta)
        self.assertNotIn("facts", meta)
        self.assertNotIn("Q3 2026 Revenue", text)
        self.assertNotIn("html", meta)
        self.assertEqual(self.client.get(f"/api/v1/verify?digest={body['id']}").status_code, 200)

    def test_unknown_expired_and_malformed(self):
        self.assertEqual(self.client.get(f"/api/v1/verify/{'a' * 64}").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/verify?digest=../x").status_code, 404)
        body = self.created()
        with patch("analystos.api_v1.blueprint.time.time", return_value=time.time() + 40 * 86400):
            r = self.client.get(f"/api/v1/verify/{body['id']}")
        self.assertEqual(r.status_code, 410)

    def test_posting_a_bundle_verifies_it_statelessly(self):
        body = self.created()
        r = self.client.post("/api/v1/verify", json={"bundle": body["seal"], "public_key": self.seal_pub})
        out = r.get_json()
        self.assertEqual((out["ok"], out["authentic"]), (True, True))
        tampered = copy.deepcopy(body["seal"])
        tampered["facts"][0]["record"]["value"] = "1.0"
        bad = self.client.post("/api/v1/verify", json={"bundle": tampered}).get_json()
        self.assertFalse(bad["ok"])

    def test_bad_verify_bodies(self):
        for payload in ({}, {"bundle": "x"}, {"bundle": {}, "public_key": 3}):
            self.assertEqual(self.client.post("/api/v1/verify", json=payload).status_code, 400 if payload != {"bundle": {}, "public_key": 3} else 400)
        self.assertEqual(self.client.post("/api/v1/verify", data="not json").status_code, 400)
        self.assertEqual(self.client.post("/api/v1/verify", json={"bundle": {}}).get_json()["ok"], False)


class PrivacyAndRetentionTest(ApiTestCase):
    def test_the_upload_is_deleted_and_the_audit_log_holds_no_content(self):
        marker_csv = CSV + f"note,{SECRET_WORDS}\n"
        before = set(Path(tempfile.gettempdir()).glob("analystos-*"))
        self.created(content=marker_csv, name="secret-filename-XYZ.csv")
        after = set(Path(tempfile.gettempdir()).glob("analystos-*"))
        self.assertEqual(after - before, set())
        log = (Path(os.environ[store_mod.STORE_ENV]) / "audit.jsonl").read_text()
        for forbidden in (SECRET_WORDS, "secret-filename-XYZ", "402000000", "Revenue"):
            self.assertNotIn(forbidden, log)
        event = json.loads(log.splitlines()[0])
        self.assertEqual(set(event), {"ts", "type", "caller", "id", "tier", "fallback_reason", "proposed", "verified",
                                      "dropped", "signed", "seal_ok", "extension", "model"})

    def test_reports_expire_and_are_purged(self):
        body = self.created()
        with patch.dict(os.environ, {store_mod.TTL_ENV: "30"}):
            with patch("analystos.api_v1.blueprint.time.time", return_value=time.time() + 31 * 86400):
                r = self.client.get(body["links"]["report"], headers=self.h())
                self.assertEqual((r.status_code, r.get_json()["error"]["code"]), (410, "expired"))
        removed = self.store.purge_expired(now=time.time() + 31 * 86400)
        self.assertEqual(removed, 1)
        self.assertIsNone(self.store.meta(body["id"]))
        self.assertEqual(self.client.get(body["links"]["report"], headers=self.h()).status_code, 404)

    def test_ttl_config(self):
        self.assertEqual(store_mod.ttl_days({}), 30)
        self.assertEqual(store_mod.ttl_days({store_mod.TTL_ENV: "7"}), 7.0)
        self.assertEqual(store_mod.ttl_days({store_mod.TTL_ENV: "junk"}), 30)
        self.assertEqual(store_mod.ttl_days({store_mod.TTL_ENV: "-1"}), 30)

    def test_no_store_sends_the_audit_line_to_stderr(self):
        with patch.dict(os.environ, {store_mod.STORE_ENV: ""}):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                data = {"file": (io.BytesIO(CSV.encode()), "a.csv")}
                self.client.post("/api/v1/analyses", data=data, headers=self.h(), content_type="multipart/form-data")
        lines = [l for l in err.getvalue().splitlines() if l.startswith('{"audit"')]
        self.assertEqual(json.loads(lines[0])["audit"]["type"], "analysis")

    def test_store_rejects_path_tricks(self):
        for bad in ("../x", "", None, "g" * 64):
            with self.assertRaises(ValueError):
                self.store._dir(bad)


class MeasuresTest(unittest.TestCase):
    EVENTS = [
        {"type": "analysis", "tier": "written", "proposed": 10, "dropped": 1, "seal_ok": True},
        {"type": "analysis", "tier": "deterministic", "proposed": 30, "dropped": 3, "seal_ok": True},
        {"type": "analysis", "tier": "plain", "proposed": 20, "dropped": 6, "seal_ok": False},
        {"type": "view"}, {"type": "link"},
    ]

    def test_the_three_charter_measures_from_a_known_log(self):
        m = measures(self.EVENTS)
        self.assertEqual((m["analysis"]["numerator"], m["analysis"]["denominator"]), (1, 3))
        self.assertEqual((m["verification"]["numerator"], m["verification"]["denominator"]), (10, 60))
        self.assertEqual((m["evidence"]["numerator"], m["evidence"]["denominator"]), (2, 3))
        self.assertAlmostEqual(m["verification"]["share"], 1 / 6)

    def test_an_empty_log_is_none_not_a_made_up_hundred_percent(self):
        self.assertTrue(all(v["share"] is None for v in measures([]).values()))

    def test_measure_text_matches_the_published_charter(self):
        charter = json.loads((REPO / "site" / ".well-known" / "flashyos-charter.json").read_text())
        published = {r["name"]: r["measure"] for r in charter["roles"]}
        computed = {k: v["measure"] for k, v in measures([]).items()}
        self.assertEqual(published, computed)

    def test_cli(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp, "audit.jsonl")
            log.write_text("\n".join(json.dumps(e) for e in MeasuresTest.EVENTS))
            self.assertEqual(cli_main(["measures", str(log)], stdout=out), 0)
            self.assertEqual(json.loads(out.getvalue())["analysis"]["denominator"], 3)
            self.assertEqual(cli_main(["measures", str(Path(tmp, "nope"))], stdout=io.StringIO()), 2)
        key_out = io.StringIO()
        self.assertEqual(cli_main(["newkey", "demo"], stdout=key_out), 0)
        self.assertIn("aos_", key_out.getvalue())
        self.assertEqual(cli_main(["newkey", "Bad Name"], stdout=io.StringIO()), 2)
        self.assertEqual(cli_main([], stdout=io.StringIO()), 2)


class DiscoveryTest(ApiTestCase):
    def test_index_links_resolve(self):
        index = self.client.get("/api/v1").get_json()
        self.assertEqual(index["openapi"], "/api/v1/openapi.json")
        self.assertEqual(self.client.get(index["openapi"]).status_code, 200)
        self.assertEqual({(e["method"], e["path"]) for e in index["endpoints"]}, {
            ("POST", "/api/v1/analyses"), ("POST", "/api/v1/jobs"), ("POST", "/api/v1/jobs/{id}/run"),
            ("GET", "/api/v1/jobs/{id}"), ("GET", "/api/v1/reports/{id}"), ("POST", "/api/v1/reports/{id}/review"),
            ("POST", "/api/v1/links"), ("GET", "/api/v1/verify/{id}"), ("POST", "/api/v1/verify")})

    def test_openapi_covers_every_route_and_method(self):
        spec = build_openapi()
        self.assertTrue(spec["openapi"].startswith("3.1"))
        documented = {(path, method.upper()) for path, item in spec["paths"].items() for method in item}
        # bare rewrite-landing paths, documented at their pretty ({id}) form instead
        landing = {("/api/v1/openapi", "GET"), ("/api/v1/reports", "GET"), ("/api/v1/reports", "POST"),
                   ("/api/v1/jobs", "GET")}
        served = set()
        for rule in app.url_map.iter_rules():
            if not str(rule).startswith("/api/v1"):
                continue
            path = re.sub(r"<[a-z]+>", "{id}", str(rule))
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                if (path, method) not in landing:
                    served.add((path, method))
        served.discard(("/api/v1/verify", "GET"))
        self.assertEqual(served - documented, set(), "routes with no OpenAPI entry")
        self.assertEqual(documented - served, set(), "OpenAPI entries with no route")

    def test_openapi_is_self_consistent(self):
        spec = build_openapi()
        text = json.dumps(spec)
        for ref in set(re.findall(r'"\$ref": "#/components/schemas/(\w+)"', text)):
            self.assertIn(ref, spec["components"]["schemas"])
        for path, item in spec["paths"].items():
            for method, op in item.items():
                self.assertIn("operationId", op, (path, method))
                self.assertTrue(op["responses"], (path, method))
        ids = [op["operationId"] for item in spec["paths"].values() for op in item.values()]
        self.assertEqual(len(ids), len(set(ids)))


class VercelDoorsTest(unittest.TestCase):
    """The production bug from Slice 20: Vercel routes one file to one path,
    so every route needs a door file - and pretty URLs need rewrites."""

    def test_every_route_has_a_door_file(self):
        base_paths = set()
        for rule in app.url_map.iter_rules():
            path = str(rule)
            if path.startswith("/api/v1"):
                path = re.sub(r"/<[a-z]+>.*$", "", path)  # a dynamic segment, and anything after it, rewrites onto its bare door
                base_paths.add(path.replace(".json", ""))
        for path in sorted(base_paths):
            relative = path[len("/api/"):] or ""
            door = REPO / "api" / (relative + ".py") if relative != "v1" else REPO / "api" / "v1" / "index.py"
            with self.subTest(path=path):
                self.assertTrue(door.is_file(), f"{path} has no Vercel door at {door}")
                self.assertIn("from api.analyze import app", door.read_text())

    def test_pretty_urls_are_rewritten_to_the_doors(self):
        config = json.loads((REPO / "vercel.json").read_text())
        rewrites = {r["source"]: r["destination"] for r in config["rewrites"]}
        self.assertEqual(rewrites["/api/v1/openapi.json"], "/api/v1/openapi")
        self.assertEqual(rewrites["/api/v1/reports/:digest"], "/api/v1/reports?digest=:digest")
        self.assertEqual(rewrites["/api/v1/reports/:digest/review"], "/api/v1/reports?digest=:digest&review=true")
        self.assertEqual(rewrites["/api/v1/verify/:digest"], "/api/v1/verify?digest=:digest")
        self.assertEqual(rewrites["/api/v1/jobs/:job"], "/api/v1/jobs?id=:job")
        self.assertEqual(rewrites["/api/v1/jobs/:job/run"], "/api/v1/jobs?id=:job&run=true")

    def test_the_old_routes_still_exist(self):
        rules = {str(r) for r in app.url_map.iter_rules()}
        self.assertTrue({"/api/analyze", "/api/extract"} <= rules)

    def test_v1_shares_the_per_ip_limiter(self):
        client = app.test_client()
        with patch.dict(os.environ, {"ANALYSTOS_RATE_LIMIT_MAX": "2", "ANALYSTOS_RATE_LIMIT_WINDOW_SECONDS": "600"}):
            codes = [client.get("/api/v1", headers={"X-Forwarded-For": "203.0.113.77"}).status_code for _ in range(4)]
        self.assertEqual(codes[:2], [200, 200])
        self.assertEqual(codes[2:], [429, 429])


if __name__ == "__main__":
    unittest.main()
