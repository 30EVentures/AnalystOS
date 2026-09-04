"""Slice 21/22 - the upload page must stay in step with api/analyze.py's contract,
including the Slice 22 access-code header."""

import unittest
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parents[1] / "site"
PAGE = SITE_DIR / "upload.html"


class UploadPageTest(unittest.TestCase):
    def test_page_exists(self):
        self.assertTrue(PAGE.is_file(), f"{PAGE} is missing")

    def test_page_matches_the_api_contract(self):
        text = PAGE.read_text(encoding="utf-8")
        for needle in (
            "/api/analyze",
            'name="file"',
            'name="schema"',
            'name="title"',
            'name="template"',
            'name="currency_unit"',
            ".csv",
            ".xlsx",
            ".docx",
            ".pptx",
            "X-Access-Code",
            "access-code",
        ):
            self.assertIn(needle, text, f"upload page is missing {needle!r} - is it stale?")

    def test_index_links_to_the_upload_page(self):
        index = SITE_DIR / "index.html"
        self.assertIn("upload.html", index.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
