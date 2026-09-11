"""Tests for L2 write_narrative's structured output + validation - one per
"Done when" in specs/slice-30/spec.md (and the Slice 27 cases it carries
forward). Uses a mocked Anthropic client throughout: no real API call, no
cost, no network dependency.
"""

import unittest
from types import SimpleNamespace

import anthropic
import httpx2

from analystos.l2.narrate import (
    _MAX_REPAIR_ATTEMPTS,
    _MAX_RETRIES,
    _build_manifest,
    _locate_problem,
    _redundant_unit_problem,
    _validate_paragraph,
    repair_language_issues,
    write_narrative,
)

SEGMENTS = [
    {  # 0: citable quote with a value
        "type": "quote", "horizon": "reported", "display": "inline", "label": "Revenue",
        "value": 10000000.0, "format": "usd", "citation": "$10,000,000",
    },
    {  # 1: citable quote with a value
        "type": "quote", "horizon": "reported", "display": "inline", "label": "Prior Revenue",
        "value": 8000000.0, "format": "usd", "citation": "$8,000,000",
    },
    {  # 2: citable qualitative quote, no value
        "type": "quote", "horizon": "reported", "display": "stat", "label": "Headcount",
        "text": "40 people", "citation": "40 people",
    },
    {  # 3: prose - not citable, no citation to attach
        "type": "prose", "horizon": "reported", "text": "Momentum continued into the next quarter.",
    },
    {  # 4: a guidance figure
        "type": "quote", "horizon": "guidance", "display": "stat", "label": "FY guidance",
        "value": 45000000.0, "format": "usd", "citation": "$45,000,000",
    },
]
TITLE = "Q4 Review"


def _report(**over):
    base = {
        "executive_summary": [{"text": "Revenue reached {{0}}, up from {{1}}."}],
        "sections": [{
            "heading": "Revenue",
            "paragraphs": [{"text": "Revenue was {{0}} against {{1}} a year earlier."}],
            "has_chart": True,
            "chart": {
                "type": "bar", "title": "Revenue", "format": "usd",
                "series": [{"label": "This year", "fact_index": 0},
                           {"label": "Last year", "fact_index": 1}],
            },
        }],
        "outlook": [{"text": "Guidance implies {{4}} for the full year."}],
    }
    base.update(over)
    return base


def _fake_client(report):
    tool_use_block = SimpleNamespace(type="tool_use", input=report)
    response = SimpleNamespace(content=[tool_use_block])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


