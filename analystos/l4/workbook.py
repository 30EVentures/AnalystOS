"""Render a verified deck spec as an Excel workbook (Slice 123).

Phase 1 of role-specific outputs, for finance, accounting and data work: the same
verified content, laid out so a reader can audit every number by clicking it.

- **Inputs**: every figure, one row each. A client figure's cell holds the client's
  value and its quote; an assumption holds its value and rationale; a calculated
  figure's cell is a live Excel formula over the cells of its inputs, written from the
  same operation the verifier recomputed, so Excel recalculates what the deck states.
- **Summary**, **Findings**, **Options**, **Plan**, **Measures**, **Risks**: the
  reasoning, with each number printed as "7% (F2)" exactly as ``deck.format_value``
  prints it in the deck.

``deck.checked_role`` re-verifies the content and binds it to the accepted engagement
before anything is written.
"""

import io
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from analystos.l4 import deck

_TAG_RE = re.compile(r"\[(F[1-9][0-9]{0,2})\]")
HEAD_FILL = PatternFill("solid", fgColor="E0E6F2")
CALC_FILL = PatternFill("solid", fgColor="DCF1E9")
HEAD_FONT = Font(bold=True, color="0F1B2D")
WRAP = Alignment(wrap_text=True, vertical="top")
BASIS = {"client": "Client", "computed": "Calculated", "assumption": "Assumption"}
# Excel number formats per unit, chosen to show what deck.format_value shows.
NUMBER_FORMATS = {"percent": '0.0##"%"', "points": '0.0##" pts"', "usd": '"$"#,##0.00', "ratio": '0.00"x"',
                  "count": "#,##0.##", "months": '0.##" months"', "other": "#,##0.##"}
VALUE_COL = "C"


def formula(operation, refs):
    """The Excel formula for a calculated figure over its input cells, mirroring the
    verifier's recomputation (``analyze._recompute`` and the consulting pack's two extra
    operations). ``refs`` are cell addresses in input order."""
    if operation == "sum":
        return f"=SUM({','.join(refs)})"
    if operation in ("difference", "remainder"):
        return "=" + refs[0] + "".join(f"-{r}" for r in refs[1:])
    if operation == "average":
        return f"=AVERAGE({','.join(refs)})"
    if operation == "ratio":
        return f"={refs[0]}/{refs[1]}"
    if operation == "growth_percent":
        return f"=({refs[1]}-{refs[0]})/{refs[0]}*100"
    if operation == "percent_of_total":
        return f"={refs[0]}/{refs[1]}*100"
    if operation == "product":
        return "=" + "*".join(refs)
    if operation == "percent_of":
        return f"={refs[0]}*{refs[1]}/100"
    raise ValueError(f"no formula for operation {operation!r}")


def _plain(text, figures):
    return _TAG_RE.sub(lambda m: f"{deck.format_value(figures[m.group(1)])} ({m.group(1)})", text or "")


def _sheet(wb, title, header, rows, widths):
    ws = wb.create_sheet(title)
    ws.append(header)
    for cell in ws[1]:
        cell.font, cell.fill = HEAD_FONT, HEAD_FILL
    for row in rows:
        ws.append(row)
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = WRAP
    ws.freeze_panes = "A2"
    return ws


