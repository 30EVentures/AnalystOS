"""Tests for legal boilerplate (forward-looking-statements/safe-harbor)
detection - specs/slice-46/spec.md, Task 2.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from docx import Document

from analystos.l1.boilerplate import strip_forward_looking_boilerplate
from analystos.l1.document_text import extract_document_text
from analystos.l2.analyze import analyze_document

TITLE = "Q3 2026 earnings release"

_DISCLAIMER_HEADING = "Forward-Looking Statements"
_DISCLAIMER_BODY_1 = (
    "This press release contains forward-looking statements within the meaning of the "
    "Private Securities Litigation Reform Act of 1995, including statements regarding the "
    "Company's future financial performance and business strategy. These forward-looking "
    "statements are based on current expectations and assumptions that are subject to risks "
    "and uncertainties, and actual results could differ materially from those anticipated."
)
_DISCLAIMER_BODY_2 = (
    "The Company undertakes no obligation to update or revise any forward-looking "
    "statements, whether as a result of new information, future events, or otherwise, "
    "except as required by law."
)


def _fake_client(segments):
    tool_use_block = SimpleNamespace(type="tool_use", input={"segments": segments})
    response = SimpleNamespace(content=[tool_use_block], stop_reason="tool_use")
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


class StripForwardLookingBoilerplateUnitTest(unittest.TestCase):
    def test_a_headed_disclaimer_section_is_fully_removed(self):
        text = "\n".join([
            "Revenue was $498.0 million in the quarter.",
            _DISCLAIMER_HEADING,
            _DISCLAIMER_BODY_1,
            _DISCLAIMER_BODY_2,
            "Gross margin was 58.7% in the quarter.",
        ])
        out = strip_forward_looking_boilerplate(text)
        self.assertIn("Revenue was $498.0 million", out)
        self.assertIn("Gross margin was 58.7%", out)
        self.assertNotIn(_DISCLAIMER_HEADING, out)
        self.assertNotIn("Litigation Reform Act", out)
        self.assertNotIn("undertake no obligation", out)

    def test_a_heading_less_disclaimer_is_removed_by_content_density_alone(self):
        # No heading at all - a less formal document that just launches
        # into the statutory language directly.
        text = "\n".join([
            "Revenue was $498.0 million in the quarter.",
            _DISCLAIMER_BODY_1,
            "Gross margin was 58.7% in the quarter.",
        ])
        out = strip_forward_looking_boilerplate(text)
        self.assertIn("Revenue was $498.0 million", out)
        self.assertIn("Gross margin was 58.7%", out)
        self.assertNotIn("Litigation Reform Act", out)

    def test_a_single_incidental_mention_of_forward_looking_is_not_stripped(self):
        # The exact failure mode a naive keyword blocklist has: one word
        # in an otherwise ordinary sentence must never trigger removal.
        text = (
            "Management remains focused on forward-looking growth initiatives "
            "and expects continued momentum into next year."
        )
        out = strip_forward_looking_boilerplate(text)
        self.assertEqual(out, text)

    def test_a_single_mention_of_risk_in_ordinary_prose_is_not_stripped(self):
        text = "A key risk to the segment is slower enterprise spending."
        out = strip_forward_looking_boilerplate(text)
        self.assertEqual(out, text)

    def test_a_document_with_no_boilerplate_at_all_is_unchanged(self):
        text = "Revenue was $498.0 million. Gross margin was 58.7%."
        self.assertEqual(strip_forward_looking_boilerplate(text), text)

    def test_only_the_disclaimer_section_is_removed_not_everything_after_it(self):
        # The "consume while still matching" logic must stop, not run
        # away and eat the rest of the document.
        text = "\n".join([
            _DISCLAIMER_HEADING,
            _DISCLAIMER_BODY_1,
            _DISCLAIMER_BODY_2,
            "Revenue guidance for Q4 2026 is $520.0 million to $530.0 million.",
            "Investor contact: ir@example.com.",
        ])
        out = strip_forward_looking_boilerplate(text)
        self.assertIn("$520.0 million to $530.0 million", out)
        self.assertIn("Investor contact", out)


class BoilerplateExclusionIntegrationTest(unittest.TestCase):
    """Task 2's actual "Done when": zero facts extracted from the
    boilerplate section, substantive facts from the rest of the same
    document unaffected - proven on the real narrated-default path
    (extract_document_text -> strip_forward_looking_boilerplate ->
    analyze_document), the only path this applies to.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "release.docx"
        doc = Document()
        doc.add_paragraph("Q3 2026 revenue was $498.0 million, up 9.5% sequentially.")
        doc.add_paragraph(_DISCLAIMER_HEADING)
        doc.add_paragraph(_DISCLAIMER_BODY_1)
        doc.add_paragraph(_DISCLAIMER_BODY_2)
        doc.add_paragraph("Gross margin was 58.7% in the third quarter.")
        doc.save(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_boilerplate_text_never_reaches_the_extraction_stage(self):
        raw = extract_document_text(self.path)
        self.assertIn("Litigation Reform Act", raw)  # confirms the fixture is realistic

        filtered = strip_forward_looking_boilerplate(raw)
        self.assertNotIn("Litigation Reform Act", filtered)
        self.assertNotIn("undertake no obligation", filtered)
        self.assertIn("$498.0 million", filtered)
        self.assertIn("58.7%", filtered)

    def test_substantive_facts_still_verify_correctly_after_filtering(self):
        document_text = strip_forward_looking_boilerplate(extract_document_text(self.path))
        segments = [{
            "type": "quote", "display": "stat", "label": "Q3 2026 revenue",
            "exact_text": "$498.0 million", "has_value": True, "value": 498000000.0,
            "sentence": "Revenue was {value}.", "format": "usd",
        }]
        out = analyze_document(document_text, TITLE, client=_fake_client(segments))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["value"], 498000000.0)

    def test_a_fact_the_model_tried_to_pull_from_the_stripped_disclaimer_fails_verification(self):
        # The strong proof of "zero extracted facts from that section":
        # even if a model ignored instructions and tried to cite the
        # disclaimer's own statutory language as a quote, verification
        # refuses it - the text simply isn't there anymore to match
        # against. (A "prose" segment is never substring-checked at all,
        # so this specifically uses a "quote" - the segment type whose
        # verification actually depends on the text still being present.)
        document_text = strip_forward_looking_boilerplate(extract_document_text(self.path))
        segments = [
            {
                "type": "quote", "display": "stat", "label": "Q3 2026 revenue",
                "exact_text": "$498.0 million", "has_value": True, "value": 498000000.0,
                "sentence": "Revenue was {value}.", "format": "usd",
            },
            {
                "type": "quote", "display": "inline", "label": "Governing statute",
                "exact_text": "Private Securities Litigation Reform Act of 1995",
                "has_value": False,
            },
        ]
        out = analyze_document(document_text, TITLE, client=_fake_client(segments))
        self.assertEqual(len(out), 1)  # the disclaimer-sourced segment was dropped
        self.assertEqual(out[0]["value"], 498000000.0)


if __name__ == "__main__":
    unittest.main()
