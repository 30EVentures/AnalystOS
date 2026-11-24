"""Slice 123 - role-specific output formats, phase 1: the memo (.docx) and the workbook
(.xlsx) draw the same verified content as the deck and add no number of their own.

The no-new-numbers check here is independent of the verifier: from each document's text
it removes the formatted values, references, quotes and formulas of the spec's figures
and the few labels the layout draws, and requires that no numeric character is left.
The workbook's formulas are evaluated by a small evaluator written here, not by the
renderer, and must equal the verified values."""

import ast
import copy
import io
import json
import operator
import re
import unicodedata
import unittest
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

from analystos.catalog import load_catalog
from analystos.l3 import engagement as eng
from analystos.l4 import deck
from analystos.l4.memo import render_memo
from analystos.l4.workbook import render_workbook
from analystos.packs import consulting as c
from analystos.packs.replay import ReplayClient

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog()
EXAMPLES = sorted([d for d in (ROOT / "fixtures" / "consulting").iterdir() if d.is_dir()]
                  + [d for d in (ROOT / "fixtures" / "roles").iterdir() if d.is_dir()])


def example(directory):
    client = json.loads((directory / "client.json").read_text())
    record = eng.new_engagement(engagement_id="5a" * 16, created="2026-11-23T00:00:00Z",
                                requested_by=client["requested_by"], problem=client["problem"],
                                roles=client["roles"], catalog=CATALOG)
    for qid, text in client["answers"].items():
        record = eng.answer(record, qid, text)
    record, problems = eng.accept(record, CATALOG)
    assert not problems, problems
    spec = c.build_deck_spec(record, CATALOG, client=ReplayClient([json.loads((directory / "response.json").read_text())]))
    return spec, record


BUILT = {d.name: example(d) for d in EXAMPLES}


def leftover_numbers(text, spec):
    figures = spec["content"]["figures"]
    removable = []
    for f in figures:
        removable += [deck.value_cell(f), deck.format_value(f), f["id"]]
        if f["basis"] == "client":
            removable.append(f["quote"])
        if f["basis"] == "computed":
            removable.append(deck.formula(f["operation"], f["inputs"]))
    removable += list(c.HORIZONS)
    removable.append(f"Engagement {spec['engagement_id']} · spec sha256 {deck.spec_digest(spec)}")
    for item in sorted(set(removable), key=len, reverse=True):
        text = re.sub(r"(?<![\w$.,])" + re.escape(item) + r"(?![\w%])(?![.,]\d)", " ", text)
    text = re.sub(r"\b(?:Q[1-4]|H[12]|FY ?(?:\d{4}|\d{2})|B2B|B2C)\b", " ", text)
    return "".join(ch for ch in text if unicodedata.numeric(ch, None) is not None)


def memo_text(data):
    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts += [cell.text for cell in row.cells]
    return "\n".join(parts)


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def evaluate(formula, values):
    """Evaluate an Excel formula of cell refs, + - * /, SUM and AVERAGE, independently."""
    expr = formula.lstrip("=")
    expr = re.sub(r"AVERAGE\(([^)]*)\)", lambda m: "((" + m.group(1).replace(",", "+") + f")/{m.group(1).count(',') + 1})", expr)
    expr = re.sub(r"SUM\(([^)]*)\)", lambda m: "(" + m.group(1).replace(",", "+") + ")", expr)
    expr = re.sub(r"C(\d+)", lambda m: repr(float(values[int(m.group(1))])), expr)

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"unexpected formula part: {ast.dump(node)}")
    return walk(ast.parse(expr, mode="eval"))


class MemoTest(unittest.TestCase):
    def test_every_example_renders_and_adds_no_number(self):
        for name, (spec, record) in BUILT.items():
            with self.subTest(example=name):
                text = memo_text(render_memo(spec, record, CATALOG))
                self.assertIn("Short answer", text)
                self.assertIn("Sources: every figure in this memo", text)
                self.assertEqual(leftover_numbers(text, spec), "")

    def test_the_check_catches_an_injected_number(self):
        spec, record = BUILT["churn-clinics"]
        text = memo_text(render_memo(spec, record, CATALOG))
        for injected in ("a 10% uplift", "TOP 3", "$1,200,000", "F99"):
            with self.subTest(injected=injected):
                self.assertTrue(leftover_numbers(text + " " + injected, spec))

    def test_the_boundary_is_stated_for_human_decides_roles(self):
        roles = {r["id"]: r for r in CATALOG["roles"]}
        checked = 0
        for name, (spec, record) in BUILT.items():
            role = roles[spec["role"]]
            if role["boundary"] == "human-decides":
                checked += 1
                self.assertIn("For the decision of a qualified person:", memo_text(render_memo(spec, record, CATALOG)))
        self.assertGreater(checked, 0)


