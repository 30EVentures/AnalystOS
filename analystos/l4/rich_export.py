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

from analystos.l4.charts import (
    bar_chart_svg,
    donut_chart_svg,
    line_chart_svg,
    waterfall_chart_svg,
)
from analystos.l4.export import (
    _BOLD_RE,
    _FOOTNOTE_RE,
    _MARKER_RE,
    display_value,
    format_number,
    narrated_footnote,
)

_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")
# Plain-text sentinels emitted by _substitute (before html.escape) and
# turned into real markup by _para_html (after it) - the same escape-then-
# convert two-pass the [n] markers use. U+27E6/27E7 never occur in
# financial prose and pass through html.escape untouched.
#   guidance/projected -> a forward-looking marker
#   q / c              -> the source tag: quote (verified) / computed
_TAG_RE = re.compile("⟦(guidance|projected|non-gaap|q|c)⟧")
_FORWARD_HORIZONS = ("guidance", "projected")

_CHART_RENDERERS = {
    "bar": bar_chart_svg,
    "line": line_chart_svg,
    "donut": donut_chart_svg,
    "waterfall": waterfall_chart_svg,
}

_STYLE = """
:root{
  --ink:#14171C; --ink-soft:#4A4E57; --paper:#FCFCFA; --panel:#F5F3EE;
  --rule:#DBD7CC; --verified:#1F4B47; --verified-bg:#EAF1EF;
  --computed:#2E4570; --computed-bg:#EAEEF6;
  --interp:#8A6A2A; --interp-bg:#F7EFDD;
  --neg:#8C3F32; --pos:#1F4B47;
  --font-display:"IBM Plex Serif",Georgia,"Times New Roman",serif;
  --font-sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  --font-mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--font-sans);
  font-size:15px;line-height:1.6;font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}
.wrap{max-width:55rem;margin:0 auto;padding:0 28px 100px}
.pdf-btn{position:fixed;top:20px;right:24px;z-index:10;font-family:var(--font-sans);
  font-size:.82rem;font-weight:600;color:var(--paper);background:var(--ink);
  border:none;border-radius:5px;padding:9px 16px;cursor:pointer;
  box-shadow:0 2px 8px rgba(0,0,0,.18)}
.pdf-btn:hover{background:var(--verified)}
header.masthead{padding:38px 0 20px;border-bottom:2px solid var(--ink);
  display:flex;justify-content:space-between;align-items:flex-end;gap:24px;flex-wrap:wrap}
header.masthead h1{font-family:var(--font-display);font-weight:600;font-size:1.8rem;
  margin:0 0 6px;letter-spacing:-0.01em}
header.masthead .sub{color:var(--ink-soft);font-size:.9rem}
header.masthead .meta{text-align:right;font-size:.8rem;color:var(--ink-soft);line-height:1.5}
p{margin:0 0 .8rem;max-width:74ch}

.kpi-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:0;
  margin:28px 0 6px;border-top:1px solid var(--ink)}
.kpi{padding:14px 12px 6px;border-right:1px solid var(--rule)}
.kpi:last-child{border-right:none}
.kpi .label{font-size:.72rem;color:var(--ink-soft);margin-bottom:6px}
.kpi .value{font-family:var(--font-display);font-size:1.4rem;font-weight:600}
.kpi .delta{font-size:.8rem;margin-top:3px}
.kpi .delta.pos{color:var(--pos)} .kpi .delta.neg{color:var(--neg)}
.kpi .delta.neutral{color:var(--ink-soft)}
.legend{display:flex;gap:20px;flex-wrap:wrap;font-size:.75rem;color:var(--ink-soft);margin:10px 0 0}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend .dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.legend .dot.v{background:var(--verified)} .legend .dot.c{background:var(--computed)}
.legend .dot.i{background:var(--interp)}

section{margin-top:40px}
h2{font-family:var(--font-display);font-weight:600;font-size:1.2rem;
  padding-bottom:8px;border-bottom:1px solid var(--rule);margin:0 0 14px}

.cite{font-size:.66rem;vertical-align:super;font-weight:600;padding:1px 4px;
  border-radius:3px;margin-left:1px;background:var(--verified-bg);color:var(--verified)}
.cite.calc{background:var(--computed-bg);color:var(--computed)}
.horizon-tag{font-family:var(--font-mono);font-size:.6rem;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;color:var(--interp);
  vertical-align:.15em;margin-left:.2em;white-space:nowrap}

.exec-summary{background:var(--panel);border:1px solid var(--rule);border-radius:4px;
  padding:22px 24px;margin-top:24px}
.exec-summary h2{border:none;padding:0;margin-bottom:12px}
.analysis-block{background:var(--interp-bg);border-left:3px solid var(--interp);
  padding:14px 16px;margin:16px 0;border-radius:0 3px 3px 0}
.analysis-block .tag{font-size:.68rem;font-weight:700;color:var(--interp);
  text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px;display:block}
.analysis-block p{margin-bottom:0}

.chart-card{margin:18px 0 6px}
.chart-card svg{width:100%;height:auto;display:block}
.chart-card figcaption{font-size:.78rem;color:var(--ink-soft);margin-top:4px}

.gap-note{font-size:.85rem;color:var(--ink-soft);background:var(--panel);
  border:1px dashed #C7C2B4;padding:10px 14px;border-radius:3px;margin:14px 0}
.gap-note b{color:var(--ink)}

.timeline{border-left:2px solid var(--rule);padding-left:18px;margin:14px 0}
.tl-item{position:relative;margin-bottom:14px;font-size:.9rem}
.tl-item::before{content:'';position:absolute;left:-23px;top:5px;width:9px;height:9px;
  border-radius:50%;background:var(--verified)}
.tl-date{font-size:.78rem;color:var(--ink-soft);font-weight:600;display:block}

.outlook{background:var(--interp-bg);border:1px solid #D8C384;border-radius:4px;
  padding:20px 24px;margin-top:36px}
.outlook h2{border:none;padding:0;color:var(--interp);margin-bottom:10px}
.outlook .interp{color:var(--interp);font-weight:600;font-style:italic}

footer.footnotes{margin-top:52px;padding-top:16px;border-top:1px solid var(--ink);
  font-size:.78rem;color:var(--ink-soft);font-family:var(--font-mono)}
footer.footnotes .heading{font-family:var(--font-sans);font-weight:600;font-size:.72rem;
  letter-spacing:.06em;text-transform:uppercase;color:var(--ink-soft);margin-bottom:8px}
footer.footnotes p{margin:.35rem 0;max-width:none}
footer.footnotes .n{color:var(--ink);font-weight:600;margin-right:.35em}
footer.footnotes a{color:var(--computed);text-decoration:none;margin-left:.35em}

@media print{
  body{background:#fff}
  .pdf-btn{display:none}
  .exec-summary,.outlook,.chart-card,.analysis-block,.gap-note,
  .kpi-strip,.tl-item,section{break-inside:avoid}
}
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
        segment = segments[index]
        if index not in footnote_number:
            footnote_number[index] = len(footnotes) + 1
            footnotes.append(
                _rich_footnote(footnote_number[index], source_hash, segment, currency_unit)
            )
        n = footnote_number[index]
        # An event's display_value() is the FULL composed timeline ("what
        # (date) - status - next: ...") - right for the dedicated .timeline
        # widget, wrong mid-sentence: a model writing "the {{N}} closed in
        # May" expects a short phrase, not the whole timeline dumped inline.
        # Found live 2026-09-11: the full string leaking into 6+ places,
        # verbatim, with "next:" showing through as a raw artifact.
        rendered = segment["what"] if segment.get("type") == "event" else display_value(segment, currency_unit)
        horizon = segment.get("horizon", "reported")
        h_tag = f" ⟦{horizon}⟧" if horizon in _FORWARD_HORIZONS else ""
        # A non-GAAP figure carries its own visible tag the same way a
        # forward-looking one does - never let an adjusted figure read as
        # though it were the audited measure. See specs/slice-45/spec.md.
        g_tag = " ⟦non-gaap⟧" if segment.get("gaap_status") == "non_gaap" else ""
        # ✓ for a direct source quote, ∑ for an independently computed value.
        src_tag = " ⟦c⟧" if segment.get("type") == "computed" else " ⟦q⟧"
        return f"{rendered}{h_tag}{g_tag}{src_tag} [{n}]"

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

    def _tag(match):
        kind = match.group(1)
        if kind == "q":
            return '<sup class="cite" title="Direct quote from source">&#10003;</sup>'
        if kind == "c":
            return '<sup class="cite calc" title="Independently computed &amp; verified">&#8721;</sup>'
        return f'<span class="horizon-tag">{kind}</span>'

    esc = _TAG_RE.sub(_tag, esc)

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


def _fmt(value, spec, currency_unit, decimals=1):
    return html.escape(format_number(value, spec or "number", currency_unit, decimals))


def _operand_fmt(value, currency_unit, decimals=1):
    return _fmt(value, "usd" if abs(value) >= 1000 else "number", currency_unit, decimals)


_COMPACT_NUM_RE = re.compile(r"-?[\d,]*\.?\d+")
_COMPACT_SCALE = {"B": 1_000_000_000, "M": 1_000_000, "K": 1_000}


def _parse_compact_usd(rendered):
    """Reverse of ``_operand_fmt``'s usd branch - "$1.95B" -> 1_950_000_000.0
    - used only to confirm an arithmetic footnote's *displayed* numbers
    actually foot, never to change what's shown. ``None`` if it isn't a
    compact usd string (a percent, a plain count - nothing to re-derive).
    """
    match = _COMPACT_NUM_RE.search(rendered)
    if not match:
        return None
    scale = _COMPACT_SCALE.get(rendered[-1], 1)
    return float(match.group(0).replace(",", "")) * scale


def _ties_out(op, operand_strs, result_str):
    """Does the expression foot using the numbers exactly as displayed?

    A footnote showing "$1.9B - $498.0M - ... = $565.0M" only proves the
    math if $1.9B really is $1.9 billion to the precision shown - but
    $1.9B is the 1-decimal *compaction* of $1,950,000,000, and
    1.9B - 498M - 455M - 432M = $515M, not $565M. The underlying
    recomputation (analystos.l2.analyze) is still correct; the *display*
    silently dropped the precision that made it correct. Found live,
    2026-09-11. Returns True (nothing to check) for a non-usd expression.
    """
    parsed_ops = [_parse_compact_usd(s) for s in operand_strs]
    parsed_result = _parse_compact_usd(result_str)
    if any(p is None for p in parsed_ops) or parsed_result is None:
        return True
    if op == "difference" and len(parsed_ops) >= 2:
        recomputed = parsed_ops[0] - sum(parsed_ops[1:])
    elif op == "sum" and parsed_ops:
        recomputed = sum(parsed_ops)
    else:
        return True
    tolerance = max(abs(parsed_result) * 0.0005, 1.0)
    return abs(recomputed - parsed_result) <= tolerance


def _arithmetic(segment, currency_unit):
    """The visible math for a computed segment - "$142.0M - $88.0M - $34.0M
    = $20.0M" - built from the canonical operand values Slice 35 carries.
    Returns "" if the shape isn't one we can spell out.

    For "difference"/"sum" in usd, the precision shown is escalated (1 ->
    2 -> 3 decimals) until the displayed numbers actually foot (see
    ``_ties_out``) - never left showing an expression that looks wrong
    even though the real recomputation behind it is right.
    """
    op = segment.get("operation")
    ops = segment.get("operands") or []
    fmt = segment.get("format") or "number"
    result_val = segment.get("value", 0)
    total = segment.get("total")

    escalate = op in ("difference", "sum") and fmt == "usd" and len(ops) >= 1
    for decimals in ((1, 2, 3) if escalate else (1,)):
        o = [_operand_fmt(v, currency_unit, decimals) for v in ops]
        result = _fmt(result_val, fmt, currency_unit, decimals)
        if not escalate or _ties_out(op, o, result):
            expr = _build_expr(op, o, result, segment, currency_unit, decimals, total)
            if expr:
                return expr
            break
    return ""


def _build_expr(op, o, result, segment, currency_unit, decimals, total):
    if op == "difference" and len(o) >= 2:
        return f"{o[0]} − {' − '.join(o[1:])} = {result}"
    if op == "sum" and o:
        return f"{' + '.join(o)} = {result}"
    if op == "average" and o:
        return f"mean of {', '.join(o)} = {result}"
    if op == "growth_percent" and len(o) == 2:
        return f"({o[1]} − {o[0]}) / {o[0]} = {result}"
    if op == "ratio" and len(o) == 2:
        return f"{o[0]} / {o[1]} = {result}"
    if op == "percent_of_total" and len(o) == 1 and total is not None:
        return f"{o[0]} / {_operand_fmt(total, currency_unit, decimals)} = {result}"
    return ""


def _rich_footnote(n, source_hash, segment, currency_unit):
    """Like ``narrated_footnote`` but, for a computed segment, shows the
    arithmetic itself - the reader sees the math, not just a citation."""
    if segment.get("type") == "computed":
        expr = _arithmetic(segment, currency_unit)
        if expr:
            return f"[{n}] {expr}, verified by recomputation. Source {source_hash}."
    return narrated_footnote(n, source_hash, segment["citation"])


_LEGEND = (
    '<div class="legend">'
    '<span><i class="dot v"></i>Direct quote from source</span>'
    '<span><i class="dot c"></i>Independently computed &amp; verified</span>'
    '<span><i class="dot i"></i>Analytical interpretation (not a verified fact)</span>'
    "</div>"
)


def _kpi_strip_html(kpis, segments, currency_unit):
    if not kpis:
        return ""
    cells = []
    for k in kpis:
        vi = k.get("value_fact", -1)
        if not isinstance(vi, int) or not (0 <= vi < len(segments)):
            continue  # defence in depth; write_narrative already filtered
        seg = segments[vi]
        if seg.get("value") is None:
            continue
        vtag = ('<sup class="cite calc">&#8721;</sup>' if seg.get("type") == "computed"
                else '<sup class="cite">&#10003;</sup>')
        delta = ""
        di = k.get("delta_fact", -1)
        if di is not None and di >= 0 and di < len(segments):
            dseg = segments[di]
            # Only "growth_percent" has a sign this codebase actually
            # defines (operands are [from, to], so positive is a real
            # increase) - a "difference"'s sign only reflects which
            # operand the model listed first, so it is never colored as
            # a rise or a fall (found live 2026-09-11: a $2.8M net-income
            # *decline*, computed as a "difference", rendered green/"pos"
            # because the raw subtraction happened to come out positive).
            if dseg.get("operation") == "growth_percent":
                cls = "pos" if (dseg.get("value") or 0) >= 0 else "neg"
            else:
                cls = "neutral"
            delta = (f'<div class="delta {cls}">{html.escape(display_value(dseg, currency_unit))}'
                     '<sup class="cite calc">&#8721;</sup></div>')
        cells.append(
            f'<div class="kpi"><div class="label">{html.escape(k.get("label") or "")}</div>'
            f'<div class="value">{html.escape(display_value(seg, currency_unit))}{vtag}</div>'
            f"{delta}</div>"
        )
    return f'<div class="kpi-strip">{"".join(cells)}</div>{_LEGEND}'


def _as_text(value):
    """``executive_insight`` / ``outlook_interpretation`` arrive from
    ``write_narrative`` as a plain string (or None); tolerate a
    ``{"text": ...}`` dict too, in case a caller passes the raw shape."""
    if isinstance(value, dict):
        value = value.get("text")
    return (value or "").strip()


def _timeline_html(segment):
    rows = []
    if segment.get("date") and segment.get("what"):
        rows.append((segment["date"], segment["what"]))
    for m in segment.get("milestones") or []:
        rows.append((m["date"], m["detail"]))
    if len(rows) < 2:
        return ""
    items = "".join(
        f'<div class="tl-item"><span class="tl-date">{html.escape(d)}</span>{html.escape(t)}</div>'
        for d, t in rows
    )
    return f'<div class="timeline">{items}</div>'


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
    if chart.get("type") == "waterfall":
        # defence in depth: only draw a bridge that actually bridges
        if len(values) < 3 or abs(
            values[0] + sum(values[1:-1]) - values[-1]
        ) > 0.01 * max(abs(values[-1]), 1.0):
            return ""
    svg = renderer(chart.get("title", ""), labels, values, chart.get("format", "number"), currency_unit)
    tag = ("&#8721; Computed &amp; verified" if chart.get("type") == "waterfall"
           else "&#10003; Direct quote")
    return f'<figure class="chart-card">{svg}<figcaption><span class="cite">{tag}</span></figcaption></figure>'


def render_rich_report(report, segments, source_hash, currency_unit="actual"):
    """Render ``report`` as a standalone HTML page in the v4 structure: a
    masthead, a KPI strip (each metric tagged direct-quote or computed), an
    executive summary with one boxed cross-section insight, section-by-
    section body with charts, disclosure-gap callouts, and a visually
    distinct outlook block with its interpretation set apart. Every figure
    still traces to a verified segment. Returns a full ``<!doctype html>``.
    """
    fn_num, footnotes = {}, []

    def paras(items):
        return _paragraphs_html(items, segments, source_hash, currency_unit, fn_num, footnotes)

    kpi_html = _kpi_strip_html(report.get("kpis"), segments, currency_unit)

    exec_body = paras(report.get("executive_summary", []))
    insight = _as_text(report.get("executive_insight"))
    if insight:
        exec_body += (
            '<div class="analysis-block"><span class="tag">Analysis</span>'
            f"<p>{_para_html(_substitute(insight, segments, source_hash, currency_unit, fn_num, footnotes), footnotes)}</p></div>"
        )

    sections_html = []
    for section in report.get("sections", []):
        body = paras(section.get("paragraphs", []))
        extra = ""
        if section.get("chart"):
            extra += _chart_html(section["chart"], segments, currency_unit)
        referenced = {
            int(m)
            for p in section.get("paragraphs", [])
            for m in _PLACEHOLDER_RE.findall(p.get("text", ""))
        }
        for i in sorted(referenced):
            if 0 <= i < len(segments) and segments[i].get("type") == "event":
                extra += _timeline_html(segments[i])
        sections_html.append(
            f'<section><h2>{html.escape(section["heading"])}</h2>{body}{extra}</section>'
        )

    gaps = report.get("disclosure_gaps") or []
    gaps_html = ""
    if gaps:
        gaps_html = "<section><h2>What the source does not disclose</h2>" + "".join(
            f'<div class="gap-note"><b>Disclosure gap:</b> '
            f'{_para_html(_substitute(g["text"], segments, source_hash, currency_unit, fn_num, footnotes), footnotes)}</div>'
            for g in gaps
        ) + "</section>"

    outlook_html = ""
    outlook_paragraphs = report.get("outlook")
    interp = _as_text(report.get("outlook_interpretation"))
    if outlook_paragraphs or interp:
        body = paras(outlook_paragraphs or [])
        if interp:
            body += (
                '<p class="interp">Interpretation: '
                f'{_para_html(_substitute(interp, segments, source_hash, currency_unit, fn_num, footnotes), footnotes)}</p>'
            )
        outlook_html = (
            '<div class="outlook"><h2>Outlook — interpretation, not verified fact</h2>'
            f"{body}</div>"
        )

    notes_html = "\n".join(
        f'<p id="fn{i + 1}"><span class="n">{i + 1}.</span>'
        f'{html.escape(_FOOTNOTE_RE.match(note).group(2))} <a href="#ref{i + 1}">&#8617;</a></p>'
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
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:'
        "ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:"
        'wght@400;500;600;700&display=swap">\n'
        f"<style>{_STYLE}</style>\n</head>\n<body>\n"
        # Native browser print, not a generated file - the browser already
        # renders this page pixel-for-pixel (real fonts, real inline SVG
        # charts), so "print to PDF" reproduces it exactly with no second
        # renderer to keep in sync. class="no-print" (via the .pdf-btn rule
        # in @media print) removes the button itself from the output.
        '<button class="pdf-btn" onclick="window.print()" aria-label="Download this report as a PDF">'
        "Download PDF</button>\n"
        '<div class="wrap">\n'
        '<header class="masthead"><div>'
        f"<h1>{esc_title}</h1>"
        '<div class="sub">Independent analysis · Prepared by AnalystOS</div></div>'
        '<div class="meta">Source: uploaded document<br>'
        "Every figure verified &#10003; or computed &#8721;</div></header>\n"
        + kpi_html
        + f'\n<section class="exec-summary"><h2>Executive summary</h2>{exec_body}</section>\n'
        + "\n".join(sections_html)
        + gaps_html
        + outlook_html
        + '\n<footer class="footnotes"><p class="heading">Sources &amp; calculations</p>\n'
        + notes_html
        + "\n</footer>\n</div>\n</body>\n</html>\n"
    )
