"""Tests for L2 analyze_document's verification logic - one per "Done when"
in specs/slice-26/spec.md. Uses a mocked Anthropic client throughout: no
real API call, no cost, no network dependency, so this suite runs clean
with no ANTHROPIC_API_KEY at all.
"""

import io
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace

import anthropic
import httpx2

from analystos.l2.analyze import (
    _detect_scale,
    _match_key,
    _really_in_document,
    _value_matches_text,
    analyze_document,
    coverage_summary,
)

DOCUMENT = (
    'Q4 revenue was $10,000,000, up from $8,000,000 in Q3. '
    'The engineering team grew to 40 people this quarter.'
)
TITLE = "Q4 Review"


def _fake_client(segments):
    """A minimal stand-in for anthropic.Anthropic() - just enough surface
    for analyze_document to call .messages.create(...) and read back a
    tool_use block shaped like the real SDK's response.
    """
    tool_use_block = SimpleNamespace(type="tool_use", input={"segments": segments})
    response = SimpleNamespace(content=[tool_use_block])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


class AnalyzeDocumentTest(unittest.TestCase):
    def test_a_real_quote_is_verified_and_kept(self):  # Done when #2
        segments = [{
            "type": "quote", "display": "inline", "label": "Revenue",
            "exact_text": "$10,000,000", "has_value": True, "value": 10000000.0,
            "sentence": "Q4 revenue was {value}.", "format": "usd",
        }]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["value"], 10000000.0)
        self.assertEqual(out[0]["citation"], "$10,000,000")

    def test_a_quote_value_that_does_not_match_its_own_exact_text_is_rejected(self):
        # Found live, 2026-09-06: a real substring match on exact_text
        # alone proves the *text* is real - it says nothing about whether
        # the paired *value* is. "$10,000,000" really is in DOCUMENT, but
        # claiming its value is 500.0 (or anything else) must still fail.
        segments = [{
            "type": "quote", "display": "inline", "label": "Revenue",
            "exact_text": "$10,000,000", "has_value": True, "value": 500.0,
            "sentence": "Q4 revenue was {value}.", "format": "usd",
        }]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_a_computed_operand_with_a_silently_negated_value_is_rejected(self):
        # Found live, 2026-09-06: subtraction isn't one of the five
        # supported operations, so a model computing "net additions"
        # (1,240 - 1,050 = 190) faked it with operation "sum" and a
        # silently negated second operand (exact_text "1,050" paired with
        # value -1050.0) - the text is real, the paired number isn't what
        # it says. Landed on the true answer this time; the point is nothing
        # stops this same trick from landing on a false one.
        document = (
            'The company ended the quarter with 1,240 customers, up from '
            '1,050 at the start of the quarter.'
        )
        segments = [{
            "type": "computed", "display": "inline", "label": "Net additions",
            "operation": "sum",
            "operands": [
                {"exact_text": "1,240", "value": 1240.0},
                {"exact_text": "1,050", "value": -1050.0},  # real text, faked value
            ],
            "has_total": False, "total_exact_text": "", "total_value": 0,
            "result": 190.0,
            "sentence": "Net customer additions were {value}.",
            "format": "number",
        }]
        with self.assertRaises(ValueError):
            analyze_document(document, "Q3 Review", client=_fake_client(segments))

    def test_percent_of_total_value_that_does_not_match_its_exact_text_is_rejected(self):
        segments = [{
            "type": "computed", "display": "inline", "label": "Share",
            "operation": "percent_of_total",
            "operands": [{"exact_text": "$8,000,000", "value": 8000000.0}],
            "has_total": True, "total_exact_text": "$10,000,000", "total_value": 1.0,
            "result": 800000000.0,
            "sentence": "Q3 revenue was {value} of Q4's.",
            "format": "percent",
        }]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_a_quote_value_matching_an_abbreviated_million_figure_is_accepted(self):
        # A real document can spell a figure out as "$1.2 million" rather
        # than "$1,200,000" - the scale word must be honored, not treated
        # as a mismatch just because the digits alone don't match.
        document = "Q3 revenue was $1.2 million, the strongest quarter yet."
        segments = [{
            "type": "quote", "display": "inline", "label": "Revenue",
            "exact_text": "$1.2 million", "has_value": True, "value": 1200000.0,
            "sentence": "Revenue was {value}.", "format": "usd",
        }]
        out = analyze_document(document, "Q3 Review", client=_fake_client(segments))
        self.assertEqual(out[0]["value"], 1200000.0)

    def test_a_number_followed_by_a_word_starting_with_m_is_not_misread_as_millions(self):
        # Regression: the scale-word check must not fire just because the
        # next word happens to start with the same letter as "million" -
        # "142 members" is 142, not 142,000,000.
        document = "The club had 142 members at the end of the quarter."
        segments = [{
            "type": "quote", "display": "inline", "label": "Members",
            "exact_text": "142 members", "has_value": True, "value": 142.0,
            "sentence": "Membership reached {value}.", "format": "number",
        }]
        out = analyze_document(document, "Q3 Review", client=_fake_client(segments))
        self.assertEqual(out[0]["value"], 142.0)

    def test_a_fabricated_quote_not_in_the_document_is_rejected(self):  # Done when #3
        segments = [{
            "type": "quote", "display": "inline", "label": "Revenue",
            "exact_text": "$99,999,999", "value": 99999999.0,  # not in DOCUMENT
            "sentence": "Q4 revenue was {value}.", "format": "usd",
        }]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_correct_computed_math_is_verified_and_kept(self):
        segments = [{
            "type": "computed", "display": "inline", "label": "Growth",
            "operation": "growth_percent",
            "operands": [
                {"exact_text": "$8,000,000", "value": 8000000.0},
                {"exact_text": "$10,000,000", "value": 10000000.0},
            ],
            "result": 25.0,
            "sentence": "Revenue grew {value} quarter over quarter.",
            "format": "percent",
        }]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]["value"], 25.0)

    def test_fabricated_math_is_rejected_even_with_real_cited_numbers(self):  # Done when #3, the core guarantee
        segments = [{
            "type": "computed", "display": "inline", "label": "Growth",
            "operation": "growth_percent",
            "operands": [
                {"exact_text": "$8,000,000", "value": 8000000.0},  # both operands are
                {"exact_text": "$10,000,000", "value": 10000000.0},  # real, cited quotes...
            ],
            "result": 90.0,  # ...but the model's arithmetic (should be 25.0) is wrong
            "sentence": "Revenue grew {value} quarter over quarter.",
            "format": "percent",
        }]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_percent_of_total_with_has_total_true_and_a_real_quoted_total_is_kept(self):
        segments = [{
            "type": "computed", "display": "inline", "label": "Share",
            "operation": "percent_of_total",
            "operands": [{"exact_text": "$8,000,000", "value": 8000000.0}],
            "has_total": True, "total_exact_text": "$10,000,000", "total_value": 10000000.0,
            "result": 80.0,
            "sentence": "Q3 revenue was {value} of Q4's.",
            "format": "percent",
        }]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]["value"], 80.0)
        self.assertIn("$10,000,000", out[0]["citation"])

    def test_percent_of_total_with_has_total_false_is_rejected(self):
        # has_total is the explicit flag that replaced "was total_exact_text
        # given at all" - a percent_of_total claim that leaves it false
        # (even if total_exact_text/total_value happen to be filled with
        # placeholders) must not be treated as a real, cited total.
        segments = [{
            "type": "computed", "display": "inline", "label": "Share",
            "operation": "percent_of_total",
            "operands": [{"exact_text": "$10,000,000", "value": 10000000.0}],
            "has_total": False, "total_exact_text": "", "total_value": 0,
            "result": 50.0,
            "sentence": "Revenue was {value} of the total.",
            "format": "percent",
        }]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_computed_operand_not_actually_in_document_is_rejected(self):
        segments = [{
            "type": "computed", "display": "inline", "label": "Growth",
            "operation": "growth_percent",
            "operands": [
                {"exact_text": "$1,234,567", "value": 1234567.0},  # not in DOCUMENT
                {"exact_text": "$10,000,000", "value": 10000000.0},
            ],
            "result": 710.0,
            "sentence": "Revenue grew {value}.",
            "format": "percent",
        }]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_missing_placeholder_is_rejected(self):
        segments = [{
            "type": "quote", "display": "inline", "label": "Revenue",
            "exact_text": "$10,000,000", "has_value": True, "value": 10000000.0,
            "sentence": "Q4 revenue was strong.",  # no {value} placeholder
            "format": "usd",
        }]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_prose_with_a_stray_number_is_rejected(self):  # Done when #3
        segments = [{"type": "prose", "text": "Growth was roughly 45% this quarter."}]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_prose_with_a_calendar_reference_is_kept(self):
        # Found live, 2026-09-06: a real analyst's connective prose almost
        # always mentions a quarter or year - "heading into Q4 2026" isn't
        # a claim that needs a source quote the way a dollar figure does,
        # and banning it made ordinary writing fail near-universally.
        segments = [{"type": "prose", "text": "Momentum should continue into Q4 2026."}]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(out[0]["text"], "Momentum should continue into Q4 2026.")

    def test_prose_with_no_numbers_is_kept(self):
        segments = [
            {"type": "prose", "text": "Momentum continued into the following quarter."},
            {
                "type": "quote", "display": "inline", "label": "Revenue",
                "exact_text": "$10,000,000", "has_value": True, "value": 10000000.0,
                "sentence": "Revenue was {value}.", "format": "usd",
            },
        ]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["type"], "prose")

    def test_stat_display_qualitative_quote_with_no_value_is_kept(self):
        segments = [{
            "type": "quote", "display": "stat", "label": "Headcount",
            "exact_text": "40 people", "has_value": False,
        }]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "40 people")

    def test_all_segments_rejected_raises(self):  # Done when #6 (never a silent partial success)
        segments = [{"type": "quote", "exact_text": "not in the document at all"}]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_model_response_with_no_tool_use_raises(self):
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text="oops")])
        client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=client)

    def test_a_missing_api_key_becomes_a_clean_valueerror_not_a_raw_crash(self):
        # A missing/empty ANTHROPIC_API_KEY doesn't raise anthropic.APIError -
        # the SDK's messages.create() raises a plain TypeError instead
        # ("Could not resolve authentication method"), which the APIError
        # handler below never sees. Only reproducible by leaving `client`
        # unset (None), since that's the only path that builds a real
        # anthropic.Anthropic() instead of taking a test's mock.
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with self.assertRaises(ValueError) as cm:
                analyze_document(DOCUMENT, TITLE, client=None)
        self.assertIn("temporarily unavailable", str(cm.exception))

    def test_an_anthropic_api_error_becomes_a_clean_valueerror(self):
        # A hit spend limit, a bad key, a rate limit, or an outage all raise
        # some anthropic.APIError subclass - none of those should reach the
        # caller as a raw, unhandled exception (api/analyze.py only catches
        # ValueError and would otherwise surface this as a bare 500).
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

        def _raise(**kwargs):
            raise anthropic.APIConnectionError(request=request)

        client = SimpleNamespace(messages=SimpleNamespace(create=_raise))
        with self.assertRaises(ValueError) as cm:
            analyze_document(DOCUMENT, TITLE, client=client)
        self.assertIn("temporarily unavailable", str(cm.exception))

    def test_an_anthropic_api_error_is_logged_server_side(self):
        # The client-facing message is deliberately generic - a bad key, no
        # billing, a rate limit, and an outage all read identically to the
        # caller. That's only diagnosable at all if the real exception is
        # still visible somewhere (Vercel's function logs), so this asserts
        # it's actually printed, not just swallowed into the ValueError.
        import io
        from contextlib import redirect_stderr

        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

        def _raise(**kwargs):
            raise anthropic.APIConnectionError(request=request)

        client = SimpleNamespace(messages=SimpleNamespace(create=_raise))
        captured = io.StringIO()
        with redirect_stderr(captured):
            with self.assertRaises(ValueError):
                analyze_document(DOCUMENT, TITLE, client=client)
        self.assertIn("APIConnectionError", captured.getvalue())


