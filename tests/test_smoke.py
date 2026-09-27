"""Slice 68 - tools/smoke.py against a local server that mimics Vercel's routing
and header rules (from vercel.json) in front of the real Flask app. No external
network. See specs/slice-68/spec.md."""

import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from wsgiref.simple_server import WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import smoke  # noqa: E402

from api.analyze import app as flask_app  # noqa: E402


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


class MiniVercel:
    """Just enough of Vercel: vercel.json rewrites and headers, static files,
    and the Flask app for /api/*. ``overrides`` maps (method, path) to a canned
    (status, content_type, body) so a test can make the 'deployment' misbehave."""

    def __init__(self, site_root, config, overrides=None):
        self.site, self.config, self.overrides = Path(site_root), config, overrides or {}

    def _rewrite(self, path, query):
        for rule in self.config.get("rewrites", []):
            pattern = re.escape(rule["source"]).replace(re.escape(":digest"), r"([0-9a-zA-Z._-]+)")
            m = re.fullmatch(pattern, path)
            if m:
                dest = rule["destination"].replace(":digest", m.group(1) if m.groups() else "")
                dpath, _, dquery = dest.partition("?")
                return dpath, "&".join(x for x in (dquery, query) if x)
        return path, query

    def _headers_for(self, path):
        out = {}
        for rule in self.config.get("headers", []):
            source = rule["source"]
            if source.endswith("(.*)"):
                hit = path.startswith(source[:-4])
            else:
                hit = path == source
            if hit:
                out.update({h["key"]: h["value"] for h in rule["headers"]})
        return out

    def __call__(self, environ, start_response):
        method, path, query = environ["REQUEST_METHOD"], environ["PATH_INFO"], environ.get("QUERY_STRING", "")
        if (method, path) in self.overrides:
            status, ctype, body = self.overrides[(method, path)]
            start_response(f"{status} X", [("Content-Type", ctype)])
            return [body if isinstance(body, bytes) else body.encode()]
        if path.startswith("/api/"):
            path, query = self._rewrite(path, query)
            # Vercel routes one file to one path: /api/x/y -> api/x/y.py, /api/x -> api/x/index.py
            rel = path[len("/api/"):].rstrip("/")
            door = ROOT / "api" / (rel + ".py")
            if not door.is_file() and not (ROOT / "api" / rel / "index.py").is_file():
                start_response("404 Not Found", [("Content-Type", "text/plain")])
                return [b"NOT_FOUND"]
            environ = dict(environ, PATH_INFO=path, QUERY_STRING=query)
            return flask_app.wsgi_app(environ, start_response)
        file = self.site / ("index.html" if path == "/" else path.lstrip("/"))
        if not file.is_file():
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"not found"]
        headers = {"Content-Type": "text/html; charset=utf-8" if file.suffix == ".html" else
                   "application/xml" if file.suffix == ".xml" else "text/plain; charset=utf-8" if file.suffix == ".txt" else "application/octet-stream"}
        headers.update(self._headers_for(path))
        start_response("200 OK", list(headers.items()))
        return [file.read_bytes()]


class Deployment:
    def __init__(self, site_root=None, config=None, overrides=None):
        self.site_root = site_root or ROOT / "site"
        self.config = config or json.loads((ROOT / "vercel.json").read_text())
        self.overrides = overrides

    def __enter__(self):
        self.server = make_server("127.0.0.1", 0, MiniVercel(self.site_root, self.config, self.overrides), handler_class=QuietHandler)
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)
        self.thread.start()
        self.env = patch.dict(os.environ, {"ANALYSTOS_RATE_LIMIT_MAX": "100000", "ANALYSTOS_API_KEYS": "", "ANALYSTOS_STORE_DIR": ""})
        self.env.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, *exc):
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()


def run(base, *flags):
    out = io.StringIO()
    code = smoke.main([base, *flags], stdout=out)
    return code, out.getvalue()


def failing(base, *flags):
    code, out = run(base, "--json", *flags)
    return code, [r["check"] for r in json.loads(out)["results"] if not r["ok"]]


