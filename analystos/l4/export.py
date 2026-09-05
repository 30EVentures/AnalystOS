"""L4 - render a working-paper section with a footnote trail.

The caller supplies a title and a list of *findings*. Each finding is a dict::

    {
        "text": "Total FY2024 revenue was {answer}.",   # must contain {answer}
        "answer": 4200000.0,
        "citation": {"source": <hash>, "row": 3, "column": "revenue"},
        "format": "usd",                                # optional
    }

A ``citation`` is either one cell (a dict) or, for a computed metric, a list
of the cells it was derived from.

``format`` is optional and controls how ``answer`` is rendered before it
replaces ``{answer}``:

- omitted        -> ``str(answer)``, unchanged (the old behaviour)
- ``"number"``    -> thousands commas: ``4,200,000``
- ``"percent"``   -> one decimal plus a percent sign: ``57.1%``
- ``"usd"``       -> a dollar amount, compactly scaled: ``$1.2K`` / ``$4.2M`` / ``$1.3B``

A negative value renders in parentheses under any format - ``($500.3M)`` -
the standard accounting convention for a loss.

``"usd"`` alone does not say what scale the raw number is *in* - a table's
"revenue" column might hold ``4200000`` meaning $4.2M, or ``4200000`` meaning
$4.2M-in-millions ($4.2 trillion). Getting this wrong produces a confidently
wrong figure, not an error (see docs/decisions.md, 2026-09-04 - hit twice
while demoing before this fix). So it is never guessed or set per finding:
``render_section`` takes one ``currency_unit`` for the *whole* section -
``"actual"`` (default, raw dollars), ``"thousands"``, or ``"millions"`` - and
every ``"usd"``-formatted answer in it is scaled the same way. Set it once,
by reading what the source document itself says ("$ in millions" is standard
on a real income statement), and every figure in the report is consistent
with it - there is no per-sentence choice left to get wrong.

``render_section`` fills each ``{answer}`` in, appends a numbered ``[n]``
marker, and lists the citations as footnotes underneath. It returns the
section as a string; it does not write a file.

``render_html`` turns that string into a standalone, printable HTML page.
``render_pdf`` turns it into a real generated PDF - not "open the HTML and
print" (see docs/decisions.md, Slice 24) - with `reportlab`. Both are
purpose-built for the format ``render_section`` produces - not a general
Markdown renderer - and both render the exact same parsed structure
(``_parse_section``): a title, body paragraphs, and footnote lines. A `[n]`
marker becomes a same-page anchor link in the HTML but only a plain
superscript in the PDF - a PDF has no equivalent low-effort mechanism, a
disclosed gap, not an oversight.
"""

import html
import io
import re
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

_MARKER_RE = re.compile(r"\[(\d+)\]")
_FOOTNOTE_RE = re.compile(r"^\[(\d+)\]\s*(.*)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

_STYLE = """
body{font:16px/1.65 Georgia,'Times New Roman',serif;max-width:42rem;
  margin:3rem auto;padding:0 1.5rem;color:#1a1a1a}
h1{font-size:1.5rem;line-height:1.3;margin:0 0 1.75rem;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
p{margin:0 0 1rem}
sup{line-height:0}
sup a{text-decoration:none;color:#2f5ce0;font-size:.72em;padding:0 .1em}
hr{border:0;border-top:1px solid #ccc;margin:2.5rem 0 1.25rem}
.footnotes{font-size:12.5px;line-height:1.5;color:#555;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.footnotes p{margin:.35rem 0}
.footnotes .n{color:#1a1a1a;font-weight:600;margin-right:.3em}
.footnotes a{color:#2f5ce0;text-decoration:none;margin-left:.3em}
@media print{body{margin:0;max-width:none;font-size:12pt}
  sup a,.footnotes a{color:#000}}
"""


_FORMATS = ("number", "percent", "usd")
_CURRENCY_UNITS = {"actual": 1, "thousands": 1_000, "millions": 1_000_000}


def _compact_usd(raw_dollars):
    """Render a raw dollar amount as $X.XK / $X.XM / $X.XB, else $X.XX."""
    if raw_dollars >= 1_000_000_000:
        return f"${raw_dollars / 1_000_000_000:,.1f}B"
    if raw_dollars >= 1_000_000:
        return f"${raw_dollars / 1_000_000:,.1f}M"
    if raw_dollars >= 1_000:
        return f"${raw_dollars / 1_000:,.1f}K"
    return f"${raw_dollars:,.2f}"


def _format_number(value, spec, currency_unit="actual"):
    """Render ``value`` per ``spec`` (see module docstring); ``None`` = unchanged.

    Falls back to ``str(value)`` for a non-numeric answer even if a format was
    requested, so a text finding with a stray "format" key never crashes.
    """
    if not spec:
        return str(value)
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)

    negative = n < 0
    n = abs(n)

    if spec == "percent":
        body = f"{n:,.1f}%"
    elif spec == "number":
        body = f"{n:,.0f}" if n == int(n) else f"{n:,.1f}"
    elif spec == "usd":
        if currency_unit not in _CURRENCY_UNITS:
            raise ValueError(
                f"unknown currency_unit {currency_unit!r}; "
                f"expected one of {tuple(_CURRENCY_UNITS)}"
            )
        body = _compact_usd(n * _CURRENCY_UNITS[currency_unit])
    else:
        raise ValueError(f"unknown format {spec!r}; expected one of {_FORMATS}")

    return f"({body})" if negative else body


