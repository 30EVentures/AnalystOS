"""Slice 126 - role-written work products for every role that owes them.

For each of the 40 roles whose catalog deliverables include a draft, register, case
file, reconciliation, plan or code, a test builds work of exactly those kinds on its
family's worked example (a synthetic client), verifies it with the role's kinds,
renders it in the role's own format, and runs the independent no-new-numbers check
(code excepted, by design). Then each rule has a refusal test.
"""

import copy
import io
import json
import re
import unittest
from pathlib import Path

from openpyxl import load_workbook

from analystos.catalog import load_catalog
from analystos.l3 import engagement as eng
from analystos.l4 import deck, formats
from analystos.packs import consulting as c
from analystos.packs import work
from analystos.packs.replay import ReplayClient
from tests.test_formats import evaluate, leftover_numbers, memo_text

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog()
ROLES = {r["id"]: r for r in CATALOG["roles"]}
OWING = [r for r in CATALOG["roles"] if work.required_kinds(r)]


def example_dir(family):
    return ROOT / "fixtures" / "consulting" / "churn-clinics" if family == "consulting" else ROOT / "fixtures" / "roles" / family


def engagement_for(role):
    client = json.loads((example_dir(role["family"]) / "client.json").read_text())
    record = eng.new_engagement(engagement_id="5a" * 16, created="2026-11-23T00:00:00Z",
                                requested_by=client["requested_by"], problem=client["problem"],
                                roles=[role["id"]], catalog=CATALOG)
    for qid, text in client["answers"].items():
        try:
            record = eng.answer(record, qid, text)
        except ValueError:
            pass  # a question this role does not ask
    record, problems = eng.accept(record, CATALOG)
    assert not problems, (role["id"], problems)
    return record


def synthetic_work(kind, figure_ids):
    """Valid work of one kind, citing the example's own figures."""
    a, b = figure_ids[0], figure_ids[1]
    return {
        "draft": {"kind": "draft", "title": "Note for the decision maker", "for": "The decision maker, email",
                  "body": [f"The case rests on [{a}] and [{b}].", "Reply with questions before the deadline."]},
        "register": {"kind": "register", "title": "Issues to track",
                     "rows": [{"item": f"Exposure linked to [{a}].", "rating": "high", "owner": "Team lead",
                               "status": "open", "action": "Confirm the source and agree an owner."},
                              {"item": f"Change in [{b}].", "rating": "medium", "owner": "Finance lead",
                               "status": "in progress", "action": "Review again next month."}]},
        "case_file": {"kind": "case_file", "subject": "Case for review",
                      "facts": [f"The record shows [{a}].", f"It also shows [{b}]."],
                      "evidence": ["The client's own figures and statements."],
                      "open_questions": ["Is any record missing?"],
                      "for_decision": "Should the qualified person approve the proposed next step?"},
        # Every role that owes a reconciliation is in accounting; its example's figures balance for real.
        "reconciliation": json.loads((example_dir("accounting-operations") / "response.json").read_text())["work"][0],
        "plan": {"kind": "plan", "title": "Next steps",
                 "steps": [{"when": "Week one", "task": f"Confirm [{a}] with the owner.", "owner": "Team lead",
                            "done_when": "The owner has confirmed it."},
                           {"when": "Week two", "task": "Share the result.", "owner": "Coordinator",
                            "done_when": "The decision maker has it."}]},
        "code": {"kind": "code", "language": "python", "purpose": "A draft helper for the reviewer.",
                 "code": "def total(rows):\n    return sum(r.amount for r in rows)  # 0 if empty\n"},
    }[kind]


def spec_for(role, kinds=None):
    response = json.loads((example_dir(role["family"]) / "response.json").read_text())
    ids = [f["id"] for f in response["figures"]]
    owed = work.required_kinds(role) if kinds is None else kinds
    response["work"] = [synthetic_work(k, ids) for k in owed]
    record = engagement_for(role)
    return c.build_deck_spec(record, CATALOG, client=ReplayClient([response])), record


