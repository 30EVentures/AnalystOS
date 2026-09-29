"""Slice 79 - the public pages credit the studio, not an individual. See specs/slice-79/spec.md."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = {name: (ROOT / "site" / name).read_text(encoding="utf-8") for name in ("index.html", "upload.html")}


class PublicPagesCreditTheStudioTest(unittest.TestCase):
    def test_no_public_page_names_an_individual(self):
        for name, text in PAGES.items():
            with self.subTest(page=name):
                self.assertNotIn("Caleb", text)
                self.assertNotIn("Solway", text)

    def test_the_homepage_credits_30e_ventures_in_byline_builder_section_and_status(self):
        text = PAGES["index.html"]
        self.assertIn("Built by 30E Ventures. Early stage", text)
        self.assertIn("AnalystOS is built by", text)
        self.assertIn("Built by 30E Ventures, early stage", text)

    def test_it_no_longer_says_solo_or_on_my_own(self):
        text = PAGES["index.html"]
        self.assertNotRegex(text, r"(?i)built solo")
        self.assertNotIn("on my own", text)

    def test_the_pilot_section_speaks_as_we_not_i(self):
        self.assertNotIn("What I need from you", PAGES["index.html"])
        self.assertIn("What we need from you", PAGES["index.html"])

    def test_the_builder_section_keeps_its_factual_claims(self):
        section = re.search(r'id="builder">(.*?)</section>', PAGES["index.html"], re.S).group(1)
        for claim in ("spec before every piece of code", "every real bug with its root cause",
                      "a number nobody can defend", "where it is weak"):
            self.assertIn(claim, section)


if __name__ == "__main__":
    unittest.main()
