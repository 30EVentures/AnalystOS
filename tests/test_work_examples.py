"""Slice 127 - a realistic worked example for every work kind each family delivers.

Slice 126 tested every role with synthetic work. These examples are written the way
the role would write them for a real (synthetic) client: each lives in
fixtures/work/<role id>/ with the client's words and a model-shaped response. Each
one must verify on the first attempt with its role's own kinds, render in the role's
own format with no number that is not a figure, and, for a reconciliation, balance in
the workbook through live formulas. A coverage test keeps the set complete: every
(family, kind) pair the catalog owes has at least one realistic example here or in
the family's own worked example.
"""

import io
import json
import re
import unittest
from pathlib import Path

from openpyxl import load_workbook

from analystos.catalog import load_catalog
from analystos.l3 import engagement as eng
from analystos.l4 import formats
from analystos.packs import consulting as c
from analystos.packs import work
from analystos.packs.replay import ReplayClient
from tests.test_formats import evaluate, leftover_numbers
from tests.test_work import example_dir, rendered_text, without_code

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog()
ROLES = {r["id"]: r for r in CATALOG["roles"]}
EXAMPLES = sorted(d for d in (ROOT / "fixtures" / "work").iterdir() if d.is_dir())
FAMILY_EXAMPLE_ROLES = {json.loads(p.read_text())["roles"][0]
                        for p in [*(ROOT / "fixtures" / "roles").glob("*/client.json"),
                                  ROOT / "fixtures" / "consulting" / "churn-clinics" / "client.json"]}
# A draft that reads as already acted on: sent, emailed, posted, booked, filed or signed (Slice 127 review).
_ACTED = r"(?:sent|emailed|posted|booked|filed|signed|submitted)"
DONE = re.compile(r"\b(?:has|have|had|was|were)\s+(?:already\s+)?(?:been\s+)?" + _ACTED + r"\b"
                  r"|\b(?:we|i)\s+(?:have\s+)?(?:already\s+)?" + _ACTED + r"\s+(?:this|it|both|these|the\s+(?:notice|entries|entry|letter|email))\b"
                  r"|\b(?:we|i)\s+" + _ACTED + r"\s+it\b", re.I)


def load(directory):
    client = json.loads((directory / "client.json").read_text())
    response = json.loads((directory / "response.json").read_text())
    return client, response


def build(directory):
    client, response = load(directory)
    record = eng.new_engagement(engagement_id="5a" * 16, created="2026-11-24T00:00:00Z",
                                requested_by=client["requested_by"], problem=client["problem"],
                                roles=client["roles"], catalog=CATALOG)
    for qid, text in client["answers"].items():
        record = eng.answer(record, qid, text)
    record, problems = eng.accept(record, CATALOG)
    assert not problems, (directory.name, problems)
    spec = c.build_deck_spec(record, CATALOG, client=ReplayClient([response]))
    return spec, record


def reconciliation_totals(data):
    """{sheet: {row label: value}} for every formula row, each formula evaluated independently."""
    wb = load_workbook(io.BytesIO(data))
    inputs = wb["Inputs"]
    values = {}
    for r in range(2, inputs.max_row + 1):
        cell = inputs.cell(row=r, column=3).value
        values[r] = evaluate(cell, values) if isinstance(cell, str) else cell
    out = {}
    for ws in wb.worksheets:
        if not ws.title.startswith("Reconciliation"):
            continue
        sheet, rows = {}, {}
        for r in range(1, ws.max_row + 1):
            label, amount = ws.cell(row=r, column=1).value, ws.cell(row=r, column=2).value
            if isinstance(amount, str) and amount.startswith("="):
                expr = re.sub(r"Inputs!C(\d+)", lambda m: repr(float(values[int(m.group(1))])), amount)
                expr = re.sub(r"\bB(\d+)\b", lambda m: repr(float(sheet[int(m.group(1))])), expr)
                sheet[r] = evaluate(expr, {})
                rows[label] = sheet[r]
        out[ws.title] = rows
    return out