class WriteNarrativeStructureTest(unittest.TestCase):
    def test_a_valid_structured_report_is_returned_and_normalized(self):  # Done when #1
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(_report()))
        self.assertEqual(out["title"], TITLE)
        self.assertEqual(len(out["executive_summary"]), 1)
        self.assertEqual(out["sections"][0]["heading"], "Revenue")
        self.assertEqual(len(out["sections"][0]["chart"]["series"]), 2)
        self.assertEqual(len(out["outlook"]), 1)
        # normalized: has_chart folded away, only render_rich_report's keys
        self.assertNotIn("has_chart", out["sections"][0])

    def test_the_report_renders_through_render_rich_report_unchanged(self):  # Done when #1
        from analystos.l4.rich_export import render_rich_report

        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(_report()))
        html = render_rich_report(out, SEGMENTS, "a1b2c3d4" * 8)
        self.assertIn("Executive summary", html)
        self.assertIn("<h2>Revenue</h2>", html)
        self.assertIn('class="outlook"', html)
        self.assertIn("$10.0M", html)
        self.assertIn("<svg", html)  # the chart drew

    def test_an_out_of_range_reference_in_a_section_is_rejected(self):  # Done when #2
        bad = _report(sections=[{
            "heading": "X", "paragraphs": [{"text": "See {{99}}."}],
            "has_chart": False, "chart": _empty_chart(),
        }])
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(bad))

    def test_a_reference_to_a_prose_segment_in_the_outlook_is_rejected(self):  # Done when #2
        bad = _report(outlook=[{"text": "As noted: {{3}}."}])
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(bad))

    def test_a_stray_digit_in_the_executive_summary_is_rejected(self):  # Done when #2
        bad = _report(executive_summary=[{"text": "Revenue grew 25% to {{0}}."}])
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(bad))

    def test_an_empty_executive_summary_is_rejected(self):  # Done when #3
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(_report(executive_summary=[])))

    def test_no_sections_is_rejected(self):  # Done when #3
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(_report(sections=[])))

    def test_a_section_with_no_paragraphs_is_rejected(self):  # Done when #3
        bad = _report(sections=[{
            "heading": "Empty", "paragraphs": [], "has_chart": False, "chart": _empty_chart(),
        }])
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(bad))

    def test_a_section_with_a_blank_heading_is_rejected(self):  # Done when #3
        bad = _report(sections=[{
            "heading": "   ", "paragraphs": [{"text": "Revenue was {{0}}."}],
            "has_chart": False, "chart": _empty_chart(),
        }])
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(bad))

    def test_a_chart_with_an_out_of_range_fact_index_is_dropped_not_raised(self):  # Done when #4
        bad_chart = _report(sections=[{
            "heading": "Revenue", "paragraphs": [{"text": "Revenue was {{0}}."}],
            "has_chart": True,
            "chart": {"type": "bar", "title": "R", "format": "usd",
                      "series": [{"label": "a", "fact_index": 0},
                                 {"label": "b", "fact_index": 99}]},
        }])
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(bad_chart))
        # one valid point left -> under two -> whole chart dropped, report kept
        self.assertIsNone(out["sections"][0]["chart"])
        self.assertEqual(out["sections"][0]["paragraphs"][0]["text"],
                         "Revenue was {{0}}.")

    def test_a_chart_pointing_at_a_prose_segment_is_dropped(self):  # Done when #4
        bad_chart = _report(sections=[{
            "heading": "Revenue", "paragraphs": [{"text": "Revenue was {{0}}."}],
            "has_chart": True,
            "chart": {"type": "bar", "title": "R", "format": "usd",
                      "series": [{"label": "a", "fact_index": 0},
                                 {"label": "prose", "fact_index": 3}]},
        }])
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(bad_chart))
        self.assertIsNone(out["sections"][0]["chart"])

    def test_a_valid_two_point_chart_survives(self):  # Done when #4
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(_report()))
        self.assertEqual(out["sections"][0]["chart"]["type"], "bar")
        self.assertEqual(
            [p["fact_index"] for p in out["sections"][0]["chart"]["series"]], [0, 1]
        )

    def test_an_empty_outlook_becomes_none(self):
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(_report(outlook=[])))
        self.assertIsNone(out["outlook"])

    def test_a_calendar_reference_outside_a_placeholder_is_allowed(self):
        ok = _report(outlook=[{"text": "Momentum should carry into Q4 2026, toward {{4}}."}])
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(ok))
        self.assertEqual(len(out["outlook"]), 1)

    def test_a_dated_day_of_month_does_not_reject_the_narrative(self):  # Slice 34
        # "as of September 30, 2026" was rejecting whole narratives live -
        # the "30" read as a stray digit and the report fell back to flat.
        ok = _report(sections=[{
            "heading": "Liquidity",
            "paragraphs": [{"text": "Cash fell to {{0}} as of September 30, 2026, "
                            "against {{1}} at December 31, 2025."}],
            "has_chart": False, "chart": _empty_chart(),
        }])
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(ok))
        self.assertEqual(out["sections"][0]["heading"], "Liquidity")

    def test_an_event_fact_can_be_referenced_like_any_citable_fact(self):  # slice 32
        segs = SEGMENTS + [{
            "type": "event", "horizon": "reported", "what": "acquired Halyard",
            "date": "May 2026", "status": "integrating", "next_step": "accretive in 2027",
            "citation": "acquired Halyard",
        }]
        rep = _report(sections=[{
            "heading": "The deal", "paragraphs": [{"text": "The company {{5}} this year."}],
            "has_chart": False, "chart": _empty_chart(),
        }])
        out = write_narrative(segs, TITLE, client=_fake_client(rep))
        self.assertEqual(out["sections"][0]["paragraphs"][0]["text"], "The company {{5}} this year.")


