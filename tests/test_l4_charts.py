"""Tests for L4 chart SVG generation - one per "Done when" in
specs/slice-28/spec.md that concerns analystos.l4.charts.
"""

import re
import unittest

from analystos.l4.charts import bar_chart_svg, donut_chart_svg, line_chart_svg

_SVG_RE = re.compile(r"^<svg\b.*</svg>\s*$", re.DOTALL)


class ChartSvgTest(unittest.TestCase):
    def test_bar_chart_is_well_formed_svg(self):  # Done when #1
        svg = bar_chart_svg("Revenue by segment", ["Enterprise", "SMB"], [21_000_000, 11_600_000], "usd")
        self.assertRegex(svg, _SVG_RE)
        self.assertEqual(svg.count("<rect"), 2)  # one bar per category

    def test_bar_chart_shows_formatted_values_and_labels(self):
        svg = bar_chart_svg("Revenue", ["Enterprise", "SMB"], [21_000_000, 11_600_000], "usd")
        self.assertIn("$21.0M", svg)
        self.assertIn("$11.6M", svg)
        self.assertIn("Enterprise", svg)
        self.assertIn("SMB", svg)

    def test_line_chart_is_well_formed_svg(self):  # Done when #1
        svg = line_chart_svg("Revenue trend", ["Q2 2026", "Q3 2026"], [27_800_000, 32_600_000], "usd")
        self.assertRegex(svg, _SVG_RE)
        self.assertIn("<polyline", svg)
        self.assertEqual(svg.count("<circle"), 2)  # one point per period

    def test_line_chart_flat_series_does_not_crash(self):
        # Equal values -> zero span; must not divide by zero.
        svg = line_chart_svg("Flat", ["A", "B", "C"], [10.0, 10.0, 10.0], "number")
        self.assertRegex(svg, _SVG_RE)

    def test_donut_chart_is_well_formed_svg(self):  # Done when #1
        svg = donut_chart_svg("Revenue mix", ["Enterprise", "SMB"], [21_000_000, 11_600_000], "usd")
        self.assertRegex(svg, _SVG_RE)
        self.assertEqual(svg.count("<circle"), 2)  # one arc per category

    def test_donut_chart_shows_percentage_share_in_legend(self):
        svg = donut_chart_svg("Mix", ["A", "B"], [75.0, 25.0], "usd")
        self.assertIn("(75%)", svg)
        self.assertIn("(25%)", svg)

    def test_labels_are_html_escaped(self):
        svg = bar_chart_svg("R&D <spend>", ["A & B"], [10.0], "number")
        self.assertNotIn("<spend>", svg)
        self.assertIn("&amp;", svg)


if __name__ == "__main__":
    unittest.main()
