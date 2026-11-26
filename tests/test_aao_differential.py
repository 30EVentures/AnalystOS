"""Slice 133 - AnalystOS's charter checker against FlashyOS's own public corpus."""

import copy
import hashlib
import json
import unittest

from analystos.aao.validate import errors, validate_charter
from tools.aao_differential import CORPUS_PATH, SNAPSHOT_SHA256, compare, main

CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


class DifferentialTest(unittest.TestCase):
    def test_the_snapshot_is_the_one_recorded(self):
        self.assertEqual(hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest(), SNAPSHOT_SHA256)

    def test_every_verdict_agrees_with_flashyos(self):
        rows = compare(CORPUS)
        self.assertEqual(len(rows), 13)
        self.assertEqual([r["id"] for r in rows if not r["agree"]], [])

    def test_an_empty_corpus_does_not_pass(self):
        self.assertEqual(main(["/nonexistent/corpus.json"]), 2)
        self.assertEqual(compare({"sets": []}), [])

    def test_the_two_question_rules_found_by_the_differential(self):
        base = CORPUS["sets"][0]["cases"][0]["input"]
        ungated = copy.deepcopy(base)
        for role in ungated["roles"]:
            role.pop("humanApprovalAtOrAbove", None)
        vague = copy.deepcopy(base)
        vague["roles"][0]["capabilities"] = ["administration"]
        for doc, code in ((ungated, "aao.approval.none_gated"), (vague, "aao.capability.vague")):
            self.assertIn(code, [p.code for p in errors(validate_charter(doc, questions=True))])
            # The schema-level check is unchanged: these are L2 questions, not schema errors.
            self.assertNotIn(code, [p.code for p in errors(validate_charter(doc))])

    def test_a_hyphenated_or_short_capability_is_not_vague(self):
        base = copy.deepcopy(CORPUS["sets"][0]["cases"][0]["input"])
        base["roles"][0]["capabilities"] = ["document-analysis", "reconcile"]
        self.assertNotIn("aao.capability.vague", [p.code for p in validate_charter(base, questions=True)])


if __name__ == "__main__":
    unittest.main()
