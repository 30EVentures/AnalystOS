"""Tests for L4 render_section - one per "Done when" in specs/slice-6/spec.md."""

import io
import re
import unittest

import pdfplumber

from analystos.l4.export import render_html, render_pdf, render_section


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

    # --- number formatting (slice 15) ---

    def test_format_usd_scales_and_abbreviates(self):
        findings = [{
            "text": "FY2025 revenue was {answer}.", "answer": 130497.0,
            "format": "usd",
            "citation": {"source": self.src, "row": 4, "column": "revenue"},
        }]
        out = render_section("Revenue", findings, currency_unit="millions")
        self.assertIn("FY2025 revenue was $130.5B.", out)

    def test_format_percent_appends_percent_sign(self):
        findings = [{
            "text": "Gross margin was {answer}.", "answer": 57.142857,
            "format": "percent",
            "citation": {"source": self.src, "row": 3, "column": "margin"},
        }]
        out = render_section("Margin", findings)
        self.assertIn("Gross margin was 57.1%.", out)

    def test_format_negative_renders_in_parentheses(self):
        findings = [{
            "text": "Net income was {answer}.", "answer": -50.0,
            "format": "usd",
            "citation": {"source": self.src, "row": 2, "column": "net_income"},
        }]
        out = render_section("Loss", findings, currency_unit="millions")
        self.assertIn("Net income was ($50.0M).", out)

    def test_currency_unit_actual_is_the_default(self):
        # 150000 raw dollars, no currency_unit given -> $150.0K, not $150.0M
        findings = [{
            "text": "Net income was {answer}.", "answer": -150000.0,
            "format": "usd",
            "citation": {"source": self.src, "row": 2, "column": "net_income"},
        }]
        out = render_section("Loss", findings)
        self.assertIn("Net income was ($150.0K).", out)

    def test_currency_unit_applies_to_every_usd_finding_in_the_section(self):
        # the whole point: one setting, every usd figure in the report scales
        # the same way - no per-sentence choice to get wrong
        findings = [
            {"text": "Revenue was {answer}.", "answer": 130497.0, "format": "usd",
             "citation": {"source": self.src, "row": 4, "column": "revenue"}},
            {"text": "Net income was {answer}.", "answer": 72880.0, "format": "usd",
             "citation": {"source": self.src, "row": 4, "column": "net_income"}},
        ]
        out = render_section("Summary", findings, currency_unit="millions")
        self.assertIn("Revenue was $130.5B.", out)
        self.assertIn("Net income was $72.9B.", out)

    def test_unknown_currency_unit_raises(self):
        findings = [{
            "text": "X was {answer}.", "answer": 1.0, "format": "usd",
            "citation": {"source": self.src, "row": 2, "column": "x"},
        }]
        with self.assertRaises(ValueError):
            render_section("X", findings, currency_unit="pesos")

    def test_format_number_adds_thousands_commas(self):
        findings = [{
            "text": "Headcount was {answer}.", "answer": 29600,
            "format": "number",
            "citation": {"source": self.src, "row": 2, "column": "headcount"},
        }]
        out = render_section("Headcount", findings)
        self.assertIn("Headcount was 29,600.", out)

    def test_no_format_is_unchanged(self):  # backward compatible with pre-slice-15 findings
        findings = [{
            "text": "FY2024 revenue was {answer}.", "answer": 4200000.0,
            "citation": {"source": self.src, "row": 3, "column": "revenue"},
        }]
        out = render_section("Revenue", findings)
        self.assertIn("FY2024 revenue was 4200000.0.", out)

    def test_unknown_format_raises(self):
        findings = [{
            "text": "X was {answer}.", "answer": 1.0, "format": "euros",
            "citation": {"source": self.src, "row": 2, "column": "x"},
        }]
        with self.assertRaises(ValueError):
            render_section("X", findings)

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

    # --- render_pdf (slice 24) ---

    def test_render_pdf_returns_real_pdf_bytes(self):  # Done when #1
        pdf_bytes = render_pdf(render_section("Revenue", self.findings))
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_render_pdf_round_trips_title_body_and_footnotes(self):  # Done when #2
        pdf_bytes = render_pdf(render_section("Revenue", self.findings))
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        self.assertIn("Revenue", text)
        self.assertIn("FY2024 revenue was 4200000.0.", text)
        self.assertIn("FY2023 revenue was 3560000.0.", text)
        self.assertIn(f'source {self.src} - row 3, column "revenue"', text)
        self.assertIn(f'source {self.src} - row 2, column "revenue"', text)

    def test_render_pdf_escapes_special_characters(self):  # Done when #2, cross-check with HTML
        findings = [
            {
                "text": "R&D <spend> was {answer}.",
                "answer": "1 & 2",
                "citation": {"source": "x" * 64, "row": 2, "column": "r&d"},
            }
        ]
        pdf_bytes = render_pdf(render_section("A & B", findings))
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        self.assertIn("A & B", text)
        self.assertIn("R&D <spend> was 1 & 2.", text)


if __name__ == "__main__":
    unittest.main()
