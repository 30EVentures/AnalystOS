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
    return normalize_content(content, c.derived_units, c._recompute_figure, c.OPERATIONS)


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
            fig["value"] = fig["value"] * 1.03 + 0.5                       # drifted
            if fig["unit"] == "points":
                fig["unit"] = "percent"                                     # percent minus percent "as percent"
        elif fig["basis"] == "assumption" and isinstance(fig.get("rationale"), str):
            fig["rationale"] = with_numbers(fig["rationale"])
    doc["figures"].append({"id": "F99", "label": "Unused extra", "value": 1, "unit": "count",
                           "basis": "assumption", "rationale": "Never used."})
    doc["notes"] = "A field nobody asked for."
    doc["roadmap"][0]["actions"].append("Review progress within 90 days.")
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
                    # Canonical values survive: the deck shows the verified numbers, not the drifted ones.
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
        self.assertEqual(narrow_quote("went from 4% to 7% in two quarters", 0.04)[0], "went from 4% to")
        self.assertEqual(narrow_quote("from 4% to 4% again", 4), (None, None))      # ambiguous
        self.assertEqual(narrow_quote("from 4% to 7%", 5), (None, None))            # no match
        self.assertEqual(narrow_quote("about $9.6 million in revenue", 9.6)[1].value, 9600000)

    def test_a_drifted_computed_value_is_recomputed_not_trusted(self):
        record = accepted_engagement(ROOT / "fixtures" / "consulting" / "churn-clinics")
        response = json.loads((ROOT / "fixtures" / "consulting" / "churn-clinics" / "response.json").read_text())
        response["figures"][13]["value"] = 999999
        out = normalize(response)
        self.assertEqual(next(f for f in out["figures"] if f["id"] == "F14")["value"], 30600)
        self.assertEqual(c.verify_content(out, c.client_text_of(record)), [])

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


if __name__ == "__main__":
    unittest.main()