def render_workbook(spec, engagement, catalog=None):
    """Excel (.xlsx) bytes for a deck spec, or ValueError. See the module docstring."""
    role = deck.checked_role(spec, engagement, catalog)
    content = spec["content"]
    figures = {f["id"]: f for f in content["figures"]}
    try:
        wb = Workbook()
        summary = wb.active
        summary.title = "Summary"
        lines = [["AnalystOS · " + role["title"]], [content["key_question"]], [],
                 ["Short answer"], [_plain(content["answer"], figures)]]
        lines += [["• " + _plain(b, figures)] for b in content["exec_summary"]]
        lines += [[], ["Background"], [_plain(content["situation"], figures)], [_plain(content["complication"], figures)]]
        if role["boundary"] == "human-decides":
            lines += [[], ["For the decision of a qualified person: " + "; ".join(role.get("human_decides", [])) + "."]]
        elif role["boundary"] == "approval-gated":
            lines += [[], ["Drafts for approval before anything happens: " + "; ".join(role.get("gated_actions", [])) + "."]]
        lines += [[], ["Every number is a figure on the Inputs sheet: the client's own words, a live formula over "
                       "other figures, or a labelled assumption."],
                  [f"Engagement {spec['engagement_id']} · spec sha256 {deck.spec_digest(spec)}"]]
        for line in lines:
            summary.append(line)
        summary.column_dimensions["A"].width = 110
        for row in summary.iter_rows():
            for cell in row:
                cell.alignment = WRAP
        for row in summary.iter_rows(max_col=1):
            if row[0].value in ("Short answer", "Background") or row[0].row == 1:
                row[0].font = HEAD_FONT
        summary.cell(row=2, column=1).font = Font(bold=True, size=14)

        inputs = wb.create_sheet("Inputs", 1)
        inputs.append(["Ref", "Figure", "Value", "Shown as", "Basis", "Where it comes from"])
        for cell in inputs[1]:
            cell.font, cell.fill = HEAD_FONT, HEAD_FILL
        row_of = {}
        for i, fig in enumerate(content["figures"], start=2):
            row_of[fig["id"]] = i
        for fig in content["figures"]:
            r = row_of[fig["id"]]
            if fig["basis"] == "computed":
                value = formula(fig["operation"], [f"{VALUE_COL}{row_of[x]}" for x in fig["inputs"]])
                where = f"Calculated: {deck.formula(fig['operation'], fig['inputs'])}"
            elif fig["basis"] == "client":
                value, where = fig["value"], f"Client's words: “{fig['quote']}”"
            else:
                value, where = fig["value"], f"Assumption: {_plain(fig['rationale'], figures)}"
            inputs.append([fig["id"], fig["label"], value, deck.format_value(fig), BASIS[fig["basis"]], where])
            cell = inputs.cell(row=r, column=3)
            cell.number_format = NUMBER_FORMATS.get(fig["unit"], "General")
            if fig["basis"] == "computed":
                cell.fill = CALC_FILL
        for col, width in zip("ABCDEF", (6, 44, 16, 14, 12, 70)):
            inputs.column_dimensions[col].width = width
        for row in inputs.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = WRAP
        inputs.freeze_panes = "A2"

        findings = []
        for branch in content["issue_tree"]:
            hyps = "; ".join(f"{h['verdict']}: {_plain(h['text'], figures)}" for h in branch.get("hypotheses", []))
            findings.append([branch["branch"], _plain(branch["finding"], figures),
                             "\n".join("• " + _plain(p, figures) for p in branch.get("points", [])),
                             hyps, _plain(branch["so_what"], figures)])
        _sheet(wb, "Findings", ["Question", "Finding", "Evidence", "Hypotheses", "So what"], findings, (24, 40, 50, 40, 40))
        rec = content["recommendation"]
        _sheet(wb, "Options", ["Option", "What it means", "Effort", "Recommended"],
               [[o["name"], _plain(o["description"], figures), o["effort"].title(),
                 "Yes: " + _plain(rec["rationale"], figures) if o["name"] == rec["option"] else ""]
                for o in content["options"]], (30, 60, 10, 60))
        _sheet(wb, "Plan", ["When", "Action"],
               [[step["horizon"], _plain(a, figures)] for step in content["roadmap"] for a in step["actions"]], (18, 90))
        _sheet(wb, "Measures", ["Measure", "Target"], [[k["name"], _plain(k["target"], figures)] for k in content["kpis"]],
               (40, 70))
        _sheet(wb, "Risks", ["Risk", "Mitigation"],
               [[_plain(r["risk"], figures), _plain(r["mitigation"], figures)] for r in content["risks"]], (55, 55))

        props = wb.properties
        props.title = content["key_question"][:250]
        props.creator = "AnalystOS"
        props.subject = role["title"]
        props.keywords = f"{deck.SPEC_FORMAT}; engagement {spec['engagement_id']}; spec sha256 {deck.spec_digest(spec)}"
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - a drawing failure is reported, never raised raw
        raise ValueError(f"could not write the workbook: {type(exc).__name__}") from exc
