# Slice 46 — GAAP/non-GAAP table proof + legal boilerplate exclusion

## Goal

Two pieces of foundation work, both depending on Slice 44's unified table
extraction and real footnote linking (confirmed in place on `main` before
any of this started - `document_text.py` calls each format's real
`_raw_rows`, `analystos/l1/footnotes.py` exists, and the Slice 44 test
suite passes live). Task 1 proves Slice 45's GAAP/non-GAAP tagging
actually holds up against a *real reconciliation table*, not just prose -
the gap this slice closes. Task 2 is genuinely new: excluding legal
forward-looking-statement/safe-harbor boilerplate from fact extraction
entirely, so that prose is never mined for "facts" in the first place.

## Included

### Task 1 - GAAP/non-GAAP via a real reconciliation table

- `tests/test_l1_l2_gaap_table_integration.py` - the mechanism already
  existed (Slice 45's `gaap_status` field, verification, and reconciling
  `difference` computation); what was missing was proof it holds through
  a genuine table, not a hand-typed prose fixture. Builds a real `.docx`
  reconciliation table, runs it through the real, unified
  `extract_document_text` (spying on `extract_docx._raw_rows` to confirm
  the same function every schema-driven table already uses actually
  parsed it), then `analyze_document` with a realistic mocked model
  response, and proves both figures verify against the real table text,
  are correctly tagged by basis, and are linked by a verified reconciling
  gap - plus a defense-in-depth case: a fabricated third figure the table
  never stated fails verification, same as any other made-up quote would.
- No new production code needed - Slice 45 already built the mechanism
  correctly; this closes a real proof gap, not a functionality gap.

### Task 2 - legal boilerplate exclusion (new)

- `analystos/l1/boilerplate.py` - `strip_forward_looking_boilerplate(text)`.
  Not a keyword blocklist: requires either (a) a canonical disclaimer
  section heading ("Forward-Looking Statements," "Safe Harbor Statement,"
  and the small set of near-identical real-world phrasings), or (b) a
  *density* of specific statutory/legal phrase patterns (citing the
  actual securities-law sections, the "actual results...differ
  materially" formulation, "undertake no obligation to update," etc.) -
  several of these must co-occur before content-only detection fires, so
  one incidental mention of "forward-looking" or "risk" in ordinary
  prose is never enough to trigger removal. Once a heading is matched,
  the disclaimer body that follows is consumed line by line for as long
  as it keeps showing at least one pattern, then stops - bounded, not a
  runaway strip of everything after the heading.
- `analystos/pipeline.py` - wired in on the narrated-default path only:
  `extract_document_text` -> `strip_forward_looking_boilerplate` ->
  `analyze_document`. The old schema/template path
  (`analystos.l1.detect.extract_any`) only ever reads literal table
  cells, never prose - a forward-looking-statements disclaimer is always
  prose, so it never appears on that path to begin with.
- `tests/test_l1_boilerplate.py` - unit tests for the stripper itself
  (headed removal, heading-less content-density removal, and explicitly
  the false-positive case a keyword blocklist would fail: a single
  incidental "forward-looking" or "risk" mention in ordinary business
  prose is left untouched) plus the real integration proof: a genuine
  `.docx` with both a substantive numeric section and a real disclaimer
  section, run through the real extraction path, proving the disclaimer
  text never reaches `analyze_document` at all - and, as defense in
  depth, that even a fabricated "fact" the model tried to pull from the
  disclaimer's own statutory language fails verification, since that
  text is no longer present to match against.

## Done when

1. **Task 1**: a real GAAP-to-non-GAAP reconciliation table produces both
   figures, correctly tagged by basis and linked via a verified
   reconciling `difference` - not two unrelated numbers - proven through
   the real unified table-extraction path
   (`tests/test_l1_l2_gaap_table_integration.py`, 3 tests).
2. **Task 2**: a realistic forward-looking-statements section produces
   zero extracted facts from that section, while substantive facts from
   the rest of the same document are still correctly extracted - both
   halves proven directly (`tests/test_l1_boilerplate.py`,
   `BoilerplateExclusionIntegrationTest`, 3 tests), plus 6 unit tests
   against the stripper itself, including the specific false-positive
   case a naive keyword blocklist would fail.
3. `python3 -m unittest discover -s tests -v` passes (406 total).
4. Direct answer, asked explicitly: both tasks run on the
   narrated-default path only -
   `analystos.l1.document_text.extract_document_text` (Slice 44's
   unified table parsing) feeding `analystos.l2.analyze.analyze_document`,
   with Task 2's stripping step now sitting between them in
   `analystos.pipeline.build_report`. The old schema/template path
   (`extract_any`) is untouched by either task: it never sees prose
   (nothing for boilerplate detection to act on) and doesn't produce
   `gaap_status`-tagged segments (that field is specific to the
   narrated-default extraction schema Slice 45 added).

## Not in this slice

- A boilerplate detector for anything other than forward-looking-
  statements/safe-harbor language specifically (other legal boilerplate
  genres - indemnification clauses, standard confidentiality legends -
  would need their own pattern sets, a separate, later piece of work).
- Running boilerplate exclusion on the schema/template path - it has no
  prose to run on, so there is nothing to add there.
