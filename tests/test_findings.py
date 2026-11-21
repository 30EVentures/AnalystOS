"""Slice 101 - the findings-register schema, validator and generator. Tested
with synthetic fixtures here, not with real finding content - the one entry
in findings/registry.json is a template, and this file must not be used as a
place to invent plausible-sounding security findings. See findings/README.md.
"""

import copy
import json
import unittest
from pathlib import Path

from findings.build_findings import build
from findings.validate import validate_entry, validate_registry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "findings" / "registry.json"
PAGES_DIR = ROOT / "findings" / "pages"

GOOD = {
    "id": "F-01",
    "title": "A test fixture for the schema, not a real finding",
    "discovered": "2026-01-01",
    "published": None,
    "status": "open",
    "severity": "Medium",
    "affected": {"package": "@example/package", "version": "1.0.0"},
    "summary": "x" * 40,
    "reproducer_exists": False,
    "fix_commit_url": None,
}


class RegistryContentTest(unittest.TestCase):
    """The real, committed registry.json - only the template is allowed."""

    def test_registry_validates(self):
        registry = json.loads(REGISTRY_PATH.read_text())
        self.assertEqual(validate_registry(registry), {})

    def test_every_committed_entry_is_a_template_not_a_real_finding(self):
        # This is the guardrail: a real finding being added should flip this
        # test, which is the point - it forces whoever adds one to read
        # findings/README.md's publishing section rather than slipping one
        # in silently.
        registry = json.loads(REGISTRY_PATH.read_text())
        for entry in registry:
            self.assertEqual(entry["status"], "template", f"{entry['id']} is not a template - see findings/README.md")

    def test_no_entry_claims_a_reproducer_it_does_not_hold(self):
        registry = json.loads(REGISTRY_PATH.read_text())
        for entry in registry:
            if entry["status"] == "template":
                self.assertFalse(entry["reproducer_exists"])


class ValidateEntryTest(unittest.TestCase):
    def test_a_well_formed_entry_passes(self):
        self.assertEqual(validate_entry(GOOD), [])

    def test_bad_id_shape_fails(self):
        entry = {**GOOD, "id": "FINDING-1"}
        self.assertTrue(any("id" in p for p in validate_entry(entry)))

    def test_missing_required_key_fails(self):
        entry = {k: v for k, v in GOOD.items() if k != "severity"}
        self.assertTrue(any("severity" in p for p in validate_entry(entry)))

    def test_unknown_key_fails(self):
        entry = {**GOOD, "exploit_payload": "nope"}
        self.assertTrue(any("unknown" in p for p in validate_entry(entry)))

    def test_summary_too_short_fails(self):
        entry = {**GOOD, "summary": "too short"}
        self.assertTrue(any("summary" in p for p in validate_entry(entry)))

    def test_bad_status_fails(self):
        entry = {**GOOD, "status": "probably-fine"}
        self.assertTrue(any("status" in p for p in validate_entry(entry)))

    def test_fixed_status_without_a_fix_url_fails(self):
        entry = {**GOOD, "status": "fixed", "fix_commit_url": None}
        self.assertTrue(any("fix_commit_url" in p for p in validate_entry(entry)))

    def test_fixed_status_with_a_fix_url_passes(self):
        entry = {**GOOD, "status": "fixed", "fix_commit_url": "https://github.com/example/example/pull/1"}
        self.assertEqual(validate_entry(entry), [])

    def test_fix_url_must_be_https(self):
        entry = {**GOOD, "status": "fixed", "fix_commit_url": "http://example.com/pr/1"}
        self.assertTrue(any("https" in p for p in validate_entry(entry)))

    def test_published_before_discovered_fails(self):
        entry = {**GOOD, "discovered": "2026-06-01", "published": "2026-01-01"}
        self.assertTrue(any("before" in p for p in validate_entry(entry)))

    def test_affected_with_extra_key_fails(self):
        entry = {**GOOD, "affected": {"package": "x", "version": "1", "extra": "nope"}}
        self.assertTrue(any("affected" in p for p in validate_entry(entry)))

    def test_never_raises_on_a_hostile_entry(self):
        for hostile in (None, [], "x", 5, {}, {"id": None}):
            with self.subTest(hostile=repr(hostile)[:30]):
                problems = validate_entry(hostile)
                self.assertIsInstance(problems, list)
                self.assertTrue(problems)


class ValidateRegistryTest(unittest.TestCase):
    def test_duplicate_ids_are_caught(self):
        registry = [GOOD, copy.deepcopy(GOOD)]
        problems = validate_registry(registry)
        self.assertTrue(any("duplicate" in str(p) for p in problems.get("<registry>", [])))

    def test_a_clean_registry_has_no_problems(self):
        self.assertEqual(validate_registry([GOOD]), {})

    def test_never_raises_on_a_hostile_registry(self):
        for hostile in (None, "x", 5, {}):
            with self.subTest(hostile=repr(hostile)[:30]):
                result = validate_registry(hostile)
                self.assertIsInstance(result, dict)


class BuildFindingsTest(unittest.TestCase):
    def test_the_real_registry_builds_without_raising(self):
        files = build()
        self.assertIn("index.md", files)
        self.assertIn("F-00.md", files)

    def test_pages_committed_on_disk_match_what_build_computes_now(self):
        computed = build()
        for name, content in computed.items():
            on_disk = (PAGES_DIR / name).read_text()
            self.assertEqual(on_disk, content, name)

    def test_markdown_table_cells_neutralise_pipes_and_newlines(self):
        from findings.build_findings import _cell

        self.assertEqual(_cell("a | b"), "a \\| b")
        self.assertEqual(_cell("a\nb"), "a b")

    def test_a_page_never_html_escapes_markdown_content(self):
        # Caught in review: an earlier draft of this generator ran titles and
        # summaries through html.escape(), which is correct for HTML output
        # and wrong for Markdown - it left literal "&lt;" in the rendered
        # page instead of "<". Pinned here so it cannot silently return.
        files = build()
        self.assertIn("<one-line description", files["F-00.md"])
        self.assertNotIn("&lt;", files["F-00.md"])


if __name__ == "__main__":
    unittest.main()
