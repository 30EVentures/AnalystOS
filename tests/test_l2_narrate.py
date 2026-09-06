"""Tests for L2 write_narrative's validation logic - one per "Done when" in
specs/slice-27/spec.md. Uses a mocked Anthropic client throughout: no real
API call, no cost, no network dependency.
"""

import unittest
from types import SimpleNamespace

import anthropic
import httpx2

from analystos.l2.narrate import write_narrative

SEGMENTS = [
    {  # 0: citable quote with a value
        "type": "quote", "display": "inline", "label": "Revenue",
        "value": 10000000.0, "format": "usd", "citation": "$10,000,000",
    },
    {  # 1: citable quote with a value
        "type": "quote", "display": "inline", "label": "Prior Revenue",
        "value": 8000000.0, "format": "usd", "citation": "$8,000,000",
    },
    {  # 2: citable qualitative quote, no value
        "type": "quote", "display": "stat", "label": "Headcount",
        "text": "40 people", "citation": "40 people",
    },
    {  # 3: prose - not citable, no citation to attach
        "type": "prose", "text": "Momentum continued into the next quarter.",
    },
]
TITLE = "Q4 Review"


def _fake_client(paragraphs):
    tool_use_block = SimpleNamespace(type="tool_use", input={"paragraphs": paragraphs})
    response = SimpleNamespace(content=[tool_use_block])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


class WriteNarrativeTest(unittest.TestCase):
    def test_a_valid_narrative_is_returned(self):  # Done when #1
        paragraphs = [{"text": "Revenue was {{0}}, up from {{1}}."}]
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(paragraphs))
        self.assertEqual(out, paragraphs)

    def test_an_out_of_range_reference_is_rejected(self):  # Done when #2
        paragraphs = [{"text": "Revenue was {{99}}."}]
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(paragraphs))

    def test_a_reference_to_a_prose_segment_is_rejected(self):  # Done when #2
        # index 3 is a "prose" segment - verified, but nothing to cite.
        paragraphs = [{"text": "Things continued: {{3}}."}]
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(paragraphs))

    def test_a_stray_digit_outside_a_placeholder_is_rejected(self):  # Done when #3
        paragraphs = [{"text": "Revenue grew 25% this quarter, to {{0}}."}]
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client(paragraphs))

    def test_a_qualitative_reference_is_allowed(self):
        paragraphs = [{"text": "Headcount reached {{2}}."}]
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(paragraphs))
        self.assertEqual(out, paragraphs)

    def test_pure_prose_with_no_placeholders_and_no_digits_is_allowed(self):
        paragraphs = [{"text": "Momentum continued into the next quarter."}]
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(paragraphs))
        self.assertEqual(out, paragraphs)

    def test_a_calendar_reference_outside_a_placeholder_is_allowed(self):
        # Found live, 2026-09-06: the same real-writing-mentions-dates
        # problem as analyze.py's own prose rule - see docs/decisions.md.
        paragraphs = [{"text": "Revenue was {{0}}, and momentum should carry into Q4 2026."}]
        out = write_narrative(SEGMENTS, TITLE, client=_fake_client(paragraphs))
        self.assertEqual(out, paragraphs)

    def test_no_citable_facts_at_all_raises_before_calling_the_model(self):
        only_prose = [{"type": "prose", "text": "Nothing to report."}]
        with self.assertRaises(ValueError):
            write_narrative(only_prose, TITLE, client=_fake_client([]))

    def test_empty_paragraphs_list_raises(self):
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=_fake_client([]))

    def test_model_response_with_no_tool_use_raises(self):
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text="oops")])
        client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
        with self.assertRaises(ValueError):
            write_narrative(SEGMENTS, TITLE, client=client)

    def test_an_anthropic_api_error_becomes_a_clean_valueerror(self):
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

        def _raise(**kwargs):
            raise anthropic.APIConnectionError(request=request)

        client = SimpleNamespace(messages=SimpleNamespace(create=_raise))
        with self.assertRaises(ValueError) as cm:
            write_narrative(SEGMENTS, TITLE, client=client)
        self.assertIn("temporarily unavailable", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