class HealthyDeploymentTest(unittest.TestCase):
    def test_every_check_passes_against_the_repository_as_deployed(self):
        with Deployment() as base:
            code, failed = failing(base)
        self.assertEqual((code, failed), (0, []))

    def test_human_output_and_json_output(self):
        with Deployment() as base:
            code, text = run(base)
            _, js = run(base, "--json")
        self.assertEqual(code, 0)
        self.assertRegex(text, r"\d+ passed, 0 failed")
        data = json.loads(js)
        self.assertEqual(data["failed"], 0)
        self.assertGreater(data["passed"], 40)

    def test_the_run_covers_the_surface_that_mattered_on_deploy_day(self):
        with Deployment() as base:
            _, js = run(base, "--json")
        names = " | ".join(r["check"] for r in json.loads(js)["results"])
        for needle in ("/.well-known/flashyos.json", "api-catalog", "pretty verify path", "query reports form",
                       "without a key is refused", "passes analystos.aao", "byte-identical", "llms.txt link"):
            self.assertIn(needle, names)


class BrokenDeploymentTest(unittest.TestCase):
    def copy_site(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        shutil.copytree(ROOT / "site", Path(tmp.name) / "site")
        return Path(tmp.name) / "site"

    def test_a_missing_file_is_named(self):
        site = self.copy_site()
        (site / "llms.txt").unlink()
        with Deployment(site) as base:
            code, failed = failing(base)
        self.assertEqual(code, 1)
        self.assertIn("GET /llms.txt -> 200 text/plain", failed)

    def test_a_wrong_content_type_is_named(self):
        config = json.loads((ROOT / "vercel.json").read_text())
        for rule in config["headers"]:
            if rule["source"] == "/.well-known/flashyos-charter.json":
                for h in rule["headers"]:
                    if h["key"] == "Content-Type":
                        h["value"] = "text/plain"
        with Deployment(config=config) as base:
            code, failed = failing(base)
        self.assertEqual(code, 1)
        self.assertIn("GET /.well-known/flashyos-charter.json -> 200 application/json", failed)

    def test_an_invalid_charter_is_caught(self):
        site = self.copy_site()
        for name in (".well-known/flashyos-charter.json", "flashyos.roles.json"):
            path = site / name
            doc = json.loads(path.read_text())
            doc["roles"][0]["humanApprovalAtOrAbove"] = "NONE"
            path.write_text(json.dumps(doc))
        with Deployment(site) as base:
            code, failed = failing(base)
        self.assertEqual(code, 1)
        self.assertIn("live charter passes analystos.aao", failed)

    def test_two_charter_paths_that_differ_are_caught(self):
        site = self.copy_site()
        (site / "flashyos.roles.json").write_text((site / "flashyos.roles.json").read_text() + " ")
        with Deployment(site) as base:
            _, failed = failing(base)
        self.assertIn("charter served at both paths is byte-identical", failed)

    def test_a_handshake_with_the_wrong_slug_is_caught(self):
        site = self.copy_site()
        path = site / ".well-known" / "flashyos.json"
        doc = json.loads(path.read_text())
        doc["org"]["slug"] = "someone-else"
        path.write_text(json.dumps(doc))
        with Deployment(site) as base:
            _, failed = failing(base)
        self.assertIn("handshake mesh is flashyos/1 and its slug equals the charter's", failed)

    def test_a_dead_link_in_llms_txt_is_caught(self):
        site = self.copy_site()
        (site / "docs" / "seal.md").unlink()
        with Deployment(site) as base:
            _, failed = failing(base)
        self.assertTrue(any("llms.txt link" in c or "docs/seal.md" in c for c in failed), failed)

    def test_an_api_that_answers_200_without_a_key_is_caught(self):
        overrides = {("POST", "/api/v1/analyses"): (200, "application/json", '{"ok": true}')}
        with Deployment(overrides=overrides) as base:
            code, failed = failing(base)
        self.assertEqual(code, 1)
        self.assertIn("an analysis without a key is refused (401 or 503)", failed)

    def test_an_api_that_crashes_is_caught_not_treated_as_closed(self):
        overrides = {("POST", "/api/v1/analyses"): (500, "text/plain", "boom")}
        with Deployment(overrides=overrides) as base:
            _, failed = failing(base)
        self.assertIn("an analysis without a key is refused (401 or 503)", failed)

    def test_a_rewrite_that_does_not_reach_the_app_is_caught(self):
        config = json.loads((ROOT / "vercel.json").read_text())
        config["rewrites"] = [r for r in config["rewrites"] if ":digest" not in r["source"]]
        with Deployment(config=config) as base:
            _, failed = failing(base)
        self.assertIn("pretty verify path reaches the app and fails closed", failed)
        self.assertIn("pretty reports path reaches the app and fails closed", failed)
        self.assertNotIn("query verify form reaches the app and fails closed", failed)

    def test_a_missing_openapi_rewrite_is_caught(self):
        config = json.loads((ROOT / "vercel.json").read_text())
        config["rewrites"] = [r for r in config["rewrites"] if r["source"] != "/api/v1/openapi.json"]
        with Deployment(config=config) as base:
            _, failed = failing(base)
        self.assertIn("GET /api/v1/openapi.json -> 200 application/json", failed)

    def test_a_missing_door_file_is_caught(self):
        real = Path.is_file
        with Deployment() as base, patch.object(Path, "is_file", lambda self: False if self.name == "verify.py" and "v1" in self.parts else real(self)):
            _, failed = failing(base)
        self.assertIn("query verify form reaches the app and fails closed", failed)

    def test_an_unreachable_host_fails_every_check_and_does_not_crash(self):
        code, failed = failing("http://127.0.0.1:9")
        self.assertEqual(code, 1)
        self.assertGreater(len(failed), 10)


class TlsTest(unittest.TestCase):
    def test_an_unverifiable_certificate_is_one_clear_message_not_thirty_failures(self):
        import ssl
        import urllib.error
        error = urllib.error.URLError(ssl.SSLCertVerificationError("unable to get local issuer certificate"))
        with patch("urllib.request.urlopen", side_effect=error):
            out = io.StringIO()
            code = smoke.main(["https://example.invalid"], stdout=out)
        self.assertEqual(code, 2)
        self.assertIn("SSL_CERT_FILE", out.getvalue())
        self.assertIn("never disabled", out.getvalue())
        self.assertNotIn("FAIL", out.getvalue())

    def test_verification_is_never_switched_off_in_the_source(self):
        source = (ROOT / "tools" / "smoke.py").read_text()
        for forbidden in ("_create_unverified_context", "CERT_NONE", "check_hostname = False", "verify=False"):
            self.assertNotIn(forbidden, source)


class FlagsTest(unittest.TestCase):
    def test_no_post_sends_no_post(self):
        seen = []
        real = smoke.fetch

        def spy(base, path, method="GET", **kw):
            seen.append(method)
            return real(base, path, method=method, **kw)

        with Deployment() as base, patch.object(smoke, "fetch", spy):
            code, failed = failing(base, "--no-post")
        self.assertEqual((code, failed), (0, []))
        self.assertNotIn("POST", seen)

    def test_with_posts_exactly_two_carry_no_document_or_secret(self):
        sent = []
        real = smoke.fetch

        def spy(base, path, method="GET", data=None, headers=None, **kw):
            if method == "POST":
                sent.append((path, data, headers))
            return real(base, path, method=method, data=data, headers=headers, **kw)

        with Deployment() as base, patch.object(smoke, "fetch", spy):
            failing(base)
        self.assertEqual([p for p, _, _ in sent], ["/api/v1/analyses", "/api/v1/verify"])
        for _, data, headers in sent:
            self.assertLess(len(data), 40)
            self.assertNotIn("Authorization", headers or {})

    def test_bad_usage(self):
        out = io.StringIO()
        self.assertEqual(smoke.main(["--bogus"], stdout=out), 2)
        self.assertEqual(smoke.main(["a", "b"], stdout=out), 2)
        self.assertIn("usage", out.getvalue())


if __name__ == "__main__":
    unittest.main()
