"""L4 - a real, server-generated PDF for the rich (v4) report, matching
``analystos.l4.rich_export``'s own visual system (a KPI strip, charts,
boxed outlook/insight/disclosure-gap blocks) as faithfully as a print
medium allows - ``reportlab``, not "open the HTML and print" (the same
guarantee Slice 24 already gives the flat report's own PDF). See
specs/slice-48/spec.md.

Charts here are **not** the inline-SVG strings ``analystos.l4.charts``
builds - ``reportlab`` doesn't render SVG - but the exact same resolved
``(labels, values)`` and the exact same ``_detect_chart_type`` decision
``rich_export`` already makes, drawn with ``reportlab``'s own graphics
primitives instead. One shape decision, two renderers - the PDF is never
a second, independent guess at what kind of chart the data is.

Typography: the real IBM Plex Sans/Serif/Mono font files (SIL Open Font
License - redistributable), bundled under ``analystos/l4/fonts/``,
registered with ``reportlab`` at import time - not the built-in base
fonts, so the PDF's typography is the same family the HTML/browser-print
version already uses, not just a same-role stand-in.
"""

import io
import re
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Line, Rect, String

from analystos.l4.export import _BOLD_RE, _MARKER_RE, display_value, format_number
from analystos.l4.rich_export import (
    _FORWARD_HORIZONS,
    _PLACEHOLDER_RE,
    _arithmetic,
    _as_text,
    _detect_chart_type,
    _resolve_chart,
)

_FONTS_DIR = Path(__file__).resolve().parent / "fonts"


def _register_fonts():
    families = {
        "IBMPlexSans": ("IBMPlexSans-Regular.ttf", "IBMPlexSans-SemiBold.ttf"),
        "IBMPlexSerif": ("IBMPlexSerif-Regular.ttf", "IBMPlexSerif-SemiBold.ttf"),
        "IBMPlexMono": ("IBMPlexMono-Regular.ttf", "IBMPlexMono-SemiBold.ttf"),
    }
    for family, (regular, bold) in families.items():
        pdfmetrics.registerFont(TTFont(family, str(_FONTS_DIR / regular)))
        pdfmetrics.registerFont(TTFont(f"{family}-Bold", str(_FONTS_DIR / bold)))
        registerFontFamily(
            family, normal=family, bold=f"{family}-Bold", italic=family, boldItalic=f"{family}-Bold",
        )


_register_fonts()

# One semantic color system, the same roles rich_export's own CSS custom
# properties already use - never a second, drifting palette.
_INK = colors.HexColor("#14171C")
_INK_SOFT = colors.HexColor("#4A4E57")
_VERIFIED = colors.HexColor("#1F4B47")
_COMPUTED = colors.HexColor("#2E4570")
_INTERP = colors.HexColor("#8A6A2A")
_INTERP_BG = colors.HexColor("#F7EFDD")
_NEG = colors.HexColor("#8C3F32")
_PANEL = colors.HexColor("#F5F3EE")
_RULE = colors.HexColor("#DBD7CC")
_PALETTE = (_VERIFIED, colors.HexColor("#C9C4B4"), _COMPUTED, colors.HexColor("#5C8A72"), _NEG)

_PAGE_SIZE = letter
_MARGIN = 0.75 * inch

