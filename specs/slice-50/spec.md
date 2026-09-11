# Slice 50 — multi-column PDF reading order + image/OCR-derived facts

## Goal

Two of the largest remaining gaps from the round-2 backend audit, tackled
together because both live in `analystos.l1` and both change what "the
document's real text" means before anything downstream sees it:

1. `analystos/l1/document_text.py`'s PDF path reads a page's text in
   `pdfplumber`'s default order, which - confirmed by direct experiment
   against a real two-column test PDF built for this slice - **interleaves
   columns line by line** ("Left column line 1 ... Right column line 1
   ... Left column line 2 ...") instead of reading one column fully before
   the next. A person reading the same PDF would never read it that way,
   and a report built from interleaved text can misattribute a sentence
   fragment to the wrong paragraph entirely.
2. An image or chart embedded in a source document is invisible to
   AnalystOS today - no OCR, no vision call, nothing. A number that only
   exists as a rendered image (a scanned exhibit, a chart with a labeled
   callout) can never become a citable fact, however material it is.

## Included

### 1. Column-aware PDF text extraction

- A new module, `analystos/l1/pdf_columns.py` - `extract_page_text(page)`
  takes one `pdfplumber` `Page` and returns its text in real reading
  order.
- Detection, not assumption: every page is inspected independently (a
  title page can be single-column while the body is two-column).
  `pdfplumber.Page.extract_words()` gives every word's bounding box;
  the detector merges all words' horizontal extents into "used" bands
  across the page width and looks for a wide, empty vertical gutter
  splitting them into two or more non-trivial groups (each with enough
  words to be a real column, not stray margin text) roughly centered in
  the printable area. No such gutter -> **falls back to
  `page.extract_text()` unchanged** - every existing single-column
  fixture and test keeps working exactly as it does today.
- A detected multi-column page is read column by column, left to right;
  within a column, words are grouped into lines by vertical position and
  read top to bottom, exactly the order a person reads it in.
- Wired into `analystos/l1/document_text.py::_text_from_pdf` in place of
  the current `page.extract_text()` call - the one place PDF prose
  becomes the text `analyze_document` sees. The table-extraction path
  (`analystos.l1.extract_pdf`, used by the schema/template jobs) is
  unaffected - `pdfplumber.extract_tables()` already reasons about cell
  geometry directly and was never subject to this bug.

### 2. Image/chart-derived citable facts

- A new module, `analystos/l1/image_facts.py` -
  `extract_image_facts(path, client=None) -> [{"transcript": ..., "bbox": ...,
  "page": ...}, ...]` for PDF sources (scope below): finds every embedded
  image via `pdfplumber`'s `page.images`, rasterizes and crops just that
  region (`page.to_image()` + crop - no system dependency; confirmed
  working, no `poppler`/`tesseract` binary needed since `pdfplumber`
  rasterizes through `pypdfium2`, already a transitive dependency), and
  sends the cropped image to a real vision-capable call.
- **Transcribe, then verify against the transcript - the same
  verification `analyze_document` already trusts, not a new, weaker
  mechanism.** The vision call's only job is a literal, verbatim
  transcription of the image's visible text (never "extract the
  revenue figure" - that invites the exact fabrication risk this
  codebase's whole verification model exists to prevent). That
  transcript is then appended into the document text
  `extract_document_text` returns, clearly delimited (e.g. `[Image on
  page 2]: <transcript>`) - and from there it flows through the
  *existing, unmodified* `analyze_document` exact-substring citation
  check, exactly like any other paragraph. A fact "from" an image is
  therefore verified exactly as rigorously as any other quote: the
  claimed citation must be an exact substring of *something* - here, a
  transcript instead of digitally-extracted text.
- The one honest, disclosed limitation: the transcript is a model
  output, not a byte-exact digital extraction (unlike every other
  source format `hash_of`/citation-matching covers) - a transcription
  error is possible in a way a digital PDF's own text never is. Every
  segment sourced this way carries a `source: "image"` tag (new,
  parallel to `gaap_status`/`horizon`) so it renders visibly distinct -
  never silently indistinguishable from a digitally-extracted fact.

## Decisions (made before build)

1. **OCR mechanism: vision via the existing Anthropic client**, not
   `tesseract` - confirmed not installed on this machine, and a new
   system-level binary is a bigger ask than anything else this repo
   has taken on. Vision needed no new dependency and reused this
   codebase's one existing choke point for spend/error handling
   (`analyze.py`'s `_create_message`) unchanged.
2. **Format scope: PDF only** - the format named in the audit gap,
   proven end to end. DOCX/PPTX/XLSX embedded images remain a natural,
   separate follow-up, not attempted here.

## Done when

1. A two-column test PDF (built for this test - two distinct runs of
   text, left and right) is read via `extract_page_text`/
   `extract_document_text` in genuine column order - the left column's
   lines all appear, in order, before any line of the right column -
   proven by asserting the exact position of each column's text in the
   returned string (not just that all the text is present somewhere).
2. A single-column PDF (an existing fixture) is unaffected - its
   extracted text is identical to before this slice (the fallback
   path), proving nothing regressed for the common case.
3. A test PDF with an embedded image containing a discoverable numeric
   value (e.g., a rendered "Q3 Revenue: $42.7 million" snippet) produces
   at least one correctly extracted, citable fact sourced from that
   image, through the real (mocked-client) verification path - the
   claimed value matches the image's real transcript, exactly like any
   other quote segment, and it carries the `source: "image"` tag.
4. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Full chart *digitization* - reading bar heights/line positions off a
  chart image to reconstruct a data series. A materially harder
  computer-vision problem than transcribing visible text/numbers, and
  the task's own "Done when" only asks for one discoverable numeric
  value, not a reconstructed series.
- Image extraction for DOCX/PPTX/XLSX (see Open decision #2) - same
  underlying idea, different follow-up.
- OCR/vision for scanned (image-only) PDF *pages* with no embedded
  "image object" distinct from the page itself - out of scope; this
  slice targets a discrete image embedded alongside real digital text,
  not a fully scanned document.

## Built (post-implementation note)

- `analystos/l1/pdf_columns.py` - `extract_page_text(page)`. Detects a
  real column gutter from `page.extract_words()`'s own bounding boxes
  (largest empty horizontal gap, at least 6% of page width, splitting
  the page into two groups of at least 3 words each); reads the left
  column fully (top to bottom, line-grouped by vertical position),
  then the right. No gutter found -> `page.extract_text()` unchanged.
  Scoped to exactly one gutter (two columns), not general N-column
  layout - see the module docstring.
- `analystos/l1/image_facts.py` - `extract_image_transcripts` (crops
  each embedded image via `page.to_image()` + PIL crop, no system
  dependency, sends it to a real vision call whose only job is a
  literal transcription - never "extract the figure"),
  `render_image_blocks` (renders transcripts as
  `[IMAGE pN]\n...\n[/IMAGE]` blocks), and `tag_image_sourced_segments`
  (purely additive `source: "image"` tagging, applied *after*
  `analyze_document` returns - the verification call itself is
  completely unmodified). A document with zero embedded images never
  resolves a client at all - proven directly (with
  `ANTHROPIC_API_KEY` cleared) so a plain PDF is guaranteed to cost
  nothing extra and never require a key just because this code exists
  on the path.
- Wired into `analystos/l1/document_text.py` (`_text_from_pdf` now
  calls `extract_page_text` instead of `page.extract_text()`, and
  appends any image blocks) and `analystos/pipeline.py` (`llm_client`
  now threaded into `extract_document_text`; `tag_image_sourced_segments`
  called right after `analyze_document`).
- `Pillow==12.3.0` added to `requirements.txt` - already an existing
  transitive dependency of `pdfplumber`/`reportlab`, now imported
  directly (in tests, to build embedded-image fixtures) so it's pinned
  explicitly rather than relied on implicitly.
- 17 new tests across `tests/test_l1_pdf_columns.py` (4),
  `tests/test_l1_image_facts.py` (10), and
  `tests/test_l1_l2_image_fact_integration.py` (3, the real seam:
  extraction -> unmodified `analyze_document` verification -> tagging).
  451/451 project tests pass.
