"""Slice 85 - cost and time caps on PDF extraction. Mocked client throughout:
no real API call, no cost, no network.
"""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pdfplumber.page
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

from analystos.l1 import extract_pdf, image_facts
from analystos.l1.document_text import extract_document_text
from analystos.l1.image_facts import DEFAULT_MAX_IMAGES, MAX_IMAGES_ENV, extract_image_transcripts, max_images

_STYLES = getSampleStyleSheet()


def _table(rows):
    t = Table([[str(v) for v in row] for row in rows])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    return t


def make_multipage_pdf(path, pages=4):
    """``pages`` pages, two ruled tables each (the second has a blank row)."""
    story = []
    for p in range(pages):
        story += [
            Paragraph(f"Page {p} commentary: revenue grew.", _STYLES["Normal"]),
            _table([["period", "revenue"], [f"FY{2020 + p}", 1000 * (p + 1)]]),
            Paragraph("between the tables", _STYLES["Normal"]),
            _table([["a", "b", "c"], ["x", "1", "2"], ["", "", ""], ["y", "3", "4"]]),
            PageBreak(),
        ]
    SimpleDocTemplate(str(path), pagesize=letter).build(story)


def make_pdf_with_images(pdf_path, png_path, count):
    Image.new("RGB", (200, 100), "white").save(png_path)
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawString(60, 750, "Exhibit page.")
    for i in range(count):
        c.drawImage(str(png_path), 60, 700 - i * 60, width=80, height=40)
    c.save()


class RecordingClient:
    def __init__(self):
        self.calls = 0
        tool_use = SimpleNamespace(type="tool_use", input={"transcript": "Q3 Revenue: $42.7 million"})
        self._response = SimpleNamespace(content=[tool_use])
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls += 1
        return self._response


class ImageCapTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def pdf(self, count):
        path = self.tmp / f"{count}.pdf"
        make_pdf_with_images(path, self.tmp / "i.png", count)
        return path

    def test_more_images_than_the_cap_fails_closed_with_zero_vision_calls(self):
        client = RecordingClient()
        with patch.dict(os.environ, {MAX_IMAGES_ENV: "3"}):
            with self.assertRaises(ValueError) as caught:
                extract_image_transcripts(self.pdf(4), client=client)
        self.assertEqual(client.calls, 0)
        message = str(caught.exception)
        self.assertIn("4 embedded images", message)
        self.assertIn("3", message)
        self.assertIn("silently", message)

    def test_the_cap_is_checked_before_a_client_is_even_resolved(self):
        with patch.dict(os.environ, {MAX_IMAGES_ENV: "1", "ANTHROPIC_API_KEY": ""}), \
                patch.object(image_facts, "_resolve_client", side_effect=AssertionError("client resolved")):
            with self.assertRaises(ValueError) as caught:
                extract_image_transcripts(self.pdf(2), client=None)
        self.assertIn("2 embedded images", str(caught.exception))

    def test_exactly_the_cap_is_allowed_and_every_image_is_read(self):
        client = RecordingClient()
        with patch.dict(os.environ, {MAX_IMAGES_ENV: "3"}):
            results = extract_image_transcripts(self.pdf(3), client=client)
        self.assertEqual(client.calls, 3)
        self.assertEqual(len(results), 3)

    def test_the_error_reaches_the_caller_of_document_extraction_not_a_silent_truncation(self):
        client = RecordingClient()
        with patch.dict(os.environ, {MAX_IMAGES_ENV: "2"}):
            with self.assertRaises(ValueError):
                extract_document_text(self.pdf(3), client=client)
        self.assertEqual(client.calls, 0)

    def test_a_pdf_without_images_ignores_the_setting_entirely(self):
        path = self.tmp / "plain.pdf"
        make_multipage_pdf(path, pages=1)
        with patch.dict(os.environ, {MAX_IMAGES_ENV: "not a number"}):
            self.assertEqual(extract_image_transcripts(path), [])

    def test_the_default_and_the_validation_of_the_setting(self):
        self.assertEqual(max_images({}), DEFAULT_MAX_IMAGES)
        self.assertEqual(max_images({MAX_IMAGES_ENV: " 7 "}), 7)
        for bad in ("0", "-1", "1.5", "ten", "1001", "٣"):
            with self.assertRaises(ValueError, msg=bad):
                max_images({MAX_IMAGES_ENV: bad})

    def test_a_malformed_setting_is_an_error_not_a_silent_default(self):
        with patch.dict(os.environ, {MAX_IMAGES_ENV: "lots"}):
            with self.assertRaises(ValueError):
                extract_image_transcripts(self.pdf(1), client=RecordingClient())


