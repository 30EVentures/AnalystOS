"""Tests for the rich (v4) report's real, server-generated PDF -
specs/slice-48/spec.md. Every check reads the actual generated PDF bytes
back with pdfplumber (already a dependency) - page count, per-page text,
low-level vector rects/lines, and per-character font/size - never a
manual visual check.
"""

import io
import unittest
from unittest.mock import patch

import pdfplumber

from analystos.l4 import rich_pdf
from analystos.l4.rich_pdf import _INTERP_BG, _PANEL, render_rich_pdf

SRC = "a1b9f2c8" * 8

SEGMENTS = [
    {"type": "quote", "horizon": "reported", "value": 498_000_000.0, "format": "usd",
     "citation": "$498.0 million"},                                                  # 0
    {"type": "computed", "horizon": "reported", "operation": "growth_percent",
     "value": -12.5, "format": "percent", "operands": [22_400_000.0, 19_600_000.0],
     "total": None, "citation": ["$22.4 million", "$19.6 million"]},                 # 1
    {"type": "quote", "horizon": "reported", "value": 88_000_000.0, "format": "usd",
     "citation": "$88.0 million"},                                                   # 2 bridge start
    {"type": "computed", "horizon": "reported", "operation": "difference",
     "value": 20_000_000.0, "format": "usd",
     "operands": [142_000_000.0, 88_000_000.0, 34_000_000.0], "total": None,
     "citation": ["$142.0M", "$88.0M", "$34.0M"]},                                    # 3 component
    {"type": "quote", "horizon": "reported", "value": 34_000_000.0, "format": "usd",
     "citation": "$34.0 million"},                                                   # 4 component
    {"type": "quote", "horizon": "reported", "value": 142_000_000.0, "format": "usd",
     "citation": "$142.0 million"},                                                  # 5 bridge end
]


def _report(**over):
    base = {
        "title": "Acme Q3",
        "kpis": [{"label": "Revenue", "value_fact": 0, "delta_fact": 1}],
        "executive_summary": [{"text": "Revenue was {{0}}."}],
        "executive_insight": "Read together, {{0}} and {{1}} tell one story.",
        "sections": [{
            "heading": "Segments",
            "paragraphs": [{"text": "It grew via a bridge from {{2}} to {{5}}."}],
            "chart": {"type": "waterfall", "title": "Bridge", "format": "usd",
                      "series": [{"label": "start", "fact_index": 2},
                                 {"label": "organic", "fact_index": 3},
                                 {"label": "halyard", "fact_index": 4},
                                 {"label": "end", "fact_index": 5}]},
        }],
        "disclosure_gaps": [{"text": "EPS is not disclosed."}],
        "outlook": [{"text": "Guidance was reiterated."}],
        "outlook_interpretation": "That reiteration is itself a signal.",
    }
    base.update(over)
    return base


class RichPdfValidityTest(unittest.TestCase):  # Done when #1
    def test_a_real_report_produces_a_structurally_valid_pdf(self):
        pdf_bytes = render_rich_pdf(_report(), SEGMENTS, SRC)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            self.assertGreaterEqual(len(pdf.pages), 1)
            full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        self.assertIn("Acme Q3", full_text)
        self.assertIn("$498.0M", full_text)
        self.assertIn("Bridge", full_text)


class RichPdfKpiAndOutlookTest(unittest.TestCase):  # Done when #3
    def setUp(self):
        pdf_bytes = render_rich_pdf(_report(), SEGMENTS, SRC)
        self.pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
        self.full_text = "\n".join((p.extract_text() or "") for p in self.pdf.pages)

    def tearDown(self):
        self.pdf.close()

    def test_the_kpi_strip_is_present(self):
        self.assertIn("Revenue", self.full_text)
        self.assertIn("$498.0M", self.full_text)
        self.assertIn("(12.5%)", self.full_text)

    def test_the_kpi_value_is_rendered_in_a_visually_distinct_font_from_body_text(self):
        # A real, programmatic "visually distinct" proof - not just that
        # the text appears somewhere, but that it's set in a materially
        # larger, different-weight face than an ordinary paragraph.
        kpi_value_chars = []
        for page in self.pdf.pages:
            text_by_char = "".join(c["text"] for c in page.chars)
            if "$498.0M" in text_by_char:
                idx = text_by_char.index("$498.0M")
                kpi_value_chars.extend(page.chars[idx:idx + len("$498.0M")])
        self.assertTrue(kpi_value_chars, "could not locate the rendered KPI value's characters")
        self.assertTrue(any("SemiBold" in c["fontname"] for c in kpi_value_chars))
        self.assertTrue(any(c["size"] >= 14 for c in kpi_value_chars))

    def test_the_outlook_section_is_present(self):
        self.assertIn("Outlook", self.full_text)
        self.assertIn("Guidance was reiterated", self.full_text)
        self.assertIn("That reiteration is itself a signal", self.full_text)

    def test_the_outlook_section_has_its_own_distinct_background_color(self):
        # The exact same amber panel color rich_export's own CSS uses for
        # .outlook - a real, checkable fill, not just nearby text.
        found = any(
            r.get("fill") and _close(r["non_stroking_color"], _rgb(_INTERP_BG))
            for page in self.pdf.pages for r in page.rects
        )
        self.assertTrue(found, "no rect found matching the outlook panel's background color")

    def test_the_executive_insight_box_has_its_own_distinct_background_color(self):
        found = any(
            r.get("fill") and _close(r["non_stroking_color"], _rgb(_PANEL))
            for page in self.pdf.pages for r in page.rects
        )
        self.assertTrue(found, "no rect found matching the executive-insight panel's background color")


