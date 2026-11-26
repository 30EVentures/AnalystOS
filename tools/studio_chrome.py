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
PAGES = [ROOT / "site" / "index.html", ROOT / "site" / "details.html", ROOT / "site" / "upload.html", ROOT / "site" / "hire.html",
         ROOT / "site" / "glossary.html"]
sys.path.insert(0, str(ROOT))

STUDIO = "https://www.30eventures.com"
PRODUCT = "AnalystOS"
BAR_LINKS = [("Portfolio", "/portfolio/"), ("About", "/about/"), ("Press", "/press/")]
# the footer: (heading, [(label, href, small note or "")]). Studio links are absolute; this product's links are root-relative.
FOOT_COLUMNS = [
    ("Product", [("How it works", "/#how", ""), ("Samples for every role", "/#samples", "73 roles, 13 families"),
                 ("Hire a specialist", "/hire.html", "access code"), ("Upload a document", "/upload.html", "access code"),
                 ("Details, privacy and known limits", "/details.html", "")]),
    ("Developers", [("API reference", "/api/v1/openapi.json", "OpenAPI 3.1"), ("API guide", "/docs/api.md", ""),
                    ("Seal specification", "/docs/seal.md", "re-verify offline"), ("Role catalog", "/api/v2/catalog", "JSON"),
                    ("API catalog", "/.well-known/api-catalog", ""), ("llms.txt", "/llms.txt", "for agents")]),
    ("Learn", [("AnalystOS glossary", "/glossary.html", "figure tag, work product, boundary"),
               ("Concepts", STUDIO + "/concepts/", "verifiable by a stranger, and six more"),
               ("Studio glossary", STUDIO + "/learn/", "agents to settlement"), ("Why we build", STUDIO + "/why/", ""),
               ("FAQ", STUDIO + "/faq/", "")]),
    ("30E Ventures", [("About the studio", STUDIO + "/about/", ""), ("Portfolio", STUDIO + "/portfolio/", ""), ("Press", STUDIO + "/press/", ""),
                      ("Brand", STUDIO + "/brand/", ""), ("Contact", STUDIO + "/contact/", "")]),
]
STATUS_NOTE = "Early stage. Not for confidential documents yet. Limits are published."

SERIF = '"Iowan Old Style","Charter","Source Serif 4","Palatino Linotype",Georgia,serif'
SANS = '-apple-system,BlinkMacSystemFont,"SF Pro Text","Inter","Segoe UI",Roboto,Helvetica,Arial,sans-serif'
MONO = 'ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace'
FORMAT_NAMES = {"memo": "Word memo", "workbook": "Excel workbook", "deck": "PowerPoint deck"}


def family_items():
    """The Roles menu: one item per family, from the catalog, opening the explorer on that family."""
    from analystos.catalog import load_catalog
    from analystos.l4.formats import FAMILY_FORMAT, FORMATS
    catalog = load_catalog()
    out = []
    for fam in catalog["families"]:
        count = sum(1 for r in catalog["roles"] if r["family"] == fam["id"])
        out.append((fam["title"], f"/?family={fam['id']}#samples",
                    f"{count} role{'s' if count != 1 else ''} \u00b7 {FORMAT_NAMES[FORMATS[FAMILY_FORMAT[fam['id']]]['name']]}"))
    return out


