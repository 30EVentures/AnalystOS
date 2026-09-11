"""Tests for L2 Gate 2 - analystos.l2.proofread. Uses a mocked Anthropic
client throughout: no real API call, no cost, no network dependency.

Gate 2 is deliberately blind to facts - it only ever sees prose text, never
segments or citations - so these tests exercise exactly that surface: does
_report_text() correctly pull every piece of reader-facing prose out of a
structured report, and does proofread_report() correctly turn the model's
tool response into (passed, issues)? Whether a *real* model actually
notices a given language problem is unverifiable without the API, the same
caveat as every other model-facing test in this codebase.
"""

import contextlib
import io
import unittest
from types import SimpleNamespace

import anthropic
import httpx2

from analystos.l2.proofread import _TOOL, _report_text, proofread_report

REPORT = {
    "executive_summary": [{"text": "Revenue reached {{0}}."}],
    "executive_insight": "Read together, {{0}} and {{1}} tell one story.",
    "sections": [{
        "heading": "Revenue",
        "paragraphs": [{"text": "Revenue was {{0}} against {{1}} a year earlier."}],
    }],
    "disclosure_gaps": [{"text": "EPS is not disclosed."}],
    "outlook": [{"text": "Guidance was reiterated."}],
    "outlook_interpretation": "That reiteration is itself a signal.",
}


def _fake_client(passed, issues=None, **rubric):
    tool_use = SimpleNamespace(
        type="tool_use", input={"passed": passed, "issues": issues or [], **rubric}
    )
    response = SimpleNamespace(content=[tool_use])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


class RubricSchemaTest(unittest.TestCase):  # Slice 49
    """The tool schema itself carries the three new structured fields
    (has_filler, has_synthesized_insight, disclosure_gaps_clear) - so a
    specific criterion's outcome is directly inspectable, not inferred by
    string-matching "problem" text."""

    def test_the_tool_schema_requires_all_three_new_fields(self):
        props = _TOOL["input_schema"]["properties"]
        for field in ("has_filler", "has_synthesized_insight", "disclosure_gaps_clear"):
            self.assertIn(field, props)
            self.assertEqual(props[field]["type"], "boolean")
        for field in ("has_filler", "has_synthesized_insight", "disclosure_gaps_clear"):
            self.assertIn(field, _TOOL["input_schema"]["required"])

    def test_the_rubric_fields_are_logged_for_auditability(self):
        client = _fake_client(
            True, [], has_filler=False, has_synthesized_insight=True, disclosure_gaps_clear=True,
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            proofread_report(REPORT, client=client)
        logged = buf.getvalue()
        self.assertIn("has_filler=False", logged)
        self.assertIn("has_synthesized_insight=True", logged)
        self.assertIn("disclosure_gaps_clear=True", logged)

    def test_passed_stays_the_single_source_of_truth_not_gated_on_the_rubric_fields(self):
        # a model response that says passed=True with no issues, but also
        # flags has_filler=True, must still ship - the three fields are
        # for auditability, never a second, competing pass/fail signal
        # (an inconsistency like this would itself indicate a confused
        # response worth logging, not a reason to override "passed").
        client = _fake_client(
            True, [], has_filler=True, has_synthesized_insight=False, disclosure_gaps_clear=False,
        )
        ok, issues = proofread_report(REPORT, client=client)
        self.assertTrue(ok)
        self.assertEqual(issues, [])


class ReportTextExtractionTest(unittest.TestCase):
    """Gate 2 only ever sees this - if a piece of prose is missing here,
    Gate 2 can never review it, no matter how good the model is."""

    def test_every_prose_element_is_included(self):
        text = _report_text(REPORT)
        self.assertIn("Revenue reached {{0}}.", text)
        self.assertIn("Read together, {{0}} and {{1}} tell one story.", text)
        self.assertIn("Revenue", text)  # section heading
        self.assertIn("Revenue was {{0}} against {{1}} a year earlier.", text)
        self.assertIn("EPS is not disclosed.", text)
        self.assertIn("Guidance was reiterated.", text)
        self.assertIn("That reiteration is itself a signal.", text)

    def test_a_report_with_no_optional_fields_still_extracts_the_required_ones(self):
        minimal = {"executive_summary": [{"text": "X."}], "sections": [
            {"heading": "H", "paragraphs": [{"text": "Y."}]}
        ]}
        text = _report_text(minimal)
        self.assertIn("X.", text)
        self.assertIn("Y.", text)

    def test_an_empty_report_produces_empty_text(self):
        self.assertEqual(_report_text({}), "")


class ProofreadReportTest(unittest.TestCase):
    def test_a_clean_report_passes(self):
        ok, issues = proofread_report(REPORT, client=_fake_client(True, []))
        self.assertTrue(ok)
        self.assertEqual(issues, [])

    def test_a_flagged_report_fails_with_its_issues_returned(self):
        problems = [{"location": "the buyback sentence", "problem": "appears three times, duplicated"}]
        ok, issues = proofread_report(REPORT, client=_fake_client(False, problems))
        self.assertFalse(ok)
        self.assertEqual(issues, problems)

    def test_duplicated_text_independently_fails_gate_2(self):
        # simulates the live Bug 2 symptom (the same sentence appearing
        # three times) - confirms the wiring: a model response flagging
        # duplication is correctly surfaced as a Gate 2 failure, the "catch
        # it from a different angle, blind to the facts" requirement.
        duplicated = {
            "executive_summary": [{"text": "The board authorized a buyback. The board authorized a buyback."}],
            "sections": [{"heading": "Capital", "paragraphs": [
                {"text": "The board authorized a buyback, mentioned again here."}
            ]}],
        }
        client = _fake_client(False, [
            {"location": "The board authorized a buyback.",
             "problem": "this sentence is duplicated verbatim"}
        ])
        ok, issues = proofread_report(duplicated, client=client)
        self.assertFalse(ok)
        self.assertIn("duplicated", issues[0]["problem"])

    def test_passed_true_but_issues_nonempty_still_fails(self):
        # "passed" and "issues" could disagree in a malformed response -
        # any real issue listed means it did not pass, regardless
        ok, issues = proofread_report(
            REPORT, client=_fake_client(True, [{"location": "x", "problem": "y"}])
        )
        self.assertFalse(ok)

    def test_a_report_with_no_prose_at_all_trivially_passes_without_calling_the_model(self):
        calls = []
        client = SimpleNamespace(messages=SimpleNamespace(
            create=lambda **kwargs: calls.append(1) or _fake_client(True)
        ))
        ok, issues = proofread_report({}, client=client)
        self.assertTrue(ok)
        self.assertEqual(calls, [])

    def test_model_response_with_no_tool_use_fails_closed(self):
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text="oops")])
        client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
        ok, issues = proofread_report(REPORT, client=client)
        self.assertFalse(ok)
        self.assertTrue(issues)

    def test_an_anthropic_api_error_becomes_a_clean_valueerror(self):
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

        def _raise(**kwargs):
            raise anthropic.APIConnectionError(request=request)

        client = SimpleNamespace(messages=SimpleNamespace(create=_raise))
        with self.assertRaises(ValueError) as cm:
            proofread_report(REPORT, client=client)
        self.assertIn("temporarily unavailable", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