class PageExtractionOnceTest(unittest.TestCase):
    PAGES = 4
    # Captured from the code before Slice 85 (reopen-and-re-extract per table)
    # for make_multipage_pdf(pages=2); the output must not change.
    GOLDEN_TEXT = (
        "Page 1:\nPage 0 commentary: revenue grew.\nperiod revenue\nFY2020 1000\nbetween the tables\n"
        "a b c\nx 1 2\ny 3 4\nperiod | revenue\nFY2020 | 1000\na | b | c\nx | 1 | 2\ny | 3 | 4\n\n"
        "Page 2:\nPage 1 commentary: revenue grew.\nperiod revenue\nFY2021 2000\nbetween the tables\n"
        "a b c\nx 1 2\ny 3 4\nperiod | revenue\nFY2021 | 2000\na | b | c\nx | 1 | 2\ny | 3 | 4"
    )
    GOLDEN_TABLES = [
        [["period", "revenue"], [[2, {"period": "FY2020", "revenue": "1000"}]]],
        [["a", "b", "c"], [[2, {"a": "x", "b": "1", "c": "2"}], [4, {"a": "y", "b": "3", "c": "4"}]]],
        [["period", "revenue"], [[2, {"period": "FY2021", "revenue": "2000"}]]],
        [["a", "b", "c"], [[2, {"a": "x", "b": "1", "c": "2"}], [4, {"a": "y", "b": "3", "c": "4"}]]],
    ]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def count_extract_tables(self, fn):
        calls = []
        real = pdfplumber.page.Page.extract_tables

        def spy(page, *args, **kwargs):
            calls.append(page.page_number)
            return real(page, *args, **kwargs)

        with patch.object(pdfplumber.page.Page, "extract_tables", spy):
            result = fn()
        return calls, result

    def test_document_text_extracts_each_pages_tables_exactly_once(self):
        path = self.tmp / "m.pdf"
        make_multipage_pdf(path, pages=self.PAGES)
        calls, text = self.count_extract_tables(lambda: extract_document_text(path))
        self.assertEqual(sorted(calls), list(range(1, self.PAGES + 1)))  # was pages + tables x pages
        self.assertIn("FY2023 | 4000", text)  # and the tables still rendered

    def test_all_tables_extracts_each_pages_tables_exactly_once(self):
        path = self.tmp / "m.pdf"
        make_multipage_pdf(path, pages=self.PAGES)
        calls, tables = self.count_extract_tables(lambda: extract_pdf.all_tables(path))
        self.assertEqual(sorted(calls), list(range(1, self.PAGES + 1)))
        self.assertEqual(len(tables), 2 * self.PAGES)

    def test_a_given_table_is_parsed_exactly_as_the_one_found_by_index(self):
        path = self.tmp / "m.pdf"
        make_multipage_pdf(path, pages=2)
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            found = [t for p in pdf.pages for t in p.extract_tables()]
        for i, table in enumerate(found):
            self.assertEqual(extract_pdf._raw_rows(path, table=table), extract_pdf._raw_rows(path, table_index=i))
        with self.assertRaises(ValueError):
            extract_pdf._raw_rows(path, table=[])

    def test_the_output_is_unchanged_from_before_the_refactor(self):
        path = self.tmp / "m.pdf"
        make_multipage_pdf(path, pages=2)
        self.assertEqual(extract_document_text(path), self.GOLDEN_TEXT)
        self.assertEqual(
            [[h, [[n, r] for n, r in rows]] for h, rows in extract_pdf.all_tables(path)], self.GOLDEN_TABLES)


if __name__ == "__main__":
    unittest.main()
