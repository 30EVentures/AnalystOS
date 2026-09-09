# Slice 33 — verification that survives a real filing's tables and scale

## Goal

A realistic fictional earnings release (`Calderon_Grid_Q3_2026`) uploaded
to the live site returned **"no verifiable content survived"** — a total
verification failure, 400 to the user. `analyze_document`'s checks were
tuned to Meridian, which was five paragraphs of prose with every figure
spelled out (`"$498.0 million"`); a real condensed income statement is a
pipe-delimited table headed *"In millions of U.S. dollars"*, and against
that the checks drop everything. Two codebase gaps, both in
`analystos/l2/analyze.py`:

- **Byte-exact substring citation.** A model reasons about a figure and
  re-expresses it — `1,842.0` in the table becomes `$1,842.0 million` or
  `$1,842` or `1842.0` in `exact_text` — and `_really_in_document` (an
  exact `in` check on whitespace-normalised text) drops each one.
- **No notion of a table's stated scale.** `1,842.0` in a document
  declared "in millions" *is* $1,842,000,000. If the model scales `value`
  to the real magnitude, `_value_matches_text` compares it to the `1,842.0`
  its `exact_text` shows and rejects it; if the model leaves it unscaled,
  it verifies but L4 renders `$1.8K`.

And a diagnostic gap: the failure logged nothing about *why* each segment
was dropped — the same "no clue why it failed" hole Slice 27 closed for
the narrative pass.

## Design decisions

- **Tolerant matching (`_match_key` + `_really_in_document`), never
  tolerant of digits.** `_match_key` folds case, unifies dashes, drops
  `$` and the `|` our own L1 table rendering inserts, and strips thousands
  separators from digit groups. `_really_in_document` then checks the
  folded citation as a substring, and — since a model reading a scaled
  table often re-appends the header's unit word — also with one trailing
  scale word removed. The digit sequence itself is never altered and must
  appear, in order, so nothing the source doesn't contain can match.
- **A model prepending a row label to a *non-leading* table cell
  (`"Diluted earnings per share 0.35"`, where the flattened text has
  `"per share 0.22 0.34 0.35"`) still fails — deliberately.** Tying a
  label to a distant number by proximity risks accepting a *mislabelled*
  one, and a false "verified" is the one outcome this system must never
  produce. The prompt tells the model to cite such a cell by the number
  alone; a miss is now logged with the exact reason.
- **Declared scale (`_detect_scale` + `_value_matches_text`).**
  `_detect_scale` reads a unit declaration once ("in millions" / "in
  thousands" / "millions of U.S. dollars"); the largest declared unit
  wins. `_value_matches_text` now returns the *canonical* value: it
  accepts the model's `value` if it equals the number `exact_text` shows
  **or** that number times the declared scale, and returns whichever
  matched — so a figure the model scaled correctly verifies, and one it
  left unscaled is still stored (unchanged behaviour, not a regression).
  Sign is preserved, so Slice 29's sign-flip guard still holds
  (`-1050` matches neither `1050` nor `1050 × scale`). The user message
  also tells the model the detected scale and that per-share amounts,
  percentages and share counts are *not* scaled.
- **Per-segment drop reasons.** `_verify_*` now return
  `(segment, None)` or `(None, reason)`. On a total failure
  `analyze_document` logs the first several reasons to stderr (Vercel
  function logs) — never to the client response, matching Slice 27. A
  partial failure logs a one-line "N verified, M dropped" summary.
- **Prompt** (`_SYSTEM_PROMPT`): `exact_text` guidance for pipe-delimited
  table cells (row label + number, or the number alone; do not abbreviate,
  add `$`, or add a unit word the cell lacks); `value` is the actual
  magnitude, scaled per the header.
- **Meridian and every prior fixture are unaffected** — a document that
  declares no unit has `doc_scale == 1`, and `_value_matches_text`'s two
  candidates collapse to the old single check; `_match_key` only forgives
  typography the old check would have wanted anyway.

## Included

- `analystos/l2/analyze.py` — `_match_key`, rewritten `_really_in_document`,
  `_detect_scale` / `_DECLARED_SCALE` / `_SCALE_NAME`, `_value_matches_text`
  (new signature + canonical return), `_verify_quote` / `_verify_computed`
  / `_verify_prose` / `_verify_event` / `_verify_segment` return
  `(result, reason)`, `analyze_document` collects reasons + logs, scale
  note appended to the user message, `_SYSTEM_PROMPT` table/scale guidance,
  dead `_normalize` removed.
- `docs/decisions.md` — dated entry.
- `tests/test_l2_analyze.py` — `_detect_scale` on declared/undeclared
  units; `_match_key` folds typography not digits; a scaled table quote
  verifies and stores the real magnitude; a re-added `$`/unit still
  verifies; growth on scaled operands; a total failure is logged with
  reasons; a mislabelled row-label+cell pair is refused; Meridian-style
  prose is unaffected. Every existing case still passes (sign-flip guard
  included).

## Done when

1. A quote citing a "$ in millions" table cell (`exact_text` "1,842.0",
   value 1 842 000 000) verifies and is stored at 1 842 000 000.
2. A quote that re-adds `$` and the unit word the cell lacks still
   verifies against the bare cell.
3. `_detect_scale` returns 1 000 000 / 1 000 / 1 for a document declaring
   millions / thousands / nothing.
4. A fabricated figure, wrong arithmetic, and a sign-flipped operand are
   still each dropped; a total failure prints the per-segment reasons to
   stderr and still raises the same `ValueError` to the caller.
5. Every Meridian-era `test_l2_analyze.py` case passes unchanged.
6. `python3 -m unittest discover -s tests -v` passes, mocked client only.

## Not in this slice

- **Column-aware table extraction** — keeping a cell tied to its row
  label and column header through L1 so "RowLabel Cell" citations of any
  column verify. That is an `analystos/l1/document_text.py` change (emit
  the docx/xlsx body in document order, keep tables structured) and its
  own slice; this slice makes such a citation fail *safely and visibly*
  rather than fixing it.
- **A real `.pdf` of the rich layout**, the mix-vs-rate bridge,
  share-of-total shift, peer benchmarks — as scoped out earlier.
- **A live paid model run** — mocked client only here. The live re-test
  of `Calderon_Grid_Q3_2026` on Vercel is the confirmation, flagged
  first.

## Verified beyond the test suite

The real L1 extraction of `Calderon_Grid_Q3_2026_earnings_TEST.docx` (the
document that failed live) was fed a hand-authored `write_report` response
mimicking what a real model produces from those tables — bare and
`$`-prefixed table cells, actual magnitudes for dollar figures, per-share
values left as printed, a growth computation, a guidance figure, a dated
event, connective prose, plus two segments that *should* fail. Result: 8
of 10 verified (was 0), dollar cells stored at real magnitude, per-share
values untouched, guidance tagged; the fabricated figure and the wrong
arithmetic were dropped with their reasons logged. The confirmation that a
*real* model clears the same bar on this document is the post-merge Vercel
re-test.
