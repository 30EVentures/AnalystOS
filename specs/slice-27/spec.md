# Slice 27 — a second pass writes the narrative; verification stays untouched

## Goal

Slice 26's narrated analysis renders one paragraph per verified fact, in
the order the model happened to extract them, with no real structure - no
executive summary, no grouping of related facts, no sentence that connects
two figures the model didn't already choose to connect in one segment.
That's a fact list with citations, not writing.

This slice adds a second model call that takes only the *already-verified*
facts from Slice 26 (never the raw document) and decides how to write
about them - what order, what to group together, what deserves its own
line versus a supporting clause. It cannot state a number itself. Every
number it wants to use is a `{{N}}` placeholder referencing a specific
verified fact by index; the actual value that appears in the final report
is always the one Slice 26 already verified and this code substitutes in,
never anything the model in this pass typed. If this pass produces
anything that references a fact that doesn't exist, or writes a stray
digit outside a placeholder, the whole narrative attempt is rejected and
the report falls back to Slice 26's plain per-segment rendering - a
worse-structured report is an acceptable outcome; an unverified number
reaching the page is not.

## Why a second call, not a bigger first prompt

Mixing "decide what's true" and "decide how to write it well" into one
model call means any prompt change aimed at better writing risks changing
what gets extracted or verified - the exact thing that must not regress.
Splitting them means `analystos/l2/analyze.py`'s extraction+verification
logic and tests are untouched by this slice entirely; the new
`analystos/l2/narrate.py` module only ever sees data that already passed
verification, and can fail outright with zero cost to correctness (the
report just falls back to today's rendering).

## Design

- **Input to the narrative pass is a manifest, not the document.**
  `analystos/l2/narrate.py`'s `write_narrative(segments, title, client)`
  builds a numbered list from Slice 26's verified `segments`: each citable
  fact (`quote`/`computed`, not `prose`) is listed as `Fact N [citable]:
  label="...", value=<its final rendered display string>`; each verified
  `prose` segment is listed as `Fact N [context, not citable]: "<text>"`
  and cannot be referenced by a placeholder - it's material the model may
  draw on for tone/content, but it isn't a citable number.
- **Strict tool use again, schema kept deliberately small.** The
  `write_narrative` tool takes one array, `paragraphs`, each just
  `{"text": string}` (required, no other properties) - one property,
  fully required, no optional-field combinatorics. Slice 26's original
  schema (`400 Schema is too complex`, `docs/decisions.md` 2026-09-05)
  is the reason this one stays this thin from the start.
- **`{{N}}` placeholders, never `refs` as a separate field.** A paragraph's
  citations are parsed directly out of its own text (`_PLACEHOLDER_RE`) -
  no second field that could disagree with what the text actually says.
- **Validation, before anything is trusted (`_validate_paragraph`):**
  every `{{N}}` must reference a real index into `segments` whose `type`
  isn't `"prose"`; every stray digit outside a placeholder (checked the
  same way `analyze_document`'s `_verify_prose` already does) rejects the
  whole narrative. Any failure - a bad reference, a stray digit, no tool
  call, an `anthropic.APIError` (logged server-side, never echoed) -
  raises `ValueError`, same contract `analyze_document` already has.
- **Rendering stays in L4, and stays trusting.** A new
  `analystos.l4.export.render_narrative_section(title, source_hash,
  segments, paragraphs, currency_unit="actual")` does the actual `{{N}}`
  substitution - each occurrence becomes `<rendered value> [n]`, footnote
  numbers assigned by first appearance so a fact referenced twice reuses
  its number - and returns the exact same section shape
  (`# Title` / paragraphs / `---` / footnotes) `render_section` and
  `render_narrated_section` already produce. `render_html`/`render_pdf`
  need no changes at all.
- **Fallback, not failure.** `analystos/pipeline.py`'s narrated-default
  branch tries `write_narrative` + `render_narrative_section`; on
  `ValueError` it falls back to Slice 26's `render_narrated_section`
  unchanged. A person always gets a report; the narrative pass is a
  quality improvement layered on top, never a new way to lose the report.
- **Still "actual" currency scale, always.** Same reasoning as
  `docs/decisions.md`, 2026-09-05 ("The narrated path always uses
  "actual" currency scale") - a quoted value is already the real number,
  never something pre-scaled by a stated convention.
- **Shared client/error-handling helpers.** `_resolve_client` and
  `_create_message` move from being inline in `analyze_document` to small
  shared functions in `analystos/l2/analyze.py` that `narrate.py` also
  calls - the missing-key check and the `anthropic.APIError` → clean
  `ValueError` conversion (`docs/decisions.md`, 2026-09-05, the two
  Anthropic error-handling fixes) must not be reimplemented, and must not
  drift, now that there are two real call sites instead of one.

## Cost

This adds a second real model call per report - roughly double the
per-report cost disclosed for Slice 26. Same standing rule as every other
real API spend: build and test entirely against a mocked client (as this
slice's own test suite does, zero cost), and get explicit sign-off before
any real, paid live call.

## Done when

1. `write_narrative` returns a list of paragraph dicts when the model's
   response validates cleanly against a mocked client.
2. A paragraph referencing an out-of-range index, or a `prose`-type
   segment's index, is rejected - `write_narrative` raises `ValueError`.
3. A paragraph with a stray digit outside any `{{N}}` placeholder is
   rejected the same way.
4. A fact referenced in two different paragraphs gets exactly one
   footnote number, reused both places.
5. A fact the narrative never references simply doesn't appear in the
   output - dropped, not an error.
6. `render_narrative_section`'s output parses cleanly through
   `render_html` and `render_pdf` with no changes to either.
7. `pipeline.build_report`'s narrated default falls back to
   `render_narrated_section` (Slice 26's plain rendering) when
   `write_narrative` raises for any reason - a person still gets a report.
8. An `anthropic.APIError` from either the extraction call or the
   narrative call is logged server-side and converted to the same clean
   `ValueError` message, using the shared `_resolve_client`/
   `_create_message` helpers - not reimplemented per call site.
9. `python3 -m unittest discover -s tests -v` passes (with the venv
   active) using only mocked clients - no real `ANTHROPIC_API_KEY` or
   network access required to run clean.

## Verified beyond the test suite

The first real live test (a richer multi-section document, real
`ANTHROPIC_API_KEY`) still rendered Slice 26's fallback despite both
Anthropic calls succeeding (`200 OK` per Vercel's logs), and surfaced two
real findings - not in this slice's own new code, but in the safety net
this slice depends on:

- **A genuine verification gap in `analyze.py`, pre-dating this slice.**
  A citable claim's `exact_text` was checked for really appearing in the
  document, but the numeric `value` paired with it never was - letting a
  model represent subtraction (not one of the five supported operations)
  by silently negating an operand inside a `sum`. Landed on the true
  number both times it happened live; nothing structural stopped a false
  one. Fixed - see `docs/decisions.md`, 2026-09-06 ("Closed a real
  verification gap...").
- **The digit-ban rule (Slice 26's own, inherited by this slice) rejected
  almost any real connective prose**, since ordinary writing constantly
  mentions a quarter or year. `write_narrative` had no logging on this
  rejection path either, so it was invisible until reproduced manually.
  Fixed with a calendar-reference carve-out plus logging - see
  `docs/decisions.md`, 2026-09-06 ("Calendar references don't need a
  citation").

A follow-up commit carrying these two fixes was itself reported "pushed"
without confirming its PR was still open - it landed after that PR had
already merged and never reached `main` at all. Recovered via
`git cherry-pick` onto a fresh branch, this time verified through
GitHub's own file-diff API rather than assumed. See `docs/decisions.md`,
2026-09-06 ("A follow-up commit landed after its PR had already merged").

Separately, before any of the above had actually succeeded live even
once, the underlying writing style itself was called out as insufficient
regardless of bug fixes: one paragraph per fact, in extraction order, is
a fact sheet, not analysis. `_SYSTEM_PROMPT` was rewritten around real
executive/analyst-writing patterns (the Minto Pyramid Principle, SCQA,
equity-research practice) rather than a generic "sound smart" instruction
- see `docs/decisions.md`, 2026-09-06 ("Rewrote the narrative prompt...").
A mechanically-real mock (hand-written paragraphs run through the actual
validation and rendering code, not typed-up prose) confirmed the shape
works before spending anything on a live test of the new prompt. That
live test is the next step.

## Not in this slice

- **Choosing the output shape** (one-pager, slide deck, memo). Next on
  the roadmap discussed 2026-09-06, not this slice.
- **The feedback/revision loop.** Same roadmap, later step.
- **Chunking documents too large for one context window.** Same roadmap.
- **A concrete, written-down quality rubric for "Fortune 10 exec-worthy."**
  This slice adds the *mechanism* for better structure; grading the actual
  writing against a rubric is its own follow-up step.
- **Retrying a rejected narrative attempt.** Falls back once, immediately -
  no regeneration loop, keeping the failure mode obvious (same choice
  Slice 26 made for a single rejected segment).
