"""Slice 64 - displayed figures round half up. See specs/slice-64/spec.md."""

import random
import unittest
from decimal import ROUND_HALF_EVEN, Decimal

from analystos.l4.charts import donut_chart_svg
from analystos.l4.export import _compact_usd, format_number, round_half_up


class RoundHalfUpTest(unittest.TestCase):
    def test_half_way_cases_go_up(self):
        for value, decimals, expected in (
            (1.95, 1, "2.0"), (12.25, 1, "12.3"), (0.35, 1, "0.4"), (0.05, 1, "0.1"), (2.5, 0, "3"),
            (1.005, 2, "1.01"), (1234.55, 1, "1,234.6"), (0.5, 0, "1"), (1.5, 0, "2"),
        ):
            with self.subTest(value=value):
                self.assertEqual(round_half_up(value, decimals), expected)

    def test_the_old_behaviour_was_wrong_for_these(self):
        self.assertEqual(f"{1.95:.1f}", "1.9")  # what the formatter used to show
        self.assertEqual(round_half_up(1.95, 1), "2.0")

    def test_negatives_round_away_from_zero(self):
        self.assertEqual(round_half_up(-1.95, 1), "-2.0")
        self.assertEqual(round_half_up(-0.25, 1), "-0.3")

    def test_non_half_way_values_are_unchanged_from_the_old_formatter(self):
        rng = random.Random(64)
        for _ in range(2000):
            x = rng.uniform(0, 5000)
            old = f"{x:,.1f}"
            new = round_half_up(x, 1)
            # differs only if x's shortest decimal form is exactly half-way
            digits = Decimal(repr(x))
            half_way = (digits * 100) % 10 == 5 and (digits * 100) == (digits * 100).to_integral_value()
            if not half_way:
                self.assertEqual(new, old, x)


class DisplayedFiguresTest(unittest.TestCase):
    def test_usd_compact_forms(self):
        for raw, expected in (
            (1_950_000_000, "$2.0B"), (1_850_000_000, "$1.9B"), (12_250_000, "$12.3M"),
            (498_000_000, "$498.0M"), (63_500_000, "$63.5M"), (2_450, "$2.5K"), (999.995, "$1,000.00"),
            (1_234.5, "$1.2K"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(_compact_usd(raw), expected)

    def test_usd_with_more_decimals_still_adds_up(self):
        self.assertEqual(_compact_usd(1_950_000_000, 2), "$1.95B")

    def test_percent_and_number(self):
        self.assertEqual(format_number(12.25, "percent"), "12.3%")
        self.assertEqual(format_number(-12.25, "percent"), "(12.3%)")
        self.assertEqual(format_number(12.24, "percent"), "12.2%")
        self.assertEqual(format_number(1234.55, "number"), "1,234.6")
        self.assertEqual(format_number(1234, "number"), "1,234")

    def test_a_scaled_currency_unit_is_still_exact(self):
        self.assertEqual(format_number(1950, "usd", "millions"), "$2.0B")
        self.assertEqual(format_number(1.95, "usd", "thousands"), "$2.0K")

    def test_non_numeric_input_still_falls_back(self):
        self.assertEqual(format_number("n/a", "usd"), "n/a")
        self.assertEqual(format_number(None, None), "None")

    def test_the_donut_share_label_rounds_half_up(self):
        # two slices, 50.5% / 49.5%: half-even printed "50%" for 50.5
        svg = donut_chart_svg("Mix", ["a", "b"], [101.0, 99.0], "number")
        self.assertIn("(51%)", svg)
        self.assertIn("(50%)", svg)


if __name__ == "__main__":
    unittest.main()