def rendered_text(data, fmt):
    if fmt["name"] == "memo":
        return memo_text(data)
    if fmt["name"] == "workbook":
        wb = load_workbook(io.BytesIO(data))
        return "\n".join(str(cell.value) for ws in wb.worksheets for row in ws.iter_rows() for cell in row
                         if isinstance(cell.value, str) and not cell.value.startswith("="))
    from pptx import Presentation
    from tests.test_deck_render import slide_text
    text = "\n".join(slide_text(s) for s in Presentation(io.BytesIO(data)).slides)
    return re.sub(r"\b\d+ / \d+\b|\(\d+ of \d+\)", " ", text)  # page numbers and sources pagination, as in the deck check


def without_code(text, spec):
    for item in spec["content"].get("work", []):
        if item["kind"] == "code":
            for line in item["code"].splitlines():
                text = text.replace(line, " ")
    return text


class EveryRoleTest(unittest.TestCase):
    def test_forty_roles_owe_work(self):
        self.assertEqual(len(OWING), 40)
        self.assertEqual(work.required_kinds(None), [])
        self.assertEqual(work.required_kinds({"deliverables": ["memo", "draft", "code"]}), ["code", "draft"])

    def test_every_role_delivers_its_work_in_its_own_format(self):
        for role in OWING:
            with self.subTest(role=role["id"]):
                spec, record = spec_for(role)
                self.assertEqual(spec["attempts"], 1)
                self.assertEqual(spec["work_kinds"], work.required_kinds(role))
                data, fmt = formats.render(spec, record, CATALOG)
                self.assertEqual(fmt, formats.format_of(role))
                text = rendered_text(data, fmt)
                for item in spec["content"]["work"]:
                    self.assertIn(work.title_of(item).split(":")[0], text)
                self.assertEqual(leftover_numbers(without_code(text, spec), spec), "")

    def test_every_role_is_refused_without_a_kind_it_owes(self):
        for role in OWING:
            kinds = work.required_kinds(role)
            with self.subTest(role=role["id"]):
                response = json.loads((example_dir(role["family"]) / "response.json").read_text())
                ids = [f["id"] for f in response["figures"]]
                response["work"] = [synthetic_work(k, ids) for k in kinds[1:]] or None
                if response["work"] is None:
                    del response["work"]
                problems = c.verify_content(c._normalize(response), c.client_text_of(engagement_for(role)), kinds)
                self.assertTrue(any(f"work must include a {kinds[0]}" in p or "work must include" in p
                                    for p in problems), problems)

    def test_roles_that_owe_no_work_may_not_add_any(self):
        role = ROLES["management-consulting-analyst"]
        response = json.loads((example_dir("consulting") / "response.json").read_text())
        response["work"] = [synthetic_work("draft", ["F1", "F2"])]
        problems = c.verify_content(c._normalize(response), c.client_text_of(engagement_for(role)), [])
        self.assertIn("work is not part of this role's output; leave it out", problems)

    def test_the_prompt_asks_for_each_kind_the_role_owes(self):
        for role in OWING:
            prompt = c.system_prompt(role)
            with self.subTest(role=role["id"]):
                for kind in work.required_kinds(role):
                    self.assertIn(f'a "{kind}"', prompt)
                if role["boundary"] == "approval-gated":
                    self.assertIn("never write as if it was sent", prompt)
        self.assertIn('Leave the content\'s "work" list out', c.system_prompt(ROLES["fpa-analyst"]))


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.role = ROLES["staff-accountant-bookkeeper"]
        self.record = engagement_for(self.role)
        self.text = c.client_text_of(self.record)
        self.response = json.loads((example_dir("accounting-operations") / "response.json").read_text())

    def problems(self, response, kinds=("reconciliation",)):
        return c.verify_content(c._normalize(response), self.text, list(kinds))

    def test_the_worked_reconciliation_balances(self):
        self.assertEqual(self.problems(self.response), [])

    def test_an_unbalanced_reconciliation_is_refused(self):
        bad = copy.deepcopy(self.response)
        bad["work"][0]["items"] = bad["work"][0]["items"][:2]  # drop the unrecorded payment
        self.assertTrue(any("does not balance" in p for p in self.problems(bad)), self.problems(bad))

    def test_an_entry_must_be_a_usd_figure(self):
        bad = copy.deepcopy(self.response)
        bad["work"][0]["entries"][0]["figure_id"] = "F99"
        self.assertTrue(any("entries[0] needs the id of a verified figure" in p for p in self.problems(bad)))

    def test_a_case_file_asks_and_never_decides(self):
        role = ROLES["fraud-analyst"]
        response = json.loads((example_dir("financial-crime") / "response.json").read_text())
        response["work"][0]["for_decision"] = "Approve the risk-ranked queue."
        problems = c.verify_content(c._normalize(response), c.client_text_of(engagement_for(role)), ["case_file"])
        self.assertTrue(any("for_decision must be the question" in p for p in problems), problems)

    def test_numbers_in_work_follow_the_rules(self):
        bad = copy.deepcopy(self.response)
        bad["work"][0]["entries"][0]["memo"] = "Record the 5,500 dollar payment now."
        bad["work"][0]["entries"][0]["debit"] = "Cash account 1010"
        problems = self.problems(bad)
        self.assertTrue(any("entries[0].memo: write numbers only as figure tags" in p for p in problems), problems)
        self.assertTrue(any("entries[0].debit may not contain numbers" in p for p in problems), problems)

    def test_a_kind_the_role_does_not_deliver_is_refused(self):
        extra = copy.deepcopy(self.response)
        extra["work"].append(synthetic_work("draft", ["F1", "F2"]))
        self.assertTrue(any("a draft is not part of this role's output" in p for p in self.problems(extra)))

    def test_fields_of_another_kind_are_refused(self):
        bad = copy.deepcopy(self.response)
        bad["work"][0]["steps"] = [{"when": "Week one", "task": "x", "owner": "y", "done_when": "z"}]
        self.assertTrue(any("do not belong to a reconciliation" in p for p in self.problems(bad)))

    def test_a_renderer_refuses_a_spec_with_other_work_kinds(self):
        spec, record = spec_for(self.role)
        forged = dict(spec, work_kinds=[])
        for render in (deck.render_deck,):
            with self.assertRaisesRegex(ValueError, "refusing to render"):
                render(forged, record, CATALOG)
        data, _ = formats.render(spec, record, CATALOG)
        self.assertTrue(data)


