"""Keep the 30E Ventures studio bar and footer line the same on every public page (Slice 78).

    python3 tools/studio_chrome.py            # rewrite the generated blocks
    python3 tools/studio_chrome.py --check    # exit 1 if any page differs from the source

The markup and CSS are defined once, below. Each page carries three marker pairs
(CSS in its <style>, the bar after <body>, the footer line inside <footer>); the
text between a pair is replaced, everything outside it is untouched. A page missing
a marker, or carrying one twice, is an error rather than a silent skip, so the
blocks cannot quietly stop being kept true.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "site" / "index.html", ROOT / "site" / "details.html", ROOT / "site" / "upload.html", ROOT / "site" / "hire.html"]

STUDIO = "https://www.30eventures.com"
PRODUCT = "AnalystOS"
BAR_LINKS = [("Portfolio", "/portfolio/"), ("About", "/about/"), ("Press", "/press/")]
# the footer: (heading, [(label, href, small note or "")]). Studio links are absolute; this product's links are root-relative.
FOOT_COLUMNS = [
    ("Product", [("How it works", "/#how", ""), ("Sample reports", "/#samples", ""), ("Hire a role", "/hire.html", "access code"),
                 ("Upload a document", "/upload.html", "access code"), ("Details, privacy and known limits", "/details.html", "")]),
    ("Developers", [("API reference", "/api/v1/openapi.json", "OpenAPI 3.1"), ("API guide", "/docs/api.md", ""),
                    ("Seal specification", "/docs/seal.md", "re-verify offline"), ("Role catalog", "/api/v2/catalog", "JSON"),
                    ("API catalog", "/.well-known/api-catalog", ""), ("llms.txt", "/llms.txt", "for agents")]),
    ("Learn", [("Concepts", STUDIO + "/concepts/", "verifiable by a stranger, and six more"), ("Glossary", STUDIO + "/learn/", "seal, verifier, fail closed"),
               ("Why we build", STUDIO + "/why/", ""), ("FAQ", STUDIO + "/faq/", "")]),
    ("30E Ventures", [("About the studio", STUDIO + "/about/", ""), ("Portfolio", STUDIO + "/portfolio/", ""), ("Press", STUDIO + "/press/", ""),
                      ("Brand", STUDIO + "/brand/", ""), ("Contact", STUDIO + "/contact/", "")]),
]
STATUS_NOTE = "Early stage. Not for confidential documents yet. Limits are published."

MARK = (
    '<svg class="studio-mark" viewBox="0 0 24 24" aria-hidden="true">'
    '<rect x="3" y="3" width="3" height="18" fill="#f2f6fa"/>'
    '<rect x="6" y="3" width="15" height="3" fill="#f2f6fa"/>'
    '<rect x="6" y="10.5" width="10" height="3" fill="#f2f6fa"/>'
    '<rect x="6" y="18" width="15" height="3" fill="#2fd4ff"/></svg>'
)

CSS = """.studio-bar{background:#030508;color:#e8f4ff;font:500 13px/1 system-ui,-apple-system,'Segoe UI',sans-serif;border-bottom:1px solid #16202c}
.studio-in{max-width:1100px;margin:0 auto;padding:10px 20px;display:flex;align-items:center;gap:18px}
.studio-brand{display:flex;align-items:center;gap:9px;color:#e8f4ff;text-decoration:none;font-weight:700;letter-spacing:.14em}
.studio-mark{width:16px;height:16px;flex:none}
.studio-sub{margin-left:.6em;font-weight:400;font-size:.85em;letter-spacing:.3em;color:#7d8fa3}
.studio-line{color:#7d8fa3}
.studio-links{margin-left:auto;display:flex;gap:16px}
.studio-links a{color:#e8f4ff;text-decoration:none;opacity:.85}
.studio-links a:hover,.studio-links a:focus-visible{opacity:1;text-decoration:underline}
.af{background:#0f1b2d;color:#c9d3e3;margin:64px 0 0;padding:56px 0 26px;border:0;font:400 15px/1.55 var(--sans,system-ui,-apple-system,'Segoe UI',sans-serif)}
.af-in{max-width:1100px;margin:0 auto;padding:0 20px}
.af-grid{display:grid;grid-template-columns:1.4fr repeat(4,1fr);gap:36px;padding-bottom:40px;border-bottom:1px solid #26354f}
.af-name{font:800 22px/1 var(--display,system-ui,sans-serif);letter-spacing:-.02em;color:#fff;text-decoration:none}
.af-line{font:400 18px/1.45 var(--serif,Georgia,serif);color:#fff;margin:16px 0 18px;max-width:17em}
.af-pill{display:flex;gap:8px;align-items:flex-start;background:#1a2a44;border:1px solid #2c3f60;border-radius:4px;padding:10px 12px;font-size:13.5px;line-height:1.4;color:#e8d9b0;max-width:20em}
.af-pill::before{content:"";flex:none;width:8px;height:8px;border-radius:50%;background:#e0a62e;margin-top:6px}
.af h2{font:600 12px/1 var(--sans,system-ui,sans-serif);letter-spacing:.09em;text-transform:uppercase;color:#8da0bd;margin:4px 0 18px}
.af ul{list-style:none;margin:0;padding:0}.af li{margin:0 0 11px}
.af a{color:#e8eef8;text-decoration:none}.af li a:hover,.af li a:focus-visible,.af-mid a:hover{text-decoration:underline;text-underline-offset:3px}
.af li small{display:block;color:#8da0bd;font-size:12.5px;margin-top:1px}
.af-note{padding:22px 0 0;font-size:13.5px;line-height:1.7;color:#aab8cf;max-width:70ch}
.af-note p,.af-note .fine{margin:0 0 8px;font:inherit;color:inherit;max-width:none}
.af-mid{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap;padding:22px 0;font-size:14.5px;color:#aab8cf}
.af-mid a{color:#fff}
.af-bot{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;font-size:13.5px;color:#8da0bd}
@media (max-width:900px){.af-grid{grid-template-columns:1fr 1fr}.af-grid>div:first-child{grid-column:1/-1}}
@media print{.af{background:#fff;color:#000}.af a,.af-name,.af-line{color:#000}}
@media (max-width:640px){.studio-line,.studio-sub{display:none}.studio-in{padding:9px 14px;gap:12px}.studio-links{gap:12px}}
@media print{.studio-bar{display:none}}"""


def render_bar():
    links = "".join(f'<a href="{STUDIO}{path}">{label}</a>' for label, path in BAR_LINKS)
    return (
        '<div class="studio-bar" role="navigation" aria-label="30E Ventures">'
        '<div class="studio-in">'
        f'<a class="studio-brand" href="{STUDIO}/">{MARK}<span>30E<span class="studio-sub">VENTURES</span></span></a>'
        f'<span class="studio-line">{PRODUCT} is a 30E Ventures product</span>'
        f'<span class="studio-links">{links}</span>'
        "</div></div>"
    )


NOTE_START, NOTE_END = "<!-- studio:note:start -->", "<!-- studio:note:end -->"


def render_footer(note=""):
    """The whole <footer>. ``note`` is a page's own fine print, kept between the note markers across regenerations."""
    cols = ""
    for title, items in FOOT_COLUMNS:
        lis = "".join(f'<li><a href="{href}">{label}</a>{f"<small>{small}</small>" if small else ""}</li>' for label, href, small in items)
        cols += f"<div><h2>{title}</h2><ul>{lis}</ul></div>"
    return (
        '<footer class="af"><div class="af-in"><div class="af-grid">'
        f'<div><a class="af-name" href="/">{PRODUCT}</a><p class="af-line">Every figure in the report, proven against its source.</p>'
        f'<div class="af-pill"><span>{STATUS_NOTE}</span></div></div>{cols}</div>'
        f'<div class="af-note">{NOTE_START}{note}{NOTE_END}</div>'
        f'<div class="af-mid"><span>{PRODUCT} is built by <a href="{STUDIO}/">30E Ventures</a>, a machine-native venture studio in Toronto building the agentic internet.</span>'
        "<span>Status: <b>live, early stage</b>.</span></div>"
        '<div class="af-bot"><span>&copy; 2026 30E Ventures &middot; Toronto, Canada</span><span>Use non-confidential documents only.</span></div>'
        "</div></footer>"
    )


# (name, start marker, end marker, replacement body)
def blocks(text=""):
    note = re.search(re.escape(NOTE_START) + r"(.*?)" + re.escape(NOTE_END), text, re.S)
    return [
        ("css", "/* studio:css:start */", "/* studio:css:end */", CSS),
        ("bar", "<!-- studio:bar:start -->", "<!-- studio:bar:end -->", render_bar()),
        ("footer", "<!-- studio:footer:start -->", "<!-- studio:footer:end -->", render_footer(note.group(1) if note else "")),
    ]


def apply(text):
    """``(new_text, problems)``. A problem is a marker pair not present exactly once."""
    problems = []
    for name, start, end, body in blocks(text):
        if text.count(start) != 1 or text.count(end) != 1:
            problems.append(f"{name}: expected exactly one '{start}' ... '{end}' pair "
                            f"(found {text.count(start)} start, {text.count(end)} end)")
            continue
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
        if not pattern.search(text):
            problems.append(f"{name}: the end marker comes before the start marker")
            continue
        text = pattern.sub(lambda _m: f"{start}\n{body}\n{end}", text, count=1)
    return text, problems


def stale(text):
    """Reasons a page is out of step with the source: marker problems, or a differing block."""
    new, problems = apply(text)
    return problems or ([] if new == text else ["a generated block differs from tools/studio_chrome.py"])


def main(argv=None):
    check = "--check" in (sys.argv[1:] if argv is None else argv)
    status = 0
    for page in PAGES:
        text = page.read_text(encoding="utf-8")
        new, problems = apply(text)
        rel = page.relative_to(ROOT)
        if problems:
            print(f"{rel}: " + "; ".join(problems))
            status = 1
        elif new != text:
            if check:
                print(f"{rel}: stale (run: python3 tools/studio_chrome.py)")
                status = 1
            else:
                page.write_text(new, encoding="utf-8")
                print(f"{rel}: rewritten")
        else:
            print(f"{rel}: up to date")
    return status


if __name__ == "__main__":
    sys.exit(main())
