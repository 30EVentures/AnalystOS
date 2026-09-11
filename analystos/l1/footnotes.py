"""L1 - link a footnote marker in body text to its explanatory content,
where the source format genuinely has a structural relationship to link -
not a heuristic guess from font size or position.

Only ``.docx`` qualifies. Word's OOXML format has a real, structural
footnote mechanism: a footnote reference in the body
(``word/document.xml``) is a distinct XML element carrying an ``id``, and
the explanatory text lives in a separate part (``word/footnotes.xml``)
under a ``<w:footnote>`` element with the matching ``id`` - the same kind
of unambiguous, machine-readable relationship a table's real cell/row
structure has (see ``analystos.l1.extract_docx``), not an inferred one.
``python-docx`` (the library this repo already depends on) exposes no
public API for footnotes at all, so this module reads the two relevant
XML parts directly.

Every other supported format was checked against the same bar and does
*not* qualify, for format-specific reasons, not because it wasn't tried:

- **PDF** has no structural footnote concept accessible through
  ``pdfplumber`` (or, in general, through an *untagged* PDF, which is the
  overwhelming majority of PDFs actually seen in practice). A real,
  reliable link would need the PDF's optional tagged-structure tree,
  which very few real-world PDFs carry and ``pdfplumber`` doesn't expose.
  What *is* possible without that - guessing from a smaller font size and
  a bottom-of-page position - is a heuristic, not structural detection,
  and would misfire on plenty of real documents (a superscript exponent,
  a page number, a caption). Deliberately not built here; a heuristic
  detector is a different, separable piece of work with a different
  reliability bar, not this one.
- **PPTX** has no footnote mechanism at all - no footnote XML part, no
  reference/marker relationship. A slide's "notes" are presenter notes
  attached to the whole slide, not to a specific marker in the visible
  text, and are a different concept entirely.
- **XLSX** has no footnote mechanism either. Cell comments/notes are the
  closest analog, but they attach to a specific *cell*, not to a marker
  inline in running body text pointing at explanatory content elsewhere -
  a genuinely different relationship.
- **CSV** is flat tabular data with no markup at all - no structural
  concept of a footnote is possible.

See specs/slice-44/spec.md.
"""

import zipfile
import xml.etree.ElementTree as ET

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_QN = f"{{{_W_NS}}}"
_NON_CONTENT_TYPES = {"separator", "continuationSeparator"}
_DOCUMENT_PART = "word/document.xml"
_FOOTNOTES_PART = "word/footnotes.xml"


def _paragraph_text(p_el):
    """The plain text of a ``<w:p>`` element - every ``<w:t>`` inside it,
    in document order, concatenated. Matches how ``python-docx`` builds a
    paragraph's ``.text``, so the same string a caller already sees from
    ``python-docx`` is what a marker's surrounding context is drawn from.
    """
    return "".join(t.text or "" for t in p_el.iter(f"{_QN}t"))


def _footnote_texts(footnotes_xml_bytes):
    """``{footnote_id: footnote_text}`` for every real footnote in
    ``footnotes.xml`` - skips the ``separator``/``continuationSeparator``
    entries every Word document carries structurally but that are never
    real footnote content (page-break markup, not a citation)."""
    root = ET.fromstring(footnotes_xml_bytes)
    out = {}
    for footnote in root.findall(f"{_QN}footnote"):
        if footnote.get(f"{_QN}type") in _NON_CONTENT_TYPES:
            continue
        fid = footnote.get(f"{_QN}id")
        text = " ".join(
            _paragraph_text(p).strip() for p in footnote.findall(f"{_QN}p")
        ).strip()
        if fid is not None and text:
            out[fid] = text
    return out


def extract_footnotes_docx(path):
    """Every footnote marker in the document's body, linked to its real
    explanatory text - ``[{"id": ..., "marker_context": ..., "footnote_text": ...}, ...]``,
    in document order.

    ``marker_context`` is the full text of the paragraph the marker sits
    in - enough for a caller to place the footnote where it belongs
    without retyping the whole document. ``[]`` if the document has no
    ``footnotes.xml`` part at all (no footnotes) or no real (non-
    separator) footnotes in it - never an error; a document with no
    footnotes is a completely normal document.
    """
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if _DOCUMENT_PART not in names or _FOOTNOTES_PART not in names:
            return []
        document_xml = z.read(_DOCUMENT_PART)
        footnotes_xml = z.read(_FOOTNOTES_PART)

    footnote_text_by_id = _footnote_texts(footnotes_xml)
    if not footnote_text_by_id:
        return []

    root = ET.fromstring(document_xml)
    linked = []
    for p_el in root.iter(f"{_QN}p"):
        context = None
        for ref in p_el.iter(f"{_QN}footnoteReference"):
            fid = ref.get(f"{_QN}id")
            if fid not in footnote_text_by_id:
                continue  # a separator/continuationSeparator reference, not real content
            if context is None:
                context = _paragraph_text(p_el).strip()
            linked.append({
                "id": fid,
                "marker_context": context,
                "footnote_text": footnote_text_by_id[fid],
            })
    return linked
