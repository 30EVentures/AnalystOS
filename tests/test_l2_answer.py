"""Tests for L2 answer_lookup - one per "Done when" in specs/slice-5/spec.md."""

import unittest

from analystos.l2.answer import answer_lookup


class AnswerLookupTest(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"period": "FY2023", "revenue": 3560000.0, "cogs": 2100000.0},
            {"period": "FY2024", "revenue": 4200000.0, "cogs": 2400000.0},
        ]
        self.src = "a1b9f2c8" * 8  # a stand-in 64-char hash

    def test_returns_answer_and_citation(self):  # Done when #1
        out = answer_lookup(
            self.rows, source=self.src, where=("period", "FY2024"), select="revenue"
        )
        self.assertEqual(out["answer"], 4200000.0)
        self.assertEqual(
            out["citation"], {"source": self.src, "row": 3, "column": "revenue"}
        )

    def test_citation_row_matches_the_csv_line(self):  # Done when #2
        out = answer_lookup(
            self.rows, source=self.src, where=("period", "FY2023"), select="cogs"
        )
        self.assertEqual(out["citation"]["row"], 2)  # first data row = line 2

    def test_no_matching_row_raises(self):  # Done when #3
        with self.assertRaises(ValueError) as cm:
            answer_lookup(
                self.rows, source=self.src, where=("period", "FY2099"), select="revenue"
            )
        self.assertIn("FY2099", str(cm.exception))

    def test_unknown_column_raises(self):  # Done when #4
        with self.assertRaises(ValueError) as cm:
            answer_lookup(
                self.rows, source=self.src, where=("period", "FY2024"), select="ebitda"
            )
        self.assertIn("ebitda", str(cm.exception))

    def test_more_than_one_match_raises(self):  # ambiguity guard
        rows = self.rows + [{"period": "FY2024", "revenue": 9.0, "cogs": 1.0}]
        with self.assertRaises(ValueError) as cm:
            answer_lookup(
                rows, source=self.src, where=("period", "FY2024"), select="revenue"
            )
        self.assertIn("expected exactly one", str(cm.exception))

    def test_empty_rows_raises(self):  # guard rail
        with self.assertRaises(ValueError):
            answer_lookup([], source=self.src, where=("period", "x"), select="y")


if __name__ == "__main__":
    unittest.main()
