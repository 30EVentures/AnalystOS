"""Slice 89 - tools/smoke.py --deployed compares the live bytes with the repository's, against a local
http.server fixture. No real network."""

import io
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import smoke  # noqa: E402

FILES = {
    "robots.txt": b"User-agent: *\nAllow: /\n",
    "llms.txt": b"# AnalystOS\n",
    ".well-known/api-catalog": b'{"linkset":[]}\n',
    "docs/api.md": b"# API\n",
}


class Fixture(BaseHTTPRequestHandler):
    behaviours = {}
    seen_headers = []
    other_host_url = ""

    def log_message(self, *args):
        pass

    def do_GET(self):
        Fixture.seen_headers.append(dict(self.headers))
        kind = Fixture.behaviours.get(self.path, "same")
        name = "index.html" if self.path == "/" else self.path.lstrip("/")
        body = FILES.get(name, b"")
        if kind == "same":
            return self.send(200, body)
        if kind == "differs":
            return self.send(200, body + b"edited\n")
        if kind == "404":
            return self.send(404, b"nope")
        if kind == "500":
            return self.send(500, b"boom")
        if kind == "timeout":
            time.sleep(1.5)
            return self.send(200, body)
        if kind == "other-host":
            return self.redirect(Fixture.other_host_url + self.path)
        if kind == "same-host-redirect":
            Fixture.behaviours[self.path + "?r"] = "same"
            return self.redirect(self.path.rstrip("/") + "/real")
        if kind == "loop":
            return self.redirect(self.path)
        if kind == "oversize":
            return self.send(200, b"x" * 5000)
        if kind == "gzip":
            return self.send(200, body, {"Content-Encoding": "gzip"})
        if kind == "truncated":
            self.send_response(200)
            self.send_header("Content-Length", str(len(body) + 50))
            self.end_headers()
            self.wfile.write(body)
            return
        return self.send(200, body)

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send(self, status, body, headers=None):
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class DeployedBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        Fixture.other_host_url = f"http://localhost:{cls.port}"  # same server, different host name
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Fixture.behaviours, Fixture.seen_headers = {}, []
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.site = Path(self._tmp.name)
        for name, body in FILES.items():
            path = self.site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)

    def states(self, **kw):
        kw.setdefault("timeout", 0.5)
        return {r["path"]: r["state"] for r in smoke.check_deployed(self.base, site=self.site, **kw)}

    def one(self, behaviour, **kw):
        Fixture.behaviours = {"/robots.txt": behaviour}
        return self.states(**kw)["/robots.txt"]


class StatesTest(DeployedBase):
    def test_identical_bytes_are_same(self):
        states = self.states()
        self.assertEqual(set(states.values()), {"SAME"})
        self.assertEqual(set(states), {"/robots.txt", "/llms.txt", "/.well-known/api-catalog", "/docs/api.md"})

    def test_different_bytes_differ(self):
        self.assertEqual(self.one("differs"), "DIFFERS")

    def test_not_found_and_server_errors_are_refused_not_differs(self):
        self.assertEqual(self.one("404"), "REFUSED")
        self.assertEqual(self.one("500"), "REFUSED")

    def test_a_timeout_is_unreachable(self):
        self.assertEqual(self.one("timeout", timeout=0.3), "UNREACHABLE")

    def test_nothing_listening_is_unreachable(self):
        rows = smoke.check_deployed("http://127.0.0.1:1", site=self.site, timeout=0.5)
        self.assertEqual({r["state"] for r in rows}, {"UNREACHABLE"})

    def test_a_truncated_body_is_unreachable_not_differs(self):
        self.assertEqual(self.one("truncated"), "UNREACHABLE")

    def test_a_redirect_to_another_host_is_refused_and_not_followed(self):
        self.assertEqual(self.one("other-host"), "REFUSED")
        # the fixture would have answered a followed request for the target; count how many requests hit robots.txt
        hits = [h for h in Fixture.seen_headers if h.get("Host", "").startswith("localhost")]
        self.assertEqual(hits, [], "the redirect to another host was followed")

    def test_a_redirect_loop_is_refused(self):
        self.assertEqual(self.one("loop"), "REFUSED")

    def test_an_oversize_body_is_refused(self):
        self.assertEqual(self.one("oversize", max_bytes=1000), "REFUSED")
        self.assertEqual(self.one("oversize", max_bytes=10_000), "DIFFERS")

    def test_an_unrequested_content_encoding_is_refused(self):
        self.assertEqual(self.one("gzip"), "REFUSED")

    def test_every_state_is_distinct_in_one_run(self):
        Fixture.behaviours = {"/robots.txt": "differs", "/llms.txt": "404", "/docs/api.md": "timeout"}
        states = self.states(timeout=0.3)
        self.assertEqual(states, {"/robots.txt": "DIFFERS", "/llms.txt": "REFUSED", "/docs/api.md": "UNREACHABLE", "/.well-known/api-catalog": "SAME"})

    def test_no_credentials_or_cookies_are_sent_and_raw_bytes_are_requested(self):
        self.states()
        self.assertTrue(Fixture.seen_headers)
        for headers in Fixture.seen_headers:
            lowered = {k.lower() for k in headers}
            self.assertFalse(lowered & {"authorization", "cookie", "proxy-authorization", "x-api-key"}, headers)
            self.assertEqual(headers.get("Accept-Encoding"), "identity")


