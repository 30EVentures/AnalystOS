"""Slice 21/22/25 - the upload page must stay in step with api/analyze.py's
contract, including the access-code header and the /api/extract preview
step that fills the schema field in automatically."""

import unittest
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parents[1] / "site"
PAGE = SITE_DIR / "upload.html"


class UploadPageTest(unittest.TestCase):
    def test_page_exists(self):
        self.assertTrue(PAGE.is_file(), f"{PAGE} is missing")

    def test_page_matches_the_api_contract(self):
        # "template" is deliberately not a static form field any more (slice
        # 26 made omitting it the new narrated-analysis default) - the page
        # only sends it when the "tabular-toggle" checkbox says the upload
        # is a table, so its presence is asserted via that JS wiring instead
        # of a literal name="template" attribute.
        text = PAGE.read_text(encoding="utf-8")
        for needle in (
            "/api/analyze",
            "/api/extract",
            'name="file"',
            'name="schema"',
            'name="title"',
            "tabular-toggle",
            "body.set('template', 'income_statement')",
            'name="currency_unit"',
            'name="pdf_confirmed"',
            ".csv",
            ".xlsx",
            ".docx",
            ".pptx",
            ".pdf",
            "X-Access-Code",
            "access-code",
        ):
            self.assertIn(needle, text, f"upload page is missing {needle!r} - is it stale?")

    def test_index_links_to_the_upload_page(self):
        index = SITE_DIR / "index.html"
        self.assertIn("upload.html", index.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
