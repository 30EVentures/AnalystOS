"""Slice 119 - surviving the live model's natural writing.

The first paid test failed because the live model wrote the natural way. This is
the free stand-in for the live model: every worked example is rewritten the way a
model naturally writes, and must still pass end to end after normalising. And
normalising must never make a wrong number acceptable."""

import copy
import io
import json
import re
import unittest
from pathlib import Path

from pptx import Presentation

from analystos.catalog import load_catalog
from analystos.l3 import engagement as eng
from analystos.l4 import deck
from analystos.packs import consulting as c
from analystos.packs.normalize import narrow_quote, normalize_content, strip_redundant_numbers
from analystos.packs.numbers import find_numbers
from analystos.packs.replay import ReplayClient
from tests.test_deck_render import unexplained_numbers

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog()
EXAMPLES = sorted([d for d in (ROOT / "fixtures" / "consulting").iterdir() if d.is_dir()]
                  + [d for d in (ROOT / "fixtures" / "roles").iterdir() if d.is_dir()])
TAG = re.compile(r"\[(F[1-9][0-9]{0,2})\]")


def normalize(content):
    return c._normalize(content)  # exactly what production runs, schema included


def accepted_engagement(directory):
    client = json.loads((directory / "client.json").read_text())
    record = eng.new_engagement(engagement_id="b" * 32, created="2026-11-23T18:00:00Z",
                                requested_by=client["requested_by"], problem=client["problem"],
                                roles=client["roles"], catalog=CATALOG)
    for qid, text in client["answers"].items():
        record = eng.answer(record, qid, text)
    record, problems = eng.accept(record, CATALOG)
    assert not problems, problems
    return record


def sentence_around(text, quote):
    """The whole client sentence that contains ``quote`` (often with several numbers)."""
    low = text.lower()
    i = low.find(quote.lower())
    dot, newline = text.rfind(". ", 0, i), text.rfind("\n", 0, i)
    start = max(dot + 2 if dot != -1 else 0, newline + 1 if newline != -1 else 0)
    end_dot = text.find(". ", i + len(quote))
    end_nl = text.find("\n", i + len(quote))
    ends = [e for e in (end_dot, end_nl) if e != -1]
    end = min(ends) if ends else len(text)
    return text[start:end].strip().rstrip(".")


def naturalise(response, client_text, variant):
    """Rewrite a correct response the way a model naturally writes it."""
    doc = copy.deepcopy(response)
    figures = {f["id"]: f for f in doc["figures"]}

    def with_numbers(text):
        def put(m):
            fig = figures[m.group(1)]
            shown = deck.format_value(fig)
            if variant == 1 and fig["unit"] == "percent":
                return f"{m.group(0)}%"                  # "[F2]%"
            if variant == 2 and fig["unit"] == "usd":
                return f"${m.group(0)}"                  # "$[F14]"
            return f"{shown} {m.group(0)}"               # "7% [F2]"
        return TAG.sub(put, text)

    def walk(value, key=None):
        if isinstance(value, str) and key not in ("quote", "label", "id", "operation", "basis", "unit", "verdict",
                                                  "effort", "horizon"):
            return with_numbers(value)
        if isinstance(value, list):
            return [walk(v) for v in value] if key != "inputs" and key != "figure_ids" else value
        if isinstance(value, dict):
            return {k: walk(v, k) for k, v in value.items()}
        return value

    doc = {k: (walk(v, k) if k != "figures" else v) for k, v in doc.items()}
    for fig in doc["figures"]:
        if fig["basis"] == "client":
            fig["quote"] = sentence_around(client_text, fig["quote"])      # a whole sentence, maybe two numbers
            if fig["unit"] == "percent" and variant == 0:
                fig["value"] = fig["value"] / 100                          # 7% given as 0.07
            fig["rationale"] = "Taken from the client's brief."           # an extra field
            fig["source"] = "client"
            if fig["unit"] in ("count", "other"):
                fig["value"] = str(fig["value"])                           # a numeric string
        elif fig["basis"] == "computed":
            fig["value"] = round(fig["value"], 1)                          # rounded, within the verifier's 1%
            if fig["unit"] == "points":
                fig["unit"] = "percent"                                     # percent minus percent "as percent"
        elif fig["basis"] == "assumption" and isinstance(fig.get("rationale"), str):
            fig["rationale"] = with_numbers(fig["rationale"])
    doc["figures"].append({"id": "F99", "label": "Unused extra", "value": 1, "unit": "count",
                           "basis": "assumption", "rationale": "Never used."})
    doc["notes"] = "A field nobody asked for."
    for option in doc["options"]:
        option["pros"] = "A nested field nobody asked for."               # extra keys inside objects
    doc["recommendation"]["option"] = "Option A: " + doc["recommendation"]["option"]
    return doc


