"""Slice 65 - the spec index is truthful and nothing cites a spec that does not
exist. See specs/slice-65/spec.md."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs"
INDEX = (SPECS / "README.md").read_text(encoding="utf-8")
EXISTING = {int(p.parent.name.split("-")[1]) for p in SPECS.glob("slice-*/spec.md")}
ROWS = {int(m.group(1)): m.group(0) for m in re.finditer(r"^\| (\d+) \|.*$", INDEX, re.MULTILINE)}


class IndexTest(unittest.TestCase):
    def test_every_existing_spec_is_indexed_and_linked(self):
        for n in sorted(EXISTING):
            with self.subTest(slice=n):
                self.assertIn(n, ROWS)
                self.assertIn(f"(slice-{n}/spec.md)", ROWS[n])

    def test_every_number_up_to_the_highest_is_a_spec_or_a_marked_gap(self):
        for n in range(1, max(EXISTING) + 1):
            with self.subTest(slice=n):
                self.assertIn(n, ROWS, f"slice {n} is neither indexed as a spec nor marked as a gap")
                if n not in EXISTING:
                    self.assertNotIn("](slice-", ROWS[n], f"slice {n} links a spec that does not exist")
                    self.assertTrue(re.search(r"\bnone\b|no slice", ROWS[n]), f"gap {n} does not say so")

    def test_the_known_gaps_are_the_ones_the_docs_name(self):
        gaps = sorted(set(range(1, max(EXISTING) + 1)) - EXISTING)
        self.assertEqual(gaps, [14, 35, 36, 37, 38, 39])


class GeneratorTest(unittest.TestCase):
    def test_the_index_is_what_the_tool_generates(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import build_specs_index
        self.assertEqual(build_specs_index.build(), INDEX, "run: python3 tools/build_specs_index.py")

    def test_an_unlisted_gap_would_be_visible(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import build_specs_index
        self.assertEqual(sorted(build_specs_index.GAPS), [14, 35, 36, 37, 38, 39])


class NoDanglingCitationsTest(unittest.TestCase):
    def test_no_source_test_or_doc_cites_a_missing_spec(self):
        pattern = re.compile(r"specs/slice-(\d+)/spec\.md")
        skip = {"specs/README.md", "docs/audit-2026-09-25.md", "docs/flashyos-alignment-2026-09-25.md"}
        offenders = []
        for base in ("analystos", "api", "tests", "tools", "live_tests", "docs", "ROADMAP.md", "README.md", "CLAUDE.md"):
            path = ROOT / base
            files = [path] if path.is_file() else [p for p in path.rglob("*") if p.suffix in (".py", ".md")]
            for f in files:
                rel = str(f.relative_to(ROOT))
                if rel in skip or "__pycache__" in rel or rel == "tests/test_specs_index.py":
                    continue
                for m in pattern.finditer(f.read_text(encoding="utf-8", errors="replace")):
                    if int(m.group(1)) not in EXISTING:
                        offenders.append(f"{rel} cites slice {m.group(1)}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
