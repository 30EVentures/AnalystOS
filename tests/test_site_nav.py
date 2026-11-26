"""Slice 130 - the product header with a dropdown on every top section, the AnalystOS
footer, the institutional look and the glossary page stay true: every menu link goes
somewhere real, every family and role link names a real family and role, the glossary's
counts match the catalog, and nothing is loaded from a third party."""

import re
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from analystos.catalog import load_catalog
from analystos.l4 import formats
from analystos.packs import work

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "tools"))
import build_site_machine  # noqa: E402
import studio_chrome  # noqa: E402

CATALOG = load_catalog()
FAMILIES = {f["id"]: f for f in CATALOG["families"]}
ROLES = {r["id"]: r for r in CATALOG["roles"]}
NAV = studio_chrome.render_nav()
GLOSSARY = (SITE / "glossary.html").read_text(encoding="utf-8")
STUDIO_HOSTS = ("https://www.30eventures.com/",)
API_PATHS = ("/api/v1/openapi.json", "/api/v2/catalog")  # served by the API, not files


def page_ids(path):
    return set(re.findall(r'\bid="([^"]+)"', (SITE / path).read_text(encoding="utf-8")))


class HeaderTest(unittest.TestCase):
    def test_every_top_section_is_a_dropdown(self):
        labels = re.findall(r'<li class="an-has"><button type="button" aria-expanded="false" aria-controls="an-m-([a-z]+)">([^<]+)<', NAV)
        self.assertEqual([label for _, label in labels], ["Roles", "Samples", "How it works", "For agents", "Learn"])
        for mid, _ in labels:
            self.assertIn(f'id="an-m-{mid}"', NAV)
        self.assertNotRegex(NAV, r'<nav class="an-primary"[^>]*><ul>\s*<li><a')  # no plain top-level links

    def test_every_menu_link_goes_somewhere_real(self):
        for href in re.findall(r'href="([^"]+)"', NAV):
            with self.subTest(href=href):
                if href.startswith(STUDIO_HOSTS):
                    continue  # the studio site; its pages are checked live, not from this repo
                self.assertTrue(href.startswith("/"), href)
                parts = urlsplit(href)
                if parts.path in API_PATHS:
                    continue
                target = "index.html" if parts.path == "/" else parts.path.lstrip("/")
                self.assertTrue((SITE / target).is_file(), target)
                if parts.fragment:
                    self.assertIn(parts.fragment, page_ids(target), href)
                query = parse_qs(parts.query)
                if "family" in query:
                    self.assertIn(query["family"][0], FAMILIES)
                if "role" in query:
                    self.assertEqual(ROLES[query["role"][0]]["family"], query["family"][0])

    def test_the_roles_menu_lists_every_family_with_its_count_and_format(self):
        menu = re.search(r'id="an-m-roles".*?</ul>', NAV, re.S).group(0)
        for fam in CATALOG["families"]:
            count = sum(1 for r in CATALOG["roles"] if r["family"] == fam["id"])
            fmt = formats.FORMATS[formats.FAMILY_FORMAT[fam["id"]]]["name"]
            with self.subTest(family=fam["id"]):
                self.assertIn(f'href="/?family={fam["id"]}#samples"', menu)
                self.assertIn(f"{count} role{'s' if count != 1 else ''} · {studio_chrome.FORMAT_NAMES[fmt]}", menu)

    def test_every_page_has_the_header_once_and_its_script(self):
        for page in studio_chrome.PAGES:
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=page.name):
                self.assertEqual(text.count('<header class="an-head" id="an-head">'), 1)
                self.assertEqual(text.count('<script src="/nav.js" defer></script>'), 1)
                self.assertNotIn('<header class="top">', text)

    def test_the_details_page_keeps_its_section_bar_and_theme_button(self):
        text = (SITE / "details.html").read_text(encoding="utf-8")
        self.assertIn('<div class="top subnav">', text)
        self.assertEqual(text.count('id="themeBtn"'), 1)
        self.assertIn('href="#trust"', text)

    def test_nothing_is_loaded_from_a_third_party(self):
        for page in studio_chrome.PAGES:
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=page.name):
                self.assertNotIn("fonts.googleapis", text)
                self.assertNotIn("fonts.gstatic", text)
                self.assertEqual(re.findall(r'<script[^>]+src="(?!/nav\.js)', text), [])

    def test_the_menu_script_never_writes_html(self):
        script = (SITE / "nav.js").read_text(encoding="utf-8")
        for unsafe in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "fetch("):
            self.assertNotIn(unsafe, script)
        self.assertIn('e.key === "Escape"', script)

    def test_the_explorer_opens_on_a_linked_family_and_role(self):
        page = (SITE / "index.html").read_text(encoding="utf-8")
        self.assertIn("params.get('family')", page)
        self.assertIn("params.get('role')", page)


