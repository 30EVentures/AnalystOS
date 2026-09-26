"""Slice 57 - the public pages must not repeat claims the audit found untrue.
Guards the wording only; see specs/slice-57/spec.md."""

import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
INDEX = (SITE / "index.html").read_text(encoding="utf-8")
UPLOAD = (SITE / "upload.html").read_text(encoding="utf-8")


class RetiredClaimsTest(unittest.TestCase):
    def test_retired_phrases_are_gone(self):
        for phrase in (
            "Stays on your machine",
            "Runs locally",
            "A report is never lost",
            "labels appear wherever a figure appears",
            "tagged GAAP only if the source says so",
            "a real server-generated PDF with bundled",
            "four real documents",
            "and a retrospective",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, INDEX)


class ReplacementStatementsTest(unittest.TestCase):
    def test_privacy_is_split_between_local_and_hosted(self):
        self.assertIn("On the hosted upload page, your file is uploaded to our server", INDEX)
        self.assertIn("deleted when the request ends", INDEX)
        self.assertIn("When you run it yourself", INDEX)

    def test_default_key_is_disclosed(self):
        self.assertIn("development key that is public in the source", INDEX)

    def test_labels_are_described_as_model_assigned(self):
        self.assertIn("not yet checked against the source", INDEX)
        self.assertIn("KPI tiles", INDEX)

    def test_degradation_is_honest(self):
        self.assertIn("If a file cannot be read at all, no report is produced.", INDEX)

    def test_known_limits_cover_relationships_and_determinism(self):
        self.assertIn("relationships between figures are only partly checked", INDEX)
        self.assertIn("not deterministic", INDEX)
        self.assertIn("no durable link", INDEX)

    def test_upload_page_names_the_third_party_and_the_scope(self):
        self.assertIn("Anthropic", UPLOAD)
        self.assertIn("non-confidential", UPLOAD)


if __name__ == "__main__":
    unittest.main()
