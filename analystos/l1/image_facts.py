"""L1 - turn an image or chart embedded in a PDF into citable text.

An embedded image is invisible to every other L1 extractor - there is no
digital text to read, so a number that only exists as a rendered image (a
scanned exhibit, a chart with a labeled callout) could never become a
citable fact. This module finds every embedded image in a PDF
(``pdfplumber``'s own ``page.images``), rasterizes and crops just that
region (``page.to_image()`` - no system dependency: ``pdfplumber``
rasterizes through ``pypdfium2``, already a transitive dependency, not
``poppler``/``tesseract``), and sends the crop to a real vision-capable
model call.

The model's ONLY job is a literal, verbatim transcription of the image's
visible text - never "extract the revenue figure." Asking it to interpret
or compute anything from the image would reintroduce exactly the
fabrication risk this codebase's whole verification model exists to
prevent. The transcript is then treated by ``analystos.l1.document_text``
as ordinary document text and flows through the *unmodified*
``analystos.l2.analyze.analyze_document`` exact-substring citation check,
same as any other paragraph - a fact "from" an image is verified exactly
as rigorously as any other quote, the claimed citation must be an exact
substring of *something*, here a transcript instead of digitally-extracted
text.

The one honest, disclosed limitation: that transcript is itself a model
output, not a byte-exact digital extraction the way every other format's
text is - a transcription error is possible in a way a digital PDF's own
text never is. ``tag_image_sourced_segments`` (below) marks every segment
whose citation came from an image's transcript with ``source: "image"``,
so it renders visibly distinct, never silently indistinguishable from a
digitally-extracted fact. See specs/slice-50/spec.md.
"""

import base64
import re
import sys
from io import BytesIO

import pdfplumber

from analystos.l2.analyze import _create_message, _resolve_client

_MODEL = "claude-sonnet-5"
_MAX_TOKENS = 1024
_RESOLUTION = 150  # DPI used to rasterize the page before cropping

_SYSTEM_PROMPT = """\
You transcribe the literal, visible text inside an image cropped from a \
financial document - a chart label, an axis, a callout, a caption, a \
scanned exhibit. Transcribe ONLY what is visibly printed in the image, \
verbatim, exactly as it appears. Do not interpret, summarize, compute, or \
infer any value that is not literally rendered as text or numerals in the \
image. If the image has no legible text at all, return an empty string.

Call transcribe_image exactly once.
"""

_TOOL = {
    "name": "transcribe_image",
    "description": "Submit the literal transcription of the image's visible text.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"transcript": {"type": "string"}},
        "required": ["transcript"],
        "additionalProperties": False,
    },
}

_IMAGE_TAG = "IMAGE"
_IMAGE_BLOCK_RE = re.compile(
    rf"\[{_IMAGE_TAG} p(\d+)\]\n(.*?)\n\[/{_IMAGE_TAG}\]", re.DOTALL
)


def _crop_image_bytes(page, image, resolution=_RESOLUTION):
    """Rasterize just ``image``'s region of ``page`` to PNG bytes."""
    page_image = page.to_image(resolution=resolution)
    scale = resolution / 72  # PDF points -> pixels at this resolution
    bbox = (
        image["x0"] * scale, image["top"] * scale,
        image["x1"] * scale, image["bottom"] * scale,
    )
    cropped = page_image.original.crop(bbox)
    buf = BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()


def _transcribe(client, png_bytes):
    encoded = base64.standard_b64encode(png_bytes).decode("ascii")
    response = _create_message(
        client,
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "transcribe_image"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": encoded,
                }},
                {"type": "text", "text": "Transcribe this image's visible text verbatim."},
            ],
        }],
    )
    tool_use = next(
        (b for b in getattr(response, "content", []) if getattr(b, "type", None) == "tool_use"),
        None,
    )
    if tool_use is None:
        return ""
    result = tool_use.input if isinstance(tool_use.input, dict) else {}
    return (result.get("transcript") or "").strip()


def extract_image_transcripts(path, client=None):
    """Every embedded image in the PDF at ``path``, transcribed via a real
    vision call - ``[{"page": page_number, "transcript": str}, ...]`` for
    images that produced a non-empty transcript (an illegible/blank image
    contributes nothing, silently, the same way an empty table is skipped
    elsewhere in L1).

    A document with no embedded images at all returns ``[]`` without ever
    resolving a client or making a call - so a plain PDF (the overwhelming
    majority) costs nothing extra and never requires ``ANTHROPIC_API_KEY``
    just because this function exists on the extraction path.

    A single image that fails to crop or transcribe (corrupt image data, a
    transient API error) is skipped, logged to stderr, and never fails the
    rest of the document's extraction - deliberately broad
    ``except Exception`` here, because the failure surface of "arbitrary
    embedded image bytes plus a live model call" isn't one this codebase
    can enumerate the way a malformed table row can be.
    """
    with pdfplumber.open(path) as pdf:
        pending = [
            (page_i, page, image)
            for page_i, page in enumerate(pdf.pages, start=1)
            for image in page.images
        ]
        if not pending:
            return []

        client = _resolve_client(client)
        results = []
        for page_i, page, image in pending:
            try:
                png_bytes = _crop_image_bytes(page, image)
                transcript = _transcribe(client, png_bytes)
            except Exception as exc:
                print(
                    f"[analystos.l1.image_facts] skipped an image on page {page_i}: {exc!r}",
                    file=sys.stderr,
                )
                continue
            if transcript:
                results.append({"page": page_i, "transcript": transcript})
        return results


def render_image_blocks(transcripts):
    """``extract_image_transcripts``'s results rendered as delimited text
    blocks - one per image - ready to append to a document's plain text.
    The delimiter is what ``tag_image_sourced_segments`` looks for
    afterward to identify which part of the (already fully verified)
    document text came from an image rather than digital extraction."""
    return [
        f"[{_IMAGE_TAG} p{item['page']}]\n{item['transcript']}\n[/{_IMAGE_TAG}]"
        for item in transcripts
    ]


def tag_image_sourced_segments(segments, document_text):
    """Mark ``source: "image"`` on every verified segment whose citation
    text came from an embedded image's transcript block in
    ``document_text``, rather than digitally-extracted prose - purely
    additive metadata, never touching verification itself. A segment's
    citation was already checked as an exact substring of the *whole*
    document_text by ``analyze_document``; this only identifies *which
    part* of that already-verified text it came from. Segments with no
    image-sourced citation are left completely untouched (no ``source``
    key added at all).
    """
    blocks = [m.group(2) for m in _IMAGE_BLOCK_RE.finditer(document_text)]
    if not blocks:
        return segments

    for segment in segments:
        citation = segment.get("citation")
        texts = citation if isinstance(citation, list) else [citation] if citation else []
        if any(t and any(t in block for block in blocks) for t in texts):
            segment["source"] = "image"
    return segments