class DifferenceOperationTest(unittest.TestCase):
    """Slice 29: subtraction is a supported operation now - safe only
    because every operand's value is still checked against the number its
    own exact_text spells out, sign included.
    """

    DOC = "Q4 revenue was $4,200,000, up from $3,950,000 in Q3 2026."

    def _seg(self, **over):
        base = {
            "type": "computed", "display": "inline", "label": "QoQ change",
            "operation": "difference",
            "operands": [
                {"exact_text": "$4,200,000", "value": 4200000.0},
                {"exact_text": "$3,950,000", "value": 3950000.0},
            ],
            "has_total": False, "total_exact_text": "", "total_value": 0,
            "result": 250000.0,
            "sentence": "Revenue rose by {value} quarter over quarter.",
            "format": "usd",
        }
        base.update(over)
        return base

    def test_correct_difference_is_recomputed_and_kept(self):  # Done when #1
        out = analyze_document(self.DOC, TITLE, client=_fake_client([self._seg()]))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["value"], 250000.0)
        self.assertEqual(out[0]["operation"], "difference")

    def test_difference_with_a_wrong_result_is_dropped(self):  # Done when #1
        with self.assertRaises(ValueError):
            analyze_document(self.DOC, TITLE, client=_fake_client([self._seg(result=999999.0)]))

    def test_difference_with_a_sign_flipped_operand_is_dropped(self):  # Done when #1
        # The pre-Slice-29 exploit, retried under the new operation:
        # "$3,950,000" really is in the document, but passing it as a
        # negative value (making a - b silently a + b) must still fail the
        # per-operand value check.
        seg = self._seg(
            operands=[
                {"exact_text": "$4,200,000", "value": 4200000.0},
                {"exact_text": "$3,950,000", "value": -3950000.0},
            ],
            result=8150000.0,
        )
        with self.assertRaises(ValueError):
            analyze_document(self.DOC, TITLE, client=_fake_client([seg]))

    def test_difference_with_only_one_operand_is_dropped(self):  # Done when #1
        seg = self._seg(
            operands=[{"exact_text": "$4,200,000", "value": 4200000.0}],
            result=4200000.0,
        )
        with self.assertRaises(ValueError):
            analyze_document(self.DOC, TITLE, client=_fake_client([seg]))


