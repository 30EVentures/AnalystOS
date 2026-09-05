"""Tests for L1 extract_any / guess_schema - one per "Done when" in specs/slice-25/spec.md."""

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from analystos.l1.detect import SUPPORTED_EXTENSIONS, extract_any
from analystos.l1.schema import guess_schema


def _pdf(path, rows):
    data = [[str(v) for v in row] for row in rows]
    t = Table(data)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(str(path), pagesize=letter).build([t])


class GuessSchemaTest(unittest.TestCase):
    def test_all_numeric_column_is_guessed_as_number(self):
        rows = [(2, {"period": "FY2023", "revenue": "1,000,000"}), (3, {"period": "FY2024", "revenue": "$1,250,000"})]
        schema = guess_schema(rows, ["period", "revenue"])
        self.assertEqual(schema, {"period": "text", "revenue": "number"})

    def test_one_non_numeric_value_makes_the_whole_column_text(self):
        rows = [(2, {"code": "100"}), (3, {"code": "N/A"})]
        schema = guess_schema(rows, ["code"])
        self.assertEqual(schema, {"code": "text"})

    def test_empty_column_is_text_not_guessed_as_number(self):
        rows = [(2, {"note": ""}), (3, {"note": ""})]
        schema = guess_schema(rows, ["note"])
        self.assertEqual(schema, {"note": "text"})

    def test_a_one_shot_iterator_still_works_for_every_header(self):
        # Regression: guess_schema scans its rows once per header - a plain
        # generator/enumerate() gets exhausted after the first header unless
        # guess_schema itself materializes it first.
        rows = [{"period": "Q1", "revenue": "120000"}, {"period": "Q2", "revenue": "145000"}]
        schema = guess_schema(enumerate(rows, start=2), ["period", "revenue"])
        self.assertEqual(schema, {"period": "text", "revenue": "number"})


class ExtractAnyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_csv_schema_is_guessed_when_omitted(self):
        path = self.tmp / "t.csv"
        path.write_text("period,revenue\nFY2023,1000000\nFY2024,1250000\n", encoding="utf-8")
        schema, rows = extract_any(path)
        self.assertEqual(schema, {"period": "text", "revenue": "number"})
        self.assertEqual(rows, [{"period": "FY2023", "revenue": 1000000.0}, {"period": "FY2024", "revenue": 1250000.0}])

    def test_xlsx_schema_is_guessed_when_omitted(self):
        path = self.tmp / "t.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["period", "revenue"])
        ws.append(["FY2024", 4200000])
        wb.save(path)
        schema, rows = extract_any(path)
        self.assertEqual(schema, {"period": "text", "revenue": "number"})
        self.assertEqual(rows, [{"period": "FY2024", "revenue": 4200000.0}])

    def test_pdf_schema_is_guessed_when_omitted(self):
        path = self.tmp / "t.pdf"
        _pdf(path, [["period", "revenue"], ["FY2024", "4200000"]])
        schema, rows = extract_any(path)
        self.assertEqual(schema, {"period": "text", "revenue": "number"})
        self.assertEqual(rows, [{"period": "FY2024", "revenue": 4200000.0}])

    def test_explicit_schema_is_honored_unchanged(self):
        path = self.tmp / "t.csv"
        path.write_text("period,code\nFY2024,007\n", encoding="utf-8")
        # "code" would be guessed "number" (007 parses) - an explicit schema overrides that
        schema, rows = extract_any(path, schema={"period": "text", "code": "text"})
        self.assertEqual(schema, {"period": "text", "code": "text"})
        self.assertEqual(rows, [{"period": "FY2024", "code": "007"}])

    def test_unsupported_extension_raises(self):
        path = self.tmp / "t.txt"
        path.write_text("not a real source format", encoding="utf-8")
        with self.assertRaises(ValueError) as cm:
            extract_any(path)
        self.assertIn(".txt", str(cm.exception))

    def test_supported_extensions_covers_every_format(self):
        self.assertEqual(SUPPORTED_EXTENSIONS, (".csv", ".docx", ".pdf", ".pptx", ".xlsx"))


if __name__ == "__main__":
    unittest.main()
