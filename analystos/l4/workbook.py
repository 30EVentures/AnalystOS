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
from analystos.packs import work as work_products

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


def _only_our_formulas(wb, own):
    """Store every text cell as text (Slice 124 review): openpyxl turns any string that starts
    with "=" into a live formula, so model- or client-written text such as
    '=HYPERLINK("...")' would otherwise run in Excel. Only the calculation cells this module
    wrote (``own``) stay formulas."""
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if (ws.title, cell.coordinate) in own:
                    continue
                if isinstance(cell.value, str) and cell.data_type == "f":
                    cell.data_type = "s"


EFFECT_SIGN = {"add_to_a": ("a", 1), "subtract_from_a": ("a", -1), "add_to_b": ("b", 1), "subtract_from_b": ("b", -1)}
TITLES = {"draft": "Draft", "register": "Register", "case_file": "Case file", "reconciliation": "Reconciliation",
          "plan": "Plan", "code": "Code"}


def _work_sheet(wb, n, item, figures, row_of, own):
    """One sheet per role-written work product (Slice 126). A reconciliation's amounts and
    adjusted balances are live formulas over the Inputs cells, so Excel shows they agree."""
    kind = item["kind"]
    ws = wb.create_sheet(f"{TITLES[kind]} {n}"[:31])
    ws.append([work_products.title_of(item)])
    ws["A1"].font = Font(bold=True, size=13)
    if kind == "draft":
        ws.append(["For: " + item["for"]])
        for text in item["body"]:
            ws.append([_plain(text, figures)])
        ws.column_dimensions["A"].width = 110
    elif kind == "register":
        ws.append(["Item", "Rating", "Owner", "Status", "Action"])
        for r in item["rows"]:
            ws.append([_plain(r["item"], figures), r["rating"].title(), r["owner"], r["status"].title(),
                       _plain(r["action"], figures)])
        for col, width in zip("ABCDE", (50, 10, 26, 14, 50)):
            ws.column_dimensions[col].width = width
    elif kind == "case_file":
        for heading, key in (("Facts", "facts"), ("Evidence", "evidence"), ("Open questions", "open_questions")):
            if item.get(key):
                ws.append([heading])
                for line in item[key]:
                    ws.append(["\u2022 " + _plain(line, figures)])
        ws.append(["For decision by a qualified person: " + _plain(item["for_decision"], figures)])
        ws.column_dimensions["A"].width = 110
    elif kind == "reconciliation":
        ws.append(["Line", "Amount", "Effect"])
        start = ws.max_row + 1
        lines = [(item["side_a"]["label"], item["side_a"]["figure_id"], "side A")]
        lines += [(l["label"], l["figure_id"], l["effect"]) for l in item.get("items", [])]
        lines.append((item["side_b"]["label"], item["side_b"]["figure_id"], "side B"))
        for label, fid, effect in lines:
            ws.append([label, f"=Inputs!{VALUE_COL}{row_of[fid]}", deck.EFFECT_TEXT.get(effect, effect)])
            own.add((ws.title, f"B{ws.max_row}"))
        a = [f"B{start}"] + [("+" if EFFECT_SIGN[e][1] > 0 else "-") + f"B{start + i + 1}"
                             for i, (_, _, e) in enumerate(lines[1:-1]) if EFFECT_SIGN[e][0] == "a"]
        b_row = start + len(lines) - 1
        b = [f"B{b_row}"] + [("+" if EFFECT_SIGN[e][1] > 0 else "-") + f"B{start + i + 1}"
                             for i, (_, _, e) in enumerate(lines[1:-1]) if EFFECT_SIGN[e][0] == "b"]
        ws.append(["Side A adjusted", "=" + "".join(a), "live formula"])
        own.add((ws.title, f"B{ws.max_row}"))
        ws.append(["Side B adjusted", "=" + "".join(b), "live formula"])
        own.add((ws.title, f"B{ws.max_row}"))
        ws.append(["Difference", f"=B{ws.max_row - 1}-B{ws.max_row}", "zero when reconciled"])
        own.add((ws.title, f"B{ws.max_row}"))
        for row in ws.iter_rows(min_row=start, max_row=ws.max_row, min_col=2, max_col=2):
            row[0].number_format = NUMBER_FORMATS.get(figures[lines[0][1]]["unit"], "General")
        if item.get("entries"):
            ws.append([])
            ws.append(["Proposed entries, for approval"])
            ws.append(["Debit", "Credit", "Amount", "Memo"])
            for e in item["entries"]:
                ws.append([e["debit"], e["credit"], f"=Inputs!{VALUE_COL}{row_of[e['figure_id']]}", _plain(e["memo"], figures)])
                own.add((ws.title, f"C{ws.max_row}"))
                ws.cell(row=ws.max_row, column=3).number_format = NUMBER_FORMATS["usd"]
        for col, width in zip("ABCD", (40, 18, 22, 60)):
            ws.column_dimensions[col].width = width
    elif kind == "plan":
        ws.append(["When", "Task", "Owner", "Done when"])
        for st in item["steps"]:
            ws.append([st["when"], _plain(st["task"], figures), st["owner"], _plain(st["done_when"], figures)])
        for col, width in zip("ABCD", (16, 50, 26, 50)):
            ws.column_dimensions[col].width = width
    elif kind == "code":
        ws.append([work_products.LANGUAGE_NAMES[item["language"]] + " \u00b7 " + _plain(item["purpose"], figures)])
        ws.append(["Draft: not run or reviewed. Numbers inside the code are not figures."])
        for line in item["code"].splitlines():
            ws.append([line])
        ws.column_dimensions["A"].width = 110
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = WRAP


def _count_format(value):
    """A count or plain number: whole numbers without a trailing point (Slice 124 review)."""
    return "#,##0" if float(value).is_integer() else "#,##0.##"


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
        own = set()  # the Inputs cells that hold the formulas written here; nothing else may be a formula
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
            cell.number_format = (_count_format(fig["value"]) if fig["unit"] in ("count", "other")
                                  else NUMBER_FORMATS.get(fig["unit"], "General"))
            if fig["basis"] == "computed":
                cell.fill = CALC_FILL
                own.add(("Inputs", cell.coordinate))
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

        for n, item in enumerate(content.get("work") or [], start=1):
            _work_sheet(wb, n, item, figures, row_of, own)
        _only_our_formulas(wb, own)

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
