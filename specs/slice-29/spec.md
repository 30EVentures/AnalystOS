# Slice 29 — L2 extraction contract: guarantee the comparisons, tag the horizon

## Goal

Every report AnalystOS produces should meet Fortune-10 quality **by
default**, on any document — not by hand-fixing one file. The diagnosis
(`docs/rich-report-diagnosis.md`) traced the gap: `analystos/l2/narrate.py`
already instructs the model in all five writing disciplines (benchmark every
number, name the mechanism, sequence past from future, narrate events,
co-state cause and effect), but the narrator can only write from the facts
`analystos/l2/analyze.py` hands it — and today `analyze_document` returns
"the important facts," with benchmarking left to the model's discretion,
one comparison at a time. No prompt on the narrator can conjure a benchmark
that was never computed.

This slice changes **`analystos/l2/analyze.py` only**: make the extraction
stage *guarantee* the derived comparison set for every headline figure, and
tag every fact with its time horizon so a later slice can keep verified
history and forward-looking guidance structurally apart. The verification
contract does not move: every number is still either a substring-verified
quote or an independently recomputed calculation, dropped on any failure.

## Design decisions

- **New `horizon` field on every segment: `"reported"` / `"guidance"` /
  `"projected"`.** `reported` is a stated actual or historical fact (the
  default). `guidance` is a figure the source attributes to the company or
  management as forward guidance / outlook / a full-year target.
  `projected` is any other forward figure the source states (a "we expect",
  a consensus estimate) that isn't official guidance. It is verified
  exactly like everything else — a guidance number still needs its
  `exact_text` in the document and its `value` matching what that text
  spells out. Nothing downstream *uses* the field yet (Slice 30/31 wires
  the outlook block and the "no projected figure in a history section"
  rule); this slice only produces it, and existing consumers
  (`narrate.py`, `rich_export.py`, `render_narrated_section`) ignore an
  extra key harmlessly.

- **New `difference` operation.** Operands `[a, b, c, ...]` →
  `a - (b + c + ...)`, independently recomputed like every other operation.
  Subtraction was deliberately excluded through Slice 26 because a model
  could smuggle a sign flip (the `sum([1240, -1050])` "net additions"
  exploit). That hole is already closed: `_value_matches_text` checks each
  operand's `value` against the number its own `exact_text` spells out,
  **including sign** — an operand quoted as "1,050" can no longer be passed
  as `-1050`. With that check in place, `total − parts` is safe, and it is
  the operation the comparison set needs: an absolute period-over-period
  change, a margin move in percentage points, and a stated target minus the
  sum of stated actuals (an implied next-period figure) are all
  impossible to express with the current five operations.

- **The "what to report" instruction becomes an explicit completeness
  contract.** Rewrite `_SYSTEM_PROMPT`'s middle section from "decide what's
  genuinely worth reporting" to: pick the handful of figures that matter,
  and for each one, surface **every comparison the source's own numbers
  support** —
  1. the prior-period value and the change (`growth_percent`, and
     `difference` for the absolute move);
  2. each period's value when three or more periods of the same metric
     appear, not only the latest (so a trend can be written and charted
     downstream);
  3. its share of a stated total (`percent_of_total`);
  4. where the source states a target or guidance for the same metric,
     that figure and the gap to it (`difference`).
  A figure featured without a comparison the source actually supports is an
  incomplete analysis and should not be featured that way.

- **Honesty rule, carried over from Slice 27's discipline 2.** If a
  comparison isn't in the source, the model does not invent one — it omits
  the figure or leaves it without that comparison. Nothing here relaxes
  "never state a number you can't cite"; it raises the bar on which
  *citable* comparisons must be computed when they are available.

- **`analyze_document` returns a small completeness summary alongside the
  segments**, for tests and for the Slice 30 narrator to act on — e.g.
  `{"segments": [...], "coverage": {"reported_figures": n,
  "comparisons": m, "horizons": {...}}}`. This is a signal, not a gate:
  a report with no comparisons still renders (the narrator will be
  instructed in Slice 30 to state the absence plainly), consistent with
  this codebase's "drop or fall back, never lose the report" rule.
  *(If threading a dict return through `pipeline.py` and every caller/test
  proves noisier than it's worth, fall back to keeping the bare list
  return and computing coverage where it's needed — decide during build,
  record which in decisions.md.)*

- **Schema stays all-required.** `horizon` is one more required enum
  property on an object whose every property is already required — it adds
  no optional-property combinatorics, so it does not risk repeating the
  `400 Schema is too complex` failure (that was caused by *optional*
  properties). `difference` joins `_OPERATIONS`, so the `operation` enum
  picks it up with no schema restructuring.

- **Model unchanged** (Claude Sonnet 5, the disclosed latency call for the
  10-second Vercel ceiling). Prompt gets longer; no new call, no second
  model, no cost change per report beyond a modestly larger prompt.

- **Tested entirely against a mocked Anthropic client** — this environment
  has no `ANTHROPIC_API_KEY`. Real output quality is confirmed later, on
  Vercel, per the agreed Step 4 plan (mock-client locally + a live smoke
  test after merge). Flagged before any paid call is made.

## Included