class WriteNarrativeFailurePathsTest(unittest.TestCase):
    def test_no_citable_facts_at_all_raises_before_calling_the_model(self):
        only_prose = [{"type": "prose", "horizon": "reported", "text": "Nothing to report."}]
        with self.assertRaises(ValueError):
            write_narrative(only_prose, TITLE, client=_fake_client(_report()))

    def test_model_response_with_no_tool_use_raises(self):
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text="oops")])
        client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=client)

    def test_a_wrong_shape_tool_response_falls_back(self):
        # e.g. the model somehow returned the old flat paragraphs list -
        # no executive_summary / sections -> reject -> caller falls back.
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE,
                            client=_fake_client({"paragraphs": [{"text": "hi {{0}}"}]}))

    def test_an_anthropic_api_error_becomes_a_clean_valueerror(self):
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

        def _raise(**kwargs):
            raise anthropic.APIConnectionError(request=request)

        client = SimpleNamespace(messages=SimpleNamespace(create=_raise))
        with self.assertRaises(ValueError) as cm:
            write_narrative(SEGMENTS, TITLE, client=client)
        self.assertIn("temporarily unavailable", str(cm.exception))


def _empty_chart():
    return {"type": "bar", "title": "", "format": "number", "series": []}


class DirectionWordGateTest(unittest.TestCase):
    """Slice 38, Gate 1 check #1 - reproduces the live bug directly: net
    income described as "rose... up $2.8M" when the verified fact behind
    it had actually fallen. Confirms the checker catches it, and that a
    correctly-signed growth_percent claim is unaffected.
    """

    GROWTH_UP = {"type": "computed", "operation": "growth_percent", "value": 12.5}
    GROWTH_DOWN = {"type": "computed", "operation": "growth_percent", "value": -12.5}
    DIFFERENCE = {"type": "computed", "operation": "difference", "value": 2.8}
    SEGS = [GROWTH_UP, GROWTH_DOWN, DIFFERENCE]

    def test_an_increase_word_on_a_declining_growth_percent_fact_is_rejected(self):
        problem = _validate_paragraph("Net income rose, up {{1}} year over year.", self.SEGS)
        self.assertIsNotNone(problem)
        self.assertIn("increase", problem)

    def test_a_decrease_word_on_a_rising_growth_percent_fact_is_rejected(self):
        problem = _validate_paragraph("Revenue fell, down {{0}}.", self.SEGS)
        self.assertIsNotNone(problem)
        self.assertIn("decrease", problem)

    def test_the_live_bug_a_difference_fact_paired_with_any_direction_word_is_rejected(self):
        # This is exactly the live failure: difference = $22.4M - $19.6M =
        # +$2.8M (positive only because of operand order), described as a
        # rise. A difference's sign is never trusted for direction, full stop.
        problem = _validate_paragraph("Net income rose, up {{2}} year over year.", self.SEGS)
        self.assertIsNotNone(problem)
        self.assertIn("difference", problem)

    def test_a_correctly_signed_growth_percent_claim_is_accepted(self):
        self.assertIsNone(_validate_paragraph("Revenue grew {{0}} year over year.", self.SEGS))
        self.assertIsNone(_validate_paragraph("Net income declined {{1}} year over year.", self.SEGS))

    def test_a_difference_fact_with_no_direction_word_is_accepted(self):
        self.assertIsNone(_validate_paragraph("Net income changed by {{2}} year over year.", self.SEGS))

    def test_a_direction_word_separated_by_another_placeholder_does_not_false_positive(self):
        # Found live 2026-09-11: "declined" correctly describes the
        # {{1}}-from-{{0}} comparison (both plain quotes, no sign-safety
        # issue), and only afterward does a separate, comma-appositive
        # restate the same move as a "difference" ({{2}}) - the direction
        # word was never describing {{2}} at all.
        text = "Net income declined to {{1}} from {{0}}, a change of {{2}}."
        self.assertIsNone(_validate_paragraph(text, self.SEGS))

    def test_a_direction_word_immediately_before_a_difference_fact_is_still_rejected(self):
        # The original live bug (no other placeholder intervening) must
        # still be caught - the fix narrows the window, it doesn't disable it.
        problem = _validate_paragraph("Net income rose, up {{2}} year over year.", self.SEGS)
        self.assertIsNotNone(problem)
        self.assertIn("difference", problem)


