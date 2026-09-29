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
PAGES = [ROOT / "site" / "index.html", ROOT / "site" / "upload.html"]

STUDIO = "https://30eventures.com"
PRODUCT = "AnalystOS"
BAR_LINKS = [("Portfolio", "/portfolio"), ("About", "/about"), ("Press", "/press")]
FOOT_LINKS = [("Portfolio", "/portfolio"), ("About", "/about"), ("Brand", "/brand"),
              ("Press", "/press"), ("Contact", "/contact")]

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
.studio-foot{margin:14px 0 0;font-size:.85rem;opacity:.9}
.studio-foot a{color:inherit;text-decoration:underline}
@media (max-width:640px){.studio-line,.studio-sub{display:none}.studio-in{padding:9px 14px;gap:12px}.studio-links{gap:12px}}
@media print{.studio-bar{display:none}}"""


def render_bar():
    links = "".join(f'<a href="{STUDIO}{path}">{label}</a>' for label, path in BAR_LINKS)
    return (
        '<div class="studio-bar" role="navigation" aria-label="30E Ventures">'
        '<div class="studio-in">'
        f'<a class="studio-brand" href="{STUDIO}">{MARK}<span>30E<span class="studio-sub">VENTURES</span></span></a>'
        f'<span class="studio-line">{PRODUCT} is a 30E Ventures product</span>'
        f'<span class="studio-links">{links}</span>'
        "</div></div>"
    )


def render_footer():
    links = " &middot; ".join(f'<a href="{STUDIO}{path}">{label}</a>' for label, path in FOOT_LINKS)
    return (
        f'<p class="studio-foot">{PRODUCT} is built by <a href="{STUDIO}">30E Ventures</a>, '
        f"a machine-native venture studio in Toronto building the agentic internet. {links}</p>"
    )


# (name, start marker, end marker, replacement body)
def blocks():
    return [
        ("css", "/* studio:css:start */", "/* studio:css:end */", CSS),
        ("bar", "<!-- studio:bar:start -->", "<!-- studio:bar:end -->", render_bar()),
        ("footer", "<!-- studio:footer:start -->", "<!-- studio:footer:end -->", render_footer()),
    ]


def apply(text):
    """``(new_text, problems)``. A problem is a marker pair not present exactly once."""
    problems = []
    for name, start, end, body in blocks():
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