class NaturalWritingTest(unittest.TestCase):
    def test_every_example_written_naturally_still_passes_end_to_end(self):
        self.assertGreaterEqual(len(EXAMPLES), 16)
        for directory in EXAMPLES:
            record = accepted_engagement(directory)
            client_text = c.client_text_of(record)
            correct = json.loads((directory / "response.json").read_text())
            for variant in (0, 1, 2):
                with self.subTest(example=directory.name, variant=variant):
                    messy = naturalise(correct, client_text, variant)
                    self.assertTrue(c.verify_content(messy, client_text))          # the raw output fails ...
                    self.assertEqual(c.verify_content(normalize(messy), client_text), [])  # ... normalised, it passes
                    spec = c.build_deck_spec(record, CATALOG, client=ReplayClient([messy]))
                    self.assertEqual(spec["attempts"], 1)
                    prs = Presentation(io.BytesIO(deck.render_deck(spec, record, CATALOG)))
                    self.assertEqual(unexplained_numbers(prs, spec), [])
                    # Canonical values survive: the deck shows the verified numbers, not the rounded ones.
                    canonical = {f["id"]: f["value"] for f in spec["content"]["figures"]}
                    for f in correct["figures"]:
                        if f["id"] in canonical:
                            self.assertAlmostEqual(canonical[f["id"]], f["value"], delta=abs(f["value"]) * 0.01 + 0.01)

    def test_the_failure_seen_live_two_number_quotes_and_an_extra_field(self):
        record = accepted_engagement(ROOT / "fixtures" / "consulting" / "churn-clinics")
        text = c.client_text_of(record)
        response = json.loads((ROOT / "fixtures" / "consulting" / "churn-clinics" / "response.json").read_text())
        response["figures"][1]["quote"] = "churn went from 4% to 7% in two quarters"
        response["figures"][6]["rationale"] = "Exit surveys."
        self.assertTrue(c.verify_content(response, text))
        self.assertEqual(c.verify_content(normalize(response), text), [])


