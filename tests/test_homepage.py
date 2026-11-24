"""Slice 122 - the short homepage (mock A) stays true: its counts match the catalog, its
slide preview shows the sample deck's verified figures, the sample deck is current, every
link it carries is served, and it says no price has been set."""

import re
import subprocess
import sys
import unittest
from pathlib import Path

from analystos.catalog import load_catalog
from analystos.l4 import deck

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PAGE = (SITE / "index.html").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "tools"))
import build_sample_deck  # noqa: E402


class HomepageTest(unittest.TestCase):
    def test_role_and_family_counts_match_the_catalog(self):
        catalog = load_catalog()
        roles, families = len(catalog["roles"]), len(catalog["families"])
        self.assertIn(f"{roles} roles in {families} families", PAGE)
        self.assertIn(f"Hire for any of {families} families", PAGE)
        named = re.search(r'<p class="roles">(.*?)</p>', PAGE).group(1)
        listed = named.count("&middot;")  # six roles named, then "and N more"
        self.assertIn(f"and {roles - listed} more", named)
        for family in catalog["families"]:
            self.assertIn(family["title"], PAGE)

    def test_the_slide_preview_shows_the_sample_decks_verified_figures(self):
        spec, _ = build_sample_deck.build()
        figures = {f["id"]: f for f in spec["content"]["figures"]}
        preview = re.search(r'<div class="slide".*?</figure>', PAGE, re.S).group(0)
        for value, fid in re.findall(r'<span class="n">([^<]+)</span><span class="ref">(F\d+)</span>', preview):
            with self.subTest(fid=fid):
                self.assertEqual(value, deck.format_value(figures[fid]))
        self.assertGreaterEqual(len(re.findall(r'class="ref">F\d+', preview)), 4)
        self.assertIn(f"2 / {deck.slide_count(spec)}", preview)

    def test_the_sample_deck_is_current(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_sample_deck.py"), "--check"],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_link_is_served(self):
        for href in sorted(set(re.findall(r'href="([^"#:]+)"', PAGE))):
            if href.startswith(("https://fonts.", "/api/")) or href == "/":
                continue
            with self.subTest(href=href):
                self.assertTrue((SITE / href.lstrip("/")).is_file(), href)

    def test_the_top_menu_has_a_few_sections_that_all_exist(self):
        menu = re.search(r'<nav class="links".*?</nav>', PAGE, re.S).group(0)
        links = re.findall(r'href="([^"]+)"', menu)
        self.assertTrue(4 <= len(links) <= 6, links)  # some sections, not the old twelve
        for href in links:
            if href.startswith("#"):
                with self.subTest(anchor=href):
                    self.assertIn(f'id="{href[1:]}"', PAGE)
        self.assertNotIn("display:none", re.search(r"\.links\{[^}]*\}", PAGE).group(0))  # never hidden

    def test_it_says_no_price_has_been_set(self):
        self.assertIn("Price: to be determined.", PAGE)
        self.assertNotRegex(PAGE, r"(?i)per (engagement )?hour|/hr\b|free trial")


if __name__ == "__main__":
    unittest.main()