class WorkExamplesTest(unittest.TestCase):
    def test_every_role_has_a_worked_example_of_its_own(self):
        # Slice 129: the 13 family examples plus one example per other role, 73 in all.
        self.assertEqual(len(FAMILY_EXAMPLE_ROLES), 13)
        self.assertEqual({d.name for d in EXAMPLES} | FAMILY_EXAMPLE_ROLES, set(ROLES))
        self.assertEqual({d.name for d in EXAMPLES} & FAMILY_EXAMPLE_ROLES, set())

    def test_each_example_carries_exactly_its_roles_work(self):
        for directory in EXAMPLES:
            client, response = load(directory)
            with self.subTest(example=directory.name):
                self.assertEqual(client["roles"], [directory.name])
                owed = work.required_kinds(ROLES[directory.name])
                self.assertEqual(sorted({item["kind"] for item in response.get("work", [])}), owed)
                if not owed:
                    self.assertNotIn("work", response)
                self.assertIn("Not a real company", client["note"])

    def test_each_example_verifies_first_time_and_renders_in_its_role_format(self):
        for directory in EXAMPLES:
            with self.subTest(example=directory.name):
                spec, record = build(directory)
                self.assertEqual(spec["attempts"], 1)
                self.assertEqual(spec["work_kinds"], work.required_kinds(ROLES[directory.name]))
                data, fmt = formats.render(spec, record, CATALOG)
                self.assertEqual(fmt, formats.format_of(ROLES[directory.name]))
                text = rendered_text(data, fmt)
                for item in spec["content"].get("work", []):
                    self.assertIn(work.title_of(item).split(":")[0], text)
                self.assertEqual(leftover_numbers(without_code(text, spec), spec), "")

    def test_each_reconciliation_balances_through_live_formulas(self):
        seen = 0
        for directory in EXAMPLES:
            _, response = load(directory)
            if not any(item["kind"] == "reconciliation" for item in response.get("work", [])):
                continue
            with self.subTest(example=directory.name):
                spec, record = build(directory)
                data, fmt = formats.render(spec, record, CATALOG)
                self.assertEqual(fmt["name"], "workbook")
                sheets = reconciliation_totals(data)
                self.assertEqual(len(sheets), 1)
                for rows in sheets.values():
                    self.assertNotIn("subtract from a", rendered_text(data, fmt))  # effects read as in the memo and deck
                    self.assertAlmostEqual(rows["Side A adjusted"], rows["Side B adjusted"])
                    self.assertAlmostEqual(rows["Difference"], 0)
                    seen += 1
        self.assertEqual(seen, sum("reconciliation" in work.required_kinds(ROLES[d.name]) for d in EXAMPLES))

    def test_drafts_are_written_for_approval_and_never_read_as_done(self):
        seen = 0
        for directory in EXAMPLES:
            _, response = load(directory)
            boundary = ROLES[directory.name]["boundary"]
            for item in response.get("work", []):
                if item["kind"] != "draft":
                    continue
                with self.subTest(example=directory.name):
                    if boundary == "approval-gated":
                        self.assertIn("approve", item["for"])
                    elif boundary == "human-decides":
                        self.assertRegex(item["for"], r"approve|review")
                    body = " ".join(item["body"])
                    self.assertIsNone(DONE.search(body), body)
                    seen += 1
        self.assertEqual(seen, sum(work.required_kinds(ROLES[d.name]).count("draft") for d in EXAMPLES))

    def test_the_done_pattern_catches_the_review_examples(self):
        for text in ("This notice has been sent and signed.", "We have already emailed this to you and posted both entries.",
                     "The entries were booked.", "We filed it yesterday.", "I sent this to the supplier."):
            self.assertIsNotNone(DONE.search(text), text)
        self.assertIsNone(DONE.search("We sent a payment of [F4] on the last day of the month."))

    def test_case_files_ask_a_qualified_person(self):
        for directory in EXAMPLES:
            _, response = load(directory)
            for item in response.get("work", []):
                if item["kind"] == "case_file":
                    with self.subTest(example=directory.name):
                        self.assertTrue(item["for_decision"].startswith("Should the "))
                        self.assertTrue(item["for_decision"].endswith("?"))


