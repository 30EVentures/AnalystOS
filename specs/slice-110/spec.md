# Slice 110 - close the engagement gate's bypasses (review of Slice 109)

## Goal

A fresh-context review of Slice 109 finished after it merged (PR #96, merge
`d9a42a8`). It found the acceptance gate could be bypassed two ways, both
reproduced against main before this slice:

1. `accept()` trusted the record's own question list. A record edited so every
   question was optional, or whose questions were swapped for one optional
   question, or whose roles were swapped for a family it never asked about, was
   accepted with nothing answered.
2. `accept()` never validated the catalog. A role marked `available` with no
   evaluation and no rate - exactly what Slice 108 forbids - was accepted, as
   was a catalog listing a role twice (planned, then available).

Neither was exploitable (nothing stores engagements or takes one back from a
client yet), but both must be closed before `/api/v2` exists. This slice also
fixes the review's smaller findings and corrects an overclaim in Slice 109's
commit message and PR description.

(Routing from the problem text, planned as Slice 110, moves to Slice 111.)

## Done when

1. **The gate recomputes, never trusts.** `accept()` refuses unless the catalog
   passes `validate_catalog`, the scoping templates pass `validate_scoping`, and
   every question the *current* templates require for the requested roles is
   present in the record, still marked required, and answered. A snapshot may
   carry extra questions from older templates; it may not drop or soften a
   required one. Each of the review's five tampered inputs is a test that is
   refused.
2. **Client text cleaning is idempotent and never silently changes meaning.**
   Order: unify line endings, remove invisible characters, NFC-normalise, trim -
   so cleaning twice changes nothing (a property test over generated strings).
   Invisible means control characters (keeping newline and tab), format
   characters, line and paragraph separators, and every Unicode
   Default_Ignorable_Code_Point (variation selectors, U+034F, Hangul fillers,
   ...). Lone surrogates, private-use and unassigned characters are **refused**,
   not dropped. Raw input far over the cap is refused before any processing.
3. **The CLI** reads stdin as strict UTF-8 (refused with exit 2 otherwise),
   treats `--agent ""` as an empty agent reference (refused), and reports
   `accepted` from the gate rather than a constant.
4. **Error types match the docstrings.** Builders (`new_engagement`, `answer`,
   `open_questions`) raise only `ValueError` on malformed input, including a
   malformed catalog or templates; validators and `accept` never raise.
   `validate_engagement` also checks question text is clean.
5. **Tests for each surviving mutant the review listed**, plus the tampered
   records, the invalid catalogs, idempotence and the CLI cases. The mutation
   claim in this slice's commit names its method and its exact count.
6. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.

## Not in this slice

- Sealing engagement records or holding them server-side (the lasting fix for
  tampering; comes with storage and `/api/v2`).
- Routing from the problem text (Slice 111).
