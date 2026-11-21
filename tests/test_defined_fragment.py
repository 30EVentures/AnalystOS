"""Slice 98 - the drafts/defined-analystos.json fragment, checked against a PROXY
validator for the documented (but unpublished, unverifiable) defined/1 rules. See
tools/defined_proxy_validator.py's module docstring for why this is a proxy, not a
conformance guarantee, and drafts/README.md for why the basis URLs do not resolve
yet - which this file checks for honestly rather than assuming away.
"""

import copy
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from tools.defined_proxy_validator import validate

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT_PATH = ROOT / "drafts" / "defined-analystos.json"
FRAGMENT = json.loads(FRAGMENT_PATH.read_text())


class LocationTest(unittest.TestCase):
    def test_not_under_the_served_site_directory(self):
        self.assertFalse(str(FRAGMENT_PATH).startswith(str(ROOT / "site")))


class RealFragmentTest(unittest.TestCase):
    def test_the_committed_fragment_passes_the_proxy_validator(self):
        self.assertEqual(validate(FRAGMENT), [])

    def test_exactly_three_owned_terms(self):
        terms = {e["term"] for e in FRAGMENT["entries"]}
        self.assertEqual(terms, {"Analyst agent", "Decision-grade output", "Deliverable acceptance criteria"})

    def test_every_entry_is_owned_by_analystos(self):
        for entry in FRAGMENT["entries"]:
            self.assertEqual(entry["authority"], "org/analystos")
        self.assertEqual(FRAGMENT["authority"], "org/analystos")

    def test_no_entry_id_is_duplicated(self):
        ids = [e["id"] for e in FRAGMENT["entries"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_deliverable_acceptance_criteria_links_decision_grade_rather_than_restating_it(self):
        entry = next(e for e in FRAGMENT["entries"] if e["term"] == "Deliverable acceptance criteria")
        self.assertIn("defined/analystos/decision-grade-output", entry.get("seeAlso", []))

    def test_the_basis_urls_do_not_resolve_yet_and_this_is_known(self):
        # The honest gap this fragment has not solved: the 18 Nov integration
        # document's own example of "the mistake not to repeat" was serving a
        # fragment whose basis pages 404. These pages do not exist in site/
        # today - checked by their absence, not by a live fetch (no network
        # access from this test). ROADMAP.md must say this is unresolved.
        for entry in FRAGMENT["entries"]:
            slug = entry["basis"].rsplit("/", 1)[-1]
            self.assertFalse(
                (ROOT / "site" / "defined" / f"{slug}.html").exists(),
                f"a page for {slug} now exists - update this test and drafts/README.md's gap note",
            )
        roadmap = (ROOT / "ROADMAP.md").read_text()
        self.assertIn("basis", roadmap.lower())


class ProxyValidatorRuleTest(unittest.TestCase):
    """Each documented rule, proven to actually fire - not merely asserted."""

    def _good_entry(self):
        return copy.deepcopy(next(e for e in FRAGMENT["entries"] if e["term"] == "Analyst agent"))

    def _wrap(self, entry):
        return {**copy.deepcopy(FRAGMENT), "entries": [entry]}

    def test_definition_too_short_fails(self):
        entry = self._good_entry()
        entry["definition"] = "Too short."
        problems = validate(self._wrap(entry))
        self.assertTrue(any("40-700" in p for p in problems), problems)

    def test_definition_too_long_fails(self):
        entry = self._good_entry()
        entry["definition"] = "x" * 701
        problems = validate(self._wrap(entry))
        self.assertTrue(any("40-700" in p for p in problems), problems)

    def test_definition_at_exactly_40_and_700_passes_that_rule(self):
        for length in (40, 700):
            entry = self._good_entry()
            entry["definition"] = "x" * length
            problems = validate(self._wrap(entry))
            self.assertFalse(any("40-700" in p for p in problems), (length, problems))

    def test_expires_not_exactly_365_days_after_asserted_fails(self):
        entry = self._good_entry()
        entry["asserted"] = "2026-01-01"
        entry["expires"] = "2027-06-01"  # not +365d
        problems = validate(self._wrap(entry))
        self.assertTrue(any("expiry-not-derived" in p for p in problems), problems)

    def test_expires_exactly_365_days_after_asserted_passes(self):
        entry = self._good_entry()
        entry["asserted"] = "2026-01-01"
        entry["expires"] = str(date(2026, 1, 1) + timedelta(days=365))
        problems = validate(self._wrap(entry))
        self.assertFalse(any("expiry-not-derived" in p for p in problems), problems)

    def test_non_https_basis_fails(self):
        entry = self._good_entry()
        entry["basis"] = "http://analystos.dev/defined/analyst-agent"
        problems = validate(self._wrap(entry))
        self.assertTrue(any("https" in p for p in problems), problems)

    def test_each_of_the_fourteen_forbidden_keys_is_caught_at_any_depth(self):
        forbidden = (
            "digest", "seal", "sealed", "hash", "signature", "signed", "merkle",
            "proof", "score", "rank", "ranking", "weight", "confidence", "authority_score",
        )
        for key in forbidden:
            with self.subTest(key=key):
                entry = self._good_entry()
                entry["nested"] = {"deep": {key: "anything"}}  # "at any depth"
                problems = validate(self._wrap(entry))
                self.assertTrue(any(key in p for p in problems), (key, problems))

    def test_a_clean_entry_has_no_forbidden_key_false_positive(self):
        problems = validate(self._wrap(self._good_entry()))
        self.assertEqual(problems, [])

    def test_a_citation_carrying_definition_text_is_refused_at_any_depth(self):
        forbidden = ("definition", "text", "body", "html", "description", "summary", "excerpt")
        for key in forbidden:
            with self.subTest(key=key):
                fragment = copy.deepcopy(FRAGMENT)
                fragment["citations"] = [{"id": "defined/flashyos/human-gate", "at": "https://x.dev/y", key: "nope"}]
                problems = validate(fragment)
                self.assertTrue(any("citation" in p and key in p for p in problems), (key, problems))

    def test_a_clean_citation_with_no_definition_text_passes(self):
        fragment = copy.deepcopy(FRAGMENT)
        fragment["citations"] = [{"id": "defined/flashyos/human-gate", "at": "https://x.dev/y", "asserted": "2026-11-21"}]
        problems = validate(fragment)
        self.assertEqual([p for p in problems if "citation" in p], [])

    def test_duplicate_entry_ids_are_caught(self):
        entry = self._good_entry()
        fragment = self._wrap(entry)
        fragment["entries"].append(copy.deepcopy(entry))
        problems = validate(fragment)
        self.assertTrue(any("duplicate" in p for p in problems), problems)

    def test_an_entry_whose_authority_differs_from_the_fragment_is_caught(self):
        entry = self._good_entry()
        entry["authority"] = "org/somebody-else"
        problems = validate(self._wrap(entry))
        self.assertTrue(any("differs from the fragment" in p for p in problems), problems)

    def test_never_raises_on_a_hostile_fragment(self):
        for hostile in (None, {}, [], "not a fragment", 5, {"entries": "not a list"}, {"entries": [None, 5, "x"]}):
            with self.subTest(hostile=repr(hostile)[:40]):
                problems = validate(hostile)
                self.assertIsInstance(problems, list)


if __name__ == "__main__":
    unittest.main()