class ConsecutiveCountGateTest(unittest.TestCase):
    """Slice 38, Gate 1 check #4 - "N consecutive quarters" needs N+1 data
    points (N transitions, not N periods)."""

    QUOTE = {"type": "quote", "value": 1.0}
    SEGS = [QUOTE, QUOTE, QUOTE, QUOTE]  # four period figures, citable as 0-3

    def test_five_consecutive_claimed_from_four_cited_points_is_rejected(self):
        text = "Margin declined for five consecutive quarters, from {{0}} to {{1}} to {{2}} to {{3}}."
        problem = _validate_paragraph(text, self.SEGS)
        self.assertIsNotNone(problem)
        self.assertIn("claims 5 consecutive quarters", problem)

    def test_three_consecutive_from_four_cited_points_is_accepted(self):
        text = "Margin declined for three consecutive quarters, from {{0}} to {{1}} to {{2}} to {{3}}."
        self.assertIsNone(_validate_paragraph(text, self.SEGS))

    def test_a_consecutive_claim_with_no_cited_periods_is_not_flagged(self):
        # nothing to verify the claim against in this sentence - stays
        # silent rather than guess (no false positive)
        self.assertIsNone(_validate_paragraph("Margin declined for five consecutive quarters.", self.SEGS))


class RedundantUnitGateTest(unittest.TestCase):  # Slice 40
    """A {{N}}'s rendered value already carries its own unit - found live
    2026-09-11: {{18}} correctly named an acquisition event in one
    sentence and was then written as "approximately {{18}} million" in
    another, an inconsistency only Gate 2 (language quality) caught."""

    def test_million_spelled_out_after_a_placeholder_is_rejected(self):
        problem = _redundant_unit_problem("Integration costs were approximately {{18}} million in Q3.")
        self.assertIsNotNone(problem)
        self.assertIn("million", problem)

    def test_billion_percent_and_thousand_are_also_rejected(self):
        for word in ("billion", "percent", "thousand"):
            with self.subTest(word=word):
                self.assertIsNotNone(_redundant_unit_problem(f"Guidance implies {{{{0}}}} {word} for the year."))

    def test_points_is_not_flagged_its_a_real_disambiguator(self):
        self.assertIsNone(_redundant_unit_problem("A {{16}}-point change in gross margin, from {{15}} to {{14}}."))
        self.assertIsNone(_redundant_unit_problem("Gross margin moved {{16}} points, from {{15}} to {{14}}."))

    def test_a_placeholder_with_no_trailing_unit_word_is_fine(self):
        self.assertIsNone(_redundant_unit_problem("Revenue reached {{0}}, up from {{1}}."))

    def test_wired_into_validate_paragraph(self):
        segs = [{"type": "event", "date": "May 14, 2026", "what": "acquisition of Halyard Analytics"}]
        text = "Integration costs tied to the {{0}} were approximately {{0}} million in Q3."
        problem = _validate_paragraph(text, segs)
        self.assertIsNotNone(problem)
        self.assertIn("million", problem)