class RichPdfChartPaginationTest(unittest.TestCase):  # Done when #2
    def test_a_chart_is_never_split_across_a_page_boundary(self):
        # Enough filler content before a chart-bearing section to force a
        # real page break near it - proving KeepTogether actually works,
        # not just that a chart happened to fit on one page by luck.
        segments = [
            {"type": "quote", "horizon": "reported", "value": float(i) * 1_000_000,
             "format": "usd", "citation": f"${i}.0 million"}
            for i in range(1, 30)
        ]
        segments += [
            {"type": "quote", "horizon": "reported", "value": 88_000_000.0, "format": "usd",
             "citation": "$88.0 million"},   # 29
            {"type": "quote", "horizon": "reported", "value": 20_000_000.0, "format": "usd",
             "citation": "$20.0 million"},   # 30
            {"type": "quote", "horizon": "reported", "value": 142_000_000.0, "format": "usd",
             "citation": "$142.0 million"},  # 31
        ]
        filler_paras = [
            {"text": f"Fact {{{{{i - 1}}}}} was reported as a routine figure this quarter, "
                     f"with no material change from prior guidance previously communicated."}
            for i in range(1, 25)
        ]
        report = {
            "title": "Dense Report", "kpis": [],
            "executive_summary": [{"text": "This report has many filler paragraphs before a chart."}],
            "executive_insight": None,
            "sections": [
                {"heading": "Filler section", "paragraphs": filler_paras, "chart": None},
                {"heading": "Bridge section",
                 "paragraphs": [{"text": "The bridge runs from {{29}} to {{31}}."}],
                 "chart": {"type": "waterfall", "title": "Bridge", "format": "usd",
                           "series": [{"label": "start", "fact_index": 29},
                                      {"label": "component", "fact_index": 30},
                                      {"label": "end", "fact_index": 31}]}},
            ],
            "disclosure_gaps": [], "outlook": None, "outlook_interpretation": None,
        }
        pdf_bytes = render_rich_pdf(report, segments, SRC)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            self.assertGreater(len(pdf.pages), 2)  # confirms this genuinely spans multiple pages
            rects_per_page = [len(page.rects) for page in pdf.pages]
        # the waterfall's 3 bars must all land on exactly one page - never
        # split 2+1, or 1+2, across a boundary
        pages_with_chart_rects = [n for n in rects_per_page if n > 0]
        self.assertEqual(pages_with_chart_rects, [3])

    def test_the_post_hoc_waterfall_tie_out_check_still_applies_to_the_pdf_path(self):
        # Same safety layer as the HTML renderer (Slice 47), independent
        # of the shape detector - proven the same way: force the detector
        # to say "waterfall" for data that doesn't tie out and confirm
        # the chart is refused (no chart flowable at all), not drawn
        # anyway.
        report = _report()
        report["sections"][0]["chart"]["series"][1]["fact_index"] = 0  # $498M breaks the bridge
        with patch.object(rich_pdf, "_detect_chart_type", return_value="waterfall"):
            pdf_bytes = render_rich_pdf(report, SEGMENTS, SRC)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            all_rects = [r for p in pdf.pages for r in p.rects]
        # the boxed panels (insight/disclosure-gap/outlook) are expected
        # and fine - what must never appear is a waterfall *bar* color,
        # which only the chart renderer itself ever produces
        from analystos.l4.rich_pdf import _VERIFIED, _NEG
        from reportlab.lib import colors as _colors
        # every fill color the waterfall drawer ever uses for a bar -
        # start/end (_VERIFIED), a positive component (this green), or a
        # negative component (_NEG) - none of them may appear if the
        # chart was genuinely refused
        bar_colors = {_rgb(_VERIFIED), _rgb(_NEG), _rgb(_colors.HexColor("#5C8A72"))}
        chart_rects = [r for r in all_rects if r.get("fill") and any(
            _close(r["non_stroking_color"], c) for c in bar_colors
        )]
        self.assertEqual(chart_rects, [])


def _rgb(reportlab_color):
    return (reportlab_color.red, reportlab_color.green, reportlab_color.blue)


def _close(a, b, tol=0.01):
    return all(abs(x - y) < tol for x, y in zip(a, b))


if __name__ == "__main__":
    unittest.main()