class ReviewNotesTest(unittest.TestCase):
    """Slice 126 review: shapes the renderers need, sides that differ, lower-case choices, code slides."""

    FIGS = ShapeRulesTestFigs = {"F1": {"id": "F1", "value": 100.0, "unit": "usd"},
                                 "F2": {"id": "F2", "value": 40.0, "unit": "usd"}}

    def check(self, work_list, owed):
        return work.verify_work(work_list, self.FIGS, c.number_problems, c.label_problems, set(), owed)

    def test_shapes_a_renderer_cannot_draw_are_refused(self):
        cases = (([{"kind": "draft", "title": "Note", "body": ["Hello."]}], ["draft"], "a draft needs 'for'"),
                 ([{"kind": "plan", "title": "Steps", "steps": ["Do it", "Then this"]}], ["plan"],
                  "steps must be a list of objects"),
                 ([{"kind": "reconciliation", "title": "Cash", "side_a": {"label": "Bank", "figure_id": "F1"},
                    "side_b": {"label": "Ledger", "figure_id": "F2"}, "entries": {"debit": "Cash"}}], ["reconciliation"],
                  "entries must be a list of objects"),
                 ([{"kind": "case_file", "subject": "Case", "facts": "one fact", "evidence": ["x"],
                    "for_decision": "Approve?"}], ["case_file"], "facts must be a list of text"))
        for work_list, owed, needle in cases:
            with self.subTest(needle=needle):
                problems = self.check(work_list, owed)
                self.assertTrue(any(needle in p for p in problems), problems)

    def test_a_figure_reconciled_against_itself_is_refused(self):
        item = {"kind": "reconciliation", "title": "Cash", "side_a": {"label": "Bank", "figure_id": "F1"},
                "side_b": {"label": "Ledger", "figure_id": "F1"}}
        self.assertTrue(any("two different figures" in p for p in self.check([item], ["reconciliation"])))

    def test_capitalised_choices_are_read_as_lower_case(self):
        rows = [{"item": "A gap.", "rating": "High", "owner": "Team lead", "status": "Open", "action": "Fix it."},
                {"item": "Another.", "rating": "LOW", "owner": "Team lead", "status": "In progress", "action": "Close."}]
        out = c._normalize({"work": [{"kind": "Register", "title": "Gaps", "rows": rows}]})
        self.assertEqual(self.check(out["work"], ["register"]), [])

    def test_the_prompt_keeps_dates_and_ids_out_of_work(self):
        self.assertIn("no dates, durations, IDs, clause, form, version or ticket numbers",
                      c.system_prompt(ROLES["content-writer-copywriter"]))

    def test_the_deck_prints_the_code_purpose_with_values_and_says_when_it_cuts(self):
        role = ROLES["junior-software-developer"]
        response = json.loads((example_dir("software-it") / "response.json").read_text())
        response["work"][0]["purpose"] = "Cut the [F3] query first."
        response["work"][0]["code"] = "\n".join(f"line_{chr(97 + i % 26)}" for i in range(50))
        spec = c.build_deck_spec(engagement_for(role), CATALOG, client=ReplayClient([response]))
        data, fmt = formats.render(spec, engagement_for(role), CATALOG)
        text = rendered_text(data, fmt)
        self.assertNotIn("[F3]", text)
        self.assertIn("Python \u00b7 Cut the", text)
        self.assertIn("Showing the first forty lines", text)

    def test_thirds_is_a_quantity_again(self):
        from analystos.packs.numbers import find_numbers
        self.assertTrue(find_numbers("split into thirds"))
        self.assertFalse(find_numbers("Third, set a reminder"))