class HorizonFieldTest(unittest.TestCase):
    """Slice 29: every verified segment carries a horizon; a guidance
    figure is verified exactly like any other quote.
    """

    def test_a_guidance_quote_is_verified_and_keeps_its_horizon(self):  # Done when #2
        document = "Management guided full-year 2027 revenue to $50,000,000."
        segments = [{
            "type": "quote", "horizon": "guidance", "display": "stat",
            "label": "FY2027 guidance", "exact_text": "$50,000,000",
            "has_value": True, "value": 50000000.0,
            "sentence": "Full-year revenue is guided to {value}.", "format": "usd",
        }]
        out = analyze_document(document, TITLE, client=_fake_client(segments))
        self.assertEqual(out[0]["value"], 50000000.0)
        self.assertEqual(out[0]["horizon"], "guidance")

    def test_a_segment_with_no_horizon_defaults_to_reported(self):  # Done when #2
        segments = [{
            "type": "quote", "display": "inline", "label": "Revenue",
            "exact_text": "$10,000,000", "has_value": True, "value": 10000000.0,
            "sentence": "Q4 revenue was {value}.", "format": "usd",
        }]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(out[0]["horizon"], "reported")

    def test_an_unrecognised_horizon_falls_back_to_reported(self):  # Done when #2
        segments = [{
            "type": "quote", "horizon": "wishful", "display": "inline",
            "label": "Revenue", "exact_text": "$10,000,000",
            "has_value": True, "value": 10000000.0,
            "sentence": "Q4 revenue was {value}.", "format": "usd",
        }]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(out[0]["horizon"], "reported")

    def test_prose_carries_a_horizon_too(self):
        segments = [{"type": "prose", "horizon": "projected",
                     "text": "Momentum should continue into 2027."}]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(out[0]["horizon"], "projected")


