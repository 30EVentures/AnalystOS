"""Slice 106 - cleaning the served devlog/1 projection after a real emit.
See tools/redact_served_devlog.py's own module docstring for why this exists:
the vendored shiplog tool faithfully reproduces real git history, including
things found live 2026-11-22 that must never be public - the owner's personal
GitHub username baked into old merge-commit titles, and this session's own
commit trailers riding along inside the free-text detail field.
"""

import unittest

from tools.redact_served_devlog import clean


class CleanTest(unittest.TestCase):
    def test_an_entry_naming_the_owner_personally_is_dropped(self):
        doc = {"entries": [
            {"id": "a", "title": "Merge pull request #66 from CalebSolway/site-new-homepage", "detail": "fine"},
            {"id": "b", "title": "Unrelated feature", "detail": "fine"},
        ]}
        out = clean(doc)
        self.assertEqual([e["id"] for e in out["entries"]], ["b"])

    def test_the_match_is_case_insensitive_and_checks_every_field(self):
        doc = {"entries": [
            {"id": "a", "title": "fine", "detail": "Reviewed by solway personally"},
        ]}
        self.assertEqual(clean(doc)["entries"], [])

    def test_a_commit_trailer_is_stripped_not_the_whole_entry(self):
        doc = {"entries": [{
            "id": "a", "title": "Add a feature",
            "detail": "The real, human-written summary.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_abc123",
        }]}
        out = clean(doc)
        self.assertEqual(len(out["entries"]), 1)
        self.assertEqual(out["entries"][0]["detail"], "The real, human-written summary.")
        self.assertNotIn("noreply@anthropic.com", out["entries"][0]["detail"])

    def test_a_standalone_claude_session_trailer_with_no_co_authored_by_is_also_stripped(self):
        doc = {"entries": [{"id": "a", "title": "x", "detail": "Real text.\nClaude-Session: https://claude.ai/code/session_abc123"}]}
        self.assertEqual(clean(doc)["entries"][0]["detail"], "Real text.")

    def test_an_entry_with_neither_problem_is_unchanged(self):
        doc = {"entries": [{"id": "a", "title": "Add a feature", "detail": "Plain description, nothing to strip."}]}
        self.assertEqual(clean(doc), doc)

    def test_an_already_clean_document_is_identical_so_check_mode_exits_zero(self):
        doc = {"entries": [{"id": "a", "title": "x", "detail": "y"}]}
        self.assertEqual(clean(doc), doc)

    def test_other_top_level_keys_are_preserved(self):
        doc = {"shipped": "1", "org": "org/analystos", "entries": []}
        self.assertEqual(clean(doc), doc)


if __name__ == "__main__":
    unittest.main()