class LookTest(unittest.TestCase):
    def test_the_ai_site_tells_are_gone_from_the_homepage(self):
        page = (SITE / "index.html").read_text(encoding="utf-8")
        style = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
        self.assertNotIn("border-radius:999px", style)  # no pill buttons, tabs or chips
        self.assertNotIn("Bricolage", style)
        self.assertNotRegex(style, r"\.ready\{[^}]*border-radius")
        self.assertIn('"Iowan Old Style"', studio_chrome.CSS)  # the 30E Ventures serif, from the system's own fonts


class FooterTest(unittest.TestCase):
    def test_the_footer_says_what_the_product_is_today(self):
        foot = studio_chrome.render_footer()
        self.assertIn("Specialist work, ready the moment you need it.", foot)
        self.assertNotIn("Every figure in the report", foot)
        self.assertIn('href="/glossary.html"', foot)
        for label in ("Concepts", "Press", "Studio glossary"):
            self.assertIn(f">{label}<", foot)


class GlossaryTest(unittest.TestCase):
    def test_every_term_has_a_unique_anchor(self):
        ids = re.findall(r'<div class="g-term" id="([^"]+)">', GLOSSARY)
        self.assertGreaterEqual(len(ids), 30)
        self.assertEqual(len(ids), len(set(ids)))

    def test_its_counts_match_the_catalog(self):
        owing = sum(1 for r in CATALOG["roles"] if work.required_kinds(r))
        self.assertIn(f"One of {len(CATALOG['roles'])} entry-level", GLOSSARY)
        self.assertIn(f"There are {len(CATALOG['families'])}.", GLOSSARY)
        self.assertIn(f"{owing} of the {len(CATALOG['roles'])} roles deliver one or more", GLOSSARY)

    def test_its_formats_match_the_catalog(self):
        for fmt, families in (("Word memo", "legal, research, audit, HR, insurance and financial crime"),
                              ("Excel workbook", "finance, accounting and data"),
                              ("PowerPoint deck", "consulting, content, sales and software")):
            self.assertIn(f"{fmt} for {families}", GLOSSARY)
        counts = {}
        for fam_format in formats.FAMILY_FORMAT.values():
            counts[fam_format] = counts.get(fam_format, 0) + 1
        self.assertEqual(sorted(counts.values()), [3, 4, 6])

    def test_its_own_links_are_served(self):
        for href in re.findall(r'href="(/[^"]*)"', GLOSSARY):
            path = urlsplit(href).path
            with self.subTest(href=href):
                if path in API_PATHS:
                    continue
                self.assertTrue((SITE / ("index.html" if path == "/" else path.lstrip("/"))).is_file(), href)

    def test_it_is_listed_for_machines(self):
        files = build_site_machine.generated_files()
        self.assertIn("/glossary.html", files["llms.txt"])
        self.assertIn("https://analystos.dev/glossary.html", files["sitemap.xml"])


if __name__ == "__main__":
    unittest.main()
