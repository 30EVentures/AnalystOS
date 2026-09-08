"""L4 - render a *rich* report: an executive summary, a section-by-section
body (each section optionally carrying a chart), and a visually distinct
outlook block - real structure, not the flat title/paragraphs/footnotes
shape every other renderer in ``analystos.l4.export`` shares.

That flat shape is exactly why this is a separate module rather than an
addition to ``export.py``: ``render_section``/``render_narrated_section``/
``render_narrative_section`` all produce one text intermediate
(``_parse_section`` then turns it into HTML or PDF), and a rich report's
sections/charts/outlook genuinely don't fit that shape. ``render_rich_report``
builds HTML directly instead.

``report`` is::

    {
        "executive_summary": [{"text": "..."}, ...],
        "sections": [
            {"heading": "...", "paragraphs": [{"text": "..."}, ...],
             "chart": {"type": "bar"|"line"|"donut", "title": "...",
                       "format": "usd"|"percent"|"number",
                       "series": [{"label": "...", "fact_index": N}, ...]}
             or None},
            ...
        ],
        "outlook": [{"text": "..."}, ...] or None,
    }

Every paragraph uses the exact ``{{N}}`` placeholder mechanism
``analystos.l2.narrate``/``render_narrative_section`` already established
- this module trusts that input the same way ``render_narrative_section``
does (validation is L2's job, already built). A chart's ``fact_index``
values are different: nothing upstream validates them yet (no L2 stage
produces chart specs today - see ``specs/slice-28/spec.md``), so
``_resolve_chart`` does its own defensive check here, dropping a single
bad point or the whole chart rather than ever rendering something
misleading. See ``docs/decisions.md``, 2026-09-06, for why this scope
line is drawn where it is.
"""

import html
import re

from analystos.l4.charts import bar_chart_svg, donut_chart_svg, line_chart_svg
from analystos.l4.export import _BOLD_RE, _FOOTNOTE_RE, _MARKER_RE, display_value, narrated_footnote

_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")
# A plain-text sentinel emitted by _substitute (before html.escape) and
# turned into a real <span> by _para_html (after it) - the same escape-
# then-convert two-pass the [n] markers use. U+27E6/27E7 never occur in
# financial prose and pass through html.escape untouched.
_HORIZON_TAG_RE = re.compile("⟦(guidance|projected)⟧")
_FORWARD_HORIZONS = ("guidance", "projected")

_CHART_RENDERERS = {"bar": bar_chart_svg, "line": line_chart_svg, "donut": donut_chart_svg}