class CommandLineTest(DeployedBase):
    def run_main(self, *args, site=None):
        out = io.StringIO()
        with patch.object(smoke, "SITE_DIR", site or self.site), patch.object(smoke, "DEPLOYED_TIMEOUT", 0.5):
            code = smoke.main([self.base, "--deployed", *args], stdout=out)
        return code, out.getvalue()

    def test_exit_zero_only_when_every_file_is_same(self):
        code, text = self.run_main()
        self.assertEqual(code, 0, text)
        self.assertIn("4 SAME, 0 DIFFERS, 0 UNREACHABLE, 0 REFUSED of 4", text)

    def test_any_other_state_is_a_nonzero_exit(self):
        for behaviour in ("differs", "404", "other-host", "timeout"):
            Fixture.behaviours = {"/llms.txt": behaviour}
            code, text = self.run_main()
            self.assertEqual(code, 1, behaviour + text)

    def test_checking_zero_files_is_a_failure(self):
        with tempfile.TemporaryDirectory() as empty:
            code, text = self.run_main(site=Path(empty))
        self.assertEqual(code, 1)
        self.assertIn("no files to check", text)

    def test_json_output_carries_counts_and_never_collapses_states(self):
        Fixture.behaviours = {"/robots.txt": "differs", "/llms.txt": "404"}
        code, text = self.run_main("--json")
        data = json.loads(text)
        self.assertEqual((code, data["ok"]), (1, False))
        self.assertEqual(data["counts"], {"SAME": 2, "DIFFERS": 1, "UNREACHABLE": 0, "REFUSED": 1})

    def test_an_unverifiable_certificate_is_a_clear_exit_2_never_a_pass(self):
        def refuse(*args, **kwargs):
            raise smoke.TlsUnverifiable("certificate verify failed")
        out = io.StringIO()
        with patch.object(smoke, "fetch_live", refuse):
            self.assertEqual(smoke.main([self.base, "--deployed"], stdout=out), 2)
        self.assertIn("never disabled", out.getvalue())

    def test_it_cannot_be_combined_with_the_other_modes(self):
        out = io.StringIO()
        self.assertEqual(smoke.main([self.base, "--deployed", "--no-post"], stdout=out), 2)
        self.assertEqual(smoke.main([self.base, "--deployed", "--seal", "x.json"], stdout=out), 2)
        self.assertIn("usage", out.getvalue())


class RealSiteFilesTest(unittest.TestCase):
    def test_the_real_file_list_covers_the_machine_files(self):
        paths = {p for p, _ in smoke.deployed_files()}
        for wanted in ("/robots.txt", "/sitemap.xml", "/llms.txt", "/llms-full.txt", "/.well-known/api-catalog",
                       "/.well-known/flashyos.json", "/.well-known/flashyos-charter.json", "/flashyos.roles.json", "/docs/seal.md", "/"):
            self.assertIn(wanted, paths)
        for p, file in smoke.deployed_files():
            self.assertTrue(file.is_file())

    def test_every_well_known_file_is_included(self):
        on_disk = {"/.well-known/" + p.name for p in (ROOT / "site" / ".well-known").iterdir() if p.is_file()}
        self.assertLessEqual(on_disk, {p for p, _ in smoke.deployed_files()})


if __name__ == "__main__":
    unittest.main()
