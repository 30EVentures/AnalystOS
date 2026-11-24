"""Slice 122 - the short homepage (mock A) stays true: its counts match the catalog, its
slide preview shows the sample deck's verified figures, the sample deck is current, every
link it carries is served, and it says no price has been set."""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from analystos.catalog import load_catalog
from analystos.l4 import deck, formats
from analystos.packs import work

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PAGE = (SITE / "index.html").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "tools"))
import build_samples  # noqa: E402

DOC, DECKS = build_samples.build()


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
        spec = DECKS["consulting.pptx"][0]
        figures = {f["id"]: f for f in spec["content"]["figures"]}
        preview = re.search(r'<div class="slide".*?</figure>', PAGE, re.S).group(0)
        for value, fid in re.findall(r'<span class="n">([^<]+)</span><span class="ref">(F\d+)</span>', preview):
            with self.subTest(fid=fid):
                self.assertEqual(value, deck.format_value(figures[fid]))
        self.assertGreaterEqual(len(re.findall(r'class="ref">F\d+', preview)), 4)
        self.assertIn(f"2 / {deck.slide_count(spec)}", preview)

    def test_the_samples_are_current(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_samples.py"), "--check"],
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


class RoleExplorerTest(unittest.TestCase):
    """The explorer shows one worked example per family, every number as its deck prints it."""

    def test_every_family_has_a_sample_deck(self):
        catalog = load_catalog()
        self.assertEqual([s["family"]["id"] for s in DOC["samples"]], [f["id"] for f in catalog["families"]])
        for sample in DOC["samples"]:
            with self.subTest(family=sample["family"]["id"]):
                self.assertTrue((SITE / sample["file"]).is_file())
                role = next(r for r in catalog["roles"] if r["id"] == sample["role"]["id"])
                self.assertEqual(sample["format"], formats.format_of(role)["name"])  # Slice 124: the role's own format
                self.assertTrue(sample["file"].endswith("." + formats.format_of(role)["extension"]))
                self.assertIn(build_samples.DELIVERS[sample["format"]], sample["delivers"])  # matches the download
                kinds = [s["kind"] for s in sample["slides"]]
                works = len(sample["slides"]) - 4
                self.assertEqual(kinds, ["summary", "finding", "recommendation"] + ["work"] * works + ["sources"])
                self.assertEqual(works, min(2, len(DECKS[sample["file"][len("samples/"):]][0]["content"].get("work", []))))

    def test_every_number_shown_is_the_verified_value(self):
        for sample in DOC["samples"] + list(DOC["roles"].values()):
            spec = DECKS[sample["file"][len("samples/"):]][0]
            figures = {f["id"]: f for f in spec["content"]["figures"]}
            shown = []

            def walk(node):
                if isinstance(node, dict):
                    if "v" in node and "ref" in node:
                        shown.append((node["v"], node["ref"]))
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)
            walk(sample["slides"])
            with self.subTest(file=sample["file"]):
                self.assertGreater(len(shown), 5)
                for value, ref in shown:
                    self.assertEqual(value, deck.format_value(figures[ref]), ref)

    def test_no_text_segment_carries_a_raw_tag_or_markup(self):
        text = json.dumps(DOC, ensure_ascii=False)
        self.assertNotRegex(text, r"\[F\d+\]")
        self.assertNotIn("<", text)

    def test_every_role_is_listed_once_in_its_own_family(self):
        catalog = load_catalog()
        roles = {r["id"]: r for r in catalog["roles"]}
        listed = []
        for sample in DOC["samples"]:
            family = sample["family"]["id"]
            ids = [r["id"] for r in sample["roles"]]
            listed += ids
            with self.subTest(family=family):
                self.assertEqual(ids[0], sample["role"]["id"])  # the family example's role first
                self.assertEqual(sorted(ids), sorted(r for r, v in roles.items() if v["family"] == family))
        self.assertEqual(sorted(listed), sorted(roles))


