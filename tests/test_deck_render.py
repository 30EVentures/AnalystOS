"""Slice 113 - rendering a verified deck spec as PowerPoint. The renderer lays out
what was verified and adds no claims: every number in the file is a figure value,
a figure reference or a slide number."""

import copy
import io
import json
import re
import unittest
from pathlib import Path

from pptx import Presentation

from analystos.l4 import deck
from analystos.packs.numbers import find_numbers
from analystos.packs import consulting as c
from analystos.packs.replay import ReplayClient
from tests.test_consulting_pack import CATALOG, ENGAGEMENT, RESPONSE

SPEC = c.build_deck_spec(ENGAGEMENT, CATALOG, client=ReplayClient([RESPONSE]))
DATA = deck.render_deck(SPEC)
PRS = Presentation(io.BytesIO(DATA))


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _allowed_per_rendered_slide(spec):
    """For each rendered slide, the numbers it may show: those written in its own spec
    slide, the formatted values of the figures that slide uses, and on sources slides
    each listed figure's value, quote and rationale."""
    figures = {f["id"]: f for f in spec["content"]["figures"]}
    out = []
    for spec_slide in spec["slides"]:
        if spec_slide["kind"] == "sources":
            for k in range(0, len(spec["content"]["figures"]), deck.SOURCES_PER_SLIDE):
                chunk = spec["content"]["figures"][k:k + deck.SOURCES_PER_SLIDE]
                texts = [deck.format_value(f) for f in chunk] + [f.get("quote", "") for f in chunk] + \
                        [f.get("rationale", "") for f in chunk]
                out.append(texts)
            continue
        texts = list(_strings({k: v for k, v in spec_slide.items() if k != "figure_ids"}))
        texts += [deck.format_value(figures[fid]) for fid in spec_slide["figure_ids"] if fid in figures]
        if spec_slide["kind"] == "issue-tree":
            texts.append(spec["content"]["key_question"])
        if spec_slide["kind"] == "recommendation":
            texts += list(_strings(spec["content"]["recommendation"]))
        if spec_slide["kind"] == "roadmap":
            texts += list(c.HORIZONS)  # the fixed column labels, part of the format, not a claim
        out.append(texts)
    allowed = []
    for texts in out:
        tokens = set()
        for text in texts:
            tokens.update(t.text.strip() for t in find_numbers(text))
            tokens.add(text.strip())
        allowed.append(tokens)
    return allowed


def unexplained_numbers(prs, spec):
    """Every number on a slide that is not, as a whole token, one that slide's own verified
    content writes, a formatted value of a figure the slide uses, a slide number, sources
    pagination or formula notation (and, on the roadmap slide only, its column labels)."""
    allowed = _allowed_per_rendered_slide(spec)
    total = len(prs.slides)
    found = []
    for i, slide in enumerate(prs.slides, start=1):
        text = slide_text(slide)
        text = re.sub(rf"\b{i} / {total}\b", " ", text)
        text = re.sub(r"\(\d+ of \d+\)", " ", text)
        text = re.sub("[\u00d7\u00f7] 100", " ", text)
        text = re.sub(r"\bF[1-9]\d{0,2}\b", " ", text)
        for token in find_numbers(text):
            shown = token.text.strip()
            if shown not in allowed[i - 1]:
                found.append((i, shown))
    return found


def slide_text(slide):
    parts = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            parts.append(shape.text_frame.text)
        if getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


