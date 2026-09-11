# Slice 45 — detect and correctly label GAAP vs. non-GAAP figures

## Goal

A company's own earnings materials routinely state the same underlying
metric two ways: the audited, standardized GAAP figure, and a company-
defined "adjusted"/"non-GAAP"/"pro forma" figure that excludes items like
stock-based compensation or restructuring charges. SEC Reg G actually
*requires* a filer to label a non-GAAP figure as such wherever it appears
- so unlike a heuristic, this is a genuinely detectable signal already
present in the source text, not something AnalystOS has to infer. Nothing
in the pipeline today distinguishes the two: a non-GAAP figure is
extracted and cited exactly like a GAAP one, with no way for the reader
to tell an "adjusted" number was presented as if it were the official
one. This slice makes that distinction real, end to end - extracted,
verified, and visibly labeled in the rendered report - not just noted in
passing.

Depends on Slice 44 (typed tables, real footnote linking): a GAAP-to-non-
GAAP reconciliation is very often presented as its own table, sometimes
referenced from body text via a footnote ("see reconciliation below") -
this slice can now rely on both being extracted for real.

## Included

- `analystos/l2/analyze.py` - the extraction schema gains a `gaap_status`
  field on every numeric (`quote`/`computed`) segment: `"gaap"` if the
  source states or implies the standard/audited figure (including simply
  not qualifying it at all - GAAP is the default when nothing marks a
  figure otherwise), `"non_gaap"` if the source itself labels it
  ("non-GAAP," "adjusted," "pro forma," "excluding [item]," or
  equivalent), `"n/a"` for a figure the distinction doesn't apply to (a
  headcount, a share count, a date). Detected from the source's own
  wording, never inferred from the number's size or direction - the same
  "verify, don't guess" standard every other extracted field already
  meets.
- When the same underlying line item appears in both forms (matched by
  label, e.g. "net income" stated once as GAAP and once as non-GAAP), a
  `"computed"` segment for the reconciling difference (`operation:
  "difference"`) is also emitted, the same existing computed-operation
  machinery already used for a YoY change - so a report can state the gap
  as a real, independently verified figure, not an eyeballed one.
- `analystos/l2/narrate.py`:
  - `_build_manifest` shows a non-GAAP fact's status to the model (a
    `[non-gaap]` tag alongside the existing `[guidance]`/`[projected]`
    horizon tag, both able to appear together), and the system prompt
    gains a discipline: state the GAAP figure as the primary fact, the
    non-GAAP figure as management's own adjusted view, never the reverse.
  - No new Gate 1 *validator* was needed for "a non-GAAP figure cited
    without its tag" - found during implementation, not planned going in:
    the tag is attached by `rich_export.py`'s renderer from the segment's
    own `gaap_status` whenever `{{N}}` is used, the exact same mechanism
    `⟦guidance⟧`/`⟦projected⟧` already use. It is structurally impossible
    for the model to omit it, the same way it can't omit those - a
    stronger guarantee than a checkable-but-skippable rule would have
    been, so the originally-planned check was dropped as redundant rather
    than built.
- `analystos/l4/rich_export.py` - `_TAG_RE` and the tag-attaching logic in
  `_substitute` extended to include `⟦non-gaap⟧`, reusing the existing
  `.horizon-tag` CSS class (already generic - no new styling needed) and
  the same generic rendering branch every unrecognised-but-matched tag
  already falls through to.

## Done when

1. A test document stating both a GAAP and non-GAAP figure for the same
   metric (e.g., "GAAP net income was $19.6 million; non-GAAP (adjusted)
   net income, which excludes $4.5 million of one-time integration
   costs, was $24.1 million") produces a `non_gaap`-tagged segment for
   the adjusted figure, a `gaap`-tagged segment for the standard one, and
   a verified `difference` segment for the $4.5 million gap -
   `GaapStatusFieldTest` in `tests/test_l2_analyze.py`.
2. Citing a `non_gaap`-tagged fact renders it with a visible
   `<span class="horizon-tag">non-gaap</span>` marker; the paired GAAP
   fact and a `gaap_status: "n/a"` computed fact next to it carry no such
   marker - `GaapStatusMarkerTest` in `tests/test_l4_rich_export.py`.
3. The manifest shown to the writer model correctly surfaces the tag
   (alone, or combined with a horizon tag) - `ManifestGaapStatusTest` in
   `tests/test_l2_narrate.py`.
4. A document with only a GAAP figure (no non-GAAP figure stated at all -
   the common case) is completely unaffected: every existing test in
   `tests/test_l2_analyze.py`, `tests/test_l2_narrate.py`, and
   `tests/test_l4_rich_export.py` keeps passing unchanged.
5. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Parsing a full GAAP-to-non-GAAP reconciliation *table* line by line
  (each individual adjustment - stock comp, restructuring, acquisition
  costs - as its own separately cited figure). This slice detects and
  labels the two headline figures and their net difference; walking a
  multi-line reconciliation table's own structure is a real, separable
  follow-up once this lands, not a prerequisite for it.
- Detecting a non-GAAP figure the source does *not* itself label as such
  (a company that fails to follow Reg G, or a non-SEC-filed document with
  looser conventions) - out of scope; this slice trusts the source's own
  labeling, the same way every other extracted field already does, and
  never invents a distinction the text doesn't state.
- Any judgment about whether a company's non-GAAP adjustments are
  reasonable or aggressive - AnalystOS labels and cites, it doesn't
  editorialize on accounting policy.
