# Slice 26 — narrated analysis: read any document, verify every number

## Goal

`income_statement` is the only template that exists, and it only works on
data shaped like an income statement (a period-like column, recognized line
items). The Company/Estimated-Revenue/Estimated-Employees file that
surfaced this gap live failed cleanly - honest, but not useful. This slice
makes AnalystOS read *any* document - table-shaped or not, any of the five
supported formats - and produce a real, executive-quality report from it,
while keeping the one rule that doesn't bend: every number shown is either
a real quote from the source, verified with an exact substring check, or a
computed value whose arithmetic is independently recomputed and checked.
The model chooses what's worth saying and how; it never gets to just state
a number.

This is not a detour from the architecture - `docs/architecture.md`
describes L2 as "retrieval + analysis over the evidence graph. Every claim
points back into L0." What shipped through Slice 25 (lookup/growth/ratio,
one template) is a deliberately thin first slice of that layer. This is the
fuller version of the same layer, bound by the same rule.

**Design note:** this spec reflects the final design as actually built -
it evolved substantially through live discussion (see `docs/decisions.md`,
2026-09-05) from an earlier draft that generated a small menu of pre-built
stats (sum/average/max/min) for the model to pick from. That approach was
replaced because it still forced every document into a typed table first;
this one doesn't.

## Design decisions

- **No forced table extraction.** `analystos/l1/document_text.py` reads a
  document's real text - paragraphs, bullet points, table cells rendered as
  readable text - the same way for all five formats. A memo or a slide deck
  with no table reads the same as a spreadsheet.
- **The model reads everything and decides what matters; it never supplies
  a number.** `analystos/l2/analyze.py` sends the whole document text to
  Claude (strict tool use, not free text) and gets back segments - each a
  `quote`, a `computed` value, or plain `prose`. A quote's `exact_text` is
  checked with a real substring match against the actual source text. A
  computed value's raw operands get the same check, and its arithmetic
  (`sum`/`average`/`ratio`/`growth_percent`/`percent_of_total`) is
  independently recomputed and compared to the model's claimed result - a
  citation proves a quote is real, it says nothing about whether math
  performed on top of it is correct, which is exactly why this second check
  exists. Prose is scanned for stray digits and rejected if any appear. A
  segment that fails verification is dropped, not shown; a report where
  nothing survives is a real `ValueError`, never a silent partial success.
- **A number renders as a number when that's the point.** Each segment
  carries its own `display`: `"stat"` for a standalone labeled figure,
  `"inline"` for a sentence with surrounding context - the model's choice
  per figure, not a global setting.
- **Model: Claude Sonnet 5, not Opus 5** - a disclosed latency call, not a
  cost call. `api/analyze.py` runs as a Vercel function with a real
  10-second ceiling; Sonnet 5 reliably fits, Opus 5's always-on extended
  thinking makes that a real risk.
- **This is the new default, not a replacement.** `build_report` runs this
  path only when *neither* `asks` nor `template` is given at all - the
  original schema/table-driven path is unchanged and costs nothing extra
  when explicitly requested.
- **A new required secret, `ANTHROPIC_API_KEY`, on Vercel**, separate from
  anything used to build this code, with a real, small, ongoing per-report
  cost.
- **Disclosed residual risk:** a text value from the source (e.g. a
  company name) still reaches the model as data it can quote or reason
  about, mitigated only by an explicit system-prompt instruction that data
  is never instructions. Verification catches every fabricated *number*;
  it cannot catch manipulated *wording* smuggled in through a text field.
- **Tested entirely against a mocked Anthropic client** - this build
  environment had no `ANTHROPIC_API_KEY` and no path to the real API.
  Real output quality can only be confirmed with a real key.

## Included

- `analystos/l1/document_text.py` - `extract_document_text(path) -> str`,
  dispatched by extension, one text-in contract for all five formats.
- `analystos/l2/analyze.py` - `analyze_document(document_text, title,
  client=None) -> list[verified segment]`; the verification logic described
  above, in full, with `client` injectable for tests.
- `analystos/l4/export.py` - `render_narrated_section(title, source_hash,
  segments, currency_unit="actual") -> str`, producing the exact same
  overall shape `render_section` already does (title, paragraphs, `---`,
  numbered footnotes) - `render_html`/`render_pdf` need no changes at all
  to render this too.
- `analystos/pipeline.py` - `build_report`: neither `asks` nor `template`
  given now runs the narrated path instead of raising; both given is still
  an error. New `llm_client` passthrough parameter for testability.
- `requirements.txt` / `docs/decisions.md` - `anthropic==1.4.0` pinned,
  full reasoning recorded.