_STYLES = {
    "title": ParagraphStyle("title", fontName="IBMPlexSerif-Bold", fontSize=22, leading=26, textColor=_INK),
    "sub": ParagraphStyle("sub", fontName="IBMPlexSans", fontSize=9.5, leading=13, textColor=_INK_SOFT),
    "h2": ParagraphStyle(
        "h2", fontName="IBMPlexSerif-Bold", fontSize=14, leading=18, textColor=_INK,
        spaceBefore=16, spaceAfter=8, borderColor=_RULE, borderWidth=0, borderPadding=0,
    ),
    "outlook_h2": ParagraphStyle(
        "outlook_h2", fontName="IBMPlexSerif-Bold", fontSize=14, leading=18, textColor=_INTERP, spaceAfter=8,
    ),
    "body": ParagraphStyle("body", fontName="IBMPlexSans", fontSize=10, leading=15, textColor=_INK, spaceAfter=8),
    "interp_tag": ParagraphStyle(
        "interp_tag", fontName="IBMPlexSans-Bold", fontSize=7.5, leading=10, textColor=_INTERP, spaceAfter=4,
    ),
    "interp_body": ParagraphStyle(
        "interp_body", fontName="IBMPlexSans", fontSize=10, leading=15, textColor=_INK,
    ),
    "outlook_interp": ParagraphStyle(
        "outlook_interp", parent=None, fontName="IBMPlexSans-Bold", fontSize=10, leading=15,
        textColor=_INTERP, spaceAfter=0,
    ),
    "gap_label": ParagraphStyle("gap_label", fontName="IBMPlexSans-Bold", fontSize=9.5, textColor=_INK),
    "kpi_label": ParagraphStyle("kpi_label", fontName="IBMPlexSans", fontSize=7.5, leading=10, textColor=_INK_SOFT),
    "kpi_value": ParagraphStyle("kpi_value", fontName="IBMPlexSerif-Bold", fontSize=15, leading=18, textColor=_INK),
    "kpi_delta_pos": ParagraphStyle("kpi_delta_pos", fontName="IBMPlexSans", fontSize=8.5, textColor=_VERIFIED),
    "kpi_delta_neg": ParagraphStyle("kpi_delta_neg", fontName="IBMPlexSans", fontSize=8.5, textColor=_NEG),
    "kpi_delta_neutral": ParagraphStyle("kpi_delta_neutral", fontName="IBMPlexSans", fontSize=8.5, textColor=_INK_SOFT),
    "footnote": ParagraphStyle("footnote", fontName="IBMPlexMono", fontSize=7.5, leading=11, textColor=_INK_SOFT),
    "footnote_heading": ParagraphStyle(
        "footnote_heading", fontName="IBMPlexSans-Bold", fontSize=8, leading=11, textColor=_INK_SOFT, spaceAfter=6,
    ),
    "timeline": ParagraphStyle("timeline", fontName="IBMPlexSans", fontSize=9, leading=13, textColor=_INK),
}

_TAG_RE = re.compile(r"\[(GUIDANCE|PROJECTED|NON-GAAP)\]")
_TAG_COLOR = _INTERP.hexval()[2:]  # "#RRGGBB" -> "RRGGBB", reportlab's own hex form
_VERIFIED_HEX = _VERIFIED.hexval()[2:]


def _substitute_pdf(text, segments, source_hash, currency_unit, footnote_number, footnotes):
    """The PDF-markup counterpart to ``rich_export._substitute`` - same
    footnote-numbering and tag logic, a plain ``[n]``/``[TAG]`` marker
    left in the text exactly the way that function does, converted to
    real ``reportlab`` markup only by ``_para_pdf_markup`` below, after
    the surrounding text has been XML-escaped - so nothing inserted here
    is ever escaped a second time.
    """
    def _sub(match):
        index = int(match.group(1))
        segment = segments[index]
        if index not in footnote_number:
            footnote_number[index] = len(footnotes) + 1
            footnotes.append(_rich_footnote_text(footnote_number[index], source_hash, segment, currency_unit))
        n = footnote_number[index]
        rendered = segment["what"] if segment.get("type") == "event" else display_value(segment, currency_unit)
        horizon = segment.get("horizon", "reported")
        h_tag = f" [{horizon.upper()}]" if horizon in _FORWARD_HORIZONS else ""
        g_tag = " [NON-GAAP]" if segment.get("gaap_status") == "non_gaap" else ""
        return f"{rendered}{h_tag}{g_tag} [{n}]"

    return _PLACEHOLDER_RE.sub(_sub, text)


def _para_pdf_markup(text):
    """Escape a paragraph, then turn ``**bold**``, a plain ``[n]``
    footnote marker, and a plain ``[TAG]`` marker into real ``reportlab``
    inline markup - in that order, so nothing inserted here is escaped a
    second time. Mirrors ``analystos.l4.export._para_pdf_markup``'s exact
    escape-then-convert order for the flat PDF path.
    """
    esc = xml_escape(text)
    esc = _BOLD_RE.sub(lambda m: f"<b>{m.group(1)}</b>", esc)
    esc = _TAG_RE.sub(lambda m: f'<font size="6.5" color="#{_TAG_COLOR}">{m.group(1)}</font>', esc)
    esc = _MARKER_RE.sub(
        lambda m: f'<super><font size="6.5" color="#{_VERIFIED_HEX}">{m.group(1)}</font></super>', esc,
    )
    return esc


