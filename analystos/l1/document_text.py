"""L1 - read a document's real content as plain text, whatever shape it is.

Every other L1 extractor assumes the source *is* a table - a real
assumption that doesn't hold for a memo, a contract, a slide deck with
bullet points instead of a grid, or any document a person would actually
hand an analyst. ``extract_document_text`` makes no such assumption: it
reads whatever text content the format actually holds - paragraphs, bullet
points, table cells rendered as readable text - the same way regardless of
which of the five supported extensions it is. This is what makes "upload
anything, read it exactly as it is" real: one function, one text-in
contract, dispatched internally by extension.

Tables aren't ignored - they're rendered as plain, readable pipe-delimited
text alongside everything else, so a spreadsheet's numbers are still in the
returned text; they just aren't parsed into typed cells the way
``analystos.l1.detect.extract_any`` does for the schema-driven path. See
``specs/slice-26/spec.md``.
"""

import csv

import pdfplumber
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation

SUPPORTED_EXTENSIONS = (".csv", ".docx", ".pdf", ".pptx", ".xlsx")


def _row_to_line(cells):
    return " | ".join((c or "").strip() for c in cells)


def _text_from_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return "\n".join(_row_to_line(row) for row in rows if any((c or "").strip() for c in row))


def _text_from_xlsx(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        chunks = []
        for ws in wb.worksheets:
            lines = [f"Sheet: {ws.title}"]
            for row in ws.iter_rows():
                values = [str(c.value) if c.value is not None else "" for c in row]
                if any(v.strip() for v in values):
                    lines.append(_row_to_line(values))
            if len(lines) > 1:
                chunks.append("\n".join(lines))
        return "\n\n".join(chunks)
    finally:
        wb.close()


def _text_from_docx(path):
    doc = Document(path)
    chunks = []
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if paragraphs:
        chunks.append("\n".join(paragraphs))
    for i, table in enumerate(doc.tables):
        lines = [f"Table {i + 1}:"]
        for row in table.rows:
            lines.append(_row_to_line(c.text for c in row.cells))
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def _text_from_pptx(path):
    prs = Presentation(path)
    chunks = []
    for slide_i, slide in enumerate(prs.slides, start=1):
        lines = [f"Slide {slide_i}:"]
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                lines.append(shape.text_frame.text.strip())
            elif shape.has_table:
                for row in shape.table.rows:
                    lines.append(_row_to_line(c.text for c in row.cells))
        if len(lines) > 1:
            chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def _text_from_pdf(path):
    chunks = []
    with pdfplumber.open(path) as pdf:
        for page_i, page in enumerate(pdf.pages, start=1):
            lines = [f"Page {page_i}:"]
            text = page.extract_text()
            if text:
                lines.append(text.strip())
            for table in page.extract_tables():
                lines.append("\n".join(_row_to_line(row) for row in table))
            if len(lines) > 1:
                chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


_EXTRACTORS = {
    ".csv": _text_from_csv,
    ".xlsx": _text_from_xlsx,
    ".docx": _text_from_docx,
    ".pptx": _text_from_pptx,
    ".pdf": _text_from_pdf,
}


def extract_document_text(path):
    """Return the real text content of the document at ``path``.

    Dispatches by extension - one of ``SUPPORTED_EXTENSIONS`` - to a
    format-specific reader, but every reader returns the same thing: plain
    text, paragraphs and rendered tables both included, nothing parsed into
    typed cells. Raises ``ValueError`` for an unsupported extension or a
    document with no readable text at all.
    """
    suffix = path.suffix.lower()
    if suffix not in _EXTRACTORS:
        raise ValueError(
            f"unsupported source file type {suffix!r}; "
            f"expected one of {sorted(SUPPORTED_EXTENSIONS)}"
        )
    text = _EXTRACTORS[suffix](path).strip()
    if not text:
        raise ValueError("document has no readable text")
    return text
