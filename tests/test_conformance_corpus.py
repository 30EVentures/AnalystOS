"""Slice 87 - the refusal-first conformance corpus for the seal and audit-log verifiers
(``conformance/seal-1.json``), its line-protocol adapter and the in-process runner."""

import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

from analystos import conformance

ROOT = Path(__file__).resolve().parents[1]


def report(**over):
    base = {"total": 50, "agreed": 50, "disagreed": 0, "unanswered": 0, "unreadable": 0,
            "bad": {}, "gaps": {}, "refusal_share": 0.8, "stderr": ""}
    base.update(over)
    return base


class CorpusShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = conformance.load_corpus()
        cls.cases = conformance.corpus_cases(cls.corpus)

    def test_it_is_big_enough_and_refusal_first(self):
        self.assertGreaterEqual(len(self.cases), 45)
        refusals = [c for c in self.cases if not c["expect"]["valid"]]
        self.assertGreaterEqual(len(refusals) / len(self.cases), 0.6)

    def test_ids_are_unique_and_every_case_has_the_documented_fields(self):
        ids = [c["id"] for c in self.cases]
        self.assertEqual(len(ids), len(set(ids)))
        for case in self.cases:
            self.assertEqual(set(case) - {"known_gap"}, {"id", "set", "input", "expect", "note"}, case["id"])
            self.assertIn("valid", case["expect"])
            self.assertTrue(case["id"].startswith(case["set"] + "/"), case["id"])

    def test_the_brief_is_covered(self):
        ids = {c["id"].split("/", 1)[1] for c in self.cases}
        for wanted in ("signed-valid-pinned", "unsigned-valid", "legacy-no-accountability-fields", "tampered-fact-value",
                       "tampered-root", "swapped-signature", "signature-by-another-key", "wrong-pinned-key",
                       "duplicate-entry-keys", "deleted-middle-entry", "reordered-entries", "inserted-forged-entry",
                       "tail-dropped-with-a-pinned-head", "signature-stripped", "legacy-only-log", "empty-log"):
            self.assertIn(wanted, ids)

    def test_the_corpus_file_is_current(self):
        done = subprocess.run([sys.executable, "tools/build_conformance_corpus.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_the_corpus_is_strict_json(self):
        # NaN/Infinity literals would make it unreadable to a strict parser in another language.
        text = (ROOT / "conformance" / "seal-1.json").read_text(encoding="utf-8")
        json.loads(text, parse_constant=lambda name: self.fail(f"non-JSON constant {name}"))


class RunnerTest(unittest.TestCase):
    def test_the_verifiers_agree_with_the_whole_corpus(self):
        outcome = conformance.run_corpus()
        self.assertEqual(conformance.problems(outcome), [], outcome["stderr"][-1500:])
        self.assertGreater(outcome["agreed"], 0)

    def test_known_gaps_stay_strict_and_are_few(self):
        outcome = conformance.run_corpus()
        for case_id in outcome["gaps"]:
            self.assertIn(case_id, outcome["bad"], f"{case_id} now agrees; remove it from KNOWN_GAPS")


class RunnerRefusesToCallAnythingGoodTest(unittest.TestCase):
    def test_zero_executed_cases_is_a_failure(self):
        outcome = conformance.run_corpus({"sets": [{"name": "seal", "kind": "validate", "cases": []}]})
        self.assertEqual(outcome["total"], 0)
        self.assertTrue(any("zero cases" in p for p in conformance.problems(outcome)))

    def test_unanswered_unreadable_and_disagreed_each_fail(self):
        for state in ("unanswered", "unreadable", "disagreed"):
            found = conformance.problems(report(bad={"seal/x": state}))
            self.assertTrue(any(state in p for p in found), state)

    def test_a_low_refusal_share_fails(self):
        self.assertTrue(any("refusals" in p for p in conformance.problems(report(refusal_share=0.59))))
        self.assertEqual(conformance.problems(report(refusal_share=0.6)), [])

    def test_a_known_gap_that_now_agrees_must_be_unannotated(self):
        self.assertTrue(any("now agrees" in p for p in conformance.problems(report(gaps={"seal/x": "was broken"}))))

    def test_an_unknown_set_is_unanswered_not_guessed(self):
        corpus = {"sets": [{"name": "no-such-set", "kind": "validate", "cases": [
            {"id": "no-such-set/a", "input": {}, "expect": {"valid": False}, "note": ""}]}]}
        outcome = conformance.run_corpus(corpus)
        self.assertEqual((outcome["total"], outcome["unanswered"]), (1, 1))
        self.assertTrue(conformance.problems(outcome))

    def test_judge_follows_the_kit_rules(self):
        self.assertEqual(conformance.judge({"valid": False}, None), "unanswered")
        self.assertEqual(conformance.judge({"valid": False}, {"valid": "no"}), "unreadable")
        self.assertEqual(conformance.judge({"valid": False}, {"valid": True}), "disagreed")
        self.assertEqual(conformance.judge({"valid": False, "codes": ["a"]}, {"valid": False, "codes": ["b"]}), "disagreed")
        self.assertEqual(conformance.judge({"valid": False, "codes": ["a"]}, {"valid": False, "codes": ["a", "b"]}), "agreed")
        self.assertEqual(conformance.judge({"valid": True}, {"valid": True}), "agreed")


class AdapterTest(unittest.TestCase):
    def test_speaks_the_line_protocol_and_ignores_noise(self):
        case = next(c for c in conformance.corpus_cases(conformance.load_corpus()) if c["id"] == "seal/unsigned-valid")
        out, err = io.StringIO(), io.StringIO()
        conformance.serve(["", "not json\n", "[1]\n", json.dumps({"no_id": 1}) + "\n",
                           json.dumps({"id": case["id"], "set": case["set"], "input": case["input"]}) + "\n"], out, err)
        lines = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(lines, [{"id": "seal/unsigned-valid", "valid": True, "codes": []}])

    def test_a_crash_leaves_the_case_unanswered_and_the_stream_alive(self):
        out, err = io.StringIO(), io.StringIO()
        conformance.serve([json.dumps({"id": "a", "set": "seal", "input": {}}) + "\n",   # no "bundle": KeyError
                           json.dumps({"id": "b", "set": "audit", "input": {"lines": []}}) + "\n"], out, err)
        answers = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual([a["id"] for a in answers], ["b"])
        self.assertIn("crashed", err.getvalue())

    def test_runs_as_a_module_over_stdin(self):
        line = json.dumps({"id": "x", "set": "audit", "input": {"lines": []}}) + "\n"
        done = subprocess.run([sys.executable, "-m", "analystos.conformance"], cwd=ROOT, input=line, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"id": "x", "valid": False, "codes": ["chain"]})


if __name__ == "__main__":
    unittest.main()
