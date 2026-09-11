"""Tests for L1 image/OCR-derived facts - specs/slice-50/spec.md, Done
when #3. Uses a mocked Anthropic client throughout except where a test
specifically proves no client is ever touched: no real API call, no
cost, no network dependency.
"""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from analystos.l1.image_facts import (
    extract_image_transcripts,
    render_image_blocks,
    tag_image_sourced_segments,
)


def _pdf_with_image(pdf_path, png_path, text="Q3 Revenue: $42.7 million"):
    img = Image.new("RGB", (400, 200), "white")
    ImageDraw.Draw(img).text((20, 80), text, fill="black")
    img.save(png_path)

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawString(60, 700, "Some intro text before the chart image.")
    c.drawImage(str(png_path), 60, 500, width=300, height=150)
    c.save()


def _fake_client(transcript):
    tool_use = SimpleNamespace(type="tool_use", input={"transcript": transcript})
    response = SimpleNamespace(content=[tool_use])
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


class ExtractImageTranscriptsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_document_with_no_images_returns_empty_and_never_resolves_a_client(self):
        path = self.tmp / "plain.pdf"
        c = canvas.Canvas(str(path), pagesize=letter)
        c.drawString(60, 700, "No images here at all.")
        c.save()

        # If this ever called _resolve_client(None), it would try to build
        # a real anthropic.Anthropic() and - with no key configured - raise.
        # Not raising is itself the proof the guard held.
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            results = extract_image_transcripts(path, client=None)
        self.assertEqual(results, [])

    def test_an_embedded_image_is_transcribed_via_the_provided_client(self):
        pdf_path = self.tmp / "chart.pdf"
        _pdf_with_image(pdf_path, self.tmp / "chart.png")
        client = _fake_client("Q3 Revenue: $42.7 million")

        results = extract_image_transcripts(pdf_path, client=client)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["page"], 1)
        self.assertEqual(results[0]["transcript"], "Q3 Revenue: $42.7 million")

    def test_an_empty_transcript_contributes_nothing(self):
        pdf_path = self.tmp / "chart.pdf"
        _pdf_with_image(pdf_path, self.tmp / "chart.png")
        client = _fake_client("")

        results = extract_image_transcripts(pdf_path, client=client)
        self.assertEqual(results, [])

    def test_a_crop_or_transcribe_failure_is_skipped_not_fatal(self):
        pdf_path = self.tmp / "chart.pdf"
        _pdf_with_image(pdf_path, self.tmp / "chart.png")
        client = _fake_client("Q3 Revenue: $42.7 million")

        with patch("analystos.l1.image_facts._crop_image_bytes", side_effect=ValueError("bad crop")):
            results = extract_image_transcripts(pdf_path, client=client)
        self.assertEqual(results, [])


class RenderImageBlocksTest(unittest.TestCase):
    def test_a_transcript_is_rendered_as_a_delimited_block(self):
        blocks = render_image_blocks([{"page": 2, "transcript": "Q3 Revenue: $42.7 million"}])
        self.assertEqual(blocks, ["[IMAGE p2]\nQ3 Revenue: $42.7 million\n[/IMAGE]"])

    def test_no_transcripts_renders_no_blocks(self):
        self.assertEqual(render_image_blocks([]), [])


class TagImageSourcedSegmentsTest(unittest.TestCase):
    def test_a_segment_citing_image_text_is_tagged(self):
        document_text = (
            "Some intro text.\n\n[IMAGE p1]\nQ3 Revenue: $42.7 million\n[/IMAGE]"
        )
        segments = [{"type": "quote", "citation": "$42.7 million"}]
        out = tag_image_sourced_segments(segments, document_text)
        self.assertEqual(out[0]["source"], "image")

    def test_a_segment_citing_digital_text_is_left_untouched(self):
        document_text = (
            "Revenue was $10.0 million this quarter.\n\n"
            "[IMAGE p1]\nQ3 Revenue: $42.7 million\n[/IMAGE]"
        )
        segments = [{"type": "quote", "citation": "$10.0 million"}]
        out = tag_image_sourced_segments(segments, document_text)
        self.assertNotIn("source", out[0])

    def test_a_list_citation_computed_segment_is_also_tagged(self):
        document_text = "[IMAGE p1]\nQ3: $42.7 million, Q2: $38.1 million\n[/IMAGE]"
        segments = [{"type": "computed", "citation": ["$42.7 million", "$38.1 million"]}]
        out = tag_image_sourced_segments(segments, document_text)
        self.assertEqual(out[0]["source"], "image")

    def test_no_image_blocks_at_all_leaves_every_segment_untouched(self):
        segments = [{"type": "quote", "citation": "$10.0 million"}]
        out = tag_image_sourced_segments(segments, "Revenue was $10.0 million this quarter.")
        self.assertNotIn("source", out[0])


if __name__ == "__main__":
    unittest.main()
