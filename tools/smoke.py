"""Smoke-test a deployment of AnalystOS (Slice 68).

    python3 tools/smoke.py [BASE_URL] [--json] [--no-post]

Standard library plus this repository's own charter checker. Sends only GET
requests and (unless --no-post) two POSTs that carry no document, key or secret.
Exit code 0 if every check passes, 1 otherwise, 2 for bad usage or when Python
cannot verify the server's certificate (see TLS_HELP; verification is never disabled).
"""

import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from analystos.aao.validate import errors, validate_charter  # noqa: E402

DEFAULT_BASE = "https://analystos.dev"
JSON_CT = "application/json"

# (path, content-type prefix) - what a deployment must serve
STATIC = [
    ("/", "text/html"), ("/upload.html", "text/html"),
    ("/llms.txt", "text/plain"), ("/llms-full.txt", "text/plain"), ("/robots.txt", "text/plain"),
    ("/sitemap.xml", "application/xml"),
    ("/.well-known/flashyos.json", JSON_CT), ("/.well-known/flashyos-charter.json", JSON_CT),
    ("/flashyos.roles.json", JSON_CT), ("/.well-known/api-catalog", "application/linkset+json"),
    ("/docs/api.md", "text/markdown"), ("/docs/seal.md", "text/markdown"), ("/docs/aao.md", "text/markdown"),
    ("/docs/mesh-identity.md", "text/markdown"), ("/docs/architecture.md", "text/markdown"),
    ("/docs/using-analystos.md", "text/markdown"),
    ("/api/v1", JSON_CT), ("/api/v1/openapi.json", JSON_CT),
]
UNKNOWN_ID = "a" * 64


class TlsUnverifiable(Exception):
    """Python could not verify the server's certificate. Almost always this
    machine's Python has no CA bundle (the python.org macOS build), not a
    problem with the site - so it is reported once, clearly, never as 30
    failed checks and never by turning verification off."""


TLS_HELP = (
    "Python could not verify the server's TLS certificate.\n"
    "This is usually the machine, not the site: the python.org macOS build ships without CA\n"
    "certificates. Either run '/Applications/Python 3.*/Install Certificates.command', or point\n"
    "Python at the system bundle for this run:\n"
    "    SSL_CERT_FILE=/etc/ssl/cert.pem python3 tools/smoke.py\n"
    "Certificate verification is never disabled by this script.\n"
)


class Response:
    def __init__(self, status, content_type, body):
        self.status, self.content_type, self.body = status, content_type or "", body

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    def text(self):
        return self.body.decode("utf-8", errors="replace")