# (id, label, heading, lead, sub, (all-link label, href), items [(title, href, line)], feature (h, title, line, (label, href)) or None)
def menus():
    return [
        ("roles", "Roles", "Roles", "73 roles in 13 families.",
         "Each role asks its own questions and delivers in its family's format.", ("Hire a specialist", "/hire.html"),
         family_items(), None),
        ("samples", "Samples", "Samples", "See the finished work before you hire.",
         "Every role has a sample of its own, built from a worked example.", ("Open the explorer", "/#samples"),
         [("Word memos", "/?family=legal-contracts-procurement#samples", "Legal, research, audit, HR, insurance and financial crime."),
          ("Excel workbooks", "/?family=finance-modeling#samples", "Finance, accounting and data, with live formulas."),
          ("PowerPoint decks", "/?family=consulting#samples", "Consulting, content, sales and software."),
          ("Role-written work", "/?family=accounting-operations&role=accounts-payable-receivable-clerk#samples",
           "Drafts, registers, case files, reconciliations, plans and code."),
          ("Every number traced", "/#sample", "Each figure points to the client's words, a calculation or an assumption.")],
         ("Download", "The consulting deck", "A full sample deck, every number traced.", ("Download the deck", "/samples/consulting.pptx"))),
        ("how", "How it works", "How it works", "Describe the problem. Get finished work.",
         "Answer first, sources last, in the format the role's work is read in.", ("How it works", "/#how"),
         [("The three steps", "/#how", "Describe it, answer a few questions, use the file."),
          ("How numbers are checked", "/details.html#trust", "Code checks every figure before anything is drawn."),
          ("Who decides", "/glossary.html#boundary", "Drafts for your approval; qualified people decide."),
          ("Evidence and limits", "/details.html#proof", "What has been measured, and what has not."),
          ("Questions", "/details.html#faq", "Privacy, documents and what it cannot do yet.")],
         ("Full details", "How it stays honest", "Privacy, known limits and the evidence behind each claim.", ("Read the details", "/details.html"))),
        ("agents", "For agents", "For agents", "Software can hire through the API.",
         "Published contracts, a role catalog and an index for language models.", ("Read the API guide", "/docs/api.md"),
         [("API guide", "/docs/api.md", "How to open, scope and fetch an engagement."),
          ("OpenAPI", "/api/v1/openapi.json", "The machine-readable API description."),
          ("Role catalog", "/api/v2/catalog", "Every role, its questions and its format, as JSON."),
          ("llms.txt", "/llms.txt", "A short index of the site for language models."),
          ("Seal specification", "/docs/seal.md", "Re-check a sealed report offline, against a key you pin."),
          ("API catalog", "/.well-known/api-catalog", "Where each API and its documents live.")], None),
        ("learn", "Learn", "Learn", "The words and ideas behind the work.",
         "Plain definitions, and the studio's thinking on the agentic internet.", ("Read the glossary", "/glossary.html"),
         [("AnalystOS glossary", "/glossary.html", "Figure tags, work products, boundaries and more."),
          ("Concepts", STUDIO + "/concepts/", "Seven ideas the studio's products are built on."),
          ("Why we build", STUDIO + "/why/", "What is changing, what breaks, and what is needed."),
          ("FAQ", STUDIO + "/faq/", "What 30E Ventures is, and where each product stands."),
          ("Press", STUDIO + "/press/", "Boilerplate, fact sheet, logos and a press contact.")],
         ("Start here", "Verifiable by a stranger", "A claim anyone can check without trusting whoever made it.",
          ("Read the concept", STUDIO + "/concepts/#verifiable"))),
    ]


CHEVRON = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>'


def render_nav():
    lis = ""
    for mid, label, heading, lead, sub_, (all_label, all_href), items, feat in menus():
        links = "".join(f'<li><a href="{href}"><b>{title}</b><span>{line}</span></a></li>' for title, href, line in items)
        aside = ""
        if feat:
            h, title, line, (go, go_href) = feat
            aside = f'<aside class="an-feat"><h3>{h}</h3><h4>{title}</h4><p>{line}</p><a class="an-go" href="{go_href}">{go}</a></aside>'
        wide = " an-wide" if len(items) > 8 else ""
        lis += (f'<li class="an-has"><button type="button" aria-expanded="false" aria-controls="an-m-{mid}">{label}{CHEVRON}</button>'
                f'<div class="an-mega{wide}" id="an-m-{mid}" role="region" aria-label="{label}"><div class="an-in">'
                f'<div><h3>{heading}</h3><p class="an-lead">{lead}</p><p class="an-sub">{sub_}</p><a class="an-all" href="{all_href}">{all_label}</a></div>'
                f"<ul>{links}</ul>{aside}</div></div></li>")
    return (
        '<header class="an-head" id="an-head"><div class="an-bar">'
        f'<a class="an-brand" href="/">Analyst<span>OS</span></a>'
        '<button class="an-burger" type="button" aria-label="Menu" aria-expanded="false" aria-controls="an-primary"><span></span><span></span><span></span></button>'
        f'<nav class="an-primary" id="an-primary" aria-label="Sections"><ul>{lis}</ul></nav>'
        '<a class="an-cta" href="/hire.html">Hire a specialist</a>'
        '</div></header><script src="/nav.js" defer></script>'
    )


THEME = (":root{--display:" + SERIF + ";--serif:" + SERIF + ";--sans:" + SANS + ";--font-display:" + SERIF
         + ";--font-sans:" + SANS + ";--font-mono:" + MONO + "}")
