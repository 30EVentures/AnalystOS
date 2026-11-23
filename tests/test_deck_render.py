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
from analystos.packs import consulting as c
from analystos.packs.replay import ReplayClient
from tests.test_consulting_pack import CATALOG, ENGAGEMENT, RESPONSE

SPEC = c.build_deck_spec(ENGAGEMENT, CATALOG, client=ReplayClient([RESPONSE]))
DATA = deck.render_deck(SPEC)
PRS = Presentation(io.BytesIO(DATA))


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
        self.assertIn("Client's words: “churn went from 4% to 7%”", sources)
        self.assertIn("Calculated: F5 × F2 ÷ 100", sources)
        self.assertIn("Calculated: F2 − F1", sources)
        self.assertIn("Assumption: A planning assumption", sources)
        self.assertIn("3 pts", sources)  # a percentage-point change is not shown as a percent

    def test_the_file_carries_a_digest_of_its_spec(self):
        self.assertIn(f"spec sha256 {deck.spec_digest(SPEC)}", PRS.core_properties.keywords)
        self.assertEqual(PRS.core_properties.author, "AnalystOS")

    def test_the_renderer_adds_no_numbers_of_its_own(self):
        allowed = set()
        for fig in SPEC["content"]["figures"]:
            allowed.add(deck.format_value(fig))
        spec_text = json.dumps(SPEC["content"], ensure_ascii=False)
        number_re = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")
        for i, slide in enumerate(PRS.slides, start=1):
            text = slide_text(slide)
            text = re.sub(rf"\b{i} / {len(PRS.slides)}\b", "", text)        # slide numbers
            text = re.sub(r"\bF\d+\b", "", text)                               # figure references
            text = re.sub(r"\((?:1|2) of 2\)", "", text)                       # sources pagination
            text = re.sub("[\u00d7\u00f7] 100", "", text)                     # formula notation, not a claim
            for token in number_re.findall(text):
                with self.subTest(slide=i, token=token):
                    self.assertTrue(token in spec_text or token in allowed or token.rstrip("%") in spec_text,
                                    f"slide {i} shows {token!r}, which is not in the verified spec")

    def test_refusals(self):
        for bad in (None, {}, {"format": "x"}, dict(SPEC, slides=[])):
            with self.assertRaises(ValueError):
                deck.render_deck(bad)
        weird = copy.deepcopy(SPEC)
        weird["slides"][3]["kind"] = "hologram"
        with self.assertRaisesRegex(ValueError, "hologram"):
            deck.render_deck(weird)


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