class RoleSamplesTest(unittest.TestCase):
    """Slice 128: a role with its own worked example shows it; every other role says it shows its family's."""

    def test_own_sample_is_true_exactly_for_roles_with_an_example(self):
        family_roles = {s["role"]["id"] for s in DOC["samples"]}
        work_roles = {d.name for d in (ROOT / "fixtures" / "work").iterdir() if d.is_dir()}
        self.assertEqual(set(DOC["roles"]), work_roles)
        for sample in DOC["samples"]:
            for r in sample["roles"]:
                with self.subTest(role=r["id"]):
                    self.assertEqual(r["own_sample"], r["id"] in family_roles | work_roles)
        self.assertEqual(sum(r["own_sample"] for s in DOC["samples"] for r in s["roles"]), 73)  # Slice 129: every role

    def test_each_role_sample_is_its_own_file_in_its_own_format(self):
        catalog = {r["id"]: r for r in load_catalog()["roles"]}
        for role_id, sample in DOC["roles"].items():
            fmt = formats.format_of(catalog[role_id])
            with self.subTest(role=role_id):
                self.assertEqual(sample["role"]["id"], role_id)
                self.assertEqual(sample["file"], f"samples/roles/{role_id}.{fmt['extension']}")
                self.assertTrue((SITE / sample["file"]).is_file())
                self.assertEqual(sample["format"], fmt["name"])
                has_work = "work" in [s["kind"] for s in sample["slides"]]
                self.assertEqual(has_work, bool(work.required_kinds(catalog[role_id])))  # work pages only for roles that owe work

    def test_delivered_work_is_never_called_planned(self):
        for sample in DOC["samples"]:
            for r in sample["roles"]:
                planned = r["delivers"].split("Also planned:")[1] if "Also planned:" in r["delivers"] else ""
                for word in ("draft", "register", "case-file", "reconciliation", "plan,", "code"):
                    with self.subTest(role=r["id"], word=word):
                        self.assertNotIn(word, planned)
        clerk = next(r for s in DOC["samples"] for r in s["roles"] if r["id"] == "accounts-payable-receivable-clerk")
        self.assertIn("with its draft and reconciliation inside", clerk["delivers"])

    def test_the_page_says_when_a_role_is_shown_on_its_familys_example(self):
        self.assertIn("No sample of its own yet: this is the family", PAGE)
        self.assertIn("own[r.id] || fam", PAGE)
        self.assertIn("'Work by the ' + sample.role.title", PAGE)  # a borrowed work page is never "the role's own"

    def test_published_files_name_only_analystos(self):
        from docx import Document
        from openpyxl import load_workbook
        from pptx import Presentation
        for path in sorted((SITE / "samples").rglob("*")):
            if path.suffix == ".pptx":
                props = Presentation(str(path)).core_properties
                people = (props.author, props.last_modified_by)
            elif path.suffix == ".docx":
                props = Document(str(path)).core_properties
                people = (props.author, props.last_modified_by)
            elif path.suffix == ".xlsx":
                props = load_workbook(str(path)).properties
                people = (props.creator, props.lastModifiedBy)
            else:
                continue
            with self.subTest(file=path.name):
                self.assertEqual(people, ("AnalystOS", "AnalystOS"))

    def test_it_says_which_format_each_family_delivers(self):
        # Slice 124: the statement must match the catalog's formats, family by family.
        catalog = load_catalog()
        statement = re.search(r'<p class="today">(.*?)</p>', PAGE, re.S).group(1)
        names = {"memo": "Word memo", "workbook": "Excel workbook", "deck": "deck for"}
        for fmt, phrase in names.items():
            self.assertIn(phrase, statement)
        self.assertIn("Every role shows a worked example of its own.", PAGE)
        families = {f["id"] for f in catalog["families"]}
        self.assertEqual(set(formats.FAMILY_FORMAT), families)

    def test_the_page_never_parses_html_from_the_data(self):
        script = re.search(r"<script>(.*?)</script>", PAGE, re.S).group(1)
        for unsafe in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertNotIn(unsafe, script)
        self.assertIn("textContent", script)
        self.assertIn("encodeURIComponent(r.id)", script)
        self.assertIn("textContent = r.delivers", script)
        self.assertNotIn("a verified analysis deck", script)  # never hard-coded again


if __name__ == "__main__":
    unittest.main()
