"""Overnight round 4 - number display at the edges.

Found by rendering boundary and extreme values through ``format_number``:

  * a dollar amount just under a unit boundary printed in the smaller unit with a four-digit
    mantissa ("$1,000.0K" for $999,999; "$1,000.0M" for $999,999,999) instead of rolling over
    to "$1.0M" / "$1.0B";
  * a finite value of about 1e30 or more raised decimal.InvalidOperation from the
    ``percent``/``usd`` formats (the default 28-digit decimal context), and inf/nan raised
    OverflowError/ValueError or printed "NaN%". A figure parsed from a long run of digits in a
    document can reach the renderer, and a renderer must not crash a report over one number;
  * a digit run too long for a float parsed as ``inf`` and could be "verified" against a model
    value of infinity.
"""

import math
import unittest

from analystos.l2.analyze import _parse_numbers, _value_matches_text
from analystos.l4.seal import build_bundle
from analystos.l4.seal_verify import parse_numbers, verify_bundle
from analystos.l4.export import _compact_usd, format_number


class UnitRolloverTest(unittest.TestCase):
    def test_a_value_that_rounds_up_to_1000_of_a_unit_moves_to_the_next_unit(self):
        for raw, expected in (
            (999_999, "$1.0M"), (999_950, "$1.0M"), (999_949.99, "$999.9K"),
            (999_999_999, "$1.0B"), (999_950_000, "$1.0B"), (999_949_999, "$999.9M"),
            (1_000_000, "$1.0M"), (1_000, "$1.0K"), (999.99, "$999.99"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(_compact_usd(raw), expected)
                self.assertEqual(format_number(raw, "usd"), expected)

    def test_rollover_follows_the_requested_precision(self):
        self.assertEqual(_compact_usd(999_995, 2), "$1.00M")
        self.assertEqual(_compact_usd(999_994, 2), "$999.99K")
        self.assertEqual(_compact_usd(999_999_995, 2), "$1.00B")

    def test_rollover_applies_after_the_currency_unit_is_applied(self):
        self.assertEqual(format_number(999.95, "usd", "thousands"), "$1.0M")
        self.assertEqual(format_number(999.95, "usd", "millions"), "$1.0B")

    def test_the_largest_unit_does_not_roll_over_further(self):
        self.assertEqual(_compact_usd(1_000_000_000_000), "$1,000.0B")
        self.assertEqual(format_number(-999_999, "usd"), "($1.0M)")


class ExtremeValuesTest(unittest.TestCase):
    def test_huge_finite_values_render_instead_of_raising(self):
        for value in (1e22, 1e30, 1e100, 1e300, 1.7e308):
            for spec in ("number", "percent", "usd"):
                with self.subTest(value=value, spec=spec):
                    self.assertTrue(format_number(value, spec))

    def test_non_finite_values_are_shown_as_text_not_formatted_or_raised(self):
        for value in (float("inf"), float("-inf"), float("nan")):
            for spec in ("number", "percent", "usd"):
                with self.subTest(value=value, spec=spec):
                    self.assertEqual(format_number(value, spec), str(value))

    def test_ordinary_values_are_unchanged(self):
        self.assertEqual(format_number(12.25, "percent"), "12.3%")
        self.assertEqual(format_number(1234, "number"), "1,234")
        self.assertEqual(format_number(-498_000_000, "usd"), "($498.0M)")


class OverlongNumberTest(unittest.TestCase):
    def test_a_digit_run_too_long_for_a_float_is_not_a_number(self):
        digits = "9" * 400
        self.assertTrue(math.isinf(float(digits)))  # why it matters: float() does not refuse it
        self.assertEqual(_parse_numbers(digits), [])
        self.assertEqual(_parse_numbers(f"Revenue was ${digits} million"), [])

    def test_it_cannot_be_matched_by_a_value_of_infinity(self):
        self.assertIsNone(_value_matches_text(float("inf"), "9" * 400))

    def test_ordinary_numbers_still_parse(self):
        self.assertEqual(_parse_numbers("$1.2 million and (3,400)"), [1_200_000.0, -3400.0])


class StandaloneVerifierNonFiniteTest(unittest.TestCase):
    """The standalone verifier is the one a stranger runs. Sealed numbers are strings, and
    ``float("inf")`` accepts "inf"; a 400-digit citation also parses to inf and equals it."""

    HUGE = "9" * 400
    TEXT = f"Revenue was ${HUGE} in total. Costs were $5 and $7."

    def verdict(self, segment):
        trace = {"tier": "deterministic", "segments": [segment], "report": None,
                 "document_text": self.TEXT, "source_hash": "a" * 64}
        return verify_bundle(build_bundle(trace), source_text=self.TEXT)

    def test_a_sealed_infinite_value_is_not_content_checked_against_a_huge_citation(self):
        outcome = self.verdict({"type": "quote", "label": "Revenue", "value": "inf", "format": "usd",
                                "citation": "$" + self.HUGE, "horizon": "reported", "gaap_status": "n/a"})
        self.assertFalse(outcome["content_checked"], outcome["checks"])

    def test_sealed_non_finite_calculations_are_not_content_checked(self):
        for operation, operands, value in (("sum", ["inf", "1"], "inf"), ("difference", ["inf", "inf"], "nan"),
                                           ("sum", ["nan", "1"], "nan"), ("sum", ["-inf", "1"], "-inf")):
            with self.subTest(operation=operation, operands=operands):
                outcome = self.verdict({"type": "computed", "label": "x", "operation": operation, "value": value,
                                        "format": "usd", "operands": operands, "total": None,
                                        "citation": ["$" + self.HUGE, "$5"], "horizon": "reported"})
                self.assertFalse(outcome["content_checked"], outcome["checks"])

    def test_a_digit_run_too_long_for_a_float_is_not_a_number_here_either(self):
        self.assertEqual(parse_numbers("9" * 400), [])
        self.assertEqual(parse_numbers("$5 and $7"), [5.0, 7.0])

    def test_an_honest_seal_still_content_checks(self):
        outcome = self.verdict({"type": "quote", "label": "Costs", "value": "5.0", "format": "usd",
                                "citation": "$5", "horizon": "reported", "gaap_status": "n/a"})
        self.assertTrue(outcome["content_checked"], outcome["checks"])


if __name__ == "__main__":
    unittest.main()