class ShapeRulesTest(unittest.TestCase):
    """Each shape rule refuses on its own (Slice 126 mutation check)."""

    FIGS = {"F1": {"id": "F1", "value": 100.0, "unit": "usd"}, "F2": {"id": "F2", "value": 40.0, "unit": "usd"},
            "F3": {"id": "F3", "value": 60.0, "unit": "usd"}, "F4": {"id": "F4", "value": 5.0, "unit": "percent"}}

    def check(self, work_list, owed):
        return work.verify_work(work_list, self.FIGS, c.number_problems, c.label_problems, set(), owed)

    def assertRefused(self, work_list, owed, needle):
        problems = self.check(work_list, owed)
        self.assertTrue(any(needle in p for p in problems), (needle, problems))

    def recon(self, **changes):
        item = {"kind": "reconciliation", "title": "Cash check", "side_a": {"label": "Bank", "figure_id": "F1"},
                "side_b": {"label": "Ledger", "figure_id": "F3"},
                "items": [{"label": "Missing payment", "figure_id": "F2", "effect": "add_to_b"}],
                "entries": [{"debit": "Cash", "credit": "Receivables", "figure_id": "F2", "memo": "Record it."}]}
        item.update(changes)
        return item

    def test_a_valid_reconciliation_passes(self):
        self.assertEqual(self.check([self.recon()], ["reconciliation"]), [])

    def test_list_and_item_shape(self):
        self.assertRefused({"kind": "draft"}, ["draft"], "work must be a list of 1 to 6 items")
        self.assertRefused([], ["draft"], "work must be a list of 1 to 6 items")
        self.assertRefused(["text"], ["draft"], "needs a kind in")
        self.assertRefused([{"kind": "poem"}], ["draft"], "needs a kind in")

    def test_counts_and_empty_text(self):
        self.assertRefused([{"kind": "draft", "title": "Note", "for": "Team", "body": []}], ["draft"],
                           "work[0].body must list 1 to 8 items")
        self.assertRefused([{"kind": "draft", "title": "Note", "for": "Team", "body": [" "]}], ["draft"],
                           "work[0].body[0] must be non-empty text")
        self.assertRefused([{"kind": "draft", "title": " ", "for": "Team", "body": ["Hello."]}], ["draft"],
                           "work[0].title must be a short non-empty name")

    def test_register_ratings_and_statuses(self):
        rows = [{"item": "A gap.", "rating": "severe", "owner": "Team lead", "status": "open", "action": "Fix it."},
                {"item": "Another.", "rating": "low", "owner": "Team lead", "status": "done", "action": "Close."}]
        problems = self.check([{"kind": "register", "title": "Gaps", "rows": rows}], ["register"])
        self.assertEqual(sum("needs a rating in" in p for p in problems), 2, problems)

    def test_reconciliation_sides_items_units_and_entries(self):
        self.assertRefused([self.recon(side_a={"label": "Bank", "figure_id": "F9"})], ["reconciliation"],
                           "side_a needs a label and the id of a verified figure")
        self.assertRefused([self.recon(items=[{"label": "X", "figure_id": "F2", "effect": "sideways"}])],
                           ["reconciliation"], "items[0] needs a verified figure id and an effect")
        self.assertRefused([self.recon(items=[{"label": "X", "figure_id": "F4", "effect": "add_to_b"}])],
                           ["reconciliation"], "every line must share one unit")
        bad_entry = self.recon(entries=[{"debit": "Cash", "credit": "Rate", "figure_id": "F4", "memo": "No."}])
        self.assertRefused([bad_entry], ["reconciliation"], "a journal entry's amount must be a usd figure")

    def test_code_language_content_and_characters(self):
        base = {"kind": "code", "language": "python", "purpose": "A helper.", "code": "pass\n"}
        self.assertEqual(self.check([base], ["code"]), [])
        self.assertRefused([dict(base, language="cobol")], ["code"], "language must be one of")
        self.assertRefused([dict(base, code="  ")], ["code"], "code must be non-empty")
        self.assertRefused([dict(base, code="x = 1\x07\n")], ["code"], "code contains control characters")


