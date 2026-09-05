# Slice 25 — universal upload: no hand-typed schema, every format treated the same

## Goal

You're right that once a table is extracted, the format it came from genuinely
doesn't matter - L0's citation, L2's answers, and L4's rendering have never
known or cared whether a row came from a CSV or a PowerPoint deck. The one
place format *did* still leak through was the upload experience itself: an
analyst had to (a) already know which of 4 extensions were accepted, (b) hand-
type an exact JSON schema, and (c) PDF wasn't accepted by the live site at
all. This slice removes all three - one upload path, every format AnalystOS
can already read (csv/xlsx/docx/pptx/pdf) treated identically, schema
detected automatically instead of typed.

## Design decisions

- **Schema auto-detection, not schema elimination.** A schema still exists
  internally - every value still needs a declared type to be safely
  formatted and computed on - it's just guessed from the data instead of
  hand-typed, using the exact same number-cleaning rules (`$`, commas, `%`,
  parens) `apply_schema` already uses to type a value, so "guessed" and
  "declared" schemas behave identically once resolved. An explicit schema is
  still honored exactly as before when one is given - nothing about existing
  callers (the CLI, `job.json` with a `"schema"` key) changes.
- **PDF's real constraint doesn't disappear - it becomes universal instead
  of special-cased.** A PDF table is still inferred from visual layout and
  can still be misread; that hasn't changed and can't be engineered away
  without OCR/heavier tooling (out of scope, per Slice 23's decisions.md
  entry). What changes: instead of PDF alone getting a confirm-before-cite
  gate, *every* format now gets a preview step before the report is
  generated - so PDF isn't treated as more restricted, the norm just moved
  to match it. Preview is read-only (no cell-value editing - same
  "accept-as-extracted-or-don't-use-it" boundary Slice 23 already drew);
  the auto-detected *schema* is editable, since a wrong guessed type is
  cheap to fix and self-checking (a bad override just raises a clear error
  when applied, same as it always has).
- **One extra shared module, not five rewrites.** Each format extractor
  already builds `(headers, numbered_raw_rows)` internally before typing
  them - that raw step is pulled out into its own function per extractor
  (`_raw_rows`), and a new `analystos.l1.detect.extract_any` dispatches to
  it by extension and guesses a schema when none is given. Every existing
  public function (`extract_table`, `extract_table_xlsx`, etc.) keeps its
  exact signature and behavior - verified by their existing tests passing
  unchanged.
- **Stateless end to end, same as everything else.** The browser calls a new
  preview endpoint first, then re-submits the same file to the real one -
  no server-side session or cache of "what was previewed." A `.pdf` source
  going straight to the real endpoint without ever previewing still requires
  the same `pdf_confirmed` flag Slice 23 built - the safety guarantee holds
  even for a direct API/CLI call that skips the UI entirely.

## Included

- `analystos/l1/schema.py` - `guess_schema(numbered_raw_rows, headers)`:
  a column is `"number"` if every non-empty value in it parses as one
  (reusing `_clean_number_token`), else `"text"`. Same heuristic
  `analystos/scaffold.py` already used for CSV, now shared instead of
  duplicated - `scaffold.py` refactored to call it too.
- `analystos/l1/extract.py`, `extract_xlsx.py`, `extract_docx.py`,
  `extract_pptx.py`, `extract_pdf.py` - each gains a `_raw_rows(...)`
  extraction-only function; each public `extract_table_*` becomes a thin
  `_raw_rows` + `apply_schema` wrapper, unchanged behavior.
- `analystos/l1/detect.py` (new) - `extract_any(source_path, schema=None,
  extract_options=None) -> (resolved_schema, rows)`: dispatches by
  extension, guesses a schema when none is given.
- `analystos/pipeline.py` - `build_report`'s `schema` parameter becomes
  optional (`None` = auto-detect); `_extract_rows`/the per-suffix dispatch
  is replaced by `extract_any`. The PDF confirm-before-cite gate is
  unchanged in behavior, now reachable via any caller (CLI or API) the same
  way.
