"""Tests for L2 analyze_document's verification logic - one per "Done when"
in specs/slice-26/spec.md. Uses a mocked Anthropic client throughout: no
real API call, no cost, no network dependency, so this suite runs clean
with no ANTHROPIC_API_KEY at all.
"""

import unittest
from types import SimpleNamespace

from analystos.l2.analyze import analyze_document

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
            "exact_text": "$10,000,000", "value": 10000000.0,
            "sentence": "Q4 revenue was {value}.", "format": "usd",
        }]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["value"], 10000000.0)
        self.assertEqual(out[0]["citation"], "$10,000,000")

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
            "exact_text": "$10,000,000", "value": 10000000.0,
            "sentence": "Q4 revenue was strong.",  # no {value} placeholder
            "format": "usd",
        }]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_prose_with_a_stray_number_is_rejected(self):  # Done when #3
        segments = [{"type": "prose", "text": "Growth was roughly 45% this quarter."}]
        with self.assertRaises(ValueError):
            analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))

    def test_prose_with_no_numbers_is_kept(self):
        segments = [
            {"type": "prose", "text": "Momentum continued into the following quarter."},
            {
                "type": "quote", "display": "inline", "label": "Revenue",
                "exact_text": "$10,000,000", "value": 10000000.0,
                "sentence": "Revenue was {value}.", "format": "usd",
            },
        ]
        out = analyze_document(DOCUMENT, TITLE, client=_fake_client(segments))
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["type"], "prose")

    def test_stat_display_qualitative_quote_with_no_value_is_kept(self):
        segments = [{
            "type": "quote", "display": "stat", "label": "Headcount",
            "exact_text": "40 people",
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


if __name__ == "__main__":
    unittest.main()