class ReconciliationWorkbookTest(unittest.TestCase):
    def test_the_adjusted_balances_are_live_formulas_that_agree(self):
        role = ROLES["staff-accountant-bookkeeper"]
        record = engagement_for(role)
        response = json.loads((example_dir("accounting-operations") / "response.json").read_text())
        spec = c.build_deck_spec(record, CATALOG, client=ReplayClient([response]))
        data, fmt = formats.render(spec, record, CATALOG)
        self.assertEqual(fmt["name"], "workbook")
        wb = load_workbook(io.BytesIO(data))
        inputs = wb["Inputs"]
        values = {}
        for r in range(2, inputs.max_row + 1):
            cell = inputs.cell(row=r, column=3).value
            values[r] = evaluate(cell, values) if isinstance(cell, str) else cell
        ws = wb["Reconciliation 1"]
        sheet = {}

        def value(cell_value):
            if isinstance(cell_value, str) and cell_value.startswith("="):
                expr = re.sub(r"Inputs!C(\d+)", lambda m: repr(float(values[int(m.group(1))])), cell_value)
                expr = re.sub(r"\bB(\d+)\b", lambda m: repr(float(sheet[int(m.group(1))])), expr)
                return evaluate(expr, {})
            return cell_value
        rows = {}
        for r in range(1, ws.max_row + 1):
            label, amount = ws.cell(row=r, column=1).value, ws.cell(row=r, column=2).value
            if isinstance(amount, str) and amount.startswith("="):
                sheet[r] = value(amount)
                rows[label] = sheet[r]
        self.assertAlmostEqual(rows["Side A adjusted"], 85450)
        self.assertAlmostEqual(rows["Side B adjusted"], 85450)
        self.assertAlmostEqual(rows["Difference"], 0)


if __name__ == "__main__":
    unittest.main()
