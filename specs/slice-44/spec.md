# Slice 44 — one real table-parsing standard + footnote detection

## Goal

Foundation work for the GAAP/non-GAAP detection work that comes after
this: that later work needs to reason about real, typed table structure
and real footnoted adjustments, and today's narrated-default path
(`analystos.l1.document_text`) doesn't give it either - it flattens every
table with its own separate, ad hoc cell-walk, and has no concept of a
footnote at all. This slice makes both real, on the same code the
schema-driven path (`analystos.l1.detect.extract_any`) already trusts.

## Included

- Every format module (`extract.py`, `extract_docx.py`, `extract_pptx.py`,
  `extract_pdf.py`, `extract_xlsx.py`) gets an `all_tables(path)` function:
  every table in the document, in document order, as
  `[(headers, numbered_rows), ...]`, each one extracted through the exact
  same `_raw_rows` the schema-driven path already calls - not a new
  parallel implementation.
- `analystos.l1.document_text` rewritten: every per-format `_text_from_*`
  function now calls that format's `_raw_rows` directly (with its own
  natural table/sheet labels: "Table N:", "Sheet: <name>", etc.) instead
  of independently walking raw cell objects. One real, demonstrable bug
  fixed by this, not just a refactor: an Excel cell formatted as a
  percentage stores its *fraction* (`0.571` for what a person sees as
  "57.1%") - the old flattening showed that raw fraction verbatim; the
  real typed path already rescaled it correctly, and the narrated path
  now does too.
- `analystos.l1.footnotes.extract_footnotes_docx` - real, structural
  footnote-marker-to-content linking for `.docx`, the one format that
  genuinely has this (Word's OOXML footnote relationship - a reference
  element in the body with an `id`, linked to real content in a separate
  `footnotes.xml` part). The module docstring explicitly confirms, with
  format-specific reasoning, why PDF, PPTX, XLSX, and CSV do **not**
  qualify for "real structural detection" the same way - see that
  docstring for the full reasoning; PDF in particular has no reliable
  structural footnote concept through `pdfplumber` (or any untagged PDF,
  which is the overwhelming majority of real ones) - only a font-size/
  position heuristic is possible there, which is guesswork, not structural
  detection, and deliberately not built as part of this slice.
- `document_text._text_from_docx` now includes a document's real
  footnotes as their own block, each one tagged with the id a reader can
  match back to its marker.

## Done when

1. `python3 -m unittest discover -s tests -v` passes.
2. One test per format (5 total,
   `tests/test_l1_table_unification.py`) proves the narrated-default path
   and the schema-driven path parse the same real table through the same
   function - each test spies on that format's `_raw_rows` and confirms
   it's actually invoked during `extract_document_text` (0 calls under the
   pre-fix code, confirmed directly: stashed this slice's changes and
   re-ran the same 5 tests - all 5 failed, all for that exact reason,
   before restoring the fix).
3. A real `.docx` fixture with a genuine OOXML footnote relationship
   (built by hand - no fixture file or `python-docx` API exists for this
   in the repo) is correctly linked marker-to-content, and a test
   confirms it - `tests/test_l1_footnotes.py`.
4. Direct answer, asked explicitly: the narrated-default path uses the
   exact same table-parsing functions as the schema-driven path - each
   format's `_raw_rows` in `analystos.l1.extract*` - not a separate
   reimplementation. Proven by the spy-based tests above, not just
   asserted.

## Not in this slice

- GAAP/non-GAAP dual-reporting detection or boilerplate detection - the
  next task this one is explicitly foundation for, not part of it.
- A PDF footnote heuristic (font-size/position based) - deliberately not
  built; see the reasoning in `analystos.l1.footnotes`'s docstring. A
  real, disclosed-as-heuristic detector is a different, separable piece
  of work with a different reliability bar.
- Multi-table structural improvements beyond enumeration (e.g., detecting
  that two adjacent tables are actually one table split across a page
  break) - out of scope; each table is still extracted as its own
  distinct unit, same as the schema-driven path already does.