class LocateProblemTest(unittest.TestCase):  # Slice 40
    def test_a_clean_report_has_no_problem(self):
        self.assertIsNone(_locate_problem(_report(), SEGMENTS))

    def test_empty_executive_summary_is_structural(self):
        problem = _locate_problem(_report(executive_summary=[]), SEGMENTS)
        self.assertEqual(problem, ("structural", "empty executive_summary"))

    def test_no_sections_is_structural(self):
        problem = _locate_problem(_report(sections=[]), SEGMENTS)
        self.assertEqual(problem, ("structural", "no sections"))

    def test_a_bad_executive_summary_paragraph_is_located_and_patchable(self):
        report = _report(executive_summary=[{"text": "Revenue reached $10,000,000."}])
        get, set_text, reason = _locate_problem(report, SEGMENTS)
        self.assertIn("digit outside any {{N}} placeholder", reason)
        self.assertEqual(get(), "Revenue reached $10,000,000.")
        set_text("Revenue reached {{0}}.")
        self.assertIsNone(_locate_problem(report, SEGMENTS))
        self.assertEqual(report["executive_summary"][0]["text"], "Revenue reached {{0}}.")

    def test_a_bad_section_paragraph_is_located_by_its_section_index(self):
        report = _report()
        report["sections"][0]["paragraphs"][0]["text"] = "Revenue was $10,000,000 flat."
        _get, _set_text, reason = _locate_problem(report, SEGMENTS)
        self.assertIn("section 0 paragraph", reason)


def _assembled_report(**over):
    """A report in the shape _assemble_report/write_narrative returns
    (post-assembly) - different from _report() above, which is the raw
    pre-assembly tool_use.input shape (nested "has_chart"/"chart" specs,
    dict executive_insight). repair_language_issues operates on this
    shape, the one render_rich_report actually consumes."""
    base = {
        "title": TITLE,
        "kpis": [],
        "executive_summary": [{"text": "Revenue reached {{0}}, up from {{1}}."}],
        "executive_insight": None,
        "sections": [{
            "heading": "Revenue",
            "paragraphs": [{"text": "Revenue was {{0}} against {{1}} a year earlier."}],
            "chart": None,
        }],
        "disclosure_gaps": [],
        "outlook": [{"text": "Guidance implies {{4}} for the full year."}],
        "outlook_interpretation": None,
    }
    base.update(over)
    return base


def _fixed_paragraph_client(fixed_text):
    response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"text": fixed_text})])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response))