class DistinctTest(unittest.TestCase):
    """Slice 129 review: every role's example is its own, never another role's renamed."""

    def all_examples(self):
        dirs = list(EXAMPLES) + [d for d in (ROOT / "fixtures" / "roles").iterdir() if d.is_dir()]
        return dirs + [ROOT / "fixtures" / "consulting" / "churn-clinics"]

    def test_every_client_problem_and_answer_is_different(self):
        problems, answers, questions = set(), set(), set()
        for directory in self.all_examples():
            client, response = load(directory)
            problems.add(client["problem"])
            answers.add(response["answer"])
            questions.add(response["key_question"])
        self.assertEqual((len(problems), len(answers), len(questions)), (73, 73, 73))


class HelperTest(unittest.TestCase):
    def test_a_blank_code_line_does_not_hide_stray_numbers(self):
        spec = {"content": {"work": [{"kind": "code", "code": "x = 1\n\ny = 2\n"}]}}
        self.assertEqual(without_code("x = 1 and 42", spec).split(), ["and", "42"])


class SignWordTest(unittest.TestCase):
    """Slice 129 review: "fell [F3]" with a negative F3 printed "fell -40%"."""

    FIGS = {"F1": {"value": -40, "unit": "percent"}, "F2": {"value": 40, "unit": "percent"},
            "F3": {"value": 1, "unit": "points"}}

    def test_a_fall_word_before_a_negative_figure_is_refused_with_the_fix(self):
        for text in ("Users fell [F1].", "Active users are down [F1].", "Margin fell by [F1].", "Users dropped [F1]"):
            with self.subTest(text=text):
                problems = c.sign_problems("answer", text, self.FIGS)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn("double negative", problems[0])
                self.assertIn("changed by [F1]", problems[0])

    def test_a_rise_word_before_a_negative_figure_is_refused(self):
        self.assertIn("says it went up", c.sign_problems("answer", "Users rose [F1].", self.FIGS)[0])

    def test_plain_or_positive_wording_passes(self):
        for text in ("Users fell [F2].", "Users changed by [F1].", "Users rose [F2].", "Users fell to [F1].",
                     "The fall was [F1]."):
            with self.subTest(text=text):
                self.assertEqual(c.sign_problems("answer", text, self.FIGS), [])

    def test_the_verifier_runs_it_on_prose_and_work(self):
        directory = ROOT / "fixtures" / "work" / "customer-success-associate"
        _, response = load(directory)
        response["answer"] = "Active seats fell [F1] last quarter, so check in before the renewal."
        response["figures"] = [{"id": "F1", "label": "x", "value": -40, "unit": "percent", "basis": "assumption",
                                "rationale": "a test value"}] + [f for f in response["figures"] if f["id"] != "F1"]
        problems = c.verify_content(c._normalize(response), "", None)
        self.assertTrue(any("double negative" in p for p in problems), problems)

    def test_one_point_is_singular(self):
        from analystos.l4 import deck
        self.assertEqual(deck.format_value({"value": 1, "unit": "points"}), "1 pt")
        self.assertEqual(deck.format_value({"value": -1, "unit": "points"}), "-1 pt")
        self.assertEqual(deck.format_value({"value": 2, "unit": "points"}), "2 pts")


class CoverageTest(unittest.TestCase):
    def test_every_kind_each_family_delivers_has_a_realistic_example(self):
        owed = {(r["family"], k) for r in CATALOG["roles"] for k in work.required_kinds(r)}
        covered = set()
        for family in {r["family"] for r in CATALOG["roles"]}:
            response = json.loads((example_dir(family) / "response.json").read_text())
            covered |= {(family, item["kind"]) for item in response.get("work", [])}
        for directory in EXAMPLES:
            _, response = load(directory)
            covered |= {(ROLES[directory.name]["family"], item["kind"]) for item in response.get("work", [])}
        self.assertEqual(sorted(owed - covered), [])
        self.assertEqual(len(owed), 20)


if __name__ == "__main__":
    unittest.main()