class WorkbookTest(unittest.TestCase):
    def load(self, name):
        spec, record = BUILT[name]
        return spec, load_workbook(io.BytesIO(render_workbook(spec, record, CATALOG)))

    def test_every_calculation_is_a_live_formula_equal_to_the_verified_value(self):
        formulas = 0
        for name in BUILT:
            spec, wb = self.load(name)
            ws = wb["Inputs"]
            values = {}
            rows = {ws.cell(row=r, column=1).value: r for r in range(2, ws.max_row + 1)}
            figures = {f["id"]: f for f in spec["content"]["figures"]}
            for fig in spec["content"]["figures"]:  # inputs come before the figures that use them
                r = rows[fig["id"]]
                cell = ws.cell(row=r, column=3).value
                with self.subTest(example=name, figure=fig["id"]):
                    self.assertEqual(ws.cell(row=r, column=4).value, deck.format_value(fig))
                    if fig["basis"] == "computed":
                        self.assertTrue(isinstance(cell, str) and cell.startswith("="), cell)
                        values[r] = evaluate(cell, values)
                        self.assertAlmostEqual(values[r], fig["value"], delta=abs(fig["value"]) * 1e-9 + 1e-9)
                        for x in fig["inputs"]:
                            self.assertIn(f"C{rows[x]}", cell)
                        formulas += 1
                    else:
                        self.assertEqual(cell, figures[fig["id"]]["value"])
                        values[r] = cell
        self.assertGreater(formulas, 20)

    def test_no_text_cell_adds_a_number(self):
        for name in BUILT:
            spec, wb = self.load(name)
            parts = []
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for cell in row:
                        if isinstance(cell.value, str) and not cell.value.startswith("="):
                            parts.append(cell.value)
            with self.subTest(example=name):
                self.assertEqual(leftover_numbers("\n".join(parts), spec), "")

    def test_every_sheet_is_there(self):
        _, wb = self.load("churn-clinics")
        self.assertEqual(wb.sheetnames, ["Summary", "Inputs", "Findings", "Options", "Plan", "Measures", "Risks"])
        heads = [c.value for c in wb["Summary"]["A"] if c.font and c.font.bold]
        self.assertIn("Short answer", heads)
        self.assertIn("Background", heads)


class InjectionTest(unittest.TestCase):
    """Slice 124 review: text that starts with "=" must never become a live Excel formula."""

    def test_text_starting_with_an_equals_sign_stays_text(self):
        directory = ROOT / "fixtures" / "roles" / "finance-modeling"
        client = json.loads((directory / "client.json").read_text())
        response = json.loads((directory / "response.json").read_text())
        payload = '=HYPERLINK("https://example.invalid/x","Open the source")'
        response["risks"][0]["risk"] = payload
        response["risks"][0]["mitigation"] = "=PI()*ROWS(B:B)"
        response["key_question"] = '=HYPERLINK("https://example.invalid/leak","What should change?")'
        record = eng.new_engagement(engagement_id="5a" * 16, created="2026-11-23T00:00:00Z",
                                    requested_by=client["requested_by"], problem=client["problem"],
                                    roles=client["roles"], catalog=CATALOG)
        for qid, text in client["answers"].items():
            record = eng.answer(record, qid, text)
        record, _ = eng.accept(record, CATALOG)
        spec = c.build_deck_spec(record, CATALOG, client=ReplayClient([response]))
        data = render_workbook(spec, record, CATALOG)
        wb = load_workbook(io.BytesIO(data))
        computed = {f["id"] for f in spec["content"]["figures"] if f["basis"] == "computed"}
        formulas = []
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if cell.data_type == "f":
                        formulas.append((ws.title, cell.coordinate))
        inputs = wb["Inputs"]
        expected = {("Inputs", f"C{r}") for r in range(2, inputs.max_row + 1)
                    if inputs.cell(row=r, column=1).value in computed}
        self.assertEqual(set(formulas), expected)
        self.assertEqual(wb["Risks"]["A2"].value, payload)  # kept, but as text
        self.assertEqual(wb["Risks"]["A2"].data_type, "s")
        import zipfile
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            sheets = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("xl/worksheets/"))
        self.assertNotIn("HYPERLINK", re.sub(r"<is>.*?</is>|<v>.*?</v>", "", sheets))
        self.assertNotIn("PI()", re.sub(r"<is>.*?</is>|<v>.*?</v>", "", sheets))


class RefusalTest(unittest.TestCase):
    def test_both_formats_refuse_what_they_cannot_reverify(self):
        spec, record = BUILT["churn-clinics"]
        edited = copy.deepcopy(spec)
        edited["content"]["answer"] = "Churn will hit [F2] next year, so act now on retention."
        forged = copy.deepcopy(spec)
        forged["client_text"] += "\nWe expect $90 million in new revenue."
        cases = (("edited", edited, record), ("forged client text", forged, record),
                 ("another role", dict(spec, role="fpa-analyst"), record),
                 ("wrong engagement", spec, dict(record, id="f" * 32)), ("not an engagement", spec, {"x": 1}))
        for render in (render_memo, render_workbook):
            for label, s, r in cases:
                with self.subTest(renderer=render.__name__, case=label):
                    with self.assertRaisesRegex(ValueError, "refusing to render"):
                        render(s, r, CATALOG)


if __name__ == "__main__":
    unittest.main()
