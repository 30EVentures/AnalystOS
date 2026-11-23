"""L4 - render a verified deck spec as a PowerPoint file (Slice 113).

Input is an ``analystos-deck-spec/1`` from ``analystos.packs.consulting``, whose
content has already passed every check there. This module only lays it out:
16:9 slides, an action title on every slide, figure tags shown as small grey
references, a footer on every slide naming the figures it uses and flagging any
assumption, and a sources section listing every figure with its basis.

It adds no claims of its own. The only numbers it writes are figure values on
the sources slides (formatted from the verified figures) and slide numbers.
The file carries a SHA-256 of the canonical deck spec in its properties - a
content digest so a reader can tie the file to the spec, not a signature.
"""

import hashlib
import io
import json
import re

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

SPEC_FORMAT = "analystos-deck-spec/1"

INK = RGBColor(0x14, 0x1B, 0x2D)
MUTED = RGBColor(0x5B, 0x64, 0x76)
FAINT = RGBColor(0x9A, 0xA1, 0xAE)
RULE = RGBColor(0xD9, 0xDD, 0xE4)
ACCENT = RGBColor(0x1F, 0x4E, 0x8C)
ACCENT_SOFT = RGBColor(0xE8, 0xEF, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
VERDICT_COLORS = {
    "supported": (RGBColor(0x1E, 0x7A, 0x46), RGBColor(0xE6, 0xF4, 0xEC)),
    "refuted": (RGBColor(0xA8, 0x32, 0x2C), RGBColor(0xFA, 0xE9, 0xE8)),
    "untested": (RGBColor(0x5B, 0x64, 0x76), RGBColor(0xEE, 0xF0, 0xF3)),
}
FONT = "Calibri"

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)
CONTENT_W = SLIDE_W - 2 * MARGIN
BODY_TOP = Inches(1.75)
FOOTER_TOP = Inches(6.95)
SOURCES_PER_SLIDE = 8

_TAG_RE = re.compile(r"\[(F[1-9][0-9]{0,2})\]")


def spec_digest(spec):
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# Excel number formats per unit, so a chart's data labels read exactly like the deck's text.
NUMBER_FORMATS = {
    "percent": '0.#"%"', "points": '0.#" pts"', "usd": '"$"#,##0', "count": "#,##0.#",
    "ratio": '0.00"x"', "months": '0.#" months"', "other": "#,##0.##",
}


def format_value(figure):
    value, unit = figure["value"], figure["unit"]
    if unit == "percent":
        text = f"{value:,.1f}".rstrip("0").rstrip(".")
        return f"{text}%"
    if unit == "points":
        text = f"{value:,.1f}".rstrip("0").rstrip(".")
        return f"{text} pts"
    if unit == "usd":
        return f"${value:,.0f}" if float(value).is_integer() or abs(value) >= 100 else f"${value:,.2f}"
    if unit == "ratio":
        return f"{value:,.2f}x"
    if unit == "months":
        return f"{value:,.1f}".rstrip("0").rstrip(".") + " months"
    return f"{value:,.1f}".rstrip("0").rstrip(".")


# --- text helpers ---------------------------------------------------------------

def _run(paragraph, text, size, color=INK, bold=False):
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = FONT
    run.font.color.rgb = color
    return run


def _rich(paragraph, text, size, color=INK, bold=False):
    """Write ``text`` with each [F#] tag as a small grey reference."""
    pos = 0
    for m in _TAG_RE.finditer(text):
        before = text[pos:m.start()].rstrip()
        if before:
            _run(paragraph, before, size, color, bold)
        _run(paragraph, f" {m.group(1)}", max(size - 6, 8), FAINT)
        pos = m.end()
    rest = text[pos:]
    if rest:
        _run(paragraph, rest, size, color, bold)