- `api/analyze.py`:
  - `_ALLOWED_EXTENSIONS` gains `.pdf`.
  - `schema` form field becomes optional (auto-detect when omitted);
    `pdf_confirmed` becomes a real form field, passed through to
    `build_report`.
  - New `POST /api/extract` - same access-code gate, takes just `file`;
    returns `{"schema": {...}, "rows": [...], "warning": "..."|null}` (a
    PDF source gets the same "extraction can misread a table" warning text
    the CLI's confirm error already carries). Nothing persists, same
    guarantee as `/api/analyze`.
- `site/upload.html`:
  - File picker now accepts `.pdf` too.
  - A "Detect columns" step: calls `/api/extract`, fills the schema
    textarea with the guessed JSON automatically (still visible, still
    editable - not hidden from the analyst), and shows a small read-only
    preview table. A PDF source shows the misread-risk warning inline.
  - "Generate report" still posts to `/api/analyze`, now with the
    (possibly-edited) auto-filled schema and, for a PDF source that's been
    previewed, `pdf_confirmed=true`.
- `docs/decisions.md` - records the auto-detection heuristic and the
  "PDF's constraint becomes universal, not special-cased" call.
- Tests across all of the above - one per "Done when" below.

## Done when

1. `extract_any` correctly guesses `"number"` vs `"text"` per column for
   real data in every one of the five formats, and honors an explicit
   schema unchanged when one is given.
2. `build_report`/`run_job` work with no `"schema"` at all - auto-detected,
   end to end, citing real cells exactly as an explicit schema would.
3. `POST /api/analyze` works with `.pdf`, and with `schema` omitted, for
   every format; the PDF confirm-before-cite gate still refuses an
   unconfirmed PDF exactly as it did before this slice.
4. `POST /api/extract` returns a real guessed schema and real preview rows
   for a real upload of each format, gated by the same access code, with
   nothing persisted afterward.
5. In a real browser: picking a file (PDF included) and clicking "Detect
   columns" fills the schema field and shows a preview with no JSON ever
   hand-typed; "Generate report" then produces the real cited report.
6. Every existing extractor's own test suite still passes unchanged -
   proof the `_raw_rows` split didn't change behavior.
7. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Verified beyond the test suite

Drove a real Chromium browser (Playwright) against the real API, served
locally alongside `site/`: uploaded a real CSV with **no schema ever
typed**, clicked "Detect columns," confirmed the auto-filled schema and
preview table showed the real values, then "Generate report" produced the
real cited report. Repeated with a real `reportlab`-built PDF: the preview
step additionally showed the misread-risk warning; "Generate report"
produced a real cited report from it too - the first time a PDF has ever
gone through the live upload page. Also confirmed a PDF submitted *without*
clicking "Detect columns" first still fails cleanly with the
confirm-required message, shown through the same error element as any other
failure - the safety gate holds even if the UI step is skipped.

Found and fixed two real issues this way, not just by reading the code:
a bug where `guess_schema` silently starved every column after the first
when given a one-shot iterator (see `docs/decisions.md`), and a confusing
error message that told a browser user to edit a `job.json` file that, in
that context, doesn't exist - reworded to name both the CLI and the live
site's own step.

## Not in this slice

- **Editing extracted cell values in the preview.** Still read-only, same
  boundary Slice 23 drew - fixing a genuinely wrong extracted value still
  means fixing the source file and re-uploading.
- **OCR / scanned or image-only PDFs.** Still explicitly out of scope, same
  reasoning as Slice 23's decisions.md entry.
- **File types with no table at all** (a `.txt` file of prose, an image, a
  plain Word doc with no table) - still a clean rejection. "Universal"
  means every format AnalystOS can extract a table from is treated
  identically, not that non-tabular content is analyzed - there is no cell
  to cite a claim to in a paragraph of prose, and the citation guarantee
  (`CLAUDE.md`: "every analytical conclusion must eventually carry a
  citation to its source") doesn't bend for this.
- **Actually setting `ANALYSTOS_ACCESS_CODE` on the live Vercel deployment.**
  Still the one open item from Slice 22 - separate from this slice, next up
  once this merges.