- Tests: `document_text` extraction per format (prose *and* tables, proving
  neither is required); `analyze_document`'s verification logic against a
  mocked client - a real quote kept, a fabricated quote rejected, correct
  math kept, **fabricated math rejected even when both operands are real,
  cited numbers** (the core guarantee), prose with a stray digit rejected,
  all-segments-rejected raises; `render_narrated_section`'s stat/inline/
  prose rendering and its compatibility with `render_html`; `build_report`
  with neither `asks` nor `template` running the new default end to end
  against a mocked client.

## Done when

1. `extract_document_text` returns real, readable text for prose-only
   content (no table at all) in every one of the five formats - not just
   for files that happen to contain a table.
2. A real, verified quote from `analyze_document` produces a finding whose
   displayed number is the model-referenced source value, confirmed
   against a mocked client.
3. A fabricated quote, or fabricated math on top of two real cited numbers,
   or prose containing a stray digit, is rejected before it ever reaches a
   rendered report - each proven with a dedicated test against a mocked
   client returning exactly that.
4. `build_report` / `run_job` with neither `asks` nor `template` given at
   all runs the narrated path and produces a real section; giving both
   still raises; giving exactly one behaves exactly as it did before this
   slice.
5. `render_narrated_section`'s output parses correctly through
   `render_html`/`render_pdf` - including a stat segment's bold label,
   which needed one small addition to both (see "Verified beyond the test
   suite" - found live, not anticipated in the original design).
6. `python3 -m unittest discover -s tests -v` passes (with the venv active)
   using only the mocked client - no dependency on a real
   `ANTHROPIC_API_KEY` or network access to run clean.

## Verified beyond the test suite

Ran the real pipeline end to end against the actual Company/Estimated-
Revenue/Estimated-Employees-shaped CSV that started this slice, with a
realistic mocked model response (not just the minimal cases in the unit
tests), and read the actual rendered `section.md`/HTML/PDF output directly.
Found and fixed one real bug this way: a stat segment's `**Label:**`
markdown was showing up as literal asterisks in the HTML and PDF output -
`render_html`/`render_pdf` had no bold-conversion at all. Fixed by adding
one shared regex-based conversion to both (`**text**` -> `<strong>`/`<b>`),
with a dedicated regression test.

Also confirmed, by deliberately constructing bad model output and running
it through the real pipeline (not just isolated unit assertions):
- A `percent_of_total` claim whose `total` is a *computed* value (a sum),
  not something written verbatim anywhere in the source, is correctly
  rejected - chaining one computed value into another isn't supported (see
  "Not in this slice"), and the system fails closed on it rather than
  fabricating a citation for the total.
- The same claim succeeds once the total is something the source document
  actually states outright - proving the sub-case that should work, does.
- A single malformed segment (missing its `{value}` placeholder) mixed in
  with otherwise-valid ones is dropped silently; the rest of the report
  still renders correctly - proving partial failure doesn't take down an
  entire report.

## Not in this slice

- **Redesigning `site/upload.html`'s UI for the new default.** Wired
  minimally: `api/analyze.py`'s `template` form field, omitted entirely,
  now runs this path (`analyze.js`, unchanged, just no longer sends a
  default `"income_statement"`). The page still shows a schema field and a
  "Detect columns" step built for the old path - real, disclosed follow-up
  work to simplify, since neither is the point of this one.
- **Chaining a computed value into another computation** - e.g. "percent of
  a computed total" where the total itself isn't written anywhere in the
  source, only derived. Confirmed live (see "Verified beyond the test
  suite"): the verifier correctly rejects this today rather than fabricate
  a citation for an unquoted total. Supporting it safely - probably by
  letting a computed segment cite another computed segment's already-
  verified result instead of requiring a raw quote - is real follow-up
  work, not silently broken.
- **Catching manipulated wording carried in through a text value** (as
  opposed to a fabricated number, which verification does catch).
- **Multi-fact, single-sentence prose that weaves several numbers
  together.** Still one citation/computation per segment - keeps
  verification simple and airtight.
- **Retrying or regenerating a rejected segment.** Dropped, not retried -
  keeps the failure mode obvious.
- **New operation types beyond sum/average/ratio/growth_percent/
  percent_of_total.** A real, likely next step, not this slice.
- **OCR / scanned or image-only PDFs**, and any format outside the five
  already supported. Still explicitly out of scope, same reasoning as
  Slice 23's decisions.md entry.
- **Actually setting `ANTHROPIC_API_KEY` on the live Vercel project.** Same
  category as `ANTHROPIC_ACCESS_CODE` before it - a manual dashboard step
  for after this merges.
