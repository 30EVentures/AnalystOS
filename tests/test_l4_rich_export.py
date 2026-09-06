"""Tests for L4 render_rich_report - one per "Done when" in
specs/slice-28/spec.md that concerns analystos.l4.rich_export.
"""

import unittest

from analystos.l4.rich_export import render_rich_report

SRC = "a1b9f2c8" * 8

SEGMENTS = [
    {"type": "quote", "value": 32_600_000.0, "format": "usd", "citation": "$32,600,000"},   # 0
    {"type": "quote", "value": 27_800_000.0, "format": "usd", "citation": "$27,800,000"},   # 1
    {"type": "quote", "value": 21_000_000.0, "format": "usd", "citation": "$21,000,000"},   # 2
    {"type": "quote", "value": 11_600_000.0, "format": "usd", "citation": "$11,600,000"},   # 3
    {"type": "quote", "text": "40 people", "citation": "40 people"},                        # 4: no "value"
    {"type": "prose", "text": "Momentum continued."},                                       # 5: not citable
]


def _report(**overrides):
    base = {
        "title": "Draft Co — Q3 2026",
        "executive_summary": [{"text": "Revenue reached {{0}}, up from {{1}}."}],
        "sections": [{
            "heading": "Revenue",
            "paragraphs": [{"text": "Enterprise contributed {{2}} against SMB's {{3}}."}],
            "chart": {
                "type": "bar", "title": "Revenue by segment", "format": "usd",
                "series": [{"label": "Enterprise", "fact_index": 2}, {"label": "SMB", "fact_index": 3}],
            },
        }],
        "outlook": [{"text": "Momentum should continue into Q4 2026."}],
    }
    base.update(overrides)
    return base


class RenderRichReportTest(unittest.TestCase):
    def test_executive_summary_section_and_outlook_all_render(self):  # Done when #4
        out = render_rich_report(_report(), SEGMENTS, SRC)
        self.assertIn("Executive summary", out)
        self.assertIn("<h2>Revenue</h2>", out)
        self.assertIn('class="outlook"', out)
        self.assertIn("$32.6M", out)
        self.assertIn("$27.8M", out)

    def test_chart_is_embedded_in_its_section(self):  # Done when #4
        out = render_rich_report(_report(), SEGMENTS, SRC)
        self.assertIn('class="chart-card"', out)
        self.assertIn("<svg", out)
        self.assertIn("$21.0M", out)  # Enterprise value, drawn into the chart

    def test_outlook_is_visually_distinct_from_verified_sections(self):  # Done when #4
        out = render_rich_report(_report(), SEGMENTS, SRC)
        outlook_start = out.index('class="outlook"')
        section_start = out.index('class="report-section"')
        self.assertNotEqual(outlook_start, section_start)
        self.assertIn("Interpretation, not a verified fact", out)

    def test_citation_marker_carries_a_hover_title(self):  # Done when #5
        out = render_rich_report(_report(), SEGMENTS, SRC)
        self.assertIn('title="source', out)
        self.assertIn('$32,600,000', out)

    def test_footnote_numbers_are_shared_across_summary_section_and_outlook(self):  # Done when #6
        report = _report(
            executive_summary=[{"text": "Revenue was {{0}}."}],
            sections=[{"heading": "Detail", "paragraphs": [{"text": "Also {{1}}."}], "chart": None}],
            outlook=[{"text": "Watch {{2}} next."}],
        )
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertIn(">1<", out)
        self.assertIn(">2<", out)
        self.assertIn(">3<", out)
        # exactly 3 footnote entries in the Sources panel, not reset per section
        self.assertEqual(out.count('<p id="fn'), 3)

    def test_a_fact_referenced_twice_reuses_one_footnote_number(self):
        report = _report(
            executive_summary=[{"text": "Revenue was {{0}}."}],
            sections=[{"heading": "Detail", "paragraphs": [{"text": "That same {{0}} figure led."}], "chart": None}],
            outlook=None,
        )
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertEqual(out.count('<p id="fn'), 1)

    def test_chart_with_an_out_of_range_reference_drops_that_point(self):  # Done when #2
        report = _report(sections=[{
            "heading": "Revenue",
            "paragraphs": [{"text": "See the chart."}],
            "chart": {
                "type": "bar", "title": "Revenue by segment", "format": "usd",
                "series": [
                    {"label": "Enterprise", "fact_index": 2},
                    {"label": "SMB", "fact_index": 3},
                    {"label": "Bad", "fact_index": 999},
                ],
            },
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertIn("<svg", out)
        self.assertNotIn("Bad", out)  # the dropped point's label never appears

    def test_chart_referencing_a_prose_segment_drops_that_point(self):  # Done when #2
        report = _report(sections=[{
            "heading": "Revenue",
            "paragraphs": [{"text": "See the chart."}],
            "chart": {
                "type": "bar", "title": "Revenue", "format": "usd",
                "series": [
                    {"label": "Enterprise", "fact_index": 2},
                    {"label": "SMB", "fact_index": 3},
                    {"label": "Not citable", "fact_index": 5},  # prose segment
                ],
            },
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertNotIn("Not citable", out)

    def test_chart_referencing_a_qualitative_quote_drops_that_point(self):  # Done when #2
        report = _report(sections=[{
            "heading": "Revenue",
            "paragraphs": [{"text": "See the chart."}],
            "chart": {
                "type": "bar", "title": "Revenue", "format": "usd",
                "series": [
                    {"label": "Enterprise", "fact_index": 2},
                    {"label": "SMB", "fact_index": 3},
                    {"label": "Qualitative", "fact_index": 4},  # no "value"
                ],
            },
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertNotIn("Qualitative", out)

    def test_a_chart_left_with_fewer_than_two_points_is_omitted_entirely(self):  # Done when #3
        report = _report(sections=[{
            "heading": "Revenue",
            "paragraphs": [{"text": "No chart should render here."}],
            "chart": {
                "type": "bar", "title": "Revenue", "format": "usd",
                "series": [
                    {"label": "Enterprise", "fact_index": 2},
                    {"label": "Bad", "fact_index": 999},
                ],
            },
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertNotIn("<svg", out)
        self.assertNotIn('class="chart-card"', out)

    def test_a_section_with_no_chart_at_all_renders_fine(self):
        report = _report(sections=[{
            "heading": "Revenue", "paragraphs": [{"text": "Revenue was {{0}}."}], "chart": None,
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertIn("<h2>Revenue</h2>", out)
        self.assertNotIn("<svg", out)

    def test_no_outlook_omits_the_outlook_block_entirely(self):
        out = render_rich_report(_report(outlook=None), SEGMENTS, SRC)
        self.assertNotIn('class="outlook"', out)

    def test_bold_markdown_in_prose_is_rendered_not_shown_literally(self):
        report = _report(
            executive_summary=[{"text": "**Revenue** reached {{0}}."}],
        )
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertIn("<strong>Revenue</strong>", out)
        self.assertNotIn("**", out)


if __name__ == "__main__":
    unittest.main()
