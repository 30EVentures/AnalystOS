"""Integration test for image/OCR-derived citable facts -
specs/slice-50/spec.md, Done when #3. Proves the real seam: a PDF with an
embedded image, its transcript produced by a (mocked) vision call, feeds
into the *unmodified* analystos.l2.analyze.analyze_document verification -
the claimed citation must be an exact substring of the image's transcript,
exactly the same exact-substring check any other quote gets - not two
isolated unit tests each asserting the other's contract on faith.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from analystos.l1.document_text import extract_document_text
from analystos.l1.image_facts import tag_image_sourced_segments
from analystos.l2.analyze import analyze_document

TITLE = "Q3 2026 review"
TRANSCRIPT = "Q3 Revenue: $42.7 million"


def _build_pdf_with_chart_image(pdf_path, png_path):
    img = Image.new("RGB", (400, 200), "white")
    ImageDraw.Draw(img).text((20, 80), TRANSCRIPT, fill="black")
    img.save(png_path)

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawString(60, 700, "See the attached exhibit for the quarter's headline figure.")
    c.drawImage(str(png_path), 60, 500, width=300, height=150)
    c.save()


def _vision_client(transcript):
    tool_use = SimpleNamespace(type="tool_use", input={"transcript": transcript})
    response = SimpleNamespace(content=[tool_use])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


def _analysis_client(exact_text, value):
    segments = [{
        "type": "quote", "gaap_status": "n/a", "display": "stat",
        "label": "Q3 Revenue", "exact_text": exact_text,
        "has_value": True, "value": value,
        "sentence": "Revenue was {value}.", "format": "usd",
    }]
    tool_use_block = SimpleNamespace(type="tool_use", input={"segments": segments})
    response = SimpleNamespace(content=[tool_use_block], stop_reason="tool_use")
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


class ImageFactIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.pdf_path = self.tmp / "exhibit.pdf"
        _build_pdf_with_chart_image(self.pdf_path, self.tmp / "chart.png")

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_images_transcript_is_present_in_the_document_text(self):
        document_text = extract_document_text(self.pdf_path, client=_vision_client(TRANSCRIPT))
        self.assertIn(f"[IMAGE p1]\n{TRANSCRIPT}\n[/IMAGE]", document_text)
        self.assertIn("attached exhibit", document_text)  # the real digital text is still there too

    def test_a_fact_transcribed_from_the_image_verifies_and_is_tagged_source_image(self):
        document_text = extract_document_text(self.pdf_path, client=_vision_client(TRANSCRIPT))
        segments = analyze_document(
            document_text, TITLE, client=_analysis_client("$42.7 million", 42_700_000.0),
        )
        segments = tag_image_sourced_segments(segments, document_text)

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["value"], 42_700_000.0)
        self.assertEqual(segments[0]["citation"], "$42.7 million")
        self.assertEqual(segments[0]["source"], "image")

    def test_a_claimed_citation_not_actually_in_the_transcript_still_fails_verification(self):
        # The image path gets no special leniency - a fabricated citation
        # against the transcript is rejected exactly like a fabricated
        # citation against any other source text.
        document_text = extract_document_text(self.pdf_path, client=_vision_client(TRANSCRIPT))
        with self.assertRaises(ValueError):
            analyze_document(
                document_text, TITLE,
                client=_analysis_client("$99.9 million", 99_900_000.0),
            )


if __name__ == "__main__":
    unittest.main()
