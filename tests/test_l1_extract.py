"""Tests for L1 extract_table - one per "Done when" in specs/slice-4/spec.md."""

import tempfile
import unittest
from pathlib import Path

from analystos.l1.extract import extract_table


class ExtractTableTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _csv(self, text):
        p = self.tmp / "table.csv"
        p.write_text(text, encoding="utf-8")
        return p

    def test_well_formed_csv_returns_typed_rows(self):  # Done when #1
        path = self._csv(
            "period,revenue,cogs\n"
            "FY2023,3560000,2100000\n"
            "FY2024,4200000,2400000\n"
        )
        schema = {"period": "text", "revenue": "number", "cogs": "number"}
        rows = extract_table(path, schema)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0], {"period": "FY2023", "revenue": 3560000.0, "cogs": 2100000.0}
        )
        self.assertIsInstance(rows[1]["revenue"], float)

    def test_missing_required_column_raises(self):  # Done when #2
        path = self._csv("period,cogs\nFY2024,2400000\n")
        with self.assertRaises(ValueError) as cm:
            extract_table(path, {"period": "text", "revenue": "number"})
        self.assertIn("revenue", str(cm.exception))

    def test_bad_number_value_raises(self):  # Done when #3
        path = self._csv("period,revenue\nFY2024,seven\n")
        with self.assertRaises(ValueError) as cm:
            extract_table(path, {"period": "text", "revenue": "number"})
        msg = str(cm.exception)
        self.assertIn("revenue", msg)
        self.assertIn("seven", msg)

    def test_whitespace_is_trimmed(self):  # Done when #4
        path = self._csv("period,revenue\n  FY2024  ,  4200000  \n")
        rows = extract_table(path, {"period": "text", "revenue": "number"})
        self.assertEqual(rows[0], {"period": "FY2024", "revenue": 4200000.0})

    def test_extra_columns_in_csv_are_ignored(self):
        path = self._csv("period,revenue,note\nFY2024,4200000,draft\n")
        rows = extract_table(path, {"period": "text", "revenue": "number"})
        self.assertEqual(rows[0], {"period": "FY2024", "revenue": 4200000.0})

    def test_unknown_schema_type_raises(self):  # guard rail
        path = self._csv("period\nFY2024\n")
        with self.assertRaises(ValueError):
            extract_table(path, {"period": "date"})


if __name__ == "__main__":
    unittest.main()
