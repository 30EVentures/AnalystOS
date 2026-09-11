# Slice 47 — organic-vs-inorganic derived splits + code-owned chart type

## Goal

Two independent capability upgrades. Task 1 generalizes a pattern that
was previously only ever produced ad hoc (a total change minus one
named, disclosed component's contribution to it - the Meridian Data
Services bridge) into a real, reusable, verified operation. Task 2 moves
chart-type selection out of the writer model's hands entirely: the model
supplies which verified facts to plot; code decides, from the data's own
shape, how to plot them.

## Included

### Task 1 - "remainder" (organic-vs-inorganic and similar splits)

- `analystos/l2/analyze.py` - a new `"remainder"` operation alongside the
  existing `sum`/`average`/`ratio`/`growth_percent`/`percent_of_total`/
  `difference`. Same formula as `difference` (operands[0] minus the sum
  of the rest) but kept as its own named operation, not a reuse of
  `difference` outright, so a "total change minus a named component's
  contribution" pattern is recognizable downstream instead of being just
  another generic magnitude. Verified exactly like every other operation
  - independently recomputed from the same checked operand values,
  dropped if the claimed result doesn't match.
- The extraction prompt's "must surface every comparison" discipline
  gains a new bullet: when the source states a total change *and*
  separately names a specific component's own disclosed contribution to
  it, compute the remainder - only from what the source actually
  discloses, never an estimated split.
- `analystos/l2/narrate.py` - `remainder` gets the same cautious
  treatment `difference` already has in the direction-word gate: its
  sign is exactly as unverifiable (nothing confirms operand[0] genuinely
  is "the total" rather than just the first number listed), so a
  directional word next to a `remainder` fact is refused the same way.

### Task 2 - code-owned chart-type selection

- `analystos/l4/rich_export.py` - `_detect_chart_type(labels, values)`:
  a start -> components -> end bridge (the identical tie-out property
  the existing post-hoc waterfall check already requires) is a
  waterfall; three or more period-labelled points (a quarter, fiscal
  year, half, month, or bare calendar year - `_PERIOD_LABEL_RE`) are a
  line; anything else is a bar. `_chart_html` now calls this on the
  *resolved, verified* `(labels, values)` and uses its answer -
  `chart.get("type")`, whatever the model declared, is never consulted
  for rendering at all.
- The existing post-hoc validation - the waterfall tie-out check, the
  under-two-point drop in `_resolve_chart` - is untouched, kept as an
  independent safety layer on top of the new detector, not replaced by
  it (verified directly: the detector was mocked to force "waterfall" on
  purpose-broken bridge data, and the separate, untouched check still
  refused to render it).
- `analystos/l2/narrate.py`'s "Charts:" prompt paragraph rewritten to
  match: the model's `"type"` field is now a formality (any valid value,
  ignored); what matters is which facts it plots and their order (start,
  then components, then end, for a bridge; chronological order for a
  trend).
- One existing test (`test_a_waterfall_that_does_not_tie_out_is_dropped`)
  updated to the new, intentional behavior: data that breaks the bridge
  no longer means the chart disappears - it means code correctly stops
  calling it a bridge and renders the same real numbers as an honest bar
  comparison instead. No chart lost, no misleading bridge shown either.
- Donut (parts of a stated whole) is not auto-detected in this slice -
  see "Not in this slice."

## Done when

1. **Task 1**: a total-plus-one-component disclosure pattern produces a
   correctly computed, independently verified remainder fact - and a
   wrong claimed result, or an operand not actually in the source, is
   dropped, not taken on faith (`RemainderOperationTest`,
   `tests/test_l2_analyze.py`, 4 tests).
2. **Task 2**: one test per shape, each deliberately declaring the
   *wrong* model-supplied type to prove the override is real
   (`ChartTypeAutoDetectionTest`, `tests/test_l4_rich_export.py`, 3
   tests) - a real bridge renders as a waterfall despite a declared
   "bar"; three categorical figures render as a bar despite a declared
   "line"; three or more period-labelled figures render as a line
   despite a declared "donut."
3. The existing post-hoc validation - the waterfall tie-out check, the
   under-two-point chart drop - is confirmed untouched and still
   passing, plus a new test confirming it still fires independently even
   when the detector itself is forced to answer "waterfall" for data
   that doesn't tie out.
4. `python3 -m unittest discover -s tests -v` passes (414 total).

## Not in this slice

- Donut auto-detection ("parts of a stated whole") - the task named
  exactly three shapes; nothing currently available to `_detect_chart_type`
  (a plain resolved `(label, value)` list, no associated "total")
  reliably distinguishes "these parts sum to a whole" from an ordinary
  categorical comparison without a new signal. Falls back to bar, a
  safe, honest default - not a silent loss of capability, a scoped
  deferral.
- A "remainder" chain deeper than one total and its named components (a
  total split three or more ways, each with its own disclosed
  contribution) - the operation supports N operands mathematically
  already (same as `difference`), but the extraction-prompt guidance and
  tests here cover the one-total/one-named-component case specifically,
  matching the task's own framing.
