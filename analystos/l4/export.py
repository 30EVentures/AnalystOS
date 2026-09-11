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
_NARRATIVE_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")

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


def _compact_usd(raw_dollars, decimals=1):
    """Render a raw dollar amount as $X.XK / $X.XM / $X.XB, else $X.XX.

    ``decimals`` defaults to 1 (unchanged historical behaviour) but a caller
    building a footnote's visible arithmetic can ask for more - $1.95B
    compacted to 1 decimal is "$1.9B", which no longer adds up against the
    other operands in the same expression (see ``analystos.l4.rich_export
    ._arithmetic``, Slice 38).
    """
    if raw_dollars >= 1_000_000_000:
        return f"${raw_dollars / 1_000_000_000:,.{decimals}f}B"
    if raw_dollars >= 1_000_000:
        return f"${raw_dollars / 1_000_000:,.{decimals}f}M"
    if raw_dollars >= 1_000:
        return f"${raw_dollars / 1_000:,.{decimals}f}K"
    return f"${raw_dollars:,.2f}"


def format_number(value, spec, currency_unit="actual", decimals=1):
    """Render ``value`` per ``spec`` (see module docstring); ``None`` = unchanged.

    Falls back to ``str(value)`` for a non-numeric answer even if a format was
    requested, so a text finding with a stray "format" key never crashes.
    Public (not ``_``-prefixed) because ``analystos.l2.narrate`` also needs
    it - a fact's displayed value must be computed exactly the same way
    whether it ends up in Slice 26's plain rendering or Slice 27's
    narrative, so there is exactly one implementation of "how a value
    gets formatted," not two that could drift apart. ``decimals`` only
    affects ``"usd"``'s compact K/M/B suffix (see ``_compact_usd``).
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
        body = _compact_usd(n * _CURRENCY_UNITS[currency_unit], decimals)
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
        rendered = format_number(finding["answer"], finding.get("format"), currency_unit)
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


def narrated_footnote(n, source_hash, citation):
    """Public (not ``_``-prefixed) because ``analystos.l4.rich_export``
    also needs it - the same "one implementation, not two that could
    drift" reasoning as ``format_number``/``display_value`` above.
    """
    if isinstance(citation, list):
        return f"[{n}] computed from: " + "; ".join(_quoted(source_hash, c) for c in citation)
    return f"[{n}] {_quoted(source_hash, citation)}"


def event_line(segment):
    """Compose a verified ``event`` segment's parts into one timeline
    string - ``what`` always, then ``(date)``, ``status``, and
    ``next: next_step`` only where the source actually supplied them
    (Slice 32). Every digit here is a verified substring; the model never
    typed it. One implementation, shared by every renderer.
    """
    line = segment["what"]
    if segment.get("date"):
        line += f" ({segment['date']})"
    if segment.get("status"):
        line += f" — {segment['status']}"
    if segment.get("next_step"):
        line += f" — next: {segment['next_step']}"
    return line


def display_value(segment, currency_unit="actual"):
    """The final string a verified segment's value renders as - a
    formatted number for a quote/computed segment that has one, an
    event's composed timeline line for an ``event`` segment, else its
    plain (qualitative) quoted text. Shared by ``render_narrated_section``
    below and ``render_narrative_section``/``analystos.l2.narrate`` (which
    builds the manifest a narrative pass is shown) - a fact's displayed
    value must be identical wherever it appears, not two implementations
    that could quietly drift apart.
    """
    if segment["type"] == "event":
        return event_line(segment)
    if "value" in segment:
        return format_number(segment["value"], segment.get("format"), currency_unit)
    return segment["text"]


def render_narrated_section(title, source_hash, segments, currency_unit="actual"):
    """Render verified segments from ``analystos.l2.analyze.analyze_document``
    as a section - same overall shape ``render_section`` produces (title,
    body paragraphs, ``---``, numbered footnotes), so ``render_html`` and
    ``render_pdf`` need no changes to render this too.

    Each segment is one of ``"quote"``, ``"computed"``, ``"event"``, or
    ``"prose"`` (see ``analystos.l2.analyze`` for the verified shape). A
    quote/computed/event segment becomes one paragraph - a plain sentence
    if its ``"display"`` is ``"inline"``, a standalone bold stat line if
    ``"stat"`` - with a footnote quoting the exact source text it was
    verified against; an ``event`` renders its composed timeline line
    (``event_line``). Prose has no footnote - it never carries a citable
    number in the first place.
    """
    body = []
    footnotes = []
    n = 0
    for segment in segments:
        if segment["type"] == "prose":
            body.append(segment["text"])
            continue

        n += 1
        if "value" in segment:
            rendered = display_value(segment, currency_unit)
            text = segment["sentence"].replace("{value}", rendered)
        else:
            # a qualitative quote (its quoted text) or an event (its
            # composed timeline line) - display_value handles both.
            text = display_value(segment, currency_unit)

        # A forward-looking figure is marked inline so this plain fallback
        # can't mislead any more than the rich path can (Slice 31). Plain
        # text - no markup - so it flows through render_html/render_pdf
        # untouched.
        horizon = segment.get("horizon", "reported")
        if horizon in ("guidance", "projected"):
            text = f"{text} ({horizon})"

        if segment.get("display") == "stat" and segment.get("label"):
            body.append(f"**{segment['label']}:** {text} [{n}]")
        else:
            body.append(f"{text} [{n}]")
        footnotes.append(narrated_footnote(n, source_hash, segment["citation"]))

    return (
        f"# {title}\n\n"
        + "\n\n".join(body)
        + "\n\n---\n"
        + "\n".join(footnotes)
        + "\n"
    )


def render_narrative_section(title, source_hash, segments, paragraphs, currency_unit="actual"):
    """Render ``analystos.l2.narrate.write_narrative``'s paragraphs as a
    section - same shape every other renderer here produces, so
    ``render_html``/``render_pdf`` need no changes.

    ``segments`` are Slice 26's already-verified facts (unchanged); each
    ``paragraph["text"]`` may contain ``{{N}}`` placeholders referencing
    one by index - ``write_narrative`` has already checked every ``N`` is
    in range and points at a citable (non-``prose``) segment, so this
    function trusts that and just substitutes. A fact referenced more than
    once keeps the same footnote number every time (assigned by first
    appearance, not by segment order) - real citations, not one per use.
    """
    footnote_number = {}
    footnotes = []

    def _substitute(match):
        index = int(match.group(1))
        if index not in footnote_number:
            footnote_number[index] = len(footnotes) + 1
            footnotes.append(
                narrated_footnote(footnote_number[index], source_hash, segments[index]["citation"])
            )
        rendered = display_value(segments[index], currency_unit)
        return f"{rendered} [{footnote_number[index]}]"

    body = [_NARRATIVE_PLACEHOLDER_RE.sub(_substitute, paragraph["text"]) for paragraph in paragraphs]

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
    """Render a section produced by ``render_section`` as a standalone HTML page.

    Idempotent on a finished page: since Slice 30 the narrated default path
    returns a complete HTML document (``analystos.l4.rich_export``), and
    ``api/analyze.py`` / ``pipeline.main`` still call this on whatever
    ``build_report`` returned. Given something that is already a full
    document, return it untouched rather than wrapping ``<!doctype html>``
    in another ``<!doctype html>``.
    """
    if section_md.lstrip().lower().startswith("<!doctype html"):
        return section_md
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