def fetch(base, path, method="GET", data=None, headers=None, timeout=30):
    request = urllib.request.Request(base.rstrip("/") + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return Response(resp.status, resp.headers.get("Content-Type"), resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return Response(exc.code, exc.headers.get("Content-Type"), exc.read())
        finally:
            exc.close()
    except (urllib.error.URLError, OSError) as exc:
        if isinstance(getattr(exc, "reason", exc), ssl.SSLCertVerificationError):
            raise TlsUnverifiable(str(exc)) from exc
        return Response(0, "", str(exc).encode())


class Smoke:
    def __init__(self, base, allow_post=True):
        self.base, self.allow_post, self.results, self.cache = base.rstrip("/"), allow_post, [], {}

    def get(self, path):
        if path not in self.cache:
            self.cache[path] = fetch(self.base, path)
        return self.cache[path]

    def record(self, name, ok, detail=""):
        self.results.append({"check": name, "ok": bool(ok), "detail": "" if ok else detail})
        return ok

    def guarded(self, name, fn):
        try:
            fn()
        except TlsUnverifiable:
            raise
        except Exception as exc:  # a check that crashes is a failed check, not a crashed run
            self.record(name, False, f"check raised {type(exc).__name__}: {exc}")

    # -- checks ---------------------------------------------------------------
    def check_static(self):
        for path, content_type in STATIC:
            r = self.get(path)
            self.record(f"GET {path} -> 200 {content_type}",
                        r.status == 200 and r.content_type.lower().startswith(content_type),
                        f"got status {r.status}, content-type {r.content_type!r}")

    def check_mesh_identity(self):
        charter, roles = self.get("/.well-known/flashyos-charter.json"), self.get("/flashyos.roles.json")
        handshake = self.get("/.well-known/flashyos.json")
        self.record("charter served at both paths is byte-identical", charter.body == roles.body and charter.status == 200,
                    "the two charter paths differ or are missing")

        def charter_valid():
            problems = errors(validate_charter(charter.json()))
            self.record("live charter passes analystos.aao", not problems, f"{[p.code for p in problems]}")
        self.guarded("live charter passes analystos.aao", charter_valid)

        def slugs():
            hs, ch = handshake.json(), charter.json()
            self.record("handshake mesh is flashyos/1 and its slug equals the charter's",
                        hs.get("mesh") == "flashyos/1" and hs.get("org", {}).get("slug") == ch.get("slug"),
                        f"handshake={hs.get('org')}, charter slug={ch.get('slug')}")
        self.guarded("handshake mesh is flashyos/1 and its slug equals the charter's", slugs)

    def check_links(self):
        llms = self.get("/llms.txt").text()
        links = re.findall(r"\]\((https?://[^)]+)\)", llms)
        self.record("llms.txt lists links", len(links) >= 8, f"only {len(links)} links found")
        origin = re.match(r"https?://[^/]+", self.base + "/").group(0)
        for link in links:
            path = re.sub(r"^https?://[^/]+", "", link).split("#")[0] or "/"
            if link.startswith("https://analystos.dev") or link.startswith(origin):
                r = self.get(path)
                self.record(f"llms.txt link {path} resolves", r.status == 200, f"status {r.status}")
        sitemap = self.get("/sitemap.xml").text()
        for url in re.findall(r"<loc>([^<]+)</loc>", sitemap):
            path = re.sub(r"^https?://[^/]+", "", url) or "/"
            r = self.get(path)
            self.record(f"sitemap URL {path} resolves", r.status == 200, f"status {r.status}")

    def check_api_discovery(self):
        def index():
            idx, spec = self.get("/api/v1").json(), self.get("/api/v1/openapi.json").json()
            self.record("api index names an OpenAPI document that is served", idx.get("openapi") == "/api/v1/openapi.json"
                        and spec.get("openapi", "").startswith("3."), f"index={idx.get('openapi')}, spec={spec.get('openapi')}")
            documented = {p for p in spec.get("paths", {})}
            listed = {e["path"] for e in idx.get("endpoints", [])}
            self.record("every endpoint the index lists is in the OpenAPI document", listed <= documented,
                        f"not documented: {sorted(listed - documented)}")
        self.guarded("api discovery", index)
        catalog = self.get("/.well-known/api-catalog")

        def cat():
            entry = catalog.json()["linkset"][0]
            self.record("api-catalog points at the OpenAPI document", entry["service-desc"][0]["href"].endswith("/api/v1/openapi.json"))
        self.guarded("api-catalog points at the OpenAPI document", cat)

    def check_rewrites_fail_closed(self):
        for label, path in (("pretty verify path", f"/api/v1/verify/{UNKNOWN_ID}"),
                            ("query verify form", f"/api/v1/verify?digest={UNKNOWN_ID}"),
                            ("pretty reports path", f"/api/v1/reports/{UNKNOWN_ID}"),
                            ("query reports form", f"/api/v1/reports?digest={UNKNOWN_ID}")):
            r = fetch(self.base, path)
            reached_app = r.content_type.lower().startswith(JSON_CT) and r.status in (401, 404, 410, 503)
            self.record(f"{label} reaches the app and fails closed", reached_app,
                        f"status {r.status}, content-type {r.content_type!r} (expected a JSON 401/404/410/503)")

    def check_posts(self):
        if not self.allow_post:
            return
        r = fetch(self.base, "/api/v1/analyses", method="POST", data=b"", headers={"Content-Type": "multipart/form-data; boundary=x"})
        self.record("an analysis without a key is refused (401 or 503)", r.status in (401, 503),
                    f"status {r.status}: an unauthenticated analysis must never succeed or crash")
        v = fetch(self.base, "/api/v1/verify", method="POST", data=b'{"bundle": {}}', headers={"Content-Type": "application/json"})

        def junk():
            self.record("verifying a junk bundle answers ok:false", v.status == 200 and v.json().get("ok") is False,
                        f"status {v.status}")
        self.guarded("verifying a junk bundle answers ok:false", junk)

    def run(self):
        for fn in (self.check_static, self.check_mesh_identity, self.check_links, self.check_api_discovery,
                   self.check_rewrites_fail_closed, self.check_posts):
            self.guarded(fn.__name__, fn)
        return self.results


def main(argv=None, stdout=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    if flags - {"--json", "--no-post"} or len(args) > 1:
        stdout.write("usage: python3 tools/smoke.py [BASE_URL] [--json] [--no-post]\n")
        return 2
    base = args[0] if args else DEFAULT_BASE
    try:
        results = Smoke(base, allow_post="--no-post" not in flags).run()
    except TlsUnverifiable as exc:
        stdout.write(TLS_HELP + f"(detail: {exc})\n")
        return 2
    failed = [r for r in results if not r["ok"]]
    if "--json" in flags:
        stdout.write(json.dumps({"base": base, "passed": len(results) - len(failed), "failed": len(failed), "results": results}, indent=2) + "\n")
    else:
        for r in results:
            stdout.write(f"{'ok  ' if r['ok'] else 'FAIL'} {r['check']}" + ("" if r["ok"] else f"\n       {r['detail']}") + "\n")
        stdout.write(f"\n{len(results) - len(failed)} passed, {len(failed)} failed against {base}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
