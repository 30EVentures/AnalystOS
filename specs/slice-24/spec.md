# Slice 24 — L4: real `.pdf` output (`reportlab`)

## Goal

A real generated `.pdf`, not "open the HTML and print" - the last item on
the current roadmap phase before R1. `render_html` (Slice 13) gave the CLI a
styled, printable page; this slice adds `render_pdf`, an actual PDF file
built with `reportlab`, alongside it - both are just different renderings of
the exact same parsed section structure.

## Design decisions

- **Scope: L4/CLI only, matching Slice 23's own discipline.** `api/analyze.py`
  and `site/upload.html` are not touched. Adding a real PDF *download* to the
  live web flow is a genuine, separate product decision (a new API response
  shape - base64 in JSON? a second binary route? - plus a UI affordance for
  it) worth its own scoped slice, not a rider on this one. The roadmap
  labels this slice "L4," the same label Slice 13 (styled HTML) carried
  before it, and that slice didn't touch the API either.
- **No clickable in-PDF footnote links.** `render_html` turns each `[n]`
  marker into a same-page anchor link; a PDF has no equivalent low-effort
  mechanism worth building here. `render_pdf` renders `[n]` as a plain
  superscript number - visually consistent, not clickable. A real, disclosed
  gap, not an oversight.
- **Shared parsing, not a second parser.** `render_html` already splits a
  `render_section` string into a title, body paragraphs, and footnote lines.
  That logic is extracted into one `_parse_section` helper both renderers
  call, instead of `render_pdf` re-deriving the same structure its own way -
  verified as a pure refactor (`render_html`'s own test suite passes
  unchanged).
- Verified directly before finalizing this design (not just read about):
  built a real `reportlab` `Paragraph`/`Spacer`/`HRFlowable` document with a
  superscript marker and a bold footnote number, got back real PDF bytes
  (`%PDF-` header), and read the *exact* expected text back out with
  `pdfplumber` (already a dependency since Slice 23) - title, body sentence,
  and footnote all present and correctly separated.

## Included

- `analystos/l4/export.py`:
  - `_parse_section(section_md)` - new shared helper (see above);
    `render_html` refactored to use it, behavior unchanged.
  - `render_pdf(section_md) -> bytes` - builds a real PDF in memory with
    `reportlab.platypus` (`SimpleDocTemplate`, `Paragraph`, `Spacer`,
    `HRFlowable`): a title, one paragraph per finding with its `[n]` marker
    as a superscript, a rule, then the footnotes in a smaller gray style -
    visually mirroring `render_html`'s layout. Returns bytes; does not write
    a file (same contract as `render_section` returning a string).
- `analystos/pipeline.py` - `main()` (the `python3 -m analystos <job-dir>`
  entrypoint) now also writes `section.pdf` alongside the existing
  `section.md`/`section.html`, using `render_pdf`. The auto-open-on-macOS
  behavior still opens `section.html`, unchanged - the PDF is an added
  deliverable file, not a change to what previews.
- `docs/decisions.md` - notes `reportlab`, pinned since Slice 23 for test
  fixtures only, is now used for its actual intended purpose.
- `tests/test_l4_export.py` - `render_pdf` returns bytes starting with the
  real `%PDF-` magic header; reading the PDF back with `pdfplumber` finds
  the title, every finding's rendered text, and every footnote's citation
  text - a real content round-trip, not just a byte-count or magic-header
  check.
- `tests/test_pipeline.py` - `main()`'s entrypoint test extended to also
  assert `section.pdf` exists and is a real PDF (checked via `pdfplumber`,
  not just that the file exists).

## Done when

1. `render_pdf` returns real PDF bytes (`%PDF-` header) for a section
   produced by `render_section`.
2. Reading that PDF back (via `pdfplumber`) finds the title, every finding's
   text with its answer already substituted, and every footnote's citation
   text - nothing silently dropped or garbled.
3. `render_html`'s existing tests still pass unchanged after the
   `_parse_section` refactor - proof it's a pure extraction, not a behavior
   change.
4. `python3 -m analystos <job-dir>` writes a real `section.pdf` alongside
   `section.md`/`section.html`.
5. `api/analyze.py` and `site/upload.html` are unchanged - confirmed by the
   existing test suites for both still passing with no new cases needed
   there.
6. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Verified beyond the test suite

Ran the real CLI (`python3 -m analystos <job-dir>`) against a real copy of
the golden fixture and rendered the resulting `section.pdf` to an image
(via `pdfplumber`'s own page-to-image, not just text extraction) to look at
it directly - not just confirm the text round-trips. It's a real, legible
one-page PDF: the title, three body sentences each with a correctly
positioned superscript footnote marker, a horizontal rule, and three gray
footnotes citing the real SHA-256 source hash - matching the design intent
exactly, not just passing an assertion.

## Not in this slice

- **A "Download PDF" button on the live site, or a PDF-returning API
  route.** Real, valuable, disclosed future work - not this slice. Until
  then, the live MVP's only path to a PDF is still the browser's own Print,
  same as it's been since Slice 21.
- **Clickable in-PDF footnote navigation.** Superscript markers only: see
  "Design decisions" above.
- **Custom fonts, a logo, or any branding in the PDF.** Plain, readable,
  `reportlab`'s default styles - a working paper, not a marketing document.
- **Page numbers, headers/footers, or multi-page layout tuning.** `reportlab`
  paginates automatically for a long section; nothing here controls how.