NAV_CSS = """.an-head{position:sticky;top:0;z-index:50;background:#fff;border-bottom:1px solid #dcdfe5;font-family:var(--sans)}
.an-bar{max-width:1200px;margin:0 auto;padding:0 clamp(20px,4vw,48px);display:flex;align-items:center;height:68px;gap:28px}
.an-brand{font:600 20px/1 var(--sans);letter-spacing:-.01em;color:#0e1726;text-decoration:none;flex:none}
.an-brand span{color:#07694b}
.an-primary{flex:1}
.an-primary>ul{display:flex;gap:2px;list-style:none;margin:0;padding:0}
.an-has>button{appearance:none;background:none;border:0;font:500 15px/1 var(--sans);color:#0e1726;padding:25px 13px;cursor:pointer;display:flex;align-items:center;gap:7px;position:relative}
.an-has>button::after{content:"";position:absolute;left:13px;right:13px;bottom:-1px;height:2px;background:transparent}
.an-has.open>button::after,.an-has>button:hover::after{background:#0e1726}
.an-has>button svg{width:11px;height:11px;transition:transform .15s}
.an-has.open>button svg{transform:rotate(180deg)}
.an-cta{flex:none;font:600 14px/1 var(--sans);text-decoration:none;padding:12px 16px;border-radius:3px;background:#0e1726;color:#fff;border:1px solid #0e1726}
.an-cta:hover{background:#1d2a42}
.an-burger{display:none;appearance:none;background:none;border:1px solid #c6cbd4;border-radius:3px;padding:9px 10px;margin-left:auto;cursor:pointer}
.an-burger span{display:block;width:20px;height:2px;background:#0e1726;margin:4px 0}
.an-mega{display:none;position:absolute;left:0;right:0;top:100%;background:#fff;color:#0e1726;border-top:1px solid #dcdfe5;border-bottom:1px solid #dcdfe5;box-shadow:0 24px 40px -24px rgba(14,23,38,.28)}
.an-has.open .an-mega{display:block}
.an-in{max-width:1200px;margin:0 auto;padding:32px clamp(20px,4vw,48px) 36px;display:grid;grid-template-columns:250px 1fr 290px;gap:44px}
.an-wide .an-in{grid-template-columns:250px 1fr}
.an-mega h3{font:600 12px/1 var(--sans);letter-spacing:.09em;text-transform:uppercase;color:#5b6678;margin:0 0 14px}
.an-lead{font:400 23px/1.25 var(--serif);margin:0 0 10px;letter-spacing:-.005em}
.an-sub{color:#37425a;font-size:15px;line-height:1.5;margin:0 0 16px}
.an-all{font-weight:600;font-size:15px;text-decoration:none;color:#0e1726;border-bottom:1px solid #0e1726}
.an-mega ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:2px 28px;align-content:start}
.an-wide ul{grid-template-columns:1fr 1fr 1fr}
.an-mega li a{display:block;padding:11px 0;border-bottom:1px solid #dcdfe5;text-decoration:none;color:#0e1726}
.an-mega li a:hover b{text-decoration:underline;text-underline-offset:3px}
.an-mega li b{font:600 15.5px/1.3 var(--sans);display:block}
.an-mega li span{display:block;color:#37425a;font-size:14px;line-height:1.45;margin-top:2px}
.an-feat{background:#f4f3ef;padding:22px 22px 20px;border-left:3px solid #07694b}
.an-feat h4{font:400 20px/1.25 var(--serif);margin:0 0 8px}
.an-feat p{font-size:14.5px;line-height:1.5;color:#37425a;margin:0 0 14px}
.an-go{font-weight:600;font-size:14.5px;color:#0e1726}
@media (max-width:980px){.an-in{grid-template-columns:200px 1fr;gap:28px}.an-feat{display:none}.an-wide ul{grid-template-columns:1fr 1fr}}
@media (max-width:860px){
  .an-burger{display:block}.an-cta{display:none}
  .an-primary{display:none;position:absolute;left:0;right:0;top:100%;background:#fff;border-bottom:1px solid #dcdfe5;max-height:calc(100vh - 110px);overflow:auto;padding:6px clamp(20px,4vw,48px) 22px}
  .an-head.nav-open .an-primary{display:block}
  .an-primary>ul{flex-direction:column}
  .an-has>button{width:100%;justify-content:space-between;padding:17px 0;border-bottom:1px solid #dcdfe5;font-size:17px}
  .an-has>button::after{display:none}
  .an-mega{position:static;box-shadow:none;border:0}
  .an-in{display:block;padding:4px 0 12px}.an-mega h3,.an-lead,.an-sub,.an-all{display:none}
  .an-mega ul,.an-wide ul{grid-template-columns:1fr}
}
@media print{.an-head{display:none}}"""

MARK = (
    '<svg class="studio-mark" viewBox="0 0 24 24" aria-hidden="true">'
    '<rect x="3" y="3" width="3" height="18" fill="#f2f6fa"/>'
    '<rect x="6" y="3" width="15" height="3" fill="#f2f6fa"/>'
    '<rect x="6" y="10.5" width="10" height="3" fill="#f2f6fa"/>'
    '<rect x="6" y="18" width="15" height="3" fill="#2fd4ff"/></svg>'
)

CSS_STUDIO = """.studio-bar{background:#030508;color:#e8f4ff;font:500 13px/1 system-ui,-apple-system,'Segoe UI',sans-serif;border-bottom:1px solid #16202c}
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
CSS = THEME + "\n" + NAV_CSS + "\n" + CSS_STUDIO


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
        f'<div><a class="af-name" href="/">{PRODUCT}</a><p class="af-line">Specialist work, ready the moment you need it.</p>'
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
        ("nav", "<!-- product:nav:start -->", "<!-- product:nav:end -->", render_nav()),
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
