"""Generate the machine-facing files under ``site/`` from ``docs/`` (Slice 62).

    python3 tools/build_site_machine.py           # write
    python3 tools/build_site_machine.py --check   # exit 1 if anything is stale

Single source: ``docs/*.md``. Generated (never hand-edited): ``site/docs/*.md``,
``site/llms.txt``, ``site/llms-full.txt``, ``site/sitemap.xml``,
``site/robots.txt`` and ``site/.well-known/api-catalog``.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://analystos.dev"

# (file in docs/, title, one-line description) - order is the order in llms.txt
GUIDES = [
    ("api.md", "API guide", "Endpoints, auth, configuration and limits of /api/v1"),
    ("seal.md", "Seal specification", "How a report is sealed and how anyone re-verifies it offline; includes a worked test vector"),
    ("aao.md", "AAO charter checking", "The FlashyOS AAO 0.1 charter checker, its rule codes and its limits"),
    ("mesh-identity.md", "Mesh identity", "The handshake and charter AnalystOS publishes, and what it does not"),
    ("architecture.md", "Architecture", "The layer model (L0-L6) and what is built"),
    ("using-analystos.md", "Using AnalystOS", "Running it yourself from the command line"),
    ("hiring-api.md", "Hiring API guide", "Hire a role through /api/v2: questions, a budget that only narrows, usage and the receipt"),
]




_NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _role_count_words():
    """The served charter's role count, in words. It read "three" after the
    charter grew to seven roles (Slice 103); derived now, so it cannot lag."""
    path = ROOT / "site" / ".well-known" / "flashyos-charter.json"
    if not path.is_file():
        return "its"  # no charter to count: "AAO 0.1, its roles, each with a measure"
    n = len(json.loads(path.read_text(encoding="utf-8"))["roles"])
    return _NUMBER_WORDS[n] if n < len(_NUMBER_WORDS) else str(n)

def _guide_line(name):
    """The llms.txt link line for one guide, looked up by file name, not position, so
    adding a guide cannot shift the FlashyOS section (which the Slice 107 fence pins)."""
    title, description = next((t, d) for n, t, d in GUIDES if n == name)
    return f"- [{title}]({BASE}/docs/{name}): {description}"


SUMMARY = (
    "Reads a source document and returns a report in which every figure is a verified quote "
    "or an independently recomputed calculation, sealed so anyone can re-verify it offline. "
    "Early stage: use non-confidential documents only."
)


def generated_files():
    """``{relative path under site/: text}``."""
    out = {}
    for name, _, _ in GUIDES:
        out[f"docs/{name}"] = (ROOT / "docs" / name).read_text(encoding="utf-8")

    lines = [f"# AnalystOS", "", f"> {SUMMARY}", ""]
    lines += ["## API", "",
              f"- [OpenAPI 3.1]({BASE}/api/v1/openapi.json): every endpoint, request and response",
              f"- [API index]({BASE}/api/v1): machine-readable list of endpoints and limits",
              f"- [Role catalog]({BASE}/api/v2/catalog): every role you can hire, its limits, how it was tested, and its questions",
              f"- `POST {BASE}/api/v2/engagements`: hire a role for one problem (access code required; each request is a paid model call). "
              "The response is the role's format (its catalog `delivers_today`): .pptx, .docx or .xlsx, named in the "
              "`X-AnalystOS-Format` header; with `?format=json` it is `output` {format, media_type, filename, base64}. "
              "An optional `budget` can only narrow the limits (2 model calls, 8192 output tokens per call); every "
              "engagement taken on gets an unsigned `analystos-receipt/1` with measured usage",
              f"- `POST {BASE}/api/v2/engagements/preflight`: the same body and checks as a hire, with no model call and "
              "no access code: says whether it would be taken on, the reasons the hire would refuse it, and the most it could use",
              _guide_line("hiring-api.md"),
              f"- [{GUIDES[0][1]}]({BASE}/docs/{GUIDES[0][0]}): {GUIDES[0][2]}", ""]
    lines += ["## Verifying a report", "",
              f"- [{GUIDES[1][1]}]({BASE}/docs/{GUIDES[1][0]}): {GUIDES[1][2]}",
              f"- `POST {BASE}/api/v1/verify`: stateless verification of any seal bundle, no account"]
    # Only advertised once the file exists: a link to a 404 is worse than no link (Slice 86).
    if (ROOT / "site" / ".well-known" / "analystos-seal-key.json").is_file():
        lines.append(f"- [Seal verification key]({BASE}/.well-known/analystos-seal-key.json): the public key seals are signed with (analystos-seal-key/1)")
    if (ROOT / "site" / ".well-known" / "jwks.json").is_file():
        lines.append(f"- [Signing keys]({BASE}/.well-known/jwks.json): the same public keys as a standard JWKS (Ed25519, kid = key_id)")
    lines.append("")
    lines += ["## Identity and the FlashyOS mesh", "",
              f"- [Handshake]({BASE}/.well-known/flashyos.json): flashyos/1",
              f"- [Charter]({BASE}/.well-known/flashyos-charter.json): AAO 0.1, {_role_count_words()} roles, each with a measure",
              _guide_line("mesh-identity.md"),
              _guide_line("aao.md"), ""]
    lines += ["## Learn", "",
              f"- [AnalystOS glossary]({BASE}/glossary.html): roles, traced figures, work products and who decides, defined plainly", ""]
    lines += ["## Limits, stated plainly", "",
              f"- [Trust and known limits]({BASE}/details.html#trust): what leaves your environment, what is and is not checked",
              "- Every figure is proven; only some relationships between figures are checked",
              "- Sealing proves a report was built from the sealed facts, not that the facts are the important ones", ""]
    lines += ["## Optional", "",
              f"- [{GUIDES[4][1]}]({BASE}/docs/{GUIDES[4][0]}): {GUIDES[4][2]}",
              f"- [{GUIDES[5][1]}]({BASE}/docs/{GUIDES[5][0]}): {GUIDES[5][2]}",
              f"- [Full documentation in one file]({BASE}/llms-full.txt)", ""]
    out["llms.txt"] = "\n".join(lines)

    full = ["# AnalystOS - full documentation", "", f"> {SUMMARY}", ""]
    for name, title, _ in GUIDES:
        full += [f"<!-- source: {BASE}/docs/{name} -->", "", (ROOT / "docs" / name).read_text(encoding="utf-8").rstrip(), "", "---", ""]
    out["llms-full.txt"] = "\n".join(full)

    urls = [f"{BASE}/", f"{BASE}/details.html", f"{BASE}/upload.html", f"{BASE}/hire.html", f"{BASE}/glossary.html",
            f"{BASE}/llms.txt", f"{BASE}/llms-full.txt",
            f"{BASE}/api/v1/openapi.json"] + [f"{BASE}/docs/{n}" for n, _, _ in GUIDES]
    out["sitemap.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    )
    # The API is not crawlable content, but its machine-readable entry points (and, since Slice 119, the
    # public role catalog in llms.txt) are advertised in the
    # sitemap, llms.txt and the api-catalog, so they are allowed by a longer (more specific) rule: the
    # longest match wins (RFC 9309), and '$' keeps "/api/v1" from opening everything below it.
    out["robots.txt"] = ("User-agent: *\nAllow: /\n"
                         "Allow: /api/v1$\nAllow: /api/v1/openapi.json$\nAllow: /api/v2/catalog$\n"
                         f"Disallow: /api/\n\nSitemap: {BASE}/sitemap.xml\n")
    out[".well-known/api-catalog"] = json.dumps({"linkset": [{
        "anchor": f"{BASE}/api/v1",
        "service-desc": [{"href": f"{BASE}/api/v1/openapi.json", "type": "application/vnd.oai.openapi+json"}],
        "service-doc": [{"href": f"{BASE}/docs/api.md", "type": "text/markdown"}],
        "status": [{"href": f"{BASE}/api/v1", "type": "application/json"}],
    }]}, indent=2) + "\n"
    return out


def main(argv=None):
    check = "--check" in (sys.argv[1:] if argv is None else argv)
    stale = []
    for rel, text in generated_files().items():
        path = ROOT / "site" / rel
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            stale.append(rel)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if check:
        print("stale: " + ", ".join(stale) if stale else "site machine files are up to date")
        return 1 if stale else 0
    print("wrote: " + ", ".join(stale) if stale else "nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