def _rich_footnote_text(n, source_hash, segment, currency_unit):
    """Plain footnote text (no markup) - the same content
    ``rich_export._rich_footnote`` produces, format-agnostic since it's
    just a citation/arithmetic string either renderer can show as-is."""
    if segment.get("type") == "computed":
        expr = _arithmetic(segment, currency_unit)
        if expr:
            return f"{n}. {expr}, verified by recomputation. Source {source_hash}."
    citation = segment.get("citation")
    if isinstance(citation, list):
        cite_text = "computed from: " + "; ".join(f'source {source_hash} - "{c}"' for c in citation)
    else:
        cite_text = f'source {source_hash} - "{citation}"'
    return f"{n}. {cite_text}"


def _paragraphs_flowables(paragraphs, segments, source_hash, currency_unit, footnote_number, footnotes, style):
    return [
        Paragraph(
            _para_pdf_markup(_substitute_pdf(p["text"], segments, source_hash, currency_unit, footnote_number, footnotes)),
            style,
        )
        for p in paragraphs
    ]


def _kpi_strip_table(kpis, segments, currency_unit):
    if not kpis:
        return None
    cells = []
    for k in kpis:
        vi = k.get("value_fact", -1)
        if not isinstance(vi, int) or not (0 <= vi < len(segments)):
            continue
        seg = segments[vi]
        if seg.get("value") is None:
            continue
        block = [
            Paragraph(xml_escape(k.get("label") or ""), _STYLES["kpi_label"]),
            Paragraph(xml_escape(display_value(seg, currency_unit)), _STYLES["kpi_value"]),
        ]
        di = k.get("delta_fact", -1)
        if isinstance(di, int) and 0 <= di < len(segments):
            dseg = segments[di]
            if dseg.get("operation") == "growth_percent":
                cls = "kpi_delta_pos" if (dseg.get("value") or 0) >= 0 else "kpi_delta_neg"
            else:
                cls = "kpi_delta_neutral"
            block.append(Paragraph(xml_escape(display_value(dseg, currency_unit)), _STYLES[cls]))
        cells.append(block)
    if not cells:
        return None
    table = Table([cells], colWidths=[(_PAGE_SIZE[0] - 2 * _MARGIN) / len(cells)] * len(cells))
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, 0), 1, _INK),
        ("LINEAFTER", (0, 0), (-2, 0), 0.5, _RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _boxed_block(flowables, bg, border=None):
    """A single-cell Table with a background/border - the print
    equivalent of a CSS "boxed" panel (the insight/outlook/disclosure-gap
    treatment), and, wrapped in KeepTogether by every caller, never split
    across a page boundary."""
    t = Table([[flowables]], colWidths=[_PAGE_SIZE[0] - 2 * _MARGIN])
    style = [
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if border:
        style.append(("BOX", (0, 0), (-1, -1), 1, border))
    t.setStyle(TableStyle(style))
    return t


def _value_label(value, fmt, currency_unit):
    return format_number(value, fmt, currency_unit)


def _pdf_bar_chart(title, labels, values, fmt, currency_unit):
    width, height = _PAGE_SIZE[0] - 2 * _MARGIN, 210
    pad_l, pad_r, pad_t, pad_b = 14, 14, 26, 34
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    max_val = max(values) or 1
    n = len(values)
    slot = plot_w / n
    bar_w = slot * 0.5
    baseline = pad_b
    d = Drawing(width, height)
    d.add(String(pad_l, height - 16, title, fontName="IBMPlexSans-Bold", fontSize=10, fillColor=_INK))
    d.add(Line(pad_l, baseline, width - pad_r, baseline, strokeColor=_RULE))
    for i, (label, val) in enumerate(zip(labels, values)):
        bar_h = (abs(val) / max_val) * plot_h if max_val else 0
        x = pad_l + i * slot + (slot - bar_w) / 2
        d.add(Rect(x, baseline, bar_w, bar_h, fillColor=_PALETTE[i % len(_PALETTE)], strokeColor=None))
        d.add(String(x + bar_w / 2, baseline + bar_h + 4, _value_label(val, fmt, currency_unit),
                      fontName="IBMPlexSans-Bold", fontSize=8, fillColor=_INK, textAnchor="middle"))
        d.add(String(x + bar_w / 2, baseline - 14, str(label), fontName="IBMPlexSans", fontSize=8,
                      fillColor=_INK_SOFT, textAnchor="middle"))
    return d


def _pdf_line_chart(title, labels, values, fmt, currency_unit):
    width, height = _PAGE_SIZE[0] - 2 * _MARGIN, 210
    pad_l, pad_r, pad_t, pad_b = 14, 14, 26, 30
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    max_val, min_val = max(values), min(values)
    span = (max_val - min_val) or 1
    n = len(values)
    step = plot_w / (n - 1) if n > 1 else 0
    baseline = pad_b
    d = Drawing(width, height)
    d.add(String(pad_l, height - 16, title, fontName="IBMPlexSans-Bold", fontSize=10, fillColor=_INK))
    d.add(Line(pad_l, baseline, width - pad_r, baseline, strokeColor=_RULE))
    points = []
    for i, val in enumerate(values):
        x = pad_l + i * step
        y = baseline + ((val - min_val) / span) * plot_h
        points.append((x, y))
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        d.add(Line(x1, y1, x2, y2, strokeColor=_VERIFIED, strokeWidth=2))
    for (x, y), val, label in zip(points, values, labels):
        d.add(Rect(x - 3, y - 3, 6, 6, fillColor=_VERIFIED, strokeColor=None))
        d.add(String(x, y + 8, _value_label(val, fmt, currency_unit), fontName="IBMPlexSans-Bold",
                      fontSize=8, fillColor=_INK, textAnchor="middle"))
        d.add(String(x, baseline - 14, str(label), fontName="IBMPlexSans", fontSize=8,
                      fillColor=_INK_SOFT, textAnchor="middle"))
    return d


def _pdf_waterfall_chart(title, labels, values, fmt, currency_unit):
    width, height = _PAGE_SIZE[0] - 2 * _MARGIN, 210
    pad_l, pad_r, pad_t, pad_b = 14, 14, 26, 34
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    n = len(values)
    baseline = pad_b
    top = max([values[0], values[-1]] + [values[0] + sum(values[1:i + 1]) for i in range(1, n - 1)]) or 1
    slot = plot_w / n
    bar_w = slot * 0.5
    d = Drawing(width, height)
    d.add(String(pad_l, height - 16, title, fontName="IBMPlexSans-Bold", fontSize=10, fillColor=_INK))
    d.add(Line(pad_l, baseline, width - pad_r, baseline, strokeColor=_INK))
    running = 0.0
    for i, (label, val) in enumerate(zip(labels, values)):
        x = pad_l + i * slot + (slot - bar_w) / 2
        if i == 0 or i == n - 1:
            level = val
            y0, y1 = baseline, baseline + (level / top) * plot_h
            color = _VERIFIED
            running = level
            shown, sign = val, ""
        else:
            start_level, end_level = running, running + val
            running = end_level
            y0 = baseline + (start_level / top) * plot_h
            y1 = baseline + (end_level / top) * plot_h
            color = colors.HexColor("#5C8A72") if val >= 0 else _NEG
            shown, sign = abs(val), ("+" if val >= 0 else "-")
        y_bot, y_top = min(y0, y1), max(y0, y1)
        d.add(Rect(x, y_bot, bar_w, max(y_top - y_bot, 1), fillColor=color, strokeColor=None))
        d.add(String(x + bar_w / 2, y_top + 4, f"{sign}{_value_label(shown, fmt, currency_unit)}",
                      fontName="IBMPlexSans-Bold", fontSize=8, fillColor=_INK, textAnchor="middle"))
        d.add(String(x + bar_w / 2, baseline - 14, str(label), fontName="IBMPlexSans", fontSize=8,
                      fillColor=_INK_SOFT, textAnchor="middle"))
    return d


_PDF_CHART_RENDERERS = {"bar": _pdf_bar_chart, "line": _pdf_line_chart, "waterfall": _pdf_waterfall_chart}


def _chart_flowable(chart, segments, currency_unit):
    """The PDF counterpart to ``rich_export._chart_html`` - same
    resolution and the exact same ``_detect_chart_type`` decision (Slice
    47), so the PDF is never a second guess at chart type. The waterfall
    tie-out check is the same post-hoc safety layer, kept independent of
    the detector, exactly as the HTML renderer keeps it.
    """
    resolved = _resolve_chart(chart, segments)
    if resolved is None:
        return None
    labels, values = resolved
    chart_type = _detect_chart_type(labels, values)
    renderer = _PDF_CHART_RENDERERS.get(chart_type)
    if renderer is None:
        return None
    if chart_type == "waterfall":
        if len(values) < 3 or abs(values[0] + sum(values[1:-1]) - values[-1]) > 0.01 * max(abs(values[-1]), 1.0):
            return None
    return renderer(chart.get("title", ""), labels, values, chart.get("format", "number"), currency_unit)


def render_rich_pdf(report, segments, source_hash, currency_unit="actual"):
    """Render ``report`` as real PDF bytes - the same four verified
    inputs ``analystos.l4.rich_export.render_rich_report`` takes, so both
    renderers are driven from identical data, never a re-derivation from
    the HTML. See the module docstring and specs/slice-48/spec.md.
    """
    fn_num, footnotes = {}, []

    def paras(items, style=_STYLES["body"]):
        return _paragraphs_flowables(items, segments, source_hash, currency_unit, fn_num, footnotes, style)

    story = []
    story.append(Paragraph(xml_escape(report.get("title", "")), _STYLES["title"]))
    story.append(Paragraph("Independent analysis &middot; Prepared by AnalystOS", _STYLES["sub"]))
    story.append(Spacer(1, 10))

    kpi_table = _kpi_strip_table(report.get("kpis"), segments, currency_unit)
    if kpi_table is not None:
        story.append(kpi_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Executive summary", _STYLES["h2"]))
    story.extend(paras(report.get("executive_summary", [])))
    insight = _as_text(report.get("executive_insight"))
    if insight:
        block = [
            Paragraph("ANALYSIS", _STYLES["interp_tag"]),
            Paragraph(
                _para_pdf_markup(_substitute_pdf(insight, segments, source_hash, currency_unit, fn_num, footnotes)),
                _STYLES["interp_body"],
            ),
        ]
        story.append(KeepTogether(_boxed_block(block, _PANEL)))
    story.append(Spacer(1, 6))

    for section in report.get("sections", []):
        section_flow = [Paragraph(xml_escape(section["heading"]), _STYLES["h2"])]
        section_flow.extend(paras(section.get("paragraphs", [])))
        if section.get("chart"):
            drawing = _chart_flowable(section["chart"], segments, currency_unit)
            if drawing is not None:
                section_flow.append(Spacer(1, 4))
                section_flow.append(drawing)
        story.append(KeepTogether(section_flow))
        story.append(Spacer(1, 4))

    gaps = report.get("disclosure_gaps") or []
    if gaps:
        story.append(Paragraph("What the source does not disclose", _STYLES["h2"]))
        for g in gaps:
            block = [
                Paragraph("Disclosure gap:", _STYLES["gap_label"]),
                Paragraph(
                    _para_pdf_markup(_substitute_pdf(g["text"], segments, source_hash, currency_unit, fn_num, footnotes)),
                    _STYLES["body"],
                ),
            ]
            story.append(KeepTogether(_boxed_block(block, colors.white, border=_RULE)))
            story.append(Spacer(1, 6))

    outlook_paragraphs = report.get("outlook")
    interp = _as_text(report.get("outlook_interpretation"))
    if outlook_paragraphs or interp:
        block = [Paragraph("Outlook &mdash; interpretation, not verified fact", _STYLES["outlook_h2"])]
        block.extend(paras(outlook_paragraphs or [], style=_STYLES["body"]))
        if interp:
            block.append(Paragraph(
                "Interpretation: " + _para_pdf_markup(
                    _substitute_pdf(interp, segments, source_hash, currency_unit, fn_num, footnotes)
                ),
                _STYLES["outlook_interp"],
            ))
        story.append(KeepTogether(_boxed_block(block, _INTERP_BG, border=colors.HexColor("#D8C384"))))
        story.append(Spacer(1, 10))

    if footnotes:
        story.append(Spacer(1, 8))
        story.append(Paragraph("SOURCES &amp; CALCULATIONS", _STYLES["footnote_heading"]))
        for note in footnotes:
            story.append(Paragraph(xml_escape(note), _STYLES["footnote"]))
            story.append(Spacer(1, 2))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=_PAGE_SIZE,
        leftMargin=_MARGIN, rightMargin=_MARGIN, topMargin=_MARGIN, bottomMargin=_MARGIN,
        title=report.get("title", ""),
    )
    doc.build(story)
    return buf.getvalue()
