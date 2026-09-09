"""Tests for L2 write_narrative's structured output + validation - one per
"Done when" in specs/slice-30/spec.md (and the Slice 27 cases it carries
forward). Uses a mocked Anthropic client throughout: no real API call, no
cost, no network dependency.
"""

import unittest
from types import SimpleNamespace

import anthropic
import httpx2

from analystos.l2.narrate import write_narrative

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


if __name__ == "__main__":
    unittest.main()