class NormalisingNeverWeakensTest(unittest.TestCase):
    FIGS = {"F2": {"id": "F2", "value": 7, "unit": "percent"}, "F14": {"id": "F14", "value": 30600, "unit": "usd"}}

    def test_a_number_that_does_not_state_its_figure_is_left_for_the_verifier(self):
        for text in ("Churn rose to 9% [F2].", "The loss is $31,000 [F14] a month.", "Churn rose to 7 [F2] clinics."):
            with self.subTest(text=text):
                out = strip_redundant_numbers(text, self.FIGS)
                self.assertTrue(re.search(r"\d", TAG.sub("", out)), out)

    def test_a_number_that_states_its_figure_is_removed(self):
        self.assertEqual(strip_redundant_numbers("Churn rose to 7% [F2].", self.FIGS), "Churn rose to [F2].")
        self.assertEqual(strip_redundant_numbers("Churn rose to [F2]%.", self.FIGS), "Churn rose to [F2].")
        self.assertEqual(strip_redundant_numbers("It costs $[F14] a month.", self.FIGS), "It costs [F14] a month.")
        self.assertEqual(strip_redundant_numbers("It costs $30.6K [F14].", self.FIGS), "It costs [F14].")

    def test_a_quote_not_in_the_clients_words_is_still_refused(self):
        record = accepted_engagement(ROOT / "fixtures" / "consulting" / "churn-clinics")
        text = c.client_text_of(record)
        response = json.loads((ROOT / "fixtures" / "consulting" / "churn-clinics" / "response.json").read_text())
        response["figures"][1]["quote"] = "churn went from 4% to 9% in two quarters"
        problems = c.verify_content(normalize(response), text)
        self.assertTrue(any("not the client's exact words" in p or "does not" in p or "quote" in p for p in problems), problems)

    def test_narrowing_needs_a_unique_match(self):
        self.assertEqual(narrow_quote("went from 4% to 7% in two quarters", 7)[0], "to 7% in two quarters")
        self.assertEqual(narrow_quote("went from 4% to 7% in two quarters", 0.04, "percent")[0], "went from 4% to")
        self.assertEqual(narrow_quote("went from 4% to 7% in two quarters", 0.04), (None, None))  # x100 only for percent
        self.assertEqual(narrow_quote("from 4% to 4% again", 4), (None, None))      # ambiguous
        self.assertEqual(narrow_quote("from 4% to 7%", 5), (None, None))            # no match
        self.assertEqual(narrow_quote("about $9.6 million in revenue", 9.6)[1].value, 9600000)

    def test_a_wrong_computed_value_is_left_for_the_verifier(self):
        # Slice 120: recomputing over the model's value hid reversed and wrong inputs.
        record = accepted_engagement(ROOT / "fixtures" / "consulting" / "churn-clinics")
        response = json.loads((ROOT / "fixtures" / "consulting" / "churn-clinics" / "response.json").read_text())
        response["figures"][13]["value"] = 999999
        out = normalize(response)
        self.assertEqual(next(f for f in out["figures"] if f["id"] == "F14")["value"], 999999)
        self.assertTrue(any("F14" in p for p in c.verify_content(out, c.client_text_of(record))))
        missing = json.loads((ROOT / "fixtures" / "consulting" / "churn-clinics" / "response.json").read_text())
        del missing["figures"][13]["value"]  # a missing value is not filled either (second review: wrong inputs)
        self.assertNotIn("value", next(f for f in normalize(missing)["figures"] if f["id"] == "F14"))
        self.assertTrue(any("F14" in p for p in c.verify_content(normalize(missing), c.client_text_of(record))))

    def test_never_raises(self):
        for junk in (None, 1, "x", [], {}, {"figures": None}, {"figures": [None, 1, {"id": []}]},
                     {"figures": [{"id": "F1", "basis": "computed", "inputs": ["F1"], "operation": "sum"}]}):
            normalize(junk)


class StatesTest(unittest.TestCase):
    """Slice 119 mutation run: the 5% rule, and inputs that are not numbers."""

    def test_within_rounding_but_more_than_five_percent_off_is_kept(self):
        figure = {"F3": {"id": "F3", "value": 0.6, "unit": "percent"}}
        self.assertEqual(strip_redundant_numbers("Churn rose 1% [F3].", figure), "Churn rose 1% [F3].")
        close = {"F3": {"id": "F3", "value": 7.2, "unit": "percent"}}
        self.assertEqual(strip_redundant_numbers("Churn rose 7% [F3].", close), "Churn rose [F3].")

    def test_a_word_number_or_a_non_number_figure_states_nothing(self):
        from analystos.packs.normalize import states
        word = find_numbers("thirteen")[0]
        self.assertIsNone(word.value)
        self.assertFalse(states(word, {"value": 13, "unit": "count"}))
        self.assertFalse(states(find_numbers("13")[0], {"value": True, "unit": "count"}))
        self.assertFalse(states(find_numbers("13")[0], {"value": "13", "unit": "count"}))

    def test_a_boolean_value_is_not_read_as_one(self):
        # True would match the 100 in the quote as "1 as a percent"; it must match nothing.
        fig = {"id": "F1", "label": "x", "value": True, "unit": "count", "basis": "client",
               "quote": "from 100 to 7 clinics"}
        doc = normalize_content({"figures": [fig], "answer": "[F1]"}, c.derived_units, c._recompute_figure,
                                c.OPERATIONS)
        self.assertEqual(doc["figures"][0]["quote"], "from 100 to 7 clinics")
        self.assertIs(doc["figures"][0]["value"], True)


