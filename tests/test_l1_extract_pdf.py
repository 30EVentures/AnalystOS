"""Tests for L1 extract_table_pdf - one per "Done when" in specs/slice-23/spec.md.

Builds real PDFs with reportlab at test time, the same way
test_l1_extract_xlsx.py builds fixtures with openpyxl - there's no committed
binary fixture anywhere in this repo, and a real PDF table needs actual
ruling lines for pdfplumber to reliably detect it.
"""

import tempfile
import unittest
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from analystos.l1.extract_pdf import extract_table_pdf
from analystos.l2.answer import answer_lookup

_STYLES = getSampleStyleSheet()


def _styled_table(rows):
    data = [["" if v is None else str(v) for v in row] for row in rows]
    t = Table(data)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    return t


def _make_pdf(path, rows, extra_page_before=False):
    """Write a minimal one-table PDF: rows[0] is the header."""
    flowables = []
    if extra_page_before:
        flowables += [Paragraph("no table on this page", _STYLES["Normal"]), PageBreak()]
    flowables.append(_styled_table(rows))
    SimpleDocTemplate(str(path), pagesize=letter).build(flowables)


def _make_pdf_two_tables(path, rows_a, rows_b):
    """Write a PDF with two separate tables, stacked on one page."""
    flowables = [_styled_table(rows_a), Spacer(1, 0.5 * inch), _styled_table(rows_b)]
    SimpleDocTemplate(str(path), pagesize=letter).build(flowables)


def _make_pdf_no_table(path):
    SimpleDocTemplate(str(path), pagesize=letter).build(
        [Paragraph("just text, no table", _STYLES["Normal"])]
    )


class ExtractPdfTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_well_formed_table_returns_typed_rows(self):  # Done when #1
        path = self.tmp / "t.pdf"
        _make_pdf(path, [["period", "revenue"], ["FY2023", "1000000"], ["FY2024", "1250000"]])
        rows = extract_table_pdf(path, {"period": "text", "revenue": "number"})
        self.assertEqual(
            rows,
            [{"period": "FY2023", "revenue": 1000000.0}, {"period": "FY2024", "revenue": 1250000.0}],
        )

    def test_blank_row_is_skipped_and_citation_row_stays_correct(self):  # Done when #1, cross-layer
        path = self.tmp / "t.pdf"
        _make_pdf(
            path, [["period", "revenue"], ["FY2023", "100"], ["", ""], ["FY2024", "200"]]
        )
        rows = extract_table_pdf(path, {"period": "text", "revenue": "number"})
        out = answer_lookup(rows, source="x" * 64, where=("period", "FY2024"), select="revenue")
        self.assertEqual(out["citation"]["row"], 4)  # not 3

    def test_missing_required_column_raises(self):  # Done when #1
        path = self.tmp / "t.pdf"
        _make_pdf(path, [["period"], ["FY2024"]])
        with self.assertRaises(ValueError) as cm:
            extract_table_pdf(path, {"period": "text", "revenue": "number"})
        self.assertIn("revenue", str(cm.exception))

    def test_bad_number_raises(self):  # Done when #1
        path = self.tmp / "t.pdf"
        _make_pdf(path, [["period", "revenue"], ["FY2024", "not-a-number"]])
        with self.assertRaises(ValueError):
            extract_table_pdf(path, {"period": "text", "revenue": "number"})

    def test_table_index_narrows_among_several_tables_on_one_page(self):  # Done when #2
        path = self.tmp / "t.pdf"
        _make_pdf_two_tables(
            path,
            [["period", "revenue"], ["FY2024", "100"]],
            [["period", "net_income"], ["FY2024", "50"]],
        )
        first = extract_table_pdf(path, {"period": "text", "revenue": "number"}, table_index=0)
        self.assertEqual(first, [{"period": "FY2024", "revenue": 100.0}])
        second = extract_table_pdf(path, {"period": "text", "net_income": "number"}, table_index=1)
        self.assertEqual(second, [{"period": "FY2024", "net_income": 50.0}])

    def test_page_narrows_the_search(self):  # Done when #2
        path = self.tmp / "t.pdf"
        _make_pdf(
            path, [["period", "revenue"], ["FY2024", "1250000"]], extra_page_before=True
        )
        # the table is on page 1 (0-based) - page 0 has none
        with self.assertRaises(ValueError) as cm:
            extract_table_pdf(path, {"period": "text"}, page=0)
        self.assertIn("page 0", str(cm.exception))
        rows = extract_table_pdf(path, {"period": "text", "revenue": "number"}, page=1)
        self.assertEqual(rows, [{"period": "FY2024", "revenue": 1250000.0}])

    def test_no_table_at_requested_index_raises(self):  # Done when #1
        path = self.tmp / "t.pdf"
        _make_pdf(path, [["period", "revenue"], ["FY2024", "100"]])
        with self.assertRaises(ValueError) as cm:
            extract_table_pdf(path, {"period": "text"}, table_index=1)
        self.assertIn("no table at index 1", str(cm.exception))

    def test_document_with_no_tables_raises(self):  # guard rail
        path = self.tmp / "t.pdf"
        _make_pdf_no_table(path)
        with self.assertRaises(ValueError):
            extract_table_pdf(path, {"period": "text"})


if __name__ == "__main__":
    unittest.main()