class RenderTest(unittest.TestCase):
    def test_it_is_a_sixteen_by_nine_deck_with_one_slide_per_spec_slide(self):
        self.assertEqual(PRS.slide_width, deck.SLIDE_W)
        self.assertEqual(len(PRS.slides), deck.slide_count(SPEC))
        self.assertEqual(len(PRS.slides), len(SPEC["slides"]) + 1)  # 15 figures: sources split in two

    def test_every_slide_carries_its_action_title(self):
        texts = [slide_text(s) for s in PRS.slides]
        for spec_slide in SPEC["slides"]:
            if spec_slide["kind"] == "sources":
                continue
            title = re.sub(r"\s*\[(F\d+)\]", r" \1", spec_slide["title"])
            self.assertTrue(any(title in t for t in texts), spec_slide["title"])

    def test_assumptions_are_flagged_on_the_slide_that_uses_them(self):
        roadmap = slide_text(PRS.slides[9])
        self.assertIn("Includes assumption F15: not from client data.", roadmap)
        self.assertNotIn("Includes assumption", slide_text(PRS.slides[2]))

    def test_sources_list_every_figure_with_its_basis(self):
        sources = slide_text(PRS.slides[12]) + slide_text(PRS.slides[13])
        for fig in RESPONSE["figures"]:
            self.assertIn(fig["label"], sources)
        self.assertIn("Client's words: “went from 4%”", sources)
        self.assertIn("Calculated: F5 × F2 ÷ 100", sources)
        self.assertIn("Calculated: F2 − F1", sources)
        self.assertIn("Assumption: A planning assumption", sources)
        self.assertIn("3 pts", sources)  # a percentage-point change is not shown as a percent

    def test_each_finding_has_a_native_chart_of_verified_values(self):
        figures = {f["id"]: f for f in SPEC["content"]["figures"]}
        findings = [s for s in SPEC["slides"] if s["kind"] == "finding"]
        rendered = [shape.chart for slide in PRS.slides for shape in slide.shapes if shape.has_chart]
        self.assertEqual(len(rendered), len(findings))
        for chart, spec_slide in zip(rendered, findings):
            expected = [figures[fid]["value"] for fid in spec_slide["chart"]["figure_ids"]]
            self.assertEqual(list(chart.plots[0].series[0].values), expected)
            self.assertEqual(list(chart.plots[0].categories), spec_slide["chart"]["labels"])
            self.assertFalse(chart.value_axis.visible)
        self.assertEqual(rendered[0].plots[0].data_labels.number_format, deck.NUMBER_FORMATS["percent"])

    def test_so_what_is_on_each_finding_slide(self):
        texts = "\n".join(slide_text(s) for s in PRS.slides)
        for spec_slide in SPEC["slides"]:
            if spec_slide["kind"] == "finding":
                self.assertIn("So what: " + spec_slide["so_what"], texts)

    def test_the_file_carries_a_digest_of_its_spec(self):
        self.assertIn(f"spec sha256 {deck.spec_digest(SPEC)}", PRS.core_properties.keywords)
        self.assertEqual(PRS.core_properties.author, "AnalystOS")

    def test_the_renderer_adds_no_numbers_of_its_own(self):
        self.assertEqual(unexplained_numbers(PRS, SPEC), [])

    def test_the_check_catches_an_injected_number(self):
        for injected in ("TOP 3 priorities", "a 10% uplift", "saves 60 clinics", "seventy percent", "2x faster"):
            with self.subTest(injected=injected):
                prs = Presentation(io.BytesIO(DATA))
                shape = next(s for s in prs.slides[3].shapes if s.has_text_frame and s.text_frame.text.strip())
                shape.text_frame.paragraphs[0].add_run().text = " " + injected
                self.assertTrue(unexplained_numbers(prs, SPEC), injected)

    def test_the_check_catches_a_misformatted_value(self):
        prs = Presentation(io.BytesIO(DATA))
        changed = 0
        for shape in prs.slides[1].shapes:
            if shape.has_text_frame and shape.text_frame.text.startswith("$30,600"):
                shape.text_frame.paragraphs[0].runs[0].text = "$30,601"
                changed += 1
        self.assertEqual(changed, 1)
        self.assertTrue(unexplained_numbers(prs, SPEC))

    def test_an_edited_spec_is_refused(self):
        edited = json.loads(json.dumps(SPEC))
        edited["content"]["answer"] = "Churn will hit 40% next year, so act now on retention."
        edited["slides"][1]["title"] = edited["content"]["answer"]
        with self.assertRaisesRegex(ValueError, "refusing to render"):
            deck.render_deck(edited)

    def test_refusals(self):
        for bad in (None, {}, {"format": "x"}, dict(SPEC, slides=[])):
            with self.assertRaises(ValueError):
                deck.render_deck(bad)
        weird = copy.deepcopy(SPEC)
        weird["slides"][3]["kind"] = "hologram"
        with self.assertRaisesRegex(ValueError, "refusing to render"):
            deck.render_deck(weird)
        for malformed in ({"format": SPEC["format"]}, dict(SPEC, content=None), dict(SPEC, client_text=None)):
            with self.assertRaises(ValueError):
                deck.render_deck(malformed)


class FormatTest(unittest.TestCase):
    def test_values(self):
        cases = ((7, "percent", "7%"), (6.5, "percent", "6.5%"), (3, "points", "3 pts"), (30600, "usd", "$30,600"),
                 (1200, "usd", "$1,200"), (2.5, "usd", "$2.50"), (59.5, "count", "59.5"), (850, "count", "850"),
                 (1.25, "ratio", "1.25x"), (6, "months", "6 months"))
        for value, unit, expected in cases:
            with self.subTest(value=value, unit=unit):
                self.assertEqual(deck.format_value({"value": value, "unit": unit}), expected)

    def test_formulas(self):
        self.assertEqual(deck.formula("difference", ["F2", "F1"]), "F2 − F1")
        self.assertEqual(deck.formula("growth_percent", ["F1", "F2"]), "(F2 − F1) ÷ F1 × 100")
        self.assertEqual(deck.formula("percent_of", ["F5", "F2"]), "F5 × F2 ÷ 100")
        self.assertEqual(deck.formula("sum", ["F1", "F2", "F3"]), "F1 + F2 + F3")


if __name__ == "__main__":
    unittest.main()