class ReviewOfPr100Test(unittest.TestCase):
    """Slice 120: every case the release review of PR #100 found, kept as a regression test."""

    def setUp(self):
        self.base = ROOT / "fixtures" / "consulting" / "churn-clinics"

    def engagement(self, extra):
        client = json.loads((self.base / "client.json").read_text())
        client["answers"]["common.materials"] += " " + extra
        record = eng.new_engagement(engagement_id="b" * 32, created="2026-11-23T18:00:00Z",
                                    requested_by=client["requested_by"], problem=client["problem"],
                                    roles=client["roles"], catalog=CATALOG)
        for qid, text in client["answers"].items():
            record = eng.answer(record, qid, text)
        return eng.accept(record, CATALOG)[0]

    def refused(self, extra, figure, sentence):
        record = self.engagement(extra)
        response = json.loads((self.base / "response.json").read_text())
        response["figures"].append(figure)
        response["answer"] += " " + sentence
        return c.verify_content(normalize(response), c.client_text_of(record))

    def test_a_word_quantity_is_never_cut_out_of_a_quote(self):
        self.assertEqual(narrow_quote("A third of our 420 enterprise seats are idle", 420), (None, None))
        self.assertEqual(narrow_quote("half of the $1,200 average", 1200, "usd"), (None, None))
        self.assertEqual(narrow_quote("quoted $1.8 million for a system that doubles picks", 1.8e6, "usd")[0],
                         "quoted $1.8 million for a system that")  # a word quantity after the number bounds the cut
        self.assertTrue(self.refused("A third of our 420 enterprise seats are idle.",
                                     {"id": "F16", "label": "Idle enterprise seats", "value": 420, "unit": "count",
                                      "basis": "client", "quote": "A third of our 420 enterprise seats are idle"},
                                     "Also, [F16] enterprise seats are idle."))

    def test_a_scale_word_in_any_case_is_part_of_the_number(self):
        for text, value in (("$12.2 Million", 12.2e6), ("$12.2 MILLION", 12.2e6), ("$12.2 MM", 12.2e6),
                            ("$12.2 mn", 12.2e6), ("12 Billion", 12e9), ("3 crore", 3e7)):
            with self.subTest(text=text):
                self.assertAlmostEqual(find_numbers(text)[0].value, value)
        client = "The pipeline was worth $12.2 Million last year."
        self.assertFalse(c.quote_number_is_whole("The pipeline was worth $12.2", client))
        self.assertTrue(c.quote_number_is_whole("The pipeline was worth $12.2 Million", client))
        response = json.loads((self.base / "response.json").read_text())
        response["figures"].append({"id": "F16", "label": "Pipeline value", "value": 12.2, "unit": "usd",
                                    "basis": "client", "quote": "The pipeline was worth $12.2 Million last year"})
        response["answer"] += " The pipeline was worth [F16]."
        out = normalize(response)  # 12.2 with "Million" in the quote is read as 12.2 million, never $12.20
        self.assertEqual(c.verify_content(out, c.client_text_of(self.engagement(client))), [])
        self.assertAlmostEqual(next(f for f in out["figures"] if f["id"] == "F16")["value"], 12.2e6)

    def test_a_quote_cannot_cut_a_grouped_number_a_sign_or_a_currency(self):
        for client, quote in (("We have 12 200 trial users.", "200 trial users"),
                              ("We have 12\u00a0200 trial users.", "200 trial users"),
                              ("We have 12'200 trial users.", "200 trial users"),
                              ("Margin moved by - 4% last year.", "4% last year"),
                              ("Revenue was \u20b912.2 million last year.", "12.2 million last year"),
                              ("Revenue was \u20ac12.2 million last year.", "12.2 million last year")):
            with self.subTest(client=client):
                self.assertFalse(c.quote_number_is_whole(quote, client))

    def test_narrowing_respects_the_declared_unit_and_scale(self):
        self.assertEqual(narrow_quote("churn hit 7% and 7 clinics left", 7, "count")[0], "and 7 clinics left")
        self.assertEqual(narrow_quote("churn hit 7% and 7 clinics left", 7, "percent")[0], "churn hit 7% and")
        self.assertEqual(narrow_quote("a $12,000 contract and a $5 fee", 12, "usd"), (None, None))  # no scale word
        fig = {"id": "F1", "label": "Payback", "value": 6, "unit": "months", "basis": "client",
               "quote": "a 6 month payback"}
        self.assertEqual(normalize({"figures": [fig], "answer": "[F1]"})["figures"][0]["unit"], "months")

    def test_an_ambiguous_option_name_is_left_alone(self):
        doc = {"options": [{"name": "Save"}, {"name": "Save desk"}], "recommendation": {"option": "Option A: Save desk"}}
        self.assertEqual(normalize(doc)["recommendation"]["option"], "Save desk")  # exact after the label
        doc = {"options": [{"name": "Save"}, {"name": "Save desk"}], "recommendation": {"option": "Save desk now"}}
        self.assertEqual(normalize(doc)["recommendation"]["option"], "Save desk now")  # no label: left alone
        doc = {"options": [{"name": "Save desk"}, {"name": "Hire"}], "recommendation": {"option": "Option A: Save desk"}}
        self.assertEqual(normalize(doc)["recommendation"]["option"], "Save desk")

    def test_a_boolean_computed_value_is_left_for_the_verifier(self):
        figures = [{"id": "F1", "label": "a", "value": 3, "unit": "count", "basis": "assumption", "rationale": "r"},
                   {"id": "F2", "label": "b", "value": 4, "unit": "count", "basis": "assumption", "rationale": "r"},
                   {"id": "F3", "label": "c", "value": True, "unit": "count", "basis": "computed", "operation": "sum",
                    "inputs": ["F1", "F2"]}]
        self.assertIs(normalize({"figures": figures, "answer": "[F3]"})["figures"][2]["value"], True)

    def test_reversed_or_wrong_inputs_are_refused_not_recomputed(self):
        response = json.loads((self.base / "response.json").read_text())
        f11 = next(f for f in response["figures"] if f["id"] == "F11")
        f11["inputs"] = list(reversed(f11["inputs"]))
        record = self.engagement("")
        self.assertTrue(any("F11" in p for p in c.verify_content(normalize(response), c.client_text_of(record))))

    def test_a_quote_cannot_change_the_declared_unit(self):
        self.assertTrue(self.refused("We have 12,000 leads.",
                                     {"id": "F16", "label": "Average deal size", "value": 12, "unit": "usd",
                                      "basis": "client", "quote": "We have 12,000 leads"}, "The average deal is [F16]."))
        self.assertTrue(self.refused("We lost 60 clinics.",
                                     {"id": "F16", "label": "Quarterly churn rate", "value": 0.6, "unit": "percent",
                                      "basis": "client", "quote": "We lost 60 clinics"}, "Quarterly churn is [F16]."))

    def test_bare_small_digits_and_durations_are_numbers(self):
        figures = {"F2": {"value": 7, "unit": "percent"}, "F5": {"value": 850, "unit": "count"}}
        for text in ("We have 1 [F5] customers.", "Churn rose from 3 to [F2].", "Churn rose 7 [F2].",
                     "Hire 2 analysts.", "Days sales outstanding has climbed to 90 days."):
            with self.subTest(text=text):
                self.assertEqual(normalize({"answer": text})["answer"], text)  # not rewritten ...
                self.assertTrue(c.number_problems("t", text, figures))         # ... and refused

    def test_years_tags_and_parentheticals(self):
        figures = {"F2": {"value": 7, "unit": "percent"}, "F5": {"value": 850, "unit": "count"}}
        for bad in ("Grow the base by 2030 customers.", "Customers grew from 2020 to 2030 clinics.",
                    "Customers grew 2020-2030 clinics.", "We added after 2025 visits.", "Churn rose to [F2][F5].",
                    "Churn rose to [F2].[F5] clinics."):
            with self.subTest(bad=bad):
                self.assertTrue(c.number_problems("t", bad, figures))
        for ok in ("Launch the save desk by the end of 2026.", "Ship the fix in mid-2026.",
                   "Churn rose after the March 2025 release.", "In 2025 churn rose to [F2].", "By 2027 sales grew."):
            with self.subTest(ok=ok):
                self.assertEqual(c.number_problems("t", ok, figures), [])
        self.assertEqual(strip_redundant_numbers("Churn reached [F2] (7%).", {"F2": figures["F2"]}), "Churn reached [F2].")
        self.assertEqual(strip_redundant_numbers("Churn reached [F2] (4%).", {"F2": figures["F2"]}),
                         "Churn reached [F2] (4%).")

    def test_a_refused_slip_is_fixed_on_the_second_attempt(self):
        # The paths the normaliser no longer fixes still deliver: the repair request names the problem.
        record = self.engagement("")
        correct = json.loads((self.base / "response.json").read_text())
        first = copy.deepcopy(correct)
        first["roadmap"][0]["actions"].append("Review progress within 90 days.")
        next(f for f in first["figures"] if f["id"] == "F14")["value"] = 31000
        replay = ReplayClient([first, correct])
        spec = c.build_deck_spec(record, CATALOG, client=replay)
        self.assertEqual(spec["attempts"], 2)
        self.assertIn("90", replay.requests[1]["messages"][0]["content"])
        prs = Presentation(io.BytesIO(deck.render_deck(spec, record, CATALOG)))
        self.assertEqual(unexplained_numbers(prs, spec), [])


