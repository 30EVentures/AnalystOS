"""Tests for L4 render_section - one per "Done when" in specs/slice-6/spec.md."""

import re
import unittest

from analystos.l4.export import render_html, render_section


class RenderSectionTest(unittest.TestCase):
    def setUp(self):
        self.src = "a1b9f2c8" * 8
        self.findings = [
            {
                "text": "FY2024 revenue was {answer}.",
                "answer": 4200000.0,
                "citation": {"source": self.src, "row": 3, "column": "revenue"},
            },
            {
                "text": "FY2023 revenue was {answer}.",
                "answer": 3560000.0,
                "citation": {"source": self.src, "row": 2, "column": "revenue"},
            },
        ]

    def test_has_title_body_and_footnotes(self):  # Done when #1
        out = render_section("Revenue", self.findings)
        self.assertIn("# Revenue", out)
        self.assertIn("FY2024 revenue was 4200000.0. [1]", out)
        self.assertIn("FY2023 revenue was 3560000.0. [2]", out)
        self.assertIn(f'[1] source {self.src} - row 3, column "revenue"', out)
        self.assertIn(f'[2] source {self.src} - row 2, column "revenue"', out)

    def test_markers_in_order_and_every_one_has_a_footnote(self):  # Done when #2
        out = render_section("Revenue", self.findings)
        body, _, notes = out.partition("\n---\n")
        markers = sorted(set(re.findall(r"\[(\d+)\]", body)), key=int)
        self.assertEqual(markers, ["1", "2"])
        for m in markers:
            self.assertRegex(notes, rf"(?m)^\[{m}\] ")

    def test_missing_placeholder_raises(self):  # Done when #3
        bad = [
            {
                "text": "no placeholder here.",
                "answer": 1,
                "citation": {"source": self.src, "row": 2, "column": "x"},
            }
        ]
        with self.assertRaises(ValueError) as cm:
            render_section("X", bad)
        self.assertIn("answer", str(cm.exception))

    def test_multi_cell_citation_renders_as_computed_from(self):  # slice 12 #4
        findings = [
            {
                "text": "Revenue grew {answer}% year over year.",
                "answer": 114.2,
                "citation": [
                    {"source": self.src, "row": 3, "column": "revenue"},
                    {"source": self.src, "row": 4, "column": "revenue"},
                ],
            }
        ]
        out = render_section("Growth", findings)
        self.assertIn("Revenue grew 114.2% year over year. [1]", out)
        self.assertIn("[1] computed from: ", out)
        self.assertIn(f'source {self.src} - row 3, column "revenue"', out)
        self.assertIn(f'source {self.src} - row 4, column "revenue"', out)

    def test_non_number_answer_is_rendered_as_text(self):  # any answer type
        one = [
            {
                "text": "Going concern status: {answer}.",
                "answer": "no material uncertainty",
                "citation": {"source": self.src, "row": 5, "column": "note"},
            }
        ]
        out = render_section("Notes", one)
        self.assertIn("Going concern status: no material uncertainty. [1]", out)


    # --- render_html (slice 13) ---

    def test_render_html_has_title_paragraphs_and_footnotes(self):  # slice 13 #2
        page = render_html(render_section("Revenue", self.findings))
        self.assertIn("<!doctype html>", page)
        self.assertIn("<h1>Revenue</h1>", page)
        self.assertIn("FY2024 revenue was 4200000.0.", page)
        self.assertIn('href="#fn1"', page)   # marker links to footnote
        self.assertIn('<p id="fn1">', page)  # footnote has the anchor

    def test_render_html_escapes_special_characters(self):  # slice 13 #3
        findings = [
            {
                "text": "R&D <spend> was {answer}.",
                "answer": "1 & 2",
                "citation": {"source": "x" * 64, "row": 2, "column": "r&d"},
            }
        ]
        page = render_html(render_section("A & B", findings))
        self.assertIn("<h1>A &amp; B</h1>", page)
        self.assertIn("R&amp;D &lt;spend&gt; was 1 &amp; 2.", page)
        self.assertNotIn("<spend>", page)


if __name__ == "__main__":
    unittest.main()