def _textbox(slide, left, top, width, height, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(frame, side, Inches(0.05))
    return box, frame


def _hang(paragraph, indent):
    """A hanging indent: wrapped lines start under the text, not under the bullet."""
    ppr = paragraph._p.get_or_add_pPr()
    ppr.set("marL", str(int(indent)))
    ppr.set("indent", str(-int(indent)))


def _bullet(frame, text, size, color=INK, space=6, first=False):
    paragraph = frame.paragraphs[0] if first else frame.add_paragraph()
    paragraph.space_after = Pt(space)
    _hang(paragraph, Pt(size * 1.1))
    _run(paragraph, "•\t", size, ACCENT, bold=True)
    _rich(paragraph, text, size, color)
    return paragraph


def _paragraphs(frame, items, size, color=INK, bullet=True, space=6):
    for i, item in enumerate(items):
        if bullet:
            _bullet(frame, item, size, color, space, first=(i == 0))
        else:
            paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            paragraph.space_after = Pt(space)
            _rich(paragraph, item, size, color)


def _rect(slide, left, top, width, height, fill, line=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(0.75)
    shape.shadow.inherit = False
    return shape


def _title_size(text):
    n = len(_TAG_RE.sub("", text))
    return 26 if n <= 70 else 22 if n <= 120 else 18 if n <= 200 else 15


def _body_size(items, base=16):
    n = sum(len(i) for i in items)
    return base if n <= 500 else base - 2 if n <= 800 else base - 4


# --- the frame every slide shares --------------------------------------------------------

def _frame(prs, spec, title, figure_ids, number, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(slide, 0, 0, SLIDE_W, Inches(0.12), ACCENT)
    _, frame = _textbox(slide, MARGIN, Inches(0.4), CONTENT_W, Inches(1.2), MSO_ANCHOR.BOTTOM)
    _rich(frame.paragraphs[0], title, _title_size(title), INK, bold=True)
    line = slide.shapes.add_connector(1, MARGIN, Inches(1.62), SLIDE_W - MARGIN, Inches(1.62))
    line.line.color.rgb = RULE
    line.line.width = Pt(1)

    figures = {f["id"]: f for f in spec["content"]["figures"]}
    used = [fid for fid in figure_ids if fid in figures]
    note = ""
    if used:
        assumptions = [fid for fid in used if figures[fid]["basis"] == "assumption"]
        note = "Figures: " + ", ".join(used) + " - see Sources."
        if assumptions:
            note += "  Includes assumption " + ", ".join(assumptions) + ": not from client data."
    _, foot = _textbox(slide, MARGIN, FOOTER_TOP, CONTENT_W - Inches(1.5), Inches(0.35))
    _run(foot.paragraphs[0], note or "Prepared by AnalystOS", 9, MUTED)
    _, page = _textbox(slide, SLIDE_W - MARGIN - Inches(1.4), FOOTER_TOP, Inches(1.4), Inches(0.35))
    page.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _run(page.paragraphs[0], f"{number} / {total}", 9, MUTED)
    return slide


def _stat_tiles(slide, spec, figure_ids, left, top, width, height=Inches(1.5), limit=3):
    """Big-number tiles for the verified figures a slide already uses - no new claims."""
    figures = {f["id"]: f for f in spec["content"]["figures"]}
    chosen = [figures[f] for f in figure_ids if f in figures][:limit]
    if not chosen:
        return
    gap = Inches(0.25)
    tile_w = (width - gap * (len(chosen) - 1)) / len(chosen)
    for i, fig in enumerate(chosen):
        x = left + i * (tile_w + gap)
        assumed = fig["basis"] == "assumption"
        _rect(slide, x, top, tile_w, height, WHITE, line=RULE)
        _rect(slide, x, top, Inches(0.08), height, FAINT if assumed else ACCENT)
        _, frame = _textbox(slide, x + Inches(0.25), top + Inches(0.1), tile_w - Inches(0.35), height - Inches(0.2), MSO_ANCHOR.MIDDLE)
        _run(frame.paragraphs[0], format_value(fig), 28, MUTED if assumed else ACCENT, bold=True)
        p = frame.add_paragraph()
        _run(p, fig["label"], 11, INK)
        p = frame.add_paragraph()
        basis = {"client": "client data", "computed": "calculated", "assumption": "assumption"}[fig["basis"]]
        _run(p, f"{fig['id']} · {basis}", 9, FAINT)


# --- one function per slide kind ---------------------------------------------------------

def _title_slide(prs, spec, s, number, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(slide, 0, 0, SLIDE_W, SLIDE_H, INK)
    _rect(slide, MARGIN, Inches(2.2), Inches(0.12), Inches(2.4), ACCENT)
    _, frame = _textbox(slide, MARGIN + Inches(0.4), Inches(2.1), Inches(11.4), Inches(2.6), MSO_ANCHOR.MIDDLE)
    _rich(frame.paragraphs[0], s["title"], 32 if len(s["title"]) <= 110 else 26, WHITE, bold=True)
    _, sub = _textbox(slide, MARGIN + Inches(0.4), Inches(5.0), Inches(11.4), Inches(1.0))
    role = spec["role"].replace("-", " ").title()
    _run(sub.paragraphs[0], f"{role}  ·  Prepared by AnalystOS", 16, RULE)
    p = sub.add_paragraph()
    _run(p, "Every figure is traced to the client's own words, a stated calculation, or a labelled assumption.", 12, FAINT)
    return slide


def _bullets_slide(prs, spec, s, number, total):
    """The executive summary: the answer as the title, its bullets, and the answer's own
    headline figures as tiles."""
    slide = _frame(prs, spec, s["title"], s["figure_ids"], number, total)
    _, frame = _textbox(slide, MARGIN, BODY_TOP, CONTENT_W, Inches(3.4))
    _paragraphs(frame, s["bullets"], _body_size(s["bullets"], 18) - 2, space=10)
    headline = [m.group(1) for m in _TAG_RE.finditer(s["title"])]
    _stat_tiles(slide, spec, headline, MARGIN, BODY_TOP + Inches(3.55), CONTENT_W, height=Inches(1.45))
    return slide


def _situation_slide(prs, spec, s, number, total):
    slide = _frame(prs, spec, s["title"], s["figure_ids"], number, total)
    width = (CONTENT_W - Inches(0.6)) / 3
    for i, text in enumerate(s["bullets"]):
        label, _, body = text.partition(": ")
        left = MARGIN + i * (width + Inches(0.3))
        _rect(slide, left, BODY_TOP, width, Inches(4.8), ACCENT_SOFT if i < 2 else INK)
        _, frame = _textbox(slide, left + Inches(0.25), BODY_TOP + Inches(0.25), width - Inches(0.5), Inches(4.3))
        _run(frame.paragraphs[0], label.upper(), 12, ACCENT if i < 2 else RULE, bold=True)
        p = frame.add_paragraph()
        p.space_before = Pt(10)
        _rich(p, body, 17 if len(body) <= 220 else 14, INK if i < 2 else WHITE)
    return slide


def _verdict_pill(slide, left, top, verdict):
    fg, bg = VERDICT_COLORS[verdict]
    pill = _rect(slide, left, top, Inches(1.15), Inches(0.32), bg)
    frame = pill.text_frame
    frame.margin_top = frame.margin_bottom = Inches(0.01)
    frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    _run(frame.paragraphs[0], verdict.upper(), 9, fg, bold=True)


def _issue_tree_slide(prs, spec, s, number, total):
    slide = _frame(prs, spec, s["title"], s["figure_ids"], number, total)
    tree = s["tree"]
    q_w = Inches(3.0)
    _rect(slide, MARGIN, BODY_TOP, q_w, Inches(4.9), INK)
    _, q = _textbox(slide, MARGIN + Inches(0.2), BODY_TOP + Inches(0.2), q_w - Inches(0.4), Inches(4.5), MSO_ANCHOR.MIDDLE)
    _rich(q.paragraphs[0], spec["content"]["key_question"], 15, WHITE, bold=True)
    left = MARGIN + q_w + Inches(0.3)
    width = SLIDE_W - MARGIN - left
    row_h = Inches(4.9) / len(tree)
    for i, branch in enumerate(tree):
        top = BODY_TOP + i * row_h
        _rect(slide, left, top + Inches(0.05), width, row_h - Inches(0.1), ACCENT_SOFT)
        _, frame = _textbox(slide, left + Inches(0.2), top + Inches(0.1), Inches(3.0), row_h - Inches(0.2), MSO_ANCHOR.MIDDLE)
        _rich(frame.paragraphs[0], branch["branch"], 14, ACCENT, bold=True)
        hyp_left = left + Inches(3.3)
        hyp_h = (row_h - Inches(0.2)) / max(len(branch["hypotheses"]), 1)
        for j, hyp in enumerate(branch["hypotheses"]):
            h_top = top + Inches(0.1) + j * hyp_h
            _verdict_pill(slide, hyp_left, h_top + (hyp_h - Inches(0.32)) / 2, hyp["verdict"])
            _, hf = _textbox(slide, hyp_left + Inches(1.3), h_top, width - Inches(4.8), hyp_h, MSO_ANCHOR.MIDDLE)
            _rich(hf.paragraphs[0], hyp["text"], 11, INK)
    return slide


def _chart(slide, spec, chart, left, top, width, height):
    """A native, editable column chart whose bars are the charted figures' verified values."""
    figures = {f["id"]: f for f in spec["content"]["figures"]}
    charted = [figures[fid] for fid in chart["figure_ids"]]
    data = CategoryChartData(number_format=NUMBER_FORMATS[charted[0]["unit"]])
    data.categories = list(chart["labels"])
    data.add_series("Value", [f["value"] for f in charted])
    graphic = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, left, top, width, height, data)
    graphic_chart = graphic.chart
    graphic_chart.has_legend = False
    graphic_chart.has_title = True
    graphic_chart.chart_title.text_frame.text = ""
    _rich(graphic_chart.chart_title.text_frame.paragraphs[0], chart["title"], 13, INK, bold=True)
    plot = graphic_chart.plots[0]
    plot.gap_width = 80
    plot.has_data_labels = True
    labels = plot.data_labels
    labels.number_format = NUMBER_FORMATS[charted[0]["unit"]]
    labels.number_format_is_linked = False
    labels.position = XL_LABEL_POSITION.OUTSIDE_END
    labels.font.size = Pt(12)
    labels.font.bold = True
    labels.font.color.rgb = INK
    value_axis = graphic_chart.value_axis
    value_axis.visible = False
    value_axis.has_major_gridlines = False
    value_axis.minimum_scale = 0
    category_axis = graphic_chart.category_axis
    category_axis.tick_labels.font.size = Pt(11)
    category_axis.tick_labels.font.color.rgb = MUTED
    category_axis.format.line.color.rgb = RULE
    series = plot.series[0]
    for i, fig in enumerate(charted):
        point = series.points[i]
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = FAINT if fig["basis"] == "assumption" else ACCENT
    return graphic


def _finding_slide(prs, spec, s, number, total):
    slide = _frame(prs, spec, s["title"], s["figure_ids"], number, total)
    left_w = Inches(7.2)
    _, frame = _textbox(slide, MARGIN, BODY_TOP, left_w, Inches(4.9))
    p = frame.paragraphs[0]
    _run(p, s["branch"].upper(), 12, ACCENT, bold=True)
    p.space_after = Pt(10)
    has_chart = "chart" in s
    for point in s["bullets"]:
        _bullet(frame, point, (15 if has_chart else 17) if len(point) <= 160 else 14, space=8 if has_chart else 12)
    if s.get("so_what"):
        para = frame.add_paragraph()
        para.space_before = Pt(6)
        _run(para, "So what: ", 14 if has_chart else 15, ACCENT, bold=True)
        _rich(para, s["so_what"], 14 if has_chart else 15, INK, bold=True)
    if has_chart:
        _chart(slide, spec, s["chart"], MARGIN, BODY_TOP + Inches(2.25), left_w, Inches(2.75))
    else:
        _stat_tiles(slide, spec, s["figure_ids"], MARGIN, BODY_TOP + Inches(3.4), left_w)
    right = MARGIN + left_w + Inches(0.4)
    width = SLIDE_W - MARGIN - right
    _rect(slide, right, BODY_TOP, width, Inches(4.9), ACCENT_SOFT)
    _, head = _textbox(slide, right + Inches(0.2), BODY_TOP + Inches(0.15), width - Inches(0.4), Inches(0.4))
    _run(head.paragraphs[0], "HYPOTHESES TESTED", 11, ACCENT, bold=True)
    top = BODY_TOP + Inches(0.7)
    for hyp in s["hypotheses"]:
        _verdict_pill(slide, right + Inches(0.2), top, hyp["verdict"])
        _, hf = _textbox(slide, right + Inches(0.2), top + Inches(0.4), width - Inches(0.4), Inches(0.8))
        _rich(hf.paragraphs[0], hyp["text"], 12, INK)
        top += Inches(1.15)
    return slide


def _table(slide, rows, col_widths, top, header, size=12, highlight=None):
    shape = slide.shapes.add_table(len(rows) + 1, len(header), MARGIN, top, CONTENT_W, Inches(0.5))
    table = shape.table
    total = sum(col_widths)
    widths = [int(CONTENT_W * w / total) for w in col_widths]
    widths[-1] = int(CONTENT_W) - sum(widths[:-1])  # exactly the content width, no rounding overflow
    for i, w in enumerate(widths):
        table.columns[i].width = Emu(w)
    for c, text in enumerate(header):
        cell = table.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = INK
        cell.text_frame.paragraphs[0].text = ""
        _run(cell.text_frame.paragraphs[0], text, size - 1, WHITE, bold=True)
    for r, row in enumerate(rows, start=1):
        for c, text in enumerate(row):
            cell = table.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = ACCENT_SOFT if highlight == r - 1 else WHITE
            cell.text_frame.word_wrap = True
            cell.text_frame.paragraphs[0].text = ""
            _rich(cell.text_frame.paragraphs[0], text, size, INK, bold=(c == 0))
    return table


def _options_slide(prs, spec, s, number, total):
    slide = _frame(prs, spec, s["title"], s["figure_ids"], number, total)
    chosen = spec["content"]["recommendation"]["option"].strip().lower()
    rows, highlight = [], None
    for i, o in enumerate(s["options"]):
        recommended = o["name"].strip().lower() == chosen
        if recommended:
            highlight = i
        rows.append([o["name"] + ("  (recommended)" if recommended else ""), o["description"], o["effort"].title()])
    _table(slide, rows, [3, 7, 1.3], BODY_TOP, ["Option", "What it means", "Effort"], 14, highlight)
    return slide


def _recommendation_slide(prs, spec, s, number, total):
    slide = _frame(prs, spec, s["title"], s["figure_ids"], number, total)
    rec = spec["content"]["recommendation"]
    _rect(slide, MARGIN, BODY_TOP, CONTENT_W, Inches(1.3), INK)
    _, top = _textbox(slide, MARGIN + Inches(0.3), BODY_TOP, CONTENT_W - Inches(0.6), Inches(1.3), MSO_ANCHOR.MIDDLE)
    _run(top.paragraphs[0], "WE RECOMMEND", 12, RULE, bold=True)
    p = top.add_paragraph()
    _rich(p, rec["option"], 26, WHITE, bold=True)
    _, why = _textbox(slide, MARGIN, BODY_TOP + Inches(1.6), CONTENT_W, Inches(1.7))
    _run(why.paragraphs[0], "WHY", 12, ACCENT, bold=True)
    p = why.add_paragraph()
    p.space_before = Pt(8)
    _rich(p, rec["rationale"], 18 if len(rec["rationale"]) <= 260 else 15, INK)
    _stat_tiles(slide, spec, s["figure_ids"], MARGIN, BODY_TOP + Inches(3.4), CONTENT_W)
    return slide


def _roadmap_slide(prs, spec, s, number, total):
    slide = _frame(prs, spec, s["title"], s["figure_ids"], number, total)
    width = (CONTENT_W - Inches(0.6)) / 3
    for i, step in enumerate(s["roadmap"]):
        left = MARGIN + i * (width + Inches(0.3))
        _rect(slide, left, BODY_TOP, width, Inches(0.6), ACCENT)
        _, head = _textbox(slide, left + Inches(0.2), BODY_TOP, width - Inches(0.4), Inches(0.6), MSO_ANCHOR.MIDDLE)
        _run(head.paragraphs[0], step["horizon"], 15, WHITE, bold=True)
        _rect(slide, left, BODY_TOP + Inches(0.6), width, Inches(4.3), ACCENT_SOFT)
        _, body = _textbox(slide, left + Inches(0.2), BODY_TOP + Inches(0.8), width - Inches(0.4), Inches(4.0))
        _paragraphs(body, step["actions"], 14 if sum(len(a) for a in step["actions"]) <= 300 else 12, space=10)
    return slide


def _two_column_table_slide(key, headers, fields, widths):
    def render(prs, spec, s, number, total):
        slide = _frame(prs, spec, s["title"], s["figure_ids"], number, total)
        rows = [[item[f] for f in fields] for item in s[key]]
        _table(slide, rows, widths, BODY_TOP, headers, 14)
        return slide
    return render


def formula(operation, inputs):
    """A calculated figure's formula, written the way a reader checks it by hand."""
    a = inputs
    if operation == "sum":
        return " + ".join(a)
    if operation in ("difference", "remainder"):
        return " − ".join(a)
    if operation == "average":
        return f"average of {', '.join(a)}"
    if operation == "ratio" and len(a) == 2:
        return f"{a[0]} ÷ {a[1]}"
    if operation == "growth_percent" and len(a) == 2:
        return f"({a[1]} − {a[0]}) ÷ {a[0]} × 100"
    if operation == "percent_of_total" and len(a) == 2:
        return f"{a[0]} ÷ {a[1]} × 100"
    if operation == "product":
        return " × ".join(a)
    if operation == "percent_of" and len(a) == 2:
        return f"{a[0]} × {a[1]} ÷ 100"
    return f"{operation.replace('_', ' ')} of {', '.join(a)}"


def _source_text(figure):
    if figure["basis"] == "client":
        return f"Client's words: “{figure['quote']}”"
    if figure["basis"] == "computed":
        return f"Calculated: {formula(figure['operation'], figure['inputs'])}"
    return f"Assumption: {figure['rationale']}"


def _sources_slides(prs, spec, s, number, total):
    figures = spec["content"]["figures"]
    slides = []
    chunks = [figures[i:i + SOURCES_PER_SLIDE] for i in range(0, len(figures), SOURCES_PER_SLIDE)]
    for k, chunk in enumerate(chunks):
        title = s["title"] if len(chunks) == 1 else f"{s['title']} ({k + 1} of {len(chunks)})"
        slide = _frame(prs, spec, title, [], number + k, total)
        rows = [[f["id"], f["label"], format_value(f), f["basis"].title(), _source_text(f)] for f in chunk]
        _table(slide, rows, [0.6, 3.2, 1.3, 1.2, 6.0], BODY_TOP, ["Ref", "Figure", "Value", "Basis", "Where it comes from"], 10)
        slides.append(slide)
    return slides


RENDERERS = {
    "title": _title_slide,
    "executive-summary": _bullets_slide,
    "situation": _situation_slide,
    "issue-tree": _issue_tree_slide,
    "finding": _finding_slide,
    "options": _options_slide,
    "recommendation": _recommendation_slide,
    "roadmap": _roadmap_slide,
    "kpis": _two_column_table_slide("kpis", ["Measure", "Target"], ["name", "target"], [4, 7]),
    "risks": _two_column_table_slide("risks", ["Risk", "Mitigation"], ["risk", "mitigation"], [5, 6]),
}


def slide_count(spec):
    figures = len(spec["content"]["figures"])
    sources = max(1, -(-figures // SOURCES_PER_SLIDE))
    return sum(sources if s["kind"] == "sources" else 1 for s in spec["slides"])


def render_deck(spec):
    """PowerPoint bytes for a deck spec. ValueError if it is not a deck spec this renders."""
    if not isinstance(spec, dict) or spec.get("format") != SPEC_FORMAT:
        raise ValueError(f"not an {SPEC_FORMAT} document")
    kinds = [s.get("kind") for s in spec.get("slides", []) if isinstance(s, dict)]
    unknown = [k for k in kinds if k not in RENDERERS and k != "sources"]
    if unknown or not kinds:
        raise ValueError(f"cannot render slide kinds {unknown or 'none'}")

    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    total = slide_count(spec)
    number = 1
    for s in spec["slides"]:
        if s["kind"] == "sources":
            number += len(_sources_slides(prs, spec, s, number, total))
        else:
            RENDERERS[s["kind"]](prs, spec, s, number, total)
            number += 1

    props = prs.core_properties
    props.title = spec["content"]["key_question"][:250]
    props.author = "AnalystOS"
    props.subject = spec["role"]
    props.keywords = f"{SPEC_FORMAT}; engagement {spec['engagement_id']}; spec sha256 {spec_digest(spec)}"
    props.comments = "Every figure is traced to the client's own words, a stated calculation, or a labelled assumption."
    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue()