class SecondReviewTest(unittest.TestCase):
    """Slice 120, second release review: the cases it found, kept as regression tests."""

    def test_a_number_that_may_change_the_kept_one_is_never_cut_away(self):
        for quote, value, unit in (("About 40% of our 850 customers are small clinics", 850, "count"),
                                   ("33% of our 420 enterprise seats are idle", 420, "count"),
                                   ("1 in 3 of our 420", 420, "count"), ("1/3 of our 420", 420, "count"),
                                   ("About 140 of our 420", 420, "count"), ("40% or so of our 850", 850, "count"),
                                   ("50% of the $1,200 average", 1200, "usd"), ("2x the $1,200 average", 1200, "usd")):
            with self.subTest(quote=quote):
                self.assertEqual(narrow_quote(quote, value, unit), (None, None))
        self.assertEqual(narrow_quote("half the $1,200 average", 1200, "usd"), (None, None))  # a word quantity, no "of"
        for quote, value, unit in (("Some 340 out of our 850 customers are small clinics", 850, "count"),
                                   ("About 40% out of our 850", 850, "count"), ("40% among our 850", 850, "count"),
                                   ("A 40% share of the 850", 850, "count"), ("40%, or about a third, of our 850", 850, "count"),
                                   ("40% (roughly) of our 850", 850, "count"), ("40% - of our 850 -", 850, "count"),
                                   ("3 times the $1,200 average", 1200, "usd"), ("$300 above the $1,200 average", 1200, "usd"),
                                   ("$300 short of the $1,200 average", 1200, "usd"),
                                   ("50% less than the $1,200 average", 1200, "usd")):
            with self.subTest(third_review=quote):  # third review: cut only at an explicit break
                self.assertEqual(narrow_quote(quote, value, unit), (None, None))
        self.assertEqual(narrow_quote("Contractor spend was $600,000 against a plan of $350,000", 350000, "usd")[0],
                         "against a plan of $350,000")
        self.assertEqual(narrow_quote("went from 4% to 7% in two quarters", 7, "percent")[0], "to 7% in two quarters")
        self.assertEqual(narrow_quote("we have 850 customers paying on average $1,200 per month", 1200, "usd")[0],
                         "customers paying on average $1,200 per month")  # plain words, nothing ties the numbers
        self.assertEqual(narrow_quote("fell to 88% this year as orders grew from 4,000", 4000, "count")[0],
                         "this year as orders grew from 4,000")  # "from" starting a range ties nothing
        for quote in ("40% across our 850", "40% between our 850", "$300 + the $1,200", "40% inside the 850",
                      "40% of each 850", "40% came from our 850", "2x our usual $1,200 average", "4 850 customers"):
            with self.subTest(linked=quote):
                self.assertEqual(narrow_quote(quote, 1200 if "1,200" in quote else 850,
                                              "usd" if "$" in quote else "count"), (None, None))

    def test_hyphenated_plural_and_short_scale_words(self):
        for text in ("$12.2-million", "$12.2 millions", "$12.2 mil", "$12.2 Mill."):
            with self.subTest(text=text):
                self.assertAlmostEqual(find_numbers(text)[0].value, 12.2e6)
        self.assertEqual([t.text for t in find_numbers("4-7%")], ["4", "7%"])  # a range is not a scale
        client = "Our pipeline was worth $12.2-million last year."
        self.assertFalse(c.quote_number_is_whole("Our pipeline was worth $12.2", client))
        self.assertTrue(c.quote_number_is_whole("Our pipeline was worth $12.2-million", client))

    def test_of_marks_a_year_only_as_end_or_start_of(self):
        figures = {"F2": {"value": 7, "unit": "percent"}}
        for bad in ("A loss of 2031 each month.", "The deficit of 2025 per clinic hurts.", "Payback of 2028 is too long.",
                    "Tier 1 [F5] customers churn least.", "Plan 3 save-desk hires by Q2.", "Wave 2 [F5] clinics.",
                    "Start Phase 1 with Tier 2 clinics."):
            with self.subTest(bad=bad):
                self.assertTrue(c.number_problems("t", bad, figures))
        for ok in ("Launch by the end of 2026.", "Start of 2027 is the deadline.", "In 2025 customers churned.",
                   "Since 2024 renewals have fallen.", "Phase 1: hire a retention owner.", "Tier 2 is the focus."):
            with self.subTest(ok=ok):
                self.assertEqual(c.number_problems("t", ok, figures), [])

    def test_an_option_is_matched_only_after_a_label(self):
        options = [{"name": "Shift budget to new sales"}, {"name": "Save desk"}]
        for said, expected in (("Option A: Save desk", "Save desk"), ("B) Save desk", "Save desk"),
                               ("Do not shift budget to new sales", "Do not shift budget to new sales"),
                               ("Save desk first, then sales", "Save desk first, then sales")):
            with self.subTest(said=said):
                doc = {"options": copy.deepcopy(options), "recommendation": {"option": said}}
                self.assertEqual(normalize(doc)["recommendation"]["option"], expected)

    def test_unit_aliases_and_unreadable_values_are_not_guessed(self):
        fig = {"id": "F1", "label": "Quarterly churn rate", "value": 0.6, "unit": "%", "basis": "client",
               "quote": "We lost 60 clinics"}
        out = normalize({"figures": [fig], "answer": "[F1]"})["figures"][0]
        self.assertEqual(out["unit"], "percent")  # "%" read as percent, never replaced by the quote's count
        odd = dict(fig, unit="clinics", value=60)
        self.assertEqual(normalize({"figures": [odd], "answer": "[F1]"})["figures"][0]["unit"], "clinics")  # left to refuse
        figures = [{"id": "F1", "label": "a", "value": 3, "unit": "count", "basis": "assumption", "rationale": "r"},
                   {"id": "F2", "label": "b", "value": 4, "unit": "count", "basis": "assumption", "rationale": "r"},
                   {"id": "F3", "label": "c", "value": "59.5 clinics", "unit": "count", "basis": "computed",
                    "operation": "sum", "inputs": ["F1", "F2"]}]
        self.assertEqual(normalize({"figures": figures, "answer": "[F3]"})["figures"][2]["value"], "59.5 clinics")


if __name__ == "__main__":
    unittest.main()
