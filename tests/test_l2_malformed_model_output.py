"""Overnight round 3 - what the model sends back is untrusted input.

The numbers a model proposes are re-verified in code, and anything that fails is dropped.
That held for *wrong values* but not for *wrong shapes*: one segment that was a string, a
``text`` that was a number, an ``operands`` entry that was not an object, or a narrative
paragraph that was ``null`` made ``analyze_document`` / ``write_narrative`` raise
AttributeError / TypeError / KeyError out of the pipeline (an HTTP 500, or a job stuck
``running``) instead of dropping the one bad item. A document that carries an injected
instruction is exactly the input that could push a model into odd output shapes.

The model is mocked throughout: no network, no cost.
"""

import contextlib
import copy
import io
import unittest
from types import SimpleNamespace

from analystos.l2.analyze import analyze_document
from analystos.l2.narrate import write_narrative
from analystos.l2.proofread import proofread_report
from tests.test_l2_narrate import SEGMENTS as NARRATE_SEGMENTS, TITLE as NARRATE_TITLE, _report

DOC = "Revenue was $498.0 million in FY2026. Net income was $19.6 million. The deal closes in March."
GOOD = {"type": "quote", "display": "stat", "label": "Revenue", "exact_text": "$498.0 million", "has_value": True,
        "value": 498000000.0, "sentence": "{value} was reported.", "format": "usd"}
OPERAND = {"exact_text": "$498.0 million", "value": 498000000.0}

MALFORMED_SEGMENTS = {
    "string": "not an object", "integer": 5, "null": None, "list": [1],
    "quote exact_text is a number": {"type": "quote", "exact_text": 5},
    "quote exact_text is a list": {"type": "quote", "exact_text": ["a"]},
    "quote value is a string": {"type": "quote", "exact_text": "$498.0 million", "has_value": True, "value": "x",
                                "sentence": "{value}"},
    "quote sentence is a number": {"type": "quote", "exact_text": "$498.0 million", "has_value": True,
                                   "value": 498000000.0, "sentence": 5},
    "prose text is a number": {"type": "prose", "text": 5},
    "prose text is a list": {"type": "prose", "text": ["a"]},
    "computed operand is a string": {"type": "computed", "operation": "sum", "operands": ["x"], "sentence": "{value}"},
    "computed operands is a number": {"type": "computed", "operation": "sum", "operands": 5, "sentence": "{value}"},
    "computed operand text is a number": {"type": "computed", "operation": "sum",
                                          "operands": [{"exact_text": 5, "value": 1}], "sentence": "{value}"},
    "computed sentence is a number": {"type": "computed", "operation": "sum", "operands": [OPERAND], "sentence": 7},
    "event is a string": {"type": "event", "event": "closes"},
    "event what is a number": {"type": "event", "event": {"what": 5}},
    "event milestones is a string": {"type": "event", "event": {"what": "The deal closes in March", "milestones": "x"}},
    "event milestone is a number": {"type": "event", "event": {"what": "The deal closes in March", "milestones": [5]}},
    "type is a list": {"type": ["quote"]},
    "type is an object": {"type": {"a": 1}},
}


def client_returning(tool_input):
    block = SimpleNamespace(type="tool_use", input=tool_input)
    response = SimpleNamespace(content=[block], stop_reason="end_turn")
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


@contextlib.contextmanager
def quiet():
    with contextlib.redirect_stderr(io.StringIO()):
        yield


class MalformedSegmentTest(unittest.TestCase):
    def test_one_malformed_segment_is_dropped_and_the_good_one_survives(self):
        for name, bad in MALFORMED_SEGMENTS.items():
            with self.subTest(case=name):
                stats = {}
                with quiet():
                    verified = analyze_document(DOC, "T", client=client_returning({"segments": [GOOD, bad]}), stats=stats)
                self.assertEqual([s["label"] for s in verified], ["Revenue"])
                self.assertEqual((stats["proposed"], stats["verified"], stats["dropped"]), (2, 1, 1))

    def test_a_segments_value_that_is_not_a_list_is_an_empty_report_not_a_crash(self):
        for value in ({"a": 1}, "text", 5, True):
            with self.subTest(segments=value), quiet():
                with self.assertRaises(ValueError):
                    analyze_document(DOC, "T", client=client_returning({"segments": value}))


class MalformedNarrativeTest(unittest.TestCase):
    VALUES = [None, 0, True, "", 5.5, "é", [], {}, ["x"], {"a": 1}, [None], [[]], {"text": 5}]

    @staticmethod
    def positions(node, prefix=()):
        yield prefix
        if isinstance(node, dict):
            for key, value in node.items():
                yield from MalformedNarrativeTest.positions(value, prefix + (key,))
        elif isinstance(node, list):
            for i, value in enumerate(node):
                yield from MalformedNarrativeTest.positions(value, prefix + (i,))

    def test_the_baseline_report_is_accepted(self):
        with quiet():
            report = write_narrative(NARRATIVE_SEGMENTS(), NARRATE_TITLE, client=client_returning(_report()))
        self.assertTrue(report["sections"])

    def test_a_wrongly_shaped_narrative_is_a_valueerror_or_a_valid_report_never_another_exception(self):
        base = _report()
        failures = []
        for path in self.positions(base):
            if not path:
                continue
            for value in self.VALUES:
                mutated = copy.deepcopy(base)
                target = mutated
                for step in path[:-1]:
                    target = target[step]
                target[path[-1]] = value
                try:
                    with quiet():
                        write_narrative(NARRATIVE_SEGMENTS(), NARRATE_TITLE, client=client_returning(mutated))
                except ValueError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{'.'.join(map(str, path))} = {value!r}: {type(exc).__name__}")
        self.assertEqual(failures, [])


class ProofreadGateTest(unittest.TestCase):
    """Gate 2 decides whether a report ships. ``bool("false")`` is True, so a verdict that
    arrived as the string "false" (or 0-ish text, or a list) used to pass the gate."""

    REPORT = {"executive_summary": [{"text": "Revenue reached {{0}}."}], "sections": []}

    def verdict(self, passed, issues=()):
        with quiet():
            return proofread_report(copy.deepcopy(self.REPORT), client=client_returning({
                "passed": passed, "has_filler": False, "has_synthesized_insight": True,
                "disclosure_gaps_clear": True, "issues": list(issues)}))

    def test_only_the_boolean_true_passes_the_gate(self):
        self.assertEqual(self.verdict(True), (True, []))
        for not_a_pass in ("false", "no", "true", "True", 1, 0, None, [], ["x"], {"a": 1}):
            with self.subTest(passed=not_a_pass):
                ok, _issues = self.verdict(not_a_pass)
                self.assertFalse(ok)

    def test_a_listed_issue_still_fails_a_true_verdict(self):
        ok, issues = self.verdict(True, [{"location": "Revenue", "problem": "filler"}])
        self.assertFalse(ok)
        self.assertEqual(len(issues), 1)


def NARRATIVE_SEGMENTS():
    return copy.deepcopy(NARRATE_SEGMENTS)


if __name__ == "__main__":
    unittest.main()