class CoverageContractTest(unittest.TestCase):
    """Slice 29: given a realistic multi-period response, the full
    comparison set survives verification and coverage_summary reports it.
    """

    DOC = (
        "Acme 2026 results. Q1 revenue was $3.20 billion. Q2 revenue was "
        "$3.55 billion. Q3 revenue was $3.80 billion, up from Q2. Data "
        "Services was $1.14 billion of the Q3 total. Full-year revenue is "
        "guided to $15.00 billion."
    )

    SEGMENTS = [
        {"type": "quote", "display": "inline", "label": "Q3 revenue",
         "exact_text": "$3.80 billion", "has_value": True, "value": 3.8e9,
         "sentence": "Q3 revenue was {value}.", "format": "usd"},
        {"type": "quote", "display": "inline", "label": "Q2 revenue",
         "exact_text": "$3.55 billion", "has_value": True, "value": 3.55e9,
         "sentence": "Q2 revenue was {value}.", "format": "usd"},
        {"type": "quote", "display": "inline", "label": "Q1 revenue",
         "exact_text": "$3.20 billion", "has_value": True, "value": 3.2e9,
         "sentence": "Q1 revenue was {value}.", "format": "usd"},
        {"type": "computed", "display": "inline", "label": "QoQ growth",
         "operation": "growth_percent",
         "operands": [{"exact_text": "$3.55 billion", "value": 3.55e9},
                      {"exact_text": "$3.80 billion", "value": 3.8e9}],
         "has_total": False, "total_exact_text": "", "total_value": 0,
         "result": 7.04, "sentence": "Revenue grew {value} from Q2 to Q3.",
         "format": "percent"},
        {"type": "computed", "display": "inline", "label": "QoQ change",
         "operation": "difference",
         "operands": [{"exact_text": "$3.80 billion", "value": 3.8e9},
                      {"exact_text": "$3.55 billion", "value": 3.55e9}],
         "has_total": False, "total_exact_text": "", "total_value": 0,
         "result": 250000000.0, "sentence": "Revenue rose {value} from Q2 to Q3.",
         "format": "usd"},
        {"type": "computed", "display": "inline", "label": "Data Services share",
         "operation": "percent_of_total",
         "operands": [{"exact_text": "$1.14 billion", "value": 1.14e9}],
         "has_total": True, "total_exact_text": "$3.80 billion", "total_value": 3.8e9,
         "result": 30.0, "sentence": "Data Services was {value} of Q3 revenue.",
         "format": "percent"},
        {"type": "quote", "horizon": "guidance", "display": "stat",
         "label": "FY guidance", "exact_text": "$15.00 billion",
         "has_value": True, "value": 15e9,
         "sentence": "Full-year revenue is guided to {value}.", "format": "usd"},
        {"type": "computed", "horizon": "guidance", "display": "inline",
         "label": "Implied H2 remaining", "operation": "difference",
         "operands": [{"exact_text": "$15.00 billion", "value": 15e9},
                      {"exact_text": "$3.20 billion", "value": 3.2e9},
                      {"exact_text": "$3.55 billion", "value": 3.55e9},
                      {"exact_text": "$3.80 billion", "value": 3.8e9}],
         "has_total": False, "total_exact_text": "", "total_value": 0,
         "result": 4450000000.0,
         "sentence": "That leaves {value} to reach the full-year guide.",
         "format": "usd"},
    ]

    def test_the_full_comparison_set_survives_verification(self):  # Done when #3
        out = analyze_document(self.DOC, TITLE, client=_fake_client(self.SEGMENTS))
        self.assertEqual(len(out), 8)  # nothing dropped

    def test_coverage_summary_counts_comparisons_and_horizons(self):  # Done when #4
        out = analyze_document(self.DOC, TITLE, client=_fake_client(self.SEGMENTS))
        cov = coverage_summary(out)
        self.assertEqual(cov["comparisons"], 4)      # growth, difference, pct_of_total, difference
        self.assertEqual(cov["reported_figures"], 3)  # the three quoted quarters
        self.assertEqual(cov["horizons"]["guidance"], 2)
        self.assertEqual(cov["horizons"]["reported"], 6)


