# Slice 49 — Gate 2's full prose-quality rubric

## Goal

Gate 2 (`analystos.l2.proofread`) today checks language mechanics only -
spelling, grammar, duplication, leftover artifacts. This slice raises its
bar to the fuller rubric: no filler sentences, at least one genuine
cross-section synthesized insight clearly labeled as interpretation, and
disclosure gaps (when the report states any) worded in clear, plain
language. Gate 2 stays exactly what it is architecturally - a third,
independent, blind pass that never sees segments, citations, or values,
mandatory alongside (never instead of) Gate 1 - only its judging
criteria grow.

## Included

- `analystos/l2/proofread.py`'s system prompt gains three concrete,
  example-anchored criteria (vague instructions produce inconsistent
  judgment - this codebase's existing prompts always ground a rule in a
  real positive/negative example, not an abstract adjective):
  - **No filler.** A sentence with no citable number, no named
    mechanism/driver, and no specific claim - just generic positive
    sentiment ("the Company remains committed to driving long-term
    shareholder value") - is filler and must be flagged, even if
    grammatically perfect. A sentence that states a real number, names a
    real cause, or makes a checkable claim is never filler, regardless
    of tone.
  - **Genuine synthesis, clearly labeled.** The executive insight (and
    outlook interpretation, where present) must read two or more facts
    *together* into a judgment neither states alone - not one fact
    restated with an adjective, and not two facts merely listed side by
    side with no connecting judgment.
  - **Disclosure gaps in plain language.** Gate 2 is blind to the source,
    so it cannot judge whether *enough* gaps were flagged (that would
    require seeing what the source actually contains - a Gate
    1/extraction-quality concern, out of scope here). What it *can*
    judge from prose alone: any gap that *is* stated must be specific and
    plain ("cash flow from operations is not disclosed"), not vague
    hand-waving ("certain items were not fully addressed").
- A **new, deterministic, Gate-1-style check** (not an LLM judgment call -
  this codebase's established preference wherever a rule can be
  mechanically verified instead of only asked for) added to
  `analystos.l2.narrate`: `executive_insight` (and `outlook_interpretation`,
  where present) must reference at least two distinct `{{N}}` fact
  indices. A single fact restated is not synthesis, whatever the prose
  around it claims, and this is checkable without any model judgment at
  all - a report failing it is rejected the same way a digit-outside-
  placeholder violation already is, repaired the same way (Slice 40's
  single-paragraph repair applies here too, unchanged).
- `_TOOL`'s schema in `proofread.py` gains explicit structured fields
  instead of only free-text `issues`, so a specific criterion's outcome
  is directly inspectable, not inferred by string-matching `problem`
  text: `has_filler` (bool), `has_synthesized_insight` (bool),
  `disclosure_gaps_clear` (bool) alongside the existing `passed`/`issues`.
  `passed` remains the single source of truth for whether the report
  ships; the three new fields exist for auditability and for the tests
  below, not as a second, competing pass/fail signal.

## Decision (made before build)

**(a) A real live run**, not an offline illustrative comparison - the
same reasoning as Slice 48's font choice: a prompt that looks right on
paper has, more than once this session, behaved differently live, and
this slice's entire premise is a model judgment call. See "Built" below
for the actual transcript.

## Done when

1. The deterministic two-distinct-facts synthesis check is proven the
   same way every other Gate 1 check already is: a mocked report citing
   only one fact in `executive_insight` is rejected with that specific
   reason; one citing two or more passes.
2. A before/after example on the same source document, produced per
   whichever option above you choose: the "before" version fails at
   least one of the three new criteria (shown as a real Gate 2 rejection
   with its specific stated reason, not a description of what it would
   probably say), and the "after" version - same facts, same source -
   passes all three.
3. `python3 -m unittest discover -s tests -v` passes, including the new
   deterministic check's tests.
4. Gate 2's independence from Gate 1 is unchanged - confirmed directly:
   the existing tests proving Gate 1 and Gate 2 run as two genuinely
   separate calls, and that Gate 2 never receives segments/citations/
   values, still pass unmodified.

## Not in this slice

- Judging whether disclosure_gaps is *complete* (whether the source had
  more gaps that should have been flagged) - structurally impossible for
  a blind pass to judge, and explicitly out of scope per the task's own
  "keep it blind" instruction.
- A numeric/scored rubric (e.g., "score prose quality 1-10") - Gate 2
  stays pass/fail with stated reasons, the same contract it already has;
  scoring is a different kind of tool, not asked for here.

## Built (post-implementation note)

- `analystos/l2/narrate.py` gained `_synthesis_problem(text)`, a fully
  deterministic check (no model call): `executive_insight` and
  `outlook_interpretation`, wherever non-empty, must cite at least 2
  *distinct* `{{N}}` fact indices - one fact restated, or none at all,
  is rejected the same way any other Gate 1 violation is, wired into
  `_locate_problem` right alongside the existing paragraph validators
  (so it gets the same single-paragraph repair treatment, unchanged).
  Proven in `tests/test_l2_narrate.py::SynthesisGateTest` (7 tests): a
  single fact, the same fact cited twice, and zero facts are all
  rejected with the specific reason stated; two or three distinct facts
  pass; an absent (empty-string) insight is correctly *not* treated as a
  failure.
- `analystos/l2/proofread.py`'s system prompt gained the three rubric
  criteria (no filler, genuine synthesis, plain-language disclosure
  gaps), each grounded in a worked example exactly as the existing
  prompt's other rules are. `_TOOL`'s schema gained `has_filler`,
  `has_synthesized_insight`, `disclosure_gaps_clear` (booleans,
  required) alongside `passed`/`issues` - logged for auditability by
  `proofread_report`, deliberately never folded into a second pass/fail
  signal (`passed` alone still decides). Proven in
  `tests/test_l2_proofread.py::RubricSchemaTest` (3 tests): the schema
  requires all three fields; they're logged when present; and a
  response that says `passed=True` with `has_filler=True` still ships -
  proving the "single source of truth" rule actually holds, not just
  stated.
- **Live before/after demonstration** (Done when #2), same underlying
  facts both times (revenue, a margin figure, reiterated guidance, an
  EPS gap) - a real `proofread_report` call against a real model, no
  mock:
  - **BEFORE** (`passed=False`, 3 issues) - flagged, verbatim: "This is
    generic filler with no citable number, named mechanism, or specific
    claim" (the boilerplate sentence); "This disclosure gap is vague
    hand-waving rather than a specific, plain statement of what is
    missing" (the vague gap); "Margin compression and reiterated
    guidance are stated side by side with no connecting judgment, so
    this does not rise to genuine synthesis" (the un-synthesized
    "insight").
  - **AFTER** (`passed=True`, 0 issues) - same facts, rewritten to state
    a specific gap (EPS) and read margin compression + reiterated
    guidance together into one judgment (temporary pressure, not a
    structural reset).
- Gate 1/Gate 2 independence (Done when #4): unmodified since the prior
  slice - `tests/test_l2_proofread.py::ReportTextExtractionTest` still
  proves `_report_text` extracts prose only, never segments/citations/
  values, and `tests/test_pipeline.py`'s dispatch-by-tool-name tests
  still prove `write_narrative` and `proofread_report` fire as two
  genuinely separate calls.
- Full suite: 434/434 passing.