def _one_cell(cell):
    return f'source {cell["source"]} - row {cell["row"]}, column "{cell["column"]}"'


def _footnote(n, citation):
    if isinstance(citation, list):
        return f"[{n}] computed from: " + "; ".join(_one_cell(c) for c in citation)
    return f"[{n}] {_one_cell(citation)}"


def render_section(title, findings, currency_unit="actual"):
    """Return the section as text: heading, body with ``[n]`` markers, footnotes.

    ``currency_unit`` - ``"actual"`` (default), ``"thousands"``, or
    ``"millions"`` - is the scale every ``"usd"``-formatted finding's answer
    is expressed in; see the module docstring for why this is a single
    section-wide setting rather than a per-finding choice.
    """
    body = []
    footnotes = []
    for n, finding in enumerate(findings, start=1):
        text = finding["text"]
        if "{answer}" not in text:
            raise ValueError(
                f"finding {n}: text has no {{answer}} placeholder: {text!r}"
            )
        rendered = _format_number(finding["answer"], finding.get("format"), currency_unit)
        body.append(text.replace("{answer}", rendered) + f" [{n}]")
        footnotes.append(_footnote(n, finding["citation"]))

    return (
        f"# {title}\n\n"
        + "\n\n".join(body)
        + "\n\n---\n"
        + "\n".join(footnotes)
        + "\n"
    )


def _para_html(text):
    """Escape a body paragraph, turn ``**text**`` into bold, and ``[n]`` into
    a superscript link (used by ``render_narrated_section``'s stat lines -
    see that function).
    """
    esc = html.escape(text)
    esc = _BOLD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", esc)
    return _MARKER_RE.sub(
        lambda m: (
            f'<sup><a href="#fn{m.group(1)}" id="ref{m.group(1)}">'
            f"{m.group(1)}</a></sup>"
        ),
        esc,
    )


def _note_html(line):
    """Turn a ``[n] ...`` footnote line into an anchored, back-linked <p>."""
    m = _FOOTNOTE_RE.match(line.strip())
    if not m:
        return f"<p>{html.escape(line.strip())}</p>"
    n, rest = m.group(1), html.escape(m.group(2))
    return (
        f'<p id="fn{n}"><span class="n">{n}.</span>{rest}'
        f' <a href="#ref{n}">&#8617;</a></p>'
    )


def _quoted(source_hash, exact_text):
    return f'source {source_hash} - "{exact_text}"'


def _narrated_footnote(n, source_hash, citation):
    if isinstance(citation, list):
        return f"[{n}] computed from: " + "; ".join(_quoted(source_hash, c) for c in citation)
    return f"[{n}] {_quoted(source_hash, citation)}"