- `analystos/l2/analyze.py`:
  - `_SYSTEM_PROMPT` — the completeness contract above; `horizon` field
    described in the field list; `difference` described under `operation`.
  - `_TOOL` schema — add `horizon` (required, enum of three); `difference`
    flows in through `list(_OPERATIONS) + ["none"]`.
  - `_OPERATIONS` — add `"difference"`.
  - `_recompute` — handle `"difference"`: `values[0] - sum(values[1:])`,
    requires ≥ 2 operands.
  - `_verify_computed` — no structural change; `difference` reuses the
    existing per-operand substring + value-match checks and the independent
    recompute-and-compare. Confirm the ≥ 2 operand guard.
  - `_verify_quote` / `_verify_computed` / `_verify_prose` — carry
    `horizon` (defaulting to `"reported"`) onto the verified segment dict.
  - `analyze_document` — return the segments plus the coverage summary
    (see the design note's caveat).
- `docs/decisions.md` — a dated entry: why subtraction is safe now, the
  completeness contract, the `horizon` field and what does *not* consume it
  yet.
- `docs/rich-report-diagnosis.md` — already written; committed with this
  slice as the rationale of record.
- Tests, `tests/test_l2_analyze.py` (extend), mocked client only:
  - `difference` with correct operands and result is kept and independently
    recomputed.
  - `difference` whose result the model got wrong is dropped.
  - `difference` with a sign-flipped operand (value not matching its
    `exact_text`) is dropped — the old exploit stays closed under the new
    operation.
  - `difference` with fewer than two operands is dropped.
  - a `guidance` quote with a real `exact_text` and matching value is kept,
    with `horizon == "guidance"`.
  - a segment with no `horizon` from the model defaults to `"reported"`.
  - a realistic multi-segment mock response (latest figure + each period of
    a 4-period trend + `growth_percent` + `difference` for the absolute
    move + `percent_of_total` + a guidance figure + the `difference` gap to
    it) all survives verification, and the coverage summary reports the
    comparison count.
  - every existing `test_l2_analyze.py` case still passes unchanged (the
    new field is additive; the four original operations are untouched).

## Done when

1. `difference` is a recognised operation: correct arithmetic over
   substring-and-value-verified operands is independently recomputed and
   kept; wrong arithmetic, a sign-flipped operand, or fewer than two
   operands each cause the segment to be dropped — one dedicated mocked
   test each.
2. Every verified segment carries a `horizon` of `"reported"`,
   `"guidance"`, or `"projected"`; absent from the model's output it
   defaults to `"reported"`; a `guidance` figure is verified by exactly the
   same substring + value-match checks as any other quote.
3. Given a realistic mocked response for a multi-period document,
   `analyze_document` returns — all verified — the latest value, every
   period's value for a 3-plus-period trend, the period-over-period
   `growth_percent` and absolute `difference`, a `percent_of_total`, and a
   stated guidance figure with the `difference` gap to it.
4. `analyze_document` exposes a coverage summary (comparison count,
   reported-figure count, horizon breakdown) usable by a test and by the
   Slice 30 narrator.
5. No change to `analystos/l2/narrate.py`, `analystos/l4/*`, or
   `analystos/pipeline.py`'s wiring; the flat narrated path still renders
   an unchanged shape, now just with an ignored extra field on each
   segment.
6. `python3 -m unittest discover -s tests -v` passes with the venv active,
   mocked client only — no dependency on a real `ANTHROPIC_API_KEY` or
   network.

## Not in this slice

- **Wiring `horizon` to anything.** The outlook block being populated from
  `horizon`, and the rule that a `guidance`/`projected` figure may never
  appear unmarked in a history section — Slice 31.
- **Structured narrator output** (executive summary / sections / per-section
  charts / outlook) and rendering via `render_rich_report` — Slice 30.
- **Share-of-total *shift*** (this quarter's mix share minus last
  quarter's). Each share is itself a `percent_of_total`, so the delta needs
  one computed value to feed another — the computed-chaining limitation
  explicitly deferred since Slice 26. Its own slice (31/32).
- **A mix-vs-rate attribution bridge** for a blended metric's move —
  Slice 32 if still needed after 30/31.
- **Dated-event structure** (`date` / `what` / `status` / `next_step` as a
  segment shape, and broadening narrate.py's discipline 4 beyond legal to
  any dated event) — Slice 31.
- **Peer / sector / index benchmarks.** The system sees one document; the
  verification guarantee forbids inventing a comparison that isn't in it.
  Out of scope unless the user supplies a second source; recorded as a
  boundary in decisions.md, not treated as a bug.
- **Hard-failing a report for insufficient comparisons.** Coverage is a
  signal this slice; the narrator is told how to handle a thin document in
  Slice 30. Consistent with "drop or fall back, never lose the report."
- **Any real paid model call.** Mock client only here; live smoke test on
  Vercel after merge, flagged first.

## Verified beyond the test suite

Before merge: hand-author a realistic `write_report`-shaped response for a
genuinely multi-period document (a fictional, clearly-labelled draft — not
a real company), run it through the real `analyze_document` verification
with a mocked client, and read the resulting verified segments directly —
confirming the comparison set (trend values, `growth_percent`,
`difference`, `percent_of_total`, guidance gap) all survives, the sign-flip
exploit is still rejected under `difference`, and the coverage summary is
right. The genuine confirmation that a real model *produces* this set from
a real document, unprompted per-run, is the post-merge Vercel smoke test in
the agreed Step 4 plan.