class RepairLanguageIssuesTest(unittest.TestCase):  # Slice 40
    """Gate 2 (language quality) gets the same "patch the one flagged
    piece, don't lose the whole report" treatment Gate 1 already has -
    found live 2026-09-11: a report can pass Gate 1 cleanly and still
    fail Gate 2 on pure wording, which had no repair path at all before."""

    def test_a_located_issue_is_repaired_in_place(self):
        report = _assembled_report()
        issues = [{"location": "Revenue was {{0}} against {{1}} a year earlier.",
                   "problem": "awkward phrasing"}]
        client = _fixed_paragraph_client("Revenue of {{0}} compared with {{1}} a year earlier.")

        out = repair_language_issues(report, issues, SEGMENTS, client=client)

        self.assertEqual(
            out["sections"][0]["paragraphs"][0]["text"],
            "Revenue of {{0}} compared with {{1}} a year earlier.",
        )

    def test_an_unlocatable_issue_is_left_unchanged(self):
        report = _assembled_report()
        original = report["sections"][0]["paragraphs"][0]["text"]
        issues = [{"location": "text that appears nowhere in the report", "problem": "..."}]
        client = _fixed_paragraph_client("should never be used")

        out = repair_language_issues(report, issues, SEGMENTS, client=client)

        self.assertEqual(out["sections"][0]["paragraphs"][0]["text"], original)

    def test_a_repair_that_would_break_gate_1_is_rejected(self):
        report = _assembled_report()
        original = report["sections"][0]["paragraphs"][0]["text"]
        issues = [{"location": "Revenue was {{0}} against {{1}} a year earlier.", "problem": "..."}]
        # a "fix" that drops a placeholder for a bare digit - a real Gate 1
        # violation - must never be accepted just because Gate 2 asked for it
        client = _fixed_paragraph_client("Revenue was $10,000,000 against {{1}} a year earlier.")

        out = repair_language_issues(report, issues, SEGMENTS, client=client)

        self.assertEqual(out["sections"][0]["paragraphs"][0]["text"], original)

    def test_executive_insight_is_repairable(self):
        report = _assembled_report(executive_insight="Revenue of {{0}} tells the story on its own.")
        issues = [{"location": "tells the story on its own", "problem": "cliche phrasing"}]
        client = _fixed_paragraph_client("Revenue of {{0}} is the single clearest signal this quarter.")

        out = repair_language_issues(report, issues, SEGMENTS, client=client)

        self.assertEqual(out["executive_insight"], "Revenue of {{0}} is the single clearest signal this quarter.")

    def test_an_ambiguous_location_matching_multiple_fields_is_left_unchanged(self):
        # The default fixture's heading ("Revenue") is also a substring of
        # both the executive summary and the section paragraph - exactly
        # the kind of short, non-unique "location" Gate 2's own prompt
        # allows ("a short, exact fragment," not a guaranteed-unique one).
        # Patching the first match blind risks silently rewriting the
        # wrong sentence, so an ambiguous issue must be left alone.
        report = _assembled_report()
        original_summary = report["executive_summary"][0]["text"]
        original_heading = report["sections"][0]["heading"]
        original_paragraph = report["sections"][0]["paragraphs"][0]["text"]
        issues = [{"location": "Revenue", "problem": "..."}]
        client = _fixed_paragraph_client("should never be used")

        out = repair_language_issues(report, issues, SEGMENTS, client=client)

        self.assertEqual(out["executive_summary"][0]["text"], original_summary)
        self.assertEqual(out["sections"][0]["heading"], original_heading)
        self.assertEqual(out["sections"][0]["paragraphs"][0]["text"], original_paragraph)

    def test_a_section_heading_is_repairable(self):
        report = _assembled_report()
        report["sections"][0]["heading"] = "Segment Performance"
        issues = [{"location": "Segment Performance", "problem": "heading is a bare label, not a point"}]
        client = _fixed_paragraph_client("Segment Performance Accelerates")

        out = repair_language_issues(report, issues, SEGMENTS, client=client)

        self.assertEqual(out["sections"][0]["heading"], "Segment Performance Accelerates")