_STYLE = """
:root{
  --paper:#F3F4F7; --surface:#FBFBFD; --raised:#FFFFFF;
  --ink:#10151F; --graphite:#565E6B; --faint:#8A93A1;
  --hairline:#D9DCE3; --hairline-strong:#C3C8D2;
  --institutional:#1B3A6B; --signal:#2F5CE0;
  --amber:#A9631A; --amber-bg:#FBF3EA;
  --font-display:"Newsreader",Georgia,"Times New Roman",serif;
  --font-sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  --font-mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--font-sans);
  font-size:16px;line-height:1.65;-webkit-font-smoothing:antialiased}
.wrap{max-width:44rem;margin:0 auto;padding:3rem 1.5rem 5rem}
.eyebrow{font-family:var(--font-mono);font-size:.72rem;letter-spacing:.12em;
  text-transform:uppercase;color:var(--faint);margin:0 0 .6rem}
h1{font-family:var(--font-display);font-weight:500;font-size:2rem;line-height:1.2;
  margin:0 0 1.6rem;text-wrap:balance}
h2{font-family:var(--font-display);font-weight:500;font-size:1.35rem;line-height:1.3;
  margin:0 0 .9rem;color:var(--institutional)}
p{margin:0 0 1rem}
sup{line-height:0}
sup a{text-decoration:none;color:var(--signal);font-size:.72em;padding:0 .1em;cursor:help}

.exec-summary{background:var(--raised);border:1px solid var(--hairline);border-left:4px solid var(--signal);
  border-radius:8px;padding:1.5rem 1.7rem;margin-bottom:2.4rem}
.exec-summary .eyebrow{color:var(--signal)}

section.report-section{margin-bottom:2.6rem}
section.report-section .chart-card{background:var(--raised);border:1px solid var(--hairline);
  border-radius:10px;padding:1.2rem 1.3rem 1rem;margin:1.2rem 0 1.4rem}
section.report-section .chart-card svg{width:100%;height:auto;display:block}

.outlook{background:var(--amber-bg);border:1px solid color-mix(in srgb,var(--amber) 35%,var(--hairline));
  border-left:4px solid var(--amber);border-radius:8px;padding:1.5rem 1.7rem;margin-top:2.6rem}
.outlook .eyebrow{color:var(--amber)}
.outlook .caption{font-family:var(--font-mono);font-size:.78rem;color:var(--graphite);
  margin:-.3rem 0 1.1rem}

hr{border:0;border-top:1px solid var(--hairline);margin:3rem 0 1.4rem}
.footnotes{font-family:var(--font-mono);font-size:.78rem;line-height:1.6;color:var(--graphite)}
.footnotes .heading{font-family:var(--font-sans);font-size:.75rem;font-weight:600;
  letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin-bottom:.8rem}
.footnotes p{margin:.4rem 0}
.footnotes .n{color:var(--ink);font-weight:600;margin-right:.35em}
.footnotes a{color:var(--signal);text-decoration:none;margin-left:.35em}

.horizon-tag{font-family:var(--font-mono);font-size:.62rem;font-weight:600;
  letter-spacing:.08em;text-transform:uppercase;color:var(--amber);
  vertical-align:.15em;margin-left:.25em;white-space:nowrap}

@media print{body{background:#fff}.exec-summary,.outlook,.chart-card{break-inside:avoid}
  .horizon-tag{color:#7A4A12}}
"""


def _substitute(text, segments, source_hash, currency_unit, footnote_number, footnotes):
    """Replace every ``{{N}}`` in ``text`` with its verified display value
    and a plain ``[n]`` marker - text only, no HTML yet (that happens in
    ``_para_html``, after escaping - inserting real ``<sup><a>`` markup
    here would just get HTML-escaped again downstream). Assigns footnote
    numbers by first appearance across the *whole* document (shared state
    passed in, not reset per paragraph/section). Trusts ``N`` is valid,
    the same way ``render_narrative_section`` trusts it; validating
    placeholders is Slice 27's job (``analystos.l2.narrate
    ._validate_paragraph``), already done before this ever runs.
    """
    def _sub(match):
        index = int(match.group(1))
        if index not in footnote_number:
            footnote_number[index] = len(footnotes) + 1
            citation = segments[index]["citation"]
            footnotes.append(narrated_footnote(footnote_number[index], source_hash, citation))
        n = footnote_number[index]
        rendered = display_value(segments[index], currency_unit)
        horizon = segments[index].get("horizon", "reported")
        tag = f" ⟦{horizon}⟧" if horizon in _FORWARD_HORIZONS else ""
        return f"{rendered}{tag} [{n}]"

    return _PLACEHOLDER_RE.sub(_sub, text)


def _para_html(text, footnotes):
    """Escape a paragraph, then turn ``**bold**`` and ``[n]`` markers into
    real HTML - in that order, so nothing inserted here ever gets
    re-escaped. A marker becomes a same-page anchor link carrying the
    real citation text as a native ``title`` (hover-visible with zero
    JavaScript), looked up from ``footnotes`` by its number.
    """
    esc = html.escape(text)
    esc = _BOLD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", esc)
    esc = _HORIZON_TAG_RE.sub(
        lambda m: f'<span class="horizon-tag">{m.group(1)}</span>', esc
    )

    def _marker(match):
        n = match.group(1)
        note_text = _FOOTNOTE_RE.match(footnotes[int(n) - 1]).group(2)
        title = html.escape(note_text)
        return f'<sup><a href="#fn{n}" id="ref{n}" title="{title}">{n}</a></sup>'

    return _MARKER_RE.sub(_marker, esc)


