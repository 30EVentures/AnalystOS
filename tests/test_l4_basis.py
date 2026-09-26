"""Slice 56 - the basis of a figure (forward horizon, non-GAAP, read from an
image) is shown on KPI tiles, chart notes, body text and footnotes, in both
the HTML and the PDF - not in body paragraphs only. See specs/slice-56/spec.md.
"""

import io
import unittest

import pdfplumber

from analystos.l4.basis import basis_labels, basis_text
from analystos.l4.rich_export import chart_basis_note, chart_points, render_rich_report
from analystos.l4.rich_pdf import render_rich_pdf

SRC = "c0ffee11" * 8

SEGMENTS = [
    {"type": "quote", "horizon": "reported", "value": 63_500_000.0, "format": "usd",
     "label": "Adj. NI", "gaap_status": "non_gaap", "citation": "$63.5 million"},        # 0
    {"type": "quote", "horizon": "guidance", "value": 1_900_000_000.0, "format": "usd",
     "label": "FY27 guide", "citation": "$1.9 billion"},                                 # 1
    {"type": "quote", "horizon": "reported", "value": 498_000_000.0, "format": "usd",
     "label": "Revenue", "citation": "$498.0 million"},                                  # 2
    {"type": "quote", "horizon": "reported", "value": 41_000_000.0, "format": "usd",
     "label": "Chart-only", "source": "image", "citation": "$41.0 million"},             # 3
    {"type": "computed", "horizon": "reported", "operation": "growth_percent",
     "value": 5.0, "format": "percent", "operands": [10.0, 10.5], "total": None,
     "citation": ["10", "10.5"], "gaap_status": "non_gaap"},                             # 4
]


def _report(**over):
    base = {
        "title": "T",
        "kpis": [
            {"label": "Adj. NI", "value_fact": 0, "delta_fact": -1},
            {"label": "Guide", "value_fact": 1, "delta_fact": -1},
            {"label": "Revenue", "value_fact": 2, "delta_fact": 4},
            {"label": "Read from image", "value_fact": 3, "delta_fact": -1},
        ],
        "executive_summary": [{"text": "Revenue was {{2}} and image-only was {{3}}."}],
        "executive_insight": "Read together, {{0}} and {{2}} tell one story.",
        "sections": [{
            "heading": "Mix",
            "paragraphs": [{"text": "Adjusted income was {{0}}."}],
            "chart": {"type": "bar", "title": "Mix", "format": "usd",
                      "series": [{"label": "Adj. NI", "fact_index": 0},
                                 {"label": "Revenue", "fact_index": 2}]},
        }],
    }
    base.update(over)
    return base


class BasisLabelsTest(unittest.TestCase):
    def test_labels_per_combination(self):
        self.assertEqual(basis_labels({}), [])
        self.assertEqual(basis_labels({"horizon": "reported"}), [])
        self.assertEqual(basis_labels({"horizon": "guidance"}), ["guidance"])
        self.assertEqual(basis_labels({"horizon": "projected", "gaap_status": "non_gaap"}), ["projected", "non-GAAP"])
        self.assertEqual(basis_labels({"gaap_status": "gaap"}), [])
        self.assertEqual(basis_labels({"source": "image", "gaap_status": "non_gaap"}), ["non-GAAP", "from image"])

    def test_text_joins_distinct_labels(self):
        a = {"gaap_status": "non_gaap"}
        b = {"gaap_status": "non_gaap", "horizon": "guidance"}
        self.assertEqual(basis_text(a, b), "non-GAAP · guidance")
        self.assertEqual(basis_text({}), "")


class HtmlBasisTest(unittest.TestCase):
    def setUp(self):
        self.html = render_rich_report(_report(), SEGMENTS, SRC)

    def test_kpi_tiles_show_their_basis(self):
        # Adj. NI, guide, Revenue (via its non-GAAP delta fact) and the image tile
        self.assertEqual(self.html.count('<div class="basis">'), 4)
        self.assertIn('<div class="basis">non-GAAP</div>', self.html)
        self.assertIn('<div class="basis">guidance</div>', self.html)
        self.assertIn('<div class="basis">from image</div>', self.html)

    def test_a_delta_facts_basis_is_shown_on_its_tile(self):
        segs = [dict(s) for s in SEGMENTS]
        segs[2] = dict(segs[2])
        html = render_rich_report(_report(kpis=[{"label": "Revenue", "value_fact": 2, "delta_fact": 4}]), segs, SRC)
        self.assertIn('<div class="basis">non-GAAP</div>', html)

    def test_a_kpi_with_no_basis_has_no_basis_line(self):
        html = render_rich_report(_report(kpis=[{"label": "Revenue", "value_fact": 2, "delta_fact": -1}]), SEGMENTS, SRC)
        self.assertNotIn('<div class="basis">', html)

    def test_chart_note_names_only_tagged_points(self):
        self.assertIn("Basis: Adj. NI: non-GAAP", self.html)
        self.assertNotIn("Revenue: non-GAAP", self.html)

    def test_body_text_and_footnote_mark_an_image_sourced_figure(self):
        self.assertIn("from image</span>", self.html)
        self.assertIn("Read from an image, not from extracted text.", self.html)

    def test_untagged_report_renders_without_any_basis_markup(self):
        plain = [{"type": "quote", "horizon": "reported", "value": 1.0, "format": "usd", "citation": "$1"},
                 {"type": "quote", "horizon": "reported", "value": 2.0, "format": "usd", "citation": "$2"}]
        report = {"title": "T", "kpis": [{"label": "A", "value_fact": 0, "delta_fact": -1}],
                  "executive_summary": [{"text": "It was {{0}} then {{1}}."}], "sections": [
                      {"heading": "H", "paragraphs": [{"text": "It was {{0}}."}],
                       "chart": {"type": "bar", "title": "C", "format": "usd",
                                 "series": [{"label": "a", "fact_index": 0}, {"label": "b", "fact_index": 1}]}}]}
        html = render_rich_report(report, plain, SRC)
        self.assertNotIn('class="basis"', html)
        self.assertNotIn("from image", html)
        self.assertNotIn("Read from an image", html)


class ChartNoteTest(unittest.TestCase):
    def test_note_matches_what_is_drawn(self):
        chart = {"series": [{"label": "x", "fact_index": 0}, {"label": "bad", "fact_index": 99},
                            {"label": "y", "fact_index": 1}]}
        self.assertEqual([label for label, _ in chart_points(chart, SEGMENTS)], ["x", "y"])
        self.assertEqual(chart_basis_note(chart, SEGMENTS), "Basis: x: non-GAAP; y: guidance")

    def test_no_note_when_nothing_is_tagged(self):
        chart = {"series": [{"label": "r", "fact_index": 2}]}
        self.assertEqual(chart_basis_note(chart, SEGMENTS), "")


class PdfBasisTest(unittest.TestCase):
    def setUp(self):
        data = render_rich_pdf(_report(), SEGMENTS, SRC)
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            self.text = "\n".join((page.extract_text() or "") for page in pdf.pages)

    def test_kpi_and_chart_and_body_basis_are_in_the_pdf(self):
        self.assertIn("NON-GAAP", self.text)
        self.assertIn("GUIDANCE", self.text)
        self.assertIn("FROM IMAGE", self.text)
        self.assertIn("Basis: Adj. NI: non-GAAP", self.text)
        self.assertIn("$41.0M FROM IMAGE", self.text)

    def test_pdf_footnote_says_image(self):
        self.assertIn("Read from an image", " ".join(self.text.split()))


if __name__ == "__main__":
    unittest.main()