class EventSegmentTest(unittest.TestCase):
    """Slice 32: a dated event is a verified structured fact - every part
    a real substring of the source, or the whole event is dropped.
    """

    DOC = (
        "On May 14, 2026, Northwind completed its acquisition of Halyard "
        "Analytics. Integration is underway, with one-time costs peaking "
        "this quarter. Management expects the deal to be accretive to "
        "earnings by the first half of 2027."
    )

    def _event(self, **over):
        ev = {
            "what": "completed its acquisition of Halyard Analytics",
            "date": "May 14, 2026",
            "status": "Integration is underway",
            "next_step": "accretive to earnings by the first half of 2027",
        }
        ev.update(over)
        return {"type": "event", "event": ev}

    def test_a_fully_real_event_is_verified_and_kept(self):  # Done when #1
        out = analyze_document(self.DOC, TITLE, client=_fake_client([self._event()]))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["type"], "event")
        self.assertEqual(out[0]["what"], "completed its acquisition of Halyard Analytics")
        self.assertEqual(out[0]["date"], "May 14, 2026")
        self.assertEqual(out[0]["next_step"], "accretive to earnings by the first half of 2027")
        self.assertEqual(out[0]["citation"], out[0]["what"])

    def test_an_event_whose_what_is_not_in_the_source_is_dropped(self):  # Done when #1
        bad = self._event(what="acquired a mystery competitor")
        with self.assertRaises(ValueError):
            analyze_document(self.DOC, TITLE, client=_fake_client([bad]))

    def test_an_event_with_a_fabricated_next_step_is_dropped_whole(self):  # Done when #1
        # what/date/status are all real, but the next step is invented ->
        # a half-verified timeline is not shown.
        bad = self._event(next_step="a spin-off planned for 2025")
        with self.assertRaises(ValueError):
            analyze_document(self.DOC, TITLE, client=_fake_client([bad]))

    def test_an_event_with_only_what_is_kept(self):  # Done when #2
        ev = self._event(date="", status="", next_step="")
        out = analyze_document(self.DOC, TITLE, client=_fake_client([ev]))
        self.assertEqual(out[0]["date"], "")
        self.assertEqual(out[0]["what"], "completed its acquisition of Halyard Analytics")

    def test_coverage_summary_reports_events(self):  # Done when #5
        quote = {
            "type": "quote", "display": "inline", "label": "x",
            "exact_text": "Halyard Analytics", "has_value": False,
        }
        out = analyze_document(self.DOC, TITLE, client=_fake_client([self._event(), quote]))
        self.assertEqual(coverage_summary(out)["events"], 1)