def _paragraphs_html(paragraphs, segments, source_hash, currency_unit, footnote_number, footnotes):
    return "\n".join(
        f"<p>{_para_html(_substitute(p['text'], segments, source_hash, currency_unit, footnote_number, footnotes), footnotes)}</p>"
        for p in paragraphs
    )


def _resolve_chart(chart, segments):
    """Turn a chart spec's ``fact_index`` list into real ``(label, value)``
    pairs, or ``None`` if what's left isn't a real chart.

    A ``fact_index`` is only trustworthy if it's in range and points at a
    quantitative fact - a ``quote`` with a real ``value`` or a ``computed``
    segment, never ``prose`` (nothing to plot) or a qualitative quote
    (no number at all). Every point that fails this is dropped, not
    rendered as a zero or a guess. A chart left with fewer than two
    points is dropped entirely - a one-bar "comparison" isn't one, and
    rendering it would suggest a shape the data doesn't actually have.
    """
    labels, values = [], []
    for point in chart.get("series", []):
        index = point.get("fact_index")
        if index is None or index < 0 or index >= len(segments):
            continue
        segment = segments[index]
        if segment["type"] == "prose" or "value" not in segment:
            continue
        labels.append(point.get("label") or display_value(segment))
        values.append(segment["value"])
    if len(values) < 2:
        return None
    return labels, values


def _chart_html(chart, segments, currency_unit):
    resolved = _resolve_chart(chart, segments)
    if resolved is None:
        return ""
    labels, values = resolved
    renderer = _CHART_RENDERERS.get(chart.get("type"))
    if renderer is None:
        return ""
    svg = renderer(chart.get("title", ""), labels, values, chart.get("format", "number"), currency_unit)
    return f'<div class="chart-card">{svg}</div>'


def render_rich_report(report, segments, source_hash, currency_unit="actual"):
    """Render ``report`` (see module docstring for its shape) as a
    standalone HTML page: an executive summary, section-by-section body
    with optional embedded charts, and a visually distinct outlook block.
    Returns a full ``<!doctype html>`` string.
    """
    footnote_number = {}
    footnotes = []

    exec_html = _paragraphs_html(
        report.get("executive_summary", []), segments, source_hash, currency_unit,
        footnote_number, footnotes,
    )

    sections_html = []
    for section in report.get("sections", []):
        body = _paragraphs_html(
            section.get("paragraphs", []), segments, source_hash, currency_unit,
            footnote_number, footnotes,
        )
        chart_html = ""
        if section.get("chart"):
            chart_html = _chart_html(section["chart"], segments, currency_unit)
        sections_html.append(
            f'<section class="report-section"><h2>{html.escape(section["heading"])}</h2>'
            f"{body}{chart_html}</section>"
        )

    outlook_html = ""
    outlook_paragraphs = report.get("outlook")
    if outlook_paragraphs:
        body = _paragraphs_html(
            outlook_paragraphs, segments, source_hash, currency_unit,
            footnote_number, footnotes,
        )
        outlook_html = (
            '<div class="outlook"><p class="eyebrow">Outlook</p>'
            '<p class="caption">Interpretation, not a verified fact - '
            "reasoning about what the figures above imply, not a new citable claim.</p>"
            f"{body}</div>"
        )

    notes_html = "\n".join(
        f'<p id="fn{i + 1}"><span class="n">{i + 1}.</span>{html.escape(_FOOTNOTE_RE.match(note).group(2))}'
        f' <a href="#ref{i + 1}">&#8617;</a></p>'
        for i, note in enumerate(footnotes)
    )

    esc_title = html.escape(report.get("title", ""))
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc_title}</title>\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:'
        'ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=IBM+Plex+Mono:'
        "wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap\">\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n"
        '<div class="wrap">\n'
        f'<p class="eyebrow">Executive report</p>\n<h1>{esc_title}</h1>\n'
        f'<div class="exec-summary"><p class="eyebrow">Executive summary</p>{exec_html}</div>\n'
        + "\n".join(sections_html)
        + outlook_html
        + '\n<hr><div class="footnotes"><p class="heading">Sources</p>\n'
        + notes_html
        + "\n</div>\n</div>\n</body>\n</html>\n"
    )
