"""Render a verified deck spec as a Word memo (Slice 123).

Phase 1 of role-specific outputs: the same verified content the deck draws, laid out
the way legal, research, audit, HR, insurance and financial-crime work is read - a
question, a short answer, then the reasoning and the sources. The memo trusts nothing
in the spec it can derive: ``deck.checked_role`` re-verifies the content and binds it
to the accepted engagement before anything is drawn. Every number is a figure's value
printed by ``deck.format_value`` followed by its reference, exactly as in the deck.
"""

import io
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from analystos.l4 import deck

_TAG_RE = re.compile(r"\[(F[1-9][0-9]{0,2})\]")
INK = RGBColor(0x0F, 0x1B, 0x2D)
MUTED = RGBColor(0x55, 0x61, 0x72)
ACCENT = RGBColor(0x0A, 0x7D, 0x5A)
VERDICT = {"supported": "Supported", "refuted": "Refuted", "untested": "Not yet tested"}
BASIS = {"client": "Client", "computed": "Calculated", "assumption": "Assumption"}


def _rich(paragraph, text, figures, size=11, bold=False, italic=False, color=INK):
    """Write ``text`` with each [F#] tag printed as its verified value and a small reference."""
    pos = 0
    for m in _TAG_RE.finditer(text or ""):
        if m.start() > pos:
            _run(paragraph, text[pos:m.start()], size, bold, italic, color)
        _run(paragraph, deck.format_value(figures[m.group(1)]), size, True, italic, color)
        _run(paragraph, f" {m.group(1)}", max(size - 3, 7), False, False, MUTED)
        pos = m.end()
    if pos < len(text or ""):
        _run(paragraph, text[pos:], size, bold, italic, color)
    return paragraph


def _run(paragraph, text, size, bold=False, italic=False, color=INK):
    run = paragraph.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return run


def _plain(text, figures):
    """``text`` with tags as "value (F#)", for table cells."""
    return _TAG_RE.sub(lambda m: f"{deck.format_value(figures[m.group(1)])} ({m.group(1)})", text or "")


def _heading(doc, text, level=1):
    p = doc.add_heading(level=level)
    _run(p, text, 15 if level == 1 else 12.5, True, False, INK)
    return p


def _bullet(doc, text, figures):
    return _rich(doc.add_paragraph(style="List Bullet"), text, figures)


def _shade(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def _table(doc, header, rows):
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    for i, title in enumerate(header):
        cell = table.rows[0].cells[i]
        cell.text = ""
        _run(cell.paragraphs[0], title, 10, True)
        _shade(cell, "E0E6F2")
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = ""
            _run(cells[i].paragraphs[0], value, 10)
    doc.add_paragraph()
    return table


def source_text(fig, figures):
    if fig["basis"] == "client":
        return f"Client's words: “{fig['quote']}”"
    if fig["basis"] == "computed":
        return f"Calculated: {deck.formula(fig['operation'], fig['inputs'])}"
    return f"Assumption: {_plain(fig['rationale'], figures)}"


def render_memo(spec, engagement, catalog=None):
    """Word (.docx) bytes for a deck spec, or ValueError. See the module docstring."""
    role = deck.checked_role(spec, engagement, catalog)
    content = spec["content"]
    figures = {f["id"]: f for f in content["figures"]}
    try:
        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(11)

        top = doc.add_paragraph()
        _run(top, "MEMO", 9, True, False, ACCENT)
        title = doc.add_paragraph()
        _run(title, content["key_question"], 18, True)
        meta = doc.add_paragraph()
        _run(meta, f"Prepared by AnalystOS · {role['title']}\n", 10, False, False, MUTED)
        _run(meta, "Every number is printed from a figure traced to the client's own words, a stated "
                   "calculation, or a labelled assumption; see Sources.", 10, False, True, MUTED)
        if role["boundary"] == "human-decides":
            p = doc.add_paragraph()
            _run(p, "For the decision of a qualified person: ", 10.5, True)
            _run(p, "; ".join(role.get("human_decides", [])) + ".", 10.5)
        elif role["boundary"] == "approval-gated":
            p = doc.add_paragraph()
            _run(p, "Drafts for approval before anything happens: ", 10.5, True)
            _run(p, "; ".join(role.get("gated_actions", [])) + ".", 10.5)

        _heading(doc, "Short answer")
        _rich(doc.add_paragraph(), content["answer"], figures, 12, True)
        for bullet in content["exec_summary"]:
            _bullet(doc, bullet, figures)

        _heading(doc, "Background")
        _rich(doc.add_paragraph(), content["situation"], figures)
        _rich(doc.add_paragraph(), content["complication"], figures)

        _heading(doc, "Findings")
        for branch in content["issue_tree"]:
            _heading(doc, branch["branch"], 2)
            _rich(doc.add_paragraph(), branch["finding"], figures, 11, True)
            for point in branch.get("points", []):
                _bullet(doc, point, figures)
            for hyp in branch.get("hypotheses", []):
                p = doc.add_paragraph()
                _run(p, f"{VERDICT[hyp['verdict']]}: ", 10, True, False, MUTED)
                _rich(p, hyp["text"], figures, 10, color=MUTED)
            chart = branch.get("chart")
            if isinstance(chart, dict):
                p = doc.add_paragraph()
                _rich(p, chart["title"], figures, 10, False, True, MUTED)
                _table(doc, ["", "Value", "Ref"],
                       [[label, deck.format_value(figures[fid]), fid]
                        for label, fid in zip(chart["labels"], chart["figure_ids"])])
            p = doc.add_paragraph()
            _run(p, "So what: ", 11, True, False, ACCENT)
            _rich(p, branch["so_what"], figures)

        rec = content["recommendation"]
        _heading(doc, "Options")
        _table(doc, ["Option", "What it means", "Effort"],
               [[o["name"] + ("  (recommended)" if o["name"] == rec["option"] else ""),
                 _plain(o["description"], figures), o["effort"].title()] for o in content["options"]])

        _heading(doc, "Recommendation")
        p = doc.add_paragraph()
        _run(p, rec["option"], 12, True, False, ACCENT)
        _rich(doc.add_paragraph(), rec["rationale"], figures)

        _heading(doc, "Next steps")
        for step in content["roadmap"]:
            p = doc.add_paragraph()
            _run(p, step["horizon"], 11, True)
            for action in step["actions"]:
                _bullet(doc, action, figures)

        _heading(doc, "Measures")
        _table(doc, ["Measure", "Target"], [[k["name"], _plain(k["target"], figures)] for k in content["kpis"]])

        _heading(doc, "Risks")
        _table(doc, ["Risk", "Mitigation"],
               [[_plain(r["risk"], figures), _plain(r["mitigation"], figures)] for r in content["risks"]])

        _heading(doc, "Sources: every figure in this memo")
        _table(doc, ["Ref", "Figure", "Value", "Basis", "Where it comes from"],
               [[f["id"], f["label"], deck.value_cell(f), BASIS[f["basis"]], source_text(f, figures)]
                for f in content["figures"]])

        foot = doc.add_paragraph()
        foot.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _run(foot, f"Engagement {spec['engagement_id']} · spec sha256 {deck.spec_digest(spec)}", 8, False, False, MUTED)

        props = doc.core_properties
        props.title = content["key_question"][:250]
        props.author = "AnalystOS"
        props.subject = role["title"]
        props.keywords = f"{deck.SPEC_FORMAT}; engagement {spec['engagement_id']}; spec sha256 {deck.spec_digest(spec)}"
        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - a drawing failure is reported, never raised raw
        raise ValueError(f"could not write the memo: {type(exc).__name__}") from exc
