# Slice 52 — a mandatory, deterministic "advanced" floor

## Goal

Replace the current two-outcome pipeline (full rich narrative, or a
bare-text fallback with no charts/KPIs at all) with a **guaranteed
three-attempt, two-visible-outcome** system:

1. Full rich narrative (Gate 1 + Gate 2 both passing) - unchanged, the
   best case, tried first, exactly as today.
2. If that fails: a new **deterministic tier** - code-only, zero
   additional model calls, zero possibility of failing a quality gate
   because there is no free-form generation step to gate. Produces a
   KPI strip, at least one chart (when the data supports one), and real
   analytical sentences (benchmarking, trend, relationship, disclosure
   gaps) - assembled entirely from already-verified segments.
3. True bare-text (today's flat renderer) - demoted to a genuine last
   resort, only reachable when a document has too few numeric facts for
   *either* tier 1 or tier 2 to produce anything (see "How often does
   tier 3 actually fire" below).

The user never sees a "degraded" signal distinguishing tier 1 from tier
2 - both render through the exact same `render_rich_report`/
`render_rich_pdf` (see "Architecture," below), so the visual system is
identical either way.

## Direct answer to the open question: is fixed-template generation sufficient?

**Yes - for exactly the four sentence types asked for here - with no
bounded model call needed.** Reasoning:

Genuine free-form synthesis (the rich narrative's `executive_insight`)
is hard to template because its whole job is *discovering* which two
facts are worth reading together - that's a real judgment call with no
fixed shape. But none of the four sentence types this slice needs
require discovering anything new:

- **Benchmarking** pairs a fact with a comparison the extraction layer
  *already found* (a computed `growth_percent`/`difference` segment
  already exists *because* the model found that comparison during
  extraction - Slice 45's writing-discipline rules just describe how to
  phrase a relationship that's already fully known).
- **Trend** only fires when 3+ periods of the same metric already exist
  as segments - the relationship (chronological, same metric) is given,
  not discovered.
- **Relationship/bridge** only fires on data `_detect_chart_type` (Slice
  47) *already classified* as a bridge - again, the relationship is
  already known before any sentence is written.
- **Disclosure gap** (see below) is a fixed checklist match, not a
  judgment call about what's *interesting* to flag.

In every case, the hard part (finding the relationship) is already done
by extraction or by the existing shape-detector - the sentence layer's
only job is *phrasing* a known fact, which a well-written template
handles the same way real automated research/screener tools already
write "flash" commentary at scale. The honest limitation: this tier's
prose will read more formulaic than the rich narrative's best case, and
it will never contain genuine cross-fact synthesis - that remains
exclusively tier 1's job. That's an acceptable, disclosed trade-off, not
a hidden one - and it's why tier 1 is still tried first, every time.

**Correction to the task's own framing:** disclosure-gap detection is
**not** currently code-driven and reusable as stated - today,
`disclosure_gaps` is content the *model* writes as part of
`write_narrative`'s structured response (`analystos/l2/narrate.py`'s
`_clean_paragraphs` only validates/cleans what the model already wrote;
it doesn't detect anything itself). If Gate 1 fails, that list doesn't
exist to reuse. This slice builds a genuinely new, deterministic
checklist-based detector instead (see below) - flagged here rather than
silently building something that claims to reuse code that doesn't
exist.

## Architecture

A new module, `analystos/l4/deterministic_report.py` -
`build_deterministic_report(segments, title) -> report | None` (`None`
if fewer than 2 numeric facts exist at all - the tier-3 trigger, below).
**It produces the identical `report` dict shape
`analystos.l2.narrate._assemble_report` already returns** (`title`,
`kpis`, `executive_summary`, `executive_insight`, `sections`,
`disclosure_gaps`, `outlook`, `outlook_interpretation`) - not a new
shape, not a new renderer. `render_rich_report`/`render_rich_pdf` render
it completely unchanged. This is the key design choice that makes "never
surfaced as a degraded mode" true by construction, not by convention: a
person looking at the two outputs side by side sees the same KPI-strip
styling, the same chart drawing, the same section layout - because it's
the exact same rendering code either way.

`analystos.pipeline.build_report`'s existing `except ValueError:` around
Gate 1/Gate 2 becomes:

```
except ValueError as exc:
    print(f"... rich report fell back ...: {exc}", file=sys.stderr)
    deterministic = build_deterministic_report(segments, title)
    if deterministic is not None:
        return render_rich_report(deterministic, segments, source_hash, "actual")
    return render_narrated_section(title, source_hash, segments, "actual")  # tier 3
```

No change to Gate 1, Gate 2, or the rich narrative path itself.

### KPI strip - deterministic selection

Up to 5 KPIs, built directly from `segments` (no model): for every
`quote` segment with `horizon == "reported"` and a numeric `value`, look
for a `computed` segment (operation `growth_percent`, never
`difference`/`remainder` - matching the existing rich-narrative rule
that a sign-unreliable operation never drives a KPI delta) whose
`citation` list contains that quote's own `citation` string exactly -
proving it's really *that* fact's comparison, not a guess by proximity
or value-matching (which could collide on a coincidentally identical
number). Pair them as `{label, value_fact: <quote index>, delta_fact:
<computed index>}`, same shape `_resolve_kpis` already consumes
unchanged. A reported quote with no matching computed delta still gets a
KPI (`delta_fact: -1`). Picks the first 5 in segment order - no
"importance" ranking a human/model would apply, disclosed as a real,
simple limitation.

### Charts - reuse, not reimplement

Directly reuses `analystos.l4.rich_export._detect_chart_type` /
`_resolve_chart`-equivalent shape detection over `segments` (the same
function the rich path and Slice 48's PDF renderer already both call) -
one function, three callers now, never a second guess at chart type. If
at least one chartable series is found (2+ numeric points, per the
existing rule), it becomes the report's one section chart with a
deterministic title. No chart-worthy series -> no chart, never a
placeholder or an invented one.

### Sentence generation - one function per type, all deterministic

- **`_benchmark_sentences(segments)`** - for every reported quote with
  one or more matching `growth_percent`/`difference`/`remainder`
  computed segments (matched by citation-string membership, same
  technique as the KPI pairing above): `"{label} was {value}, {direction}
  {pct}% {comparison_phrase}."` The direction word is read directly off
  the computed segment's own sign for `growth_percent`
  (`_gaap_status`-style safe default, never guessed) - `difference`/
  `remainder` never get a direction word at all, the same
  "sign isn't reliable" rule Gate 1's own `_direction_problem` already
  enforces, so this generator is incapable of making the exact mistake
  that rule exists to catch. When 2+ comparisons exist for the same
  quote (e.g. QoQ and YoY both present), they're stacked in one sentence
  - the same "stack the comparison" discipline the rich narrative prompt
  already states, just applied by code instead of asked of a model.
- **`_trend_sentences(segments)`** - for 3+ `quote` segments sharing a
  `label`, sorted by any parseable period ordering already used by
  `rich_export._is_time_series_shape`: only emits a trend claim
  ("has grown/declined for N consecutive periods") when *every*
  consecutive step moves the same direction - otherwise states the bare
  values with no trend word at all, mirroring `_consecutive_count_problem`'s
  own "stay silent rather than guess" rule. Belt-and-suspenders: the
  assembled sentence is additionally run through the existing
  `analystos.l2.narrate._consecutive_count_problem`/`_direction_problem`
  validators before use - should never trip (the generator derives
  words directly from the data, it doesn't guess at them), but this
  catches a bug in the generator itself the same way Slice 47's
  independent tie-out check catches a bug in chart detection.
- **`_relationship_sentences(segments)`** - only for a series
  `_detect_chart_type` classifies as a bridge/waterfall: states the
  total change and each named component's real contribution in one
  sentence, reusing each segment's own `label`/`citation` text (never
  inventing a driver name).
- **`_disclosure_gap_sentences(segments)`** (new, not a reuse - see
  correction above) - a fixed, short checklist of commonly-expected
  financial metrics (EPS, cash flow from operations, free cash flow,
  effective tax rate, gross margin) checked by keyword match against
  every segment's `label`/`citation`/`text`; each checklist item with no
  matching segment anywhere becomes one plain sentence ("Earnings per
  share is not disclosed in this document."). Capped at 5 so a document
  that simply isn't a full financial statement doesn't get flooded with
  "not disclosed" lines for irrelevant items.

**No Gate 1 or Gate 2 call over this tier's output at all** - not "a
lighter gate," genuinely none. Correctness here comes from construction
(every word is derived directly from already-verified segment data),
not from review; running either gate would reintroduce exactly the
model-dependency this tier exists to eliminate, for content that cannot
express Gate 1/Gate 2's failure modes in the first place (there's no
free-form claim to mis-cite, no prose to judge for filler).

## How often does tier 3 (true bare-text) actually fire?

Rarer than it might sound, and narrower than "no chartable facts":
`analyze_document` itself already raises (before either tier is ever
reached, aborting the whole request) if *zero* segments verify at all -
tier 2/3 only matter for documents where extraction *did* succeed.
Given that, tier 2 produces *something* (at minimum, a benchmarking
sentence + a KPI) as soon as **2 or more numeric `quote`/`computed`
facts exist anywhere in the document** - true tier 3 needs *fewer than
2*. Concretely, that means:

- A document with exactly one isolated numeric fact and nothing to
  compare it to (rare for a real financial report, plausible for a
  one-line data snippet).
- A document that is genuinely pure narrative/event content with no
  quantifiable figures at all - e.g. a short press release announcing
  an event (a leadership change, an award) with zero dollar figures or
  percentages anywhere.

For any real quarterly/annual report, 10-K/10-Q excerpt, or earnings
release - the actual target documents this system is built for - tier 3
should be effectively unreachable; it's a genuine edge case for
non-financial or single-fact documents, not a realistic outcome for the
kind of document this system exists to analyze.

## Done when

1. A document engineered to fail Gate 1/Gate 2 (reusing the existing
   test technique - a fake client whose narrative response is
   deliberately malformed) still automatically produces a report - via
   the identical `render_rich_report` - containing a KPI strip, at
   least one chart, and at least one sentence of each type (benchmarking,
   trend, relationship, disclosure-gap), proven by direct inspection of
   the rendered output, not just that `build_deterministic_report`
   returned something. Zero calls to `write_narrative`'s or
   `proofread_report`'s underlying client succeed or are even required
   to for this to pass. No field/marker distinguishes this output as
   "degraded" to the renderer or the reader.
2. A document with fewer than 2 numeric facts (the true tier-3 trigger)
   still falls through to today's flat renderer, proven directly - and
   a document with 2+ numeric facts but a failing Gate 1/Gate 2 never
   reaches tier 3.
3. The benchmark/trend generators' direction words are proven correct
   against deliberately adversarial segment data (a decline dressed as
   a rise would be caught, the same class of bug as Gate 1's own
   direction-word tests) - proving correctness-by-construction, not
   asserting it.
4. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Any change to Gate 1, Gate 2, or the rich narrative path itself -
  purely additive, a new tier under the existing best case.
- Genuine cross-fact synthesis in the deterministic tier - explicitly
  out of scope per the reasoning above; `executive_insight` stays
  `None` in a tier-2 report (an absent insight box, not a fabricated
  one - `render_rich_report` already treats `None` as "omit the box,"
  no new handling needed).
- A configurable/extensible disclosure-gap checklist (e.g. per-industry
  lists) - a fixed, short, general list for this slice; broader
  configurability is a real but separate follow-up.

## Separately required, not part of this slice's build

Find and report the actual root cause of Test #4/#8's Gate 1/Gate 2
fallback - still outstanding, still needs the real stderr log from a
live run, not guessed. Tracked and pursued in parallel; this slice's
new floor does not substitute for that diagnosis. (Test #9, run later
the same session against a different real document, succeeded on the
rich narrative path - it does not explain what made Test #4/#8 fail;
that root cause remains genuinely unresolved.)

## Built (post-implementation note)

`analystos/l4/deterministic_report.py` built as specified -
`build_deterministic_report(segments, title)` returns the exact
`_assemble_report` shape, or `None` below 2 numeric facts. Wired into
`analystos.pipeline.build_report`'s existing `except ValueError:` block,
between the rich path and the true bare-text fallback.

**Two real bugs found only by running a real document through it (not
caught by hand-built fixtures) - both fixed, both now covered by
dedicated regression tests:**

1. **KPI/benchmark sentences attaching to the wrong quarter.** The
   first design used citation *position* to decide which of a computed
   fact's cited quotes was "current" (last citation for
   `growth_percent`, first for `difference`/`remainder`). A real
   document produced "Net Income Q3 2025 was $22.4M, a change of
   $-2.8M" - attached to the *older* quarter, when Q3 2026 was what
   actually changed. Root cause: `analystos.l2.analyze`'s own
   `growth_percent` verification explicitly tries operands in *either*
   order and accepts whichever matches the model's claimed result - a
   model is never actually constrained to one order, so position was
   never a trustworthy signal at all, only ever a coincidence that
   happened to hold in hand-built test fixtures. Fixed by
   `_current_quote_index`: determine "current" from each candidate
   quote's own period token/chronology, never from citation position.
2. **An ordinary two-point `difference` treated as a bridge.**
   `_select_bridge` required only 2 citations, which any plain YoY
   `difference` also satisfies - producing a nonsensical "Net Income Q3
   2025 moved from {{a}} to {{b}}" relationship sentence for a fact with
   no named component at all. Fixed by requiring 3+ citations (end,
   start, and at least one real named component) - a genuine bridge,
   never an ordinary two-point comparison.

Both were caught by running the real Meridian Q3 2026 document (the
same one behind Test #8/#9) through the tier directly, per your own
requirement not to call this done from engineered fixtures alone - see
`tests/test_l4_deterministic_report.py::ChronologyNotPositionTest` for
the regression tests built directly from this live failure.

**Test proof:**
- `tests/test_l4_deterministic_report.py` (32 tests) - every selector
  and sentence generator unit-tested independently, including the two
  live-found regressions above and the adversarial
  flipped-sign-can't-lie test for the trend generator.
- `tests/test_pipeline.py::test_a_permanent_gate1_failure_still_produces_charts_kpis_and_analysis`
  - Done when #1: a permanently-broken `write_narrative` mock (same
    technique already used elsewhere in this file) still yields a
    rendered rich report with a real KPI strip, a real `<svg>` chart,
    and all four sentence types, with zero reliance on
    `write_narrative`/`proofread_report`'s underlying calls ever
    succeeding, and no field distinguishing the output as degraded
    (`test_no_field_marks_this_output_as_degraded` confirms the exact
    same key set `_assemble_report` produces).
- `tests/test_pipeline.py::test_fewer_than_two_numeric_facts_still_falls_through_to_plain_text`
  - Done when #2: a single-fact document still falls through to the
    true bare-text renderer even with a permanently-broken narrative.
- Full suite: 492/492 passing.

**Real live-run confirmation (your own requirement before calling this
done):** the real Meridian Q3 2026 document run through
`build_deterministic_report` directly (bypassing `write_narrative`
entirely - one real extraction/verification call, zero cost from this
tier itself) produced, after the two fixes above: a 5-KPI strip (Q3 2026
Revenue, Net Income, Data Services Revenue, Data Services % of Revenue,
Gross Margin - each correctly attached to the current quarter), a real
5-quarter revenue line chart, benchmarking sentences ("Net Income Q3
2026 was $19.6M, which declined..."), a trend sentence ("Revenue has
grown for 4 consecutive periods..."), and 4 disclosure-gap sentences.
The relationship/bridge sentence type was not exercised by this
particular document - its one candidate bridge fact (Data Services
organic growth) is correctly *not* verified in the first place (the
$54.0M subtotal is nowhere stated verbatim in the source), which is
correct extraction-layer behavior, not a gap in this slice; the
generator itself is proven directly by `RelationshipSentenceTest` and
the pipeline integration test above against engineered bridge data.
