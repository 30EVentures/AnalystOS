"""Slice 11 - the analyst guide must stay in step with the real commands."""

import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "using-analystos.md"


class UsingDocTest(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(DOC.is_file(), f"{DOC} is missing")

    def test_doc_names_the_current_commands(self):
        text = DOC.read_text(encoding="utf-8")
        for needle in (
            "python3 -m analystos.scaffold",
            "python3 -m analystos ",
            "job.json",
            "section.md",
            "section.html",
            "{answer}",
            "template",
            "currency_unit",
        ):
            self.assertIn(needle, text, f"guide is missing {needle!r} - is it stale?")


if __name__ == "__main__":
    unittest.main()