class WriteNarrativeRepairLoopTest(unittest.TestCase):  # Slice 40
    """A single bad paragraph should be patched with one small call, not
    force a full-document regenerate - see specs/slice-40/spec.md."""

    def _dispatching_client(self, write_responses, repair_response=None):
        calls = {"write_narrative": 0, "fixed_paragraph": 0}

        def _create(**kwargs):
            name = kwargs["tool_choice"]["name"]
            calls[name] += 1
            if name == "fixed_paragraph":
                return repair_response
            i = min(calls["write_narrative"], len(write_responses)) - 1
            return write_responses[i]

        client = SimpleNamespace(messages=SimpleNamespace(create=_create))
        return client, calls

    def test_one_bad_paragraph_is_repaired_without_a_full_regenerate(self):
        bad = _report(executive_summary=[{"text": "Revenue reached $10,000,000, up from {{1}}."}])
        write_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=bad)])
        repair_response = SimpleNamespace(content=[SimpleNamespace(
            type="tool_use", input={"text": "Revenue reached {{0}}, up from {{1}}."},
        )])
        client, calls = self._dispatching_client([write_response], repair_response)

        out = write_narrative(SEGMENTS, TITLE, client=client)

        self.assertEqual(out["executive_summary"][0]["text"], "Revenue reached {{0}}, up from {{1}}.")
        self.assertEqual(calls["write_narrative"], 1)  # no full regenerate needed
        self.assertEqual(calls["fixed_paragraph"], 1)

    def test_a_repair_call_with_no_usable_response_falls_back_to_full_regenerate(self):
        bad = _report(executive_summary=[{"text": "Revenue reached $10,000,000, up from {{1}}."}])
        write_bad = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=bad)])
        write_good = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=_report())])
        no_tool_use = SimpleNamespace(content=[SimpleNamespace(type="text", text="oops")])
        client, calls = self._dispatching_client([write_bad, write_good], no_tool_use)

        out = write_narrative(SEGMENTS, TITLE, client=client)

        self.assertEqual(out["executive_summary"][0]["text"], "Revenue reached {{0}}, up from {{1}}.")
        self.assertEqual(calls["fixed_paragraph"], 1)  # repair attempted once, gave up
        self.assertEqual(calls["write_narrative"], 2)  # then one full regenerate

    def test_a_structural_problem_skips_repair_entirely(self):
        empty = SimpleNamespace(content=[SimpleNamespace(
            type="tool_use", input=_report(executive_summary=[]),
        )])
        client, calls = self._dispatching_client([empty])

        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=client)

        self.assertEqual(calls["fixed_paragraph"], 0)
        self.assertEqual(calls["write_narrative"], 1 + _MAX_RETRIES)

    def test_repair_keeps_chasing_a_second_paragraph_the_first_repair_exposes(self):
        # Fixing paragraph A can reveal (or introduce) a problem in B - the
        # repair loop should chase B too rather than immediately falling
        # back to a full regenerate. Found live 2026-09-11.
        bad = _report(
            executive_summary=[{"text": "Revenue reached $10,000,000, up from {{1}}."}],
            outlook=[{"text": "Guidance implies $45,000,000 for the full year."}],
        )
        write_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=bad)])
        fixes = iter([
            SimpleNamespace(content=[SimpleNamespace(
                type="tool_use", input={"text": "Revenue reached {{0}}, up from {{1}}."},
            )]),
            SimpleNamespace(content=[SimpleNamespace(
                type="tool_use", input={"text": "Guidance implies {{4}} for the full year."},
            )]),
        ])
        calls = {"write_narrative": 0, "fixed_paragraph": 0}

        def _create(**kwargs):
            name = kwargs["tool_choice"]["name"]
            calls[name] += 1
            if name == "fixed_paragraph":
                return next(fixes)
            return write_response

        client = SimpleNamespace(messages=SimpleNamespace(create=_create))
        out = write_narrative(SEGMENTS, TITLE, client=client)

        self.assertEqual(out["executive_summary"][0]["text"], "Revenue reached {{0}}, up from {{1}}.")
        self.assertEqual(out["outlook"][0]["text"], "Guidance implies {{4}} for the full year.")
        self.assertEqual(calls["write_narrative"], 1)
        self.assertEqual(calls["fixed_paragraph"], 2)
        self.assertLessEqual(2, _MAX_REPAIR_ATTEMPTS)


class ManifestGaapStatusTest(unittest.TestCase):  # Slice 45
    def test_a_non_gaap_fact_is_tagged_in_the_manifest(self):
        segs = [{
            "type": "quote", "horizon": "reported", "gaap_status": "non_gaap",
            "label": "Non-GAAP net income", "value": 24100000.0, "format": "usd",
        }]
        manifest = _build_manifest(segs)
        self.assertIn("[non-gaap]", manifest)

    def test_a_gaap_fact_carries_no_tag(self):
        segs = [{
            "type": "quote", "horizon": "reported", "gaap_status": "gaap",
            "label": "GAAP net income", "value": 19600000.0, "format": "usd",
        }]
        manifest = _build_manifest(segs)
        self.assertNotIn("[non-gaap]", manifest)
        self.assertNotIn("[gaap]", manifest)  # gaap is the unmarked default, same as "reported"

    def test_both_a_horizon_and_a_gaap_tag_can_appear_together(self):
        segs = [{
            "type": "quote", "horizon": "guidance", "gaap_status": "non_gaap",
            "label": "FY guide (adjusted)", "value": 50000000.0, "format": "usd",
        }]
        manifest = _build_manifest(segs)
        self.assertIn("[guidance, non-gaap]", manifest)


if __name__ == "__main__":
    unittest.main()