class RealFilingTablesTest(unittest.TestCase):
    """Slice 33: a table-heavy filing that states its unit once. Meridian
    (all prose, every figure spelled out "$498.0 million") hid these; a
    real condensed income statement broke verification to zero live.
    """

    # An L1-style extraction of a condensed statement: a scale line, then
    # a pipe-delimited table, the way analystos.l1.document_text renders it.
    DOC = (
        "Calderon Grid Technologies — Third Quarter 2026 Results\n"
        "In millions of U.S. dollars, except per share amounts.\n"
        "Table 1:\n"
        " | Q3 2026 | Q2 2026 | Q3 2025\n"
        "Revenue | 1,842.0 | 1,788.0 | 1,715.0\n"
        "Operating income | 110.0 | 150.0 | 149.1\n"
        "Diluted earnings per share | 0.22 | 0.34 | 0.35\n"
    )

    def test_detect_scale_reads_the_unit_declaration(self):
        self.assertEqual(_detect_scale(self.DOC), 1_000_000)
        self.assertEqual(_detect_scale("Amounts in thousands. Revenue 4,200."), 1_000)
        self.assertEqual(_detect_scale("figures in millions of US dollars"), 1_000_000)
        self.assertEqual(_detect_scale("Q4 revenue was $498.0 million."), 1)  # prose, no unit line

    def test_match_key_folds_typography_not_digits(self):
        self.assertIn("revenue 1842.0", _match_key("Revenue | 1,842.0 | 1,788.0"))
        self.assertTrue(_really_in_document("$1,842.0", _match_key(self.DOC)))
        self.assertTrue(_really_in_document("Revenue 1842.0", _match_key(self.DOC)))
        # a model that re-appends the header's unit word still locates the cell
        self.assertTrue(_really_in_document("1,842.0 million", _match_key(self.DOC)))
        # a number that isn't in the document still cannot match
        self.assertFalse(_really_in_document("9,999.0", _match_key(self.DOC)))

    def test_a_bare_cell_number_locates_but_a_mislabelled_pair_does_not(self):
        mk = _match_key(self.DOC)
        # the prompt tells the model to cite a non-leading cell by the
        # number alone - that always locates
        self.assertTrue(_really_in_document("1,715.0", mk))
        self.assertTrue(_really_in_document("0.35", mk))
        # row-label + distant cell is refused rather than risk accepting a
        # mislabelled number - a false "verified" is never acceptable
        self.assertFalse(_really_in_document("Operating income 1,715.0", mk))

    def test_value_matches_text_accepts_the_declared_scale(self):
        # the model gave the actual magnitude for a "1,842.0" cell in millions
        self.assertEqual(_value_matches_text(1_842_000_000.0, "1,842.0", 1_000_000), 1_842_000_000.0)
        # the model left it unscaled - still matches (stored as-is), not dropped
        self.assertEqual(_value_matches_text(1_842.0, "1,842.0", 1_000_000), 1_842.0)
        # a fabricated magnitude matches neither scale
        self.assertIsNone(_value_matches_text(9_999_000_000.0, "1,842.0", 1_000_000))
        # sign flip still rejected (Slice 29 guard holds)
        self.assertIsNone(_value_matches_text(-1_050.0, "1,050", 1_000_000))

    def test_a_scaled_table_quote_verifies_and_is_stored_at_real_size(self):
        segs = [{
            "type": "quote", "display": "stat", "label": "Q3 revenue",
            "exact_text": "Revenue 1,842.0", "has_value": True, "value": 1_842_000_000.0,
            "sentence": "Third-quarter revenue was {value}.", "format": "usd",
        }]
        out = analyze_document(self.DOC, TITLE, client=_fake_client(segs))
        self.assertEqual(out[0]["value"], 1_842_000_000.0)

    def test_a_quote_that_re_adds_the_dollar_sign_and_unit_still_verifies(self):
        segs = [{
            "type": "quote", "display": "inline", "label": "Q3 revenue",
            "exact_text": "$1,842.0 million", "has_value": True, "value": 1_842_000_000.0,
            "sentence": "Revenue reached {value}.", "format": "usd",
        }]
        out = analyze_document(self.DOC, TITLE, client=_fake_client(segs))
        self.assertEqual(out[0]["value"], 1_842_000_000.0)

    def test_growth_on_scaled_table_operands_verifies_even_if_left_unscaled(self):
        # bare-cell citations (what the prompt now tells the model to use
        # for a non-leading table column), left at the table's printed
        # scale - the growth % is scale-invariant, and both operands are
        # canonicalised to real size before the recompute either way.
        segs = [{
            "type": "computed", "display": "inline", "label": "Revenue growth",
            "operation": "growth_percent",
            "operands": [
                {"exact_text": "1,715.0", "value": 1_715.0},
                {"exact_text": "1,842.0", "value": 1_842.0},
            ],
            "has_total": False, "total_exact_text": "", "total_value": 0,
            "result": 7.4,
            "sentence": "Revenue grew {value} year over year.", "format": "percent",
        }]
        out = analyze_document(self.DOC, TITLE, client=_fake_client(segs))
        self.assertAlmostEqual(out[0]["value"], (1842 - 1715) / 1715 * 100, places=1)

    def test_total_verification_failure_is_logged_with_reasons(self):
        segs = [
            {"type": "quote", "display": "inline", "label": "x",
             "exact_text": "Revenue of $9,999.9 billion", "has_value": True,
             "value": 9_999_900_000_000.0, "sentence": "It was {value}.", "format": "usd"},
            {"type": "prose", "text": "Growth was roughly 45% this quarter."},
        ]
        buf = io.StringIO()
        with redirect_stderr(buf), self.assertRaises(ValueError):
            analyze_document(self.DOC, TITLE, client=_fake_client(segs))
        logged = buf.getvalue()
        self.assertIn("0 verified", logged)
        self.assertIn("not found in document", logged)

    def test_prose_only_meridian_style_document_is_unaffected(self):
        doc = "Third-quarter revenue was $498.0 million, up 9.5% from the prior quarter."
        segs = [{
            "type": "quote", "display": "inline", "label": "Revenue",
            "exact_text": "$498.0 million", "has_value": True, "value": 498_000_000.0,
            "sentence": "Revenue was {value}.", "format": "usd",
        }]
        out = analyze_document(doc, TITLE, client=_fake_client(segs))
        self.assertEqual(out[0]["value"], 498_000_000.0)


if __name__ == "__main__":
    unittest.main()