def render_narrated_section(title, source_hash, segments, currency_unit="actual"):
    """Render verified segments from ``analystos.l2.analyze.analyze_document``
    as a section - same overall shape ``render_section`` produces (title,
    body paragraphs, ``---``, numbered footnotes), so ``render_html`` and
    ``render_pdf`` need no changes to render this too.

    Each segment is one of ``"quote"``, ``"computed"``, or ``"prose"`` (see
    ``analystos.l2.analyze`` for the verified shape). A quote/computed
    segment becomes one paragraph - a plain sentence if its ``"display"``
    is ``"inline"``, a standalone bold stat line if ``"stat"`` - with a
    footnote quoting the exact source text it was verified against. Prose
    has no footnote - it never carries a citable number in the first place.
    """
    body = []
    footnotes = []
    n = 0
    for segment in segments:
        if segment["type"] == "prose":
            body.append(segment["text"])
            continue

        n += 1
        if "sentence" in segment:
            rendered = _format_number(segment["value"], segment.get("format"), currency_unit)
            text = segment["sentence"].replace("{value}", rendered)
        else:
            text = segment["text"]

        if segment.get("display") == "stat" and segment.get("label"):
            body.append(f"**{segment['label']}:** {text} [{n}]")
        else:
            body.append(f"{text} [{n}]")
        footnotes.append(_narrated_footnote(n, source_hash, segment["citation"]))

    return (
        f"# {title}\n\n"
        + "\n\n".join(body)
        + "\n\n---\n"
        + "\n".join(footnotes)
        + "\n"
    )


def _parse_section(section_md):
    """Split a rendered section into (title, body paragraphs, footnote lines).

    Shared by every L4 renderer (``render_html``, ``render_pdf``) - each is
    just a different rendering of this same parsed structure, so there is
    exactly one place that does the parsing.
    """
    body_part, _, notes_part = section_md.partition("\n---\n")
    chunks = [c.strip() for c in body_part.strip().split("\n\n") if c.strip()]

    title = ""
    paragraphs = []
    for chunk in chunks:
        if chunk.startswith("# ") and not title:
            title = chunk[2:].strip()
        else:
            paragraphs.append(chunk)

    notes = [line.strip() for line in notes_part.strip().split("\n") if line.strip()]
    return title, paragraphs, notes


def render_html(section_md):
    """Render a section produced by ``render_section`` as a standalone HTML page."""
    title, paragraphs, notes = _parse_section(section_md)

    esc_title = html.escape(title)
    body = "\n".join(f"<p>{_para_html(p)}</p>" for p in paragraphs)
    notes_html = "\n".join(_note_html(line) for line in notes)

    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{esc_title}</title>\n<style>{_STYLE}</style>\n</head>\n<body>\n"
        f"<h1>{esc_title}</h1>\n{body}\n<hr>\n"
        f'<div class="footnotes">\n{notes_html}\n</div>\n</body>\n</html>\n'
    )


_FOOTNOTE_STYLE = ParagraphStyle(
    "AnalystOSFootnote", fontSize=8, leading=11, textColor=colors.HexColor("#555555")
)


def _para_pdf_markup(text):
    """Escape a body paragraph for reportlab's markup, turn ``**text**`` into
    bold and ``[n]`` into a superscript (used by ``render_narrated_section``'s
    stat lines - see that function).
    """
    esc = xml_escape(text)
    esc = _BOLD_RE.sub(lambda m: f"<b>{m.group(1)}</b>", esc)
    return _MARKER_RE.sub(lambda m: f"<super>{m.group(1)}</super>", esc)


def _note_pdf_markup(line):
    """Turn a ``[n] ...`` footnote line into reportlab markup with a bold number."""
    m = _FOOTNOTE_RE.match(line.strip())
    if not m:
        return xml_escape(line.strip())
    n, rest = m.group(1), xml_escape(m.group(2))
    return f"<b>{n}.</b> {rest}"


def render_pdf(section_md):
    """Render a section produced by ``render_section`` as real PDF bytes.

    A real generated PDF via ``reportlab`` - not "open the HTML and print"
    (see docs/decisions.md, Slice 24). Returns bytes; does not write a file,
    same contract as ``render_section`` returning a string.
    """
    title, paragraphs, notes = _parse_section(section_md)
    styles = getSampleStyleSheet()

    story = [Paragraph(xml_escape(title), styles["Title"]), Spacer(1, 16)]
    for paragraph in paragraphs:
        story.append(Paragraph(_para_pdf_markup(paragraph), styles["BodyText"]))
        story.append(Spacer(1, 10))
    if notes:
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc")))
        story.append(Spacer(1, 10))
        for line in notes:
            story.append(Paragraph(_note_pdf_markup(line), _FOOTNOTE_STYLE))
            story.append(Spacer(1, 3))

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=letter, title=title).build(story)
    return buf.getvalue()
