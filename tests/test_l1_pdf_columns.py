"""Tests for L1 column-aware PDF text extraction - specs/slice-50/spec.md,
Done when #1 and #2.
"""

import tempfile
import unittest
from pathlib import Path

import pdfplumber
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate

from analystos.l1.pdf_columns import extract_page_text


def _two_column_pdf(path):
    c = canvas.Canvas(str(path), pagesize=letter)
    w, h = letter
    left_x, right_x = 60, w / 2 + 20
    top = h - 80
    for i in range(10):
        c.drawString(left_x, top - i * 18, f"Left column line {i + 1} alpha")
        c.drawString(right_x, top - i * 18, f"Right column line {i + 1} beta")
    c.save()


class ColumnDetectionTest(unittest.TestCase):  # Slice 50, Done when #1
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_two_column_page_reads_one_column_fully_before_the_other(self):
        path = self.tmp / "twocol.pdf"
        _two_column_pdf(path)
        with pdfplumber.open(path) as pdf:
            text = extract_page_text(pdf.pages[0])

        # every left-column line appears, in order, strictly before every
        # right-column line - not merely present somewhere in the text
        left_positions = [text.index(f"Left column line {i} alpha") for i in range(1, 11)]
        right_positions = [text.index(f"Right column line {i} beta") for i in range(1, 11)]
        self.assertEqual(left_positions, sorted(left_positions))
        self.assertEqual(right_positions, sorted(right_positions))
        self.assertLess(max(left_positions), min(right_positions))

    def test_the_default_pdfplumber_reading_order_really_does_interleave(self):
        # Confirms the bug this slice fixes is real, not assumed - the
        # same fixture, read the old way, interleaves both columns line
        # by line instead of reading one column fully first.
        path = self.tmp / "twocol.pdf"
        _two_column_pdf(path)
        with pdfplumber.open(path) as pdf:
            raw = pdf.pages[0].extract_text()
        self.assertLess(
            raw.index("Left column line 1 alpha"),
            raw.index("Right column line 1 beta"),
        )
        self.assertLess(
            raw.index("Right column line 1 beta"),
            raw.index("Left column line 2 alpha"),
        )


class SingleColumnFallbackTest(unittest.TestCase):  # Slice 50, Done when #2
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_single_column_page_is_identical_to_the_pre_slice_50_output(self):
        path = self.tmp / "prose.pdf"
        styles = getSampleStyleSheet()
        SimpleDocTemplate(str(path), pagesize=letter).build(
            [Paragraph("This is a real prose paragraph about the business.", styles["Normal"])]
        )
        with pdfplumber.open(path) as pdf:
            page = pdf.pages[0]
            self.assertEqual(extract_page_text(page), page.extract_text())

    def test_an_empty_page_does_not_raise(self):
        path = self.tmp / "blank.pdf"
        c = canvas.Canvas(str(path), pagesize=letter)
        c.showPage()
        c.save()
        with pdfplumber.open(path) as pdf:
            self.assertEqual(extract_page_text(pdf.pages[0]), "")


if __name__ == "__main__":
    unittest.main()
