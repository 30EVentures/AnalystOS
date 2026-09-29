"""Slice 80 - the served site names the studio, never an individual, and its only contact
address is 30eventures@gmail.com. See specs/slice-80/spec.md."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
TEXT_SUFFIXES = {".html", ".txt", ".md", ".json", ".xml", ".js", ".css", ""}
CONTACT = "30eventures@gmail.com"


def served_files():
    for path in sorted(SITE.rglob("*")):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            yield path


class ServedSiteIdentityTest(unittest.TestCase):
    def test_the_scan_actually_covers_the_pages_and_the_generated_docs(self):
        names = {p.relative_to(SITE).as_posix() for p in served_files()}
        for expected in ("index.html", "upload.html", "index.old.html", "llms.txt", "docs/api.md"):
            self.assertIn(expected, names)

    def test_no_served_file_contains_a_personal_name_or_email(self):
        for path in served_files():
            with self.subTest(file=path.relative_to(SITE).as_posix()):
                text = path.read_text(encoding="utf-8", errors="replace")
                self.assertIsNone(re.search(r"(?i)caleb|solway", text))

    def test_every_real_email_address_in_the_served_site_is_the_studio_contact(self):
        # RFC 2606 reserved example domains (you@example.com in the AAO guide, which the
        # validator is meant to reject) are documentation placeholders, not contacts.
        pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        for path in served_files():
            for address in pattern.findall(path.read_text(encoding="utf-8", errors="replace")):
                if address.lower().endswith(("@example.com", "@example.org", "@example.net")):
                    continue
                with self.subTest(file=path.relative_to(SITE).as_posix(), address=address):
                    self.assertEqual(address.lower(), CONTACT)

    def test_the_sample_manifest_is_accountable_to_the_studio_contact(self):
        manifest = json.loads((ROOT / "solwayholdings.aao.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["accountableTo"], CONTACT)


if __name__ == "__main__":
    unittest.main()
