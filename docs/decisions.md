# Decisions

Dated log, newest first. One entry per real choice, with the reason.

## 2026-09-08 — Horizon made visible in the rendered report (Slice 31)

Slice 29 tags every fact `reported` / `guidance` / `projected`; Slice 30
surfaces that to the narrator and asks it to keep forward material in the
outlook. This slice makes it *enforced in the output*: a `guidance` or
`projected` figure is visibly marked wherever it appears - executive
summary, any section, the outlook - so it can't be read as a verified
historical result regardless of where the model put it.

- **Mark, don't police.** A hard "reject a guidance fact used outside the
  outlook" rule was rejected: the Slice 30 prompt legitimately allows a
  forward fact in a clearly-forward-marked part of a section, so a hard
  rule would cause needless fallbacks. Marking at the point of
  substitution is strictly safer - the fact is always flagged, the report
  is never lost, and there is no model call in the slice at all.
- **Two-pass, matching the existing pattern.** `rich_export._substitute`
  runs before `html.escape` (Slice 28's double-escape bug), so it emits a
  plain-text sentinel `⟦guidance⟧` / `⟦projected⟧` (U+27E6/27E7 - never in
  financial prose, pass through `html.escape` untouched) and `_para_html`
  converts it to `<span class="horizon-tag">` in the same escape-then-
  convert pass that already handles `[n]`.
- **The plain fallback marks it too.** `render_narrated_section` appends a
  literal ` (guidance)` / ` (projected)` - plain text, flows through
  `render_html` / `render_pdf` untouched. The degraded path must not
  mislead any more than the rich one.
- **`horizon` absent → no marker.** Purely additive; every pre-existing
  test segment (no `horizon` key) renders unchanged.
- Verified beyond the suite: the Slice 30 hand-authored end-to-end run,
  re-checked - `$15.0B` (guidance) and `$4.5B` (the implied-remaining
  `difference`, also guidance) carry the marker in both the executive
  summary and the outlook; the reported quarterly figures do not; the
  sentinel never leaks as literal text.
- **Dated-event structure is explicitly NOT here.** `date` / `what` /
  `status` / `next_step` as a quote-verified segment shape in
  `analyze.py`, so an acquisition or regulatory step can be narrated as a
  real timeline, is the other half of the diagnosis's Mechanism 4. It is
  a genuine `analyze.py` + `narrate.py` change and gets its own slice
  (proposed Slice 32) - not part of the pre-approved 29-31 run. Slice 30
  already broadened discipline 4 in the prompt; until 32, events are
  narrated from `quote` / `prose` segments.

## 2026-09-08 — Structured narrator, wired end to end (Slice 30)

Slice 28 built `analystos/l4/rich_export.py` (executive summary, sections,
per-section charts, a distinct outlook block) and wired it to nothing.
Slice 29 made `analyze_document` guarantee the comparison set and tag each
fact's `horizon`. This slice closes the loop: `write_narrative` returns
the structured report shape and `pipeline.build_report`'s default path
renders it through `render_rich_report`. From here, the default output of
AnalystOS is the rich report, for any document, verification contract
untouched.

- **`write_narrative` returns a `report` dict, not a `paragraphs` list** —
  `executive_summary`, `sections` (each with an optional `chart`),
  `outlook` — exactly what `render_rich_report` consumes. It validates,
  then normalizes (`has_chart` folded away, `chart` → `None` when false or
  invalid, empty `outlook` → `None`).
- **Schema stays all-required, zero optional properties** — the exact
  pattern that fixed Slice 26's `400 Schema is too complex`. "Not
  applicable" is the `has_chart` boolean plus placeholder values, never an
  absent key. Nesting (report → section → chart → series) is fine; it was
  *optional*-property combinatorics that broke the grammar compiler, and
  there are none.
- **A malformed chart is the one non-fatal case.** Every paragraph
  failure (bad `{{N}}`, stray digit) and every structural failure (empty
  summary/sections, a section with no heading or body) raises → the
  pipeline falls back to Slice 26's plain rendering, no partial
  acceptance. A bad chart is just dropped (`chart` → `None`), matching
  `rich_export._resolve_chart`'s existing "a bad chart is left out, the
  report is never lost" rule — that check stays as defence in depth,
  `write_narrative` now also runs it up front.
- **Prompt extends the five disciplines, doesn't replace them.**
  Discipline 4 broadened from "legal/regulatory content" to *any* dated or
  sequential event (a deal, a launch, a leadership change, a financing) —
  the user's ask was explicitly wider than the reference pieces that
  seeded the original wording. Discipline 5 got a worked example of
  co-stating trigger and consequence in one sentence. New structural
  instruction (exec summary / 3-5 sections / outlook), chart guidance
  (only 2+ cited facts, only when the shape carries information), and a
  `horizon` instruction (forward-looking facts belong in the outlook —
  Slice 31 *enforces* it). `coverage_summary` from Slice 29 is passed into
  the prompt so a genuinely thin document is described as thin rather than
  dressed up.
- **`build_report`'s default path now returns a full HTML document**,
  where the table/`template` path still returns section markdown.
  Contained by two small guards, no contract rewrite: `render_html` is
  idempotent on an already-complete document (so `api/analyze.py` needs no
  change — the live frontend only reads `data.html` anyway), and
  `pipeline.main()` writes `section.html` directly for an HTML section and
  skips the `.md`/`.pdf` writes for it. A real `.pdf` of the
  sectioned/charted layout (extending Slice 24's `reportlab` renderer) is
  its own follow-up.
- **`render_narrative_section`** (the flat narrative renderer) stays in
  `export.py` for its own tests but leaves the pipeline path — rich or the
  Slice 26 plain fallback, nothing in between.
- Tested against a mocked client only. A hand-authored structured response
  for the Slice 29 multi-period mock document, run through the real
  `write_narrative` + `render_rich_report`, produced the target shape:
  executive summary, sections, a line chart drawn only from cited
  quarterly facts, a distinct outlook, one shared 8-footnote sequence,
  guidance and implied-remaining figures rendered from verified `computed`
  segments. Whether a *real* model produces this well from a real
  document is the post-merge Vercel smoke test, flagged before any paid
  call.

## 2026-09-08 — L2 extraction contract: guarantee the comparisons, tag the horizon (Slice 29)

`analystos/l2/narrate.py`'s prompt already instructs all five
executive-writing disciplines (benchmark, name the mechanism, sequence
past from future, narrate events, co-state cause and effect). The gap the
`mock_rich_report_v3.html` diagnosis surfaced
(`docs/rich-report-diagnosis.md`) is upstream of the writing: the
narrator can only write from what `analyze_document` extracted, and that
stage returned "the important facts" with benchmarking left to the
model's per-run discretion. No prompt on the narrator conjures a
comparison that was never computed. This slice is `analyze.py` only.

- **`difference` is now a supported operation.** Subtraction was excluded
  through Slice 26 because a model could smuggle a sign flip (the
  `sum([1240, -1050])` "net additions" case). That hole was closed
  separately by `_value_matches_text`, which checks each operand's value
  against the number its own `exact_text` spells out, sign included. With
  that check in place `operands[0] - sum(rest)` is safe — and it is the
  operation an absolute period-over-period change, a margin move in
  points, and "stated target minus the actuals so far" all need, none of
  which the five prior operations could express. A dedicated test retries
  the old sign-flip exploit under `difference` and confirms it still
  fails.
- **Every segment carries a `horizon`:** `reported` (default),
  `guidance`, or `projected`, verified by the same substring + value-match
  checks as any quote. Nothing in L4 consumes it yet — Slice 31 wires the
  outlook block from it and enforces "no projected figure unmarked in a
  history section." Produced now so that wiring has something to read.
- **The prompt's "what to report" section is now a completeness
  contract:** for every figure featured, surface *every* comparison the
  source's own numbers support (prior value + `growth_percent` +
  `difference`; each period of a 3-plus-period trend as its own quote;
  `percent_of_total` of a stated total; target-vs-actuals where a target
  is stated). The honesty rule is unchanged and explicit: if the source
  doesn't contain a comparison, leave the figure without one — never
  invent one. The bar is on which *citable* comparisons must be computed
  when available, not on inventing them.
- **Return type stays `list[segment]`.** The spec floated returning a
  dict with a coverage summary; threading that through `pipeline.py` and
  ~20 tests was more churn than value for a signal that's derivable from
  the segments. Instead `coverage_summary(segments)` is a module helper —
  comparison count, reported-figure count, horizon breakdown — for the
  Slice 30 narrator to flag a thin document, and for tests. Verified
  segments also now carry `operation` (previously dropped after
  verification) so the helper, and later the narrator, can tell a
  comparison from an aggregate.
- **Schema stays all-required.** `horizon` is one more required enum on an
  object whose every property is already required — no optional-property
  combinatorics, so no repeat of the `400 Schema is too complex` failure
  (that was caused by *optional* properties).
- **Peer / sector / index benchmarks remain out of scope.** The system
  sees one document; the verification guarantee forbids a comparison it
  can't cite. A boundary, not a bug — revisit only if a second (peer)
  source is supplied.
- Tested against a mocked client only (no `ANTHROPIC_API_KEY` in the
  build env). Whether a *real* model produces the full comparison set
  from a real document, unprompted per run, is the post-merge Vercel
  smoke test in the agreed proof plan — flagged before any paid call.

## 2026-09-06 — Rich rendering: charts, real section structure, a distinct outlook block (Slice 28)

Slice 27 fixed how the words read; this fixes what the report looks
like. Explicit bar: a Fortune 10 executive should see something their
own strategy/IR team would produce - charts where data supports them, a
real executive-summary-first section structure, forward-looking
"outlook" content visually impossible to mistake for a verified fact.

**Scope drawn deliberately narrow, and stated up front:** this slice
builds the *rendering capability* - new `analystos/l4/charts.py` and
`analystos/l4/rich_export.py` - proven by hand-authoring the structured
input a future L2 stage would produce and running it through the real
render code, not by writing throwaway HTML. It does not build that L2
stage (a model actually deciding section structure/chart placement/
outlook content from a real document) - that's a new prompt, schema, and
tool-use design in its own right, and it needs its own live test before
it's trusted, same as every other model-facing change today. Drawing
this line let the rendering side get reviewed and merged on its own
strength, independent of a not-yet-built model-decision layer.

**Charting approach**: checked `requirements.txt` first, per the
instruction to use what's already available before reaching for
something new. Nothing exists yet. Chose plain inline SVG (zero new
dependency - a browser renders it natively with no JavaScript) over
`matplotlib`, which would add real weight to Vercel's serverless
functions for something a few hundred lines of string-built markup
already does. `reportlab` (already a dependency) has
`reportlab.graphics.charts` for a PDF equivalent - explicitly deferred,
not part of this round's ask (an HTML draft specifically).

**A chart data point inherits Slice 26's verification by construction,
not a new check.** A chart spec's `fact_index` can only point into
`segments`, which is already 100% verified by the time anything reaches
L4 - exactly how `{{N}}` already works in prose. `_resolve_chart` does
its own defensive bounds/type check (in range, quantitative, not
`prose`) because no L2 stage produces or validates chart specs yet - the
same structural check `_validate_paragraph` already does for text
placeholders, just not inherited from anywhere since this is new. A bad
point is dropped; a chart left with fewer than two points is dropped
entirely rather than rendered as something misleading.

**A real bug caught by the new test suite, not by review**: the first
draft inserted real `<sup><a>` HTML during placeholder substitution, then
ran the whole paragraph through `html.escape()` afterward - double-
escaping the markup into literal `&lt;sup&gt;` text. Fixed by matching
the existing codebase's own pattern (`export.py`'s `_para_html`): escape
first, then convert plain `[n]` markers into real HTML - two passes, not
one, so nothing inserted mid-pipeline gets re-escaped downstream.

Verified with a hand-authored mock (a clearly-labeled DRAFT/TEMPLATE
earnings report for a fictional company, not a real client's data), run
through the real `render_rich_report` - 4 embedded charts, a shared
footnote sequence across the executive summary/4 sections/outlook, cross-
section synthesis (margin compression and segment-mix shift connected
explicitly as one story, not two). Honestly scoped: this fictional
source has no legal/regulatory content and no market-reaction event
either, so two of Slice 27's five writing disciplines still aren't
exercised by any mock built so far - even a *real* earnings report
wouldn't naturally contain those, since a company's own report doesn't
cover its own stock's reaction to itself. Proving those two needs a
source that's actually news coverage, not a financial report.

## 2026-09-06 — Five mechanical writing disciplines, grounded in four real reference pieces

The prior prompt rewrite (Pyramid Principle/SCQA) fixed structure but was
still too abstract to mechanically prevent a flat fact-list - "say what's
notable" doesn't tell a model *how*. Given four real, fully-read reference
pieces (a McKesson equity-research note, a Zacks research digest, a
Courthouse News DOJ/Google appeal story, and CNBC's UnitedHealth DOJ
investigation coverage) and asked to extract the actual mechanical
patterns that separate them from a fact sheet - not another round of
stylistic guessing.

Five disciplines, each traced to a specific thing the reference pieces do
and now written into `_SYSTEM_PROMPT` in `analystos/l2/narrate.py`:

1. **Benchmark every number, stacking comparisons when the source
   supports more than one** - the McKesson piece never reports a return
   alone; it layers one-year vs. S&P 500, then YTD-only, then a
   sector ETF, because each comparison told a different part of the
   story.
2. **Name the specific mechanism behind any tension, never a category
   word** - McKesson names actual drivers (oncology, GLP-1 demand vs. a
   named primary-care mix shift), never "headwinds."
3. **Sequence past from future; never blend them in one sentence** - both
   financial pieces fully resolve current performance before turning to
   forward-looking material (ratings, targets, catalysts) as a distinct,
   later block.
4. **Legal/regulatory content narrated as a dated, unfolding process** -
   the Courthouse News piece names the specific remedy being appealed and
   gives a concrete filing date, never a generic "legal risk" label.
5. **State a triggering event and its reaction together** - the
   UnitedHealth coverage states the stock-drop magnitude and its specific
   cause in the same breath, and represents the company's own stated
   defense faithfully rather than asserting a verdict.

Explicitly scoped as conditional: not every document has legal or
market-reaction content, and the prompt says so - apply each discipline
only where the source actually supports it, never force one that
doesn't fit. The verification contract is untouched (same `{{N}}`
mechanism, same `_validate_paragraph`, same schema).

Rebuilt the mechanically-real mock (hand-written paragraphs through the
actual `_validate_paragraph`/`render_narrative_section` code) against the
new prompt, and was honest about its limits: the Solstice source has no
legal or market-reaction content, so disciplines 4 and 5 aren't
exercised by this mock at all - only a live test on a document that
actually contains that kind of material can confirm those two work.
Also deliberately did *not* invent a mechanism for a cost-growth figure
the source doesn't explain, rather than force discipline 2 where it
isn't supported - flagged in the mock's own text instead.

## 2026-09-06 — Rewrote the narrative prompt against real executive-writing patterns

Every live test so far (even before any of them succeeded end to end)
carried the same underlying flaw: `write_narrative`'s prompt asked for
"structure however best serves an executive reader" - vague enough that
one fact per paragraph, in extraction order with a bolded label, trivially
satisfies it. That's a fact sheet, not analysis, and it was never going to
change on its own no matter how many bug fixes landed. Explicit ask: fix
this *before* spending more on a live test, not after, since a working
bug fix paired with a still-flat writing style would waste the test on a
known-insufficient output shape.

Researched how real executive/analyst writing is actually structured
rather than defaulting to a generic "sound smart" instruction:

- The **Minto Pyramid Principle** (Barbara Minto, McKinsey) - lead with
  the single governing answer, then MECE-grouped support ordered by
  importance. "You think from the bottom up, but you present from the top
  down" - the standard taught at McKinsey/BCG/Bain.
- **SCQA** (Situation-Complication-Question-Answer), the same Minto
  framework applied to how an opening frames "why this matters" before
  the supporting detail.
- **Equity research practice**: "numbers by themselves do not usually
  convince anybody of anything" - reports connect figures to a story,
  usually built around two or three things that actually matter, with
  qualitative context explaining *why* a number is moving, not just that
  it is.

Rewrote `_SYSTEM_PROMPT` in `analystos/l2/narrate.py` around these:
open with a 2-3 sentence bottom-line takeaway; 3-5 substantive paragraphs
each built around one analytical point (not one number) with facts woven
in as evidence; explicitly call out tension/anomalies/comparisons rather
than flat restatement; a closing risk/outlook note. Explicit anti-pattern
named directly in the prompt: "never produce a paragraph that is just
'Label: sentence with one number in it,' repeated fact after fact."

The verification contract is completely unchanged - still `{{N}}`
placeholders only, still the same `_validate_paragraph` checks, still no
schema change (kept to the same single required `text` property, given
Slice 26's `400 Schema is too complex` history). This is purely a change
to what the model is asked to do with already-verified facts, never to
how those facts are checked.

Before spending on a live test, produced a mechanically-real mock (not
just typed-up prose): hand-wrote paragraphs in the new style using the
already-verified Solstice facts from Test #2/#3, ran them through the
actual `_validate_paragraph` and `render_narrative_section` code (not a
model call), and confirmed the shape renders correctly. Also surfaced a
real, expected side effect of the earlier verification-gap fix: a fake
"operating income" figure (previously only reachable via the negated-
operand exploit) is gone for good, since subtraction still isn't one of
the five supported operations - the mock instead uses a legitimate `sum`
of cost of revenue + opex (both real, correctly-signed quoted operands).

## 2026-09-06 — A follow-up commit landed after its PR had already merged

Test #3's continued fallback-shaped output looked like the value-matching
and calendar fixes below hadn't worked. They hadn't been *deployed at
all*: they were pushed as a second commit to the `slice-27-narrative-pass`
branch after PR #39 (which only covered the branch's first commit) had
already been merged - `git log`/`git branch --contains` confirmed the
merge commit only covers up through the "Add PR #39 reference" commit,
and the fix commit existed only on the now-orphaned branch, never on
`main`. Reported it as "pushed to PR #39" without re-checking the PR was
still open at that moment - it wasn't. The "190" exploit's absence in
Test #3 was the model choosing different phrasing that run, unrelated to
any fix actually running. Recovered by cherry-picking that commit's real
changes onto a fresh branch off current `main`, rather than assuming a
push reached wherever it was aimed - and by actually diffing the merge
commit against the fix commit to confirm, not just asking for another
retest and guessing again from the result.

## 2026-09-06 — write_narrative's remaining failure paths were unlogged

A precaution taken alongside the recovery above, before any of this had
actually reached a live test: the per-paragraph validation-rejection path
had logging (added earlier today), but `write_narrative`'s other two
failure points - the model's response having no `tool_use` block at all,
and the model returning an empty `paragraphs` list - did not. Either
could produce a silent fallback with zero log evidence, exactly like the
gap that motivated adding logging in the first place. Added logging to
both remaining raise points, plus a success line (`narrative accepted: N
paragraphs`) so a clean run is also visible, not just inferred from the
absence of a rejection - the next live check is conclusive either way.

## 2026-09-06 — Closed a real verification gap found on the first Slice 27 live test

The first live test of Slice 27 (two real Anthropic calls, both `200 OK`
per Vercel's logs) still rendered Slice 26's plain fallback, and the
output contained "Net customer additions were 190" - correct
arithmetically (1,240 − 1,050 = 190), but subtraction isn't one of the
five operations `_recompute` supports (`sum`/`average`/`ratio`/
`growth_percent`/`percent_of_total`). The only way to land on exactly 190
is `sum([1240, -1050])` - the model quoted the real substring `"1,050"`
but paired it with `value: -1050.0`. `_verify_computed` only checked that
`"1,050"` really appears in the document; it never checked that the
*number* paired with it (`-1050` vs `1050`) is what the text actually
says. Same root cause explained a `$7.6M` operating-income figure computed
via a three-way signed `sum` faking `revenue − cogs − opex`. Both landed
on the *true* number this time - the finding is that nothing stops the
same mechanism from landing on a false one, which is the entire premise
this project is built to prevent.

Fixed in `analystos/l2/analyze.py`: `_parse_number`/`_value_matches_text`
parse the actual number a piece of quoted text spells out (handling `$`,
commas, `%`, accounting-parens negatives, and `K`/`M`/`B`/`thousand`/
`million`/`billion` scale words, with a lookahead so "142 members" isn't
misread as 142 million) and reject a quote or computed operand whose
claimed `value` doesn't match. Applied to `_verify_quote`, every operand
in `_verify_computed`, and `percent_of_total`'s `total_value`. New tests
reproduce the exact live exploit (confirmed they fail without the fix,
pass with it) plus the abbreviated-figure and false-positive-word cases
the stricter parsing has to get right to avoid new false rejections.

## 2026-09-06 — Calendar references don't need a citation

Also found on that same live test, from the Vercel log's two `200 OK`
Anthropic calls: the narrative pass got a real, successful model response
and my own validation code rejected it anyway - `write_narrative` had no
logging on that path, only on an `anthropic.APIError`, so this was
invisible until reproduced manually. Root cause: `_verify_prose` (Slice
26) and `write_narrative`'s paragraph check (Slice 27) both ban any digit
outside a citation - but ordinary analyst writing constantly mentions a
quarter or year ("heading into Q4 2026"), so the ban was rejecting almost
any real connective prose, not just genuine unverified figures.

Added `_CALENDAR_RE` in `analyze.py` (quarters, halves, `FY`-prefixed
years, bare `19xx`/`20xx` years) and strip it before the digit check in
both `_verify_prose` and `narrate._validate_paragraph`, so a calendar
reference is allowed while an actual number still isn't - it was never a
claim that needed a source quote in the first place. Also added logging
to `write_narrative`'s own validation-rejection path (previously silent),
matching the logging `analyze_document` already had for API failures -
this exact gap is why the live failure had to be reproduced manually
instead of read straight from the logs.

## 2026-09-06 — Backend-first roadmap toward Fortune 10 exec-quality reports

Slice 26 proved the core loop works on a real live document, but its
output is a fact list, not writing - one paragraph per verified fact, in
extraction order, with no real structure. Discussed the end goal directly:
any document, any size, any format, a report worthy of a Fortune 10
executive, the user choosing the output shape (one-pager/slide deck/memo)
and giving feedback on a generated report to have it improve. Agreed
backend work comes before frontend polish, in this order:

1. Split verification from writing so writing quality can be pushed hard
   without ever reopening the door to a fabricated number (Slice 27,
   below).
2. Write down a concrete rubric for "Fortune 10 exec-worthy," not vibes.
3. Handle documents too large for one model call (chunk, verify per
   chunk, synthesize once over the combined verified facts).
4. Harden extraction for messier real-world files.
5. Add an output-shape selector on the backend (one-pager/memo/slide
   deck), API-first, before any UI exists to choose it.
6. Add the feedback/revision loop - re-run the writing pass with a
   person's critique, but always re-verify before showing anything.
7. Move off "one HTTP request does everything" once chunking/feedback
   both need multi-step state.
8. Build a real eval set graded against the rubric from step 2.
9. Iterate against that eval set - the same live-testing discipline as
   every slice so far, systematized instead of one document at a time.
10. Frontend controls for shape choice and feedback, last.

## 2026-09-06 — Split verification from writing (Slice 27)

Step 1 of the roadmap above. `analystos/l2/analyze.py`'s extraction and
verification logic is completely untouched by this slice - it's the
safety net every later step still depends on, so it stays frozen while
writing quality gets pushed on separately.

Added `analystos/l2/narrate.py`: a second, narrower model call
(`write_narrative`) that takes only the already-verified `segments` from
`analyze_document` - never the raw document - and returns an ordered list
of paragraphs. A paragraph is free prose that may reference a citable
fact via a `{{N}}` placeholder (`N` = that fact's index); it can group
several facts into one sentence, add a transition, or skip a fact
entirely - real structural choices Slice 26's one-paragraph-per-fact
rendering couldn't make. It cannot write a number itself: every
placeholder is substituted afterward, in `analystos/l4/export.py`'s new
`render_narrative_section`, with the exact value Slice 26 already
verified - a fact referenced twice reuses one footnote number, by first
appearance. A stray digit outside a placeholder, or a placeholder
pointing at an out-of-range index or a `prose` segment (nothing to cite),
rejects the whole narrative.

Two design choices worth recording:

- **Fail to the known-good path, not to an error.** `pipeline.build_report`
  tries `write_narrative` + `render_narrative_section`; any `ValueError`
  (bad model output, a validation failure, an `anthropic.APIError`) falls
  back to Slice 26's `render_narrated_section` unchanged. A worse-structured
  report is an acceptable cost of a quality experiment; losing the report
  entirely is not.
- **`{{N}}` parsed from the text itself, no separate `refs` field.** A
  redundant field that could disagree with the text it's describing is a
  bug waiting to happen; parsing keeps one source of truth. Also kept the
  tool schema to exactly one property (`paragraphs: [{text}]`, fully
  required) - deliberately, after Slice 26's schema already produced a
  real `400 Schema is too complex` once (see 2026-09-05).

Refactored `analyze_document`'s inline client-resolution and error-
handling into shared `_resolve_client`/`_create_message` helpers in
`analyze.py`, since there are now two real call sites (`analyze_document`
and `write_narrative`) that must not reimplement or drift from the same
missing-key check and `APIError`→clean-`ValueError` conversion. Also
renamed `analystos.l4.export._format_number` to `format_number` and
factored a new `display_value` helper there, both now genuinely shared
across L2 and L4 rather than L4-private.

Doubles the per-report Anthropic cost (a second real model call) - not
deployed or live-tested with a real API key yet; built and tested
entirely against mocked clients per the standing rule on real spend.

## 2026-09-05 — The narrated path always uses "actual" currency scale

Found on the first successful real report: every dollar figure came back
1000x too large ($18.4B instead of $18.4M for a real "$18,400,000" quoted
directly from the source memo) - all math was verified correct
independently (confirmed by hand: 29.6% growth, 59.8% share, 5.2%
non-renewal rate, $8.7M profit all check out), so this was a display bug,
not a verification bug. Cause: the upload page's "Currency scale" dropdown
was set to "Data is in thousands," and `build_report` passed that straight
through to the narrated path's renderer, multiplying an already-real
number by 1,000.

That control only ever made sense for the old table-driven path, where a
CSV/Excel table's own header can say "figures in thousands" - a real,
if old-fashioned, accounting convention. It has no meaning for the
narrated path: `analyze_document`'s quoted `value`s are always the literal
number as it's written in the source text, never something pre-scaled by
a stated convention. Fixed in `analystos/pipeline.py` by hardcoding
`"actual"` for `render_narrated_section` regardless of what's passed in -
the parameter is accepted but ignored on this path, matching how the
narrated default already ignores `schema`. Also moved the "Currency scale"
control in `site/upload.html` behind the same "this file is a table"
checkbox as the rest of the old-path-only UI, so it's not visible (and
can't be mis-set) for a narrated upload at all.

## 2026-09-05 — Every segment field is required, not just "type" (real live 400)

The first real, paid call to `write_report` - after `ANTHROPIC_API_KEY` was
finally working and the previous logging fix let the real error surface -
came back `400 Bad Request: "Schema is too complex."` from Anthropic
itself, not from any bug this codebase's own error handling could catch.
The original `_TOOL["input_schema"]` required only `"type"` on each
segment, leaving twelve properties genuinely optional (`display`, `label`,
`value`, `operands`, `total_exact_text`, ...). Strict-mode tool use
compiles the schema into a grammar, and a schema with that many optional
properties on one object forces the compiler to represent every possible
combination of which ones are present - exactly the kind of blowup real
users have hit and reported upstream (this is a known, if under-documented,
strict/structured-output limitation, not unique to this schema).

No mocked test could have caught this - every test in
`tests/test_l2_analyze.py` patches `client.messages.create` directly, so
the real schema is never sent to Anthropic's real validator. This is the
first defect only a genuine, paid API call could surface.

Fixed by making every property required and replacing "is this key present"
with explicit `has_value`/`has_total` booleans - a segment that doesn't use
a field still supplies a placeholder (`""`, `0`, `[]`, `"none"`) and the
flag says whether to look at it. This removes the combinatorial optionality
entirely (every segment object now has exactly one shape) at the cost of a
longer system prompt and a few more required keys. `_verify_quote` and
`_verify_computed` in `analystos/l2/analyze.py` now branch on the explicit
flags instead of key absence; existing tests updated to set them. Added
dedicated positive/negative tests for `has_total` specifically, since that
branch (`percent_of_total`) had no direct test coverage before.

## 2026-09-05 — Log the real Anthropic failure server-side, not just a generic message

Found immediately after the previous fix went live: the client-facing
message ("analysis is temporarily unavailable") is deliberately generic -
it has to be, since `anthropic.APIError`'s own text can carry account/
request detail that shouldn't reach a client response. But that means a
bad key, missing billing, a rate limit, a wrong model name, and a real
Anthropic-side outage are now genuinely indistinguishable from the outside
- including to me, debugging this from outside Vercel's dashboard. Nothing
printed the real exception anywhere, so a handled `ValueError` left no
trace at all in the function logs.

Fixed by printing the real `anthropic.APIError` (`repr(exc)` - the SDK's
own error text, which does include the useful part like an HTTP status
code) to stderr before converting it, right where it's caught in
`analystos/l2/analyze.py`. Server logs only, never the response body -
that boundary is unchanged. Vercel's function logs are the actual next
diagnostic step for the real live-test failure this follows.

## 2026-09-05 — A missing API key must fail clean too, not just a bad call

Found via a real live test: the first Anthropic error-handling fix only
caught `anthropic.APIError` around `client.messages.create(...)`, on the
assumption that any auth problem would come back from Anthropic's server as
an API-shaped error (`AuthenticationError`, a subclass of `APIError`). A
completely missing or empty `ANTHROPIC_API_KEY` doesn't reach the server at
all - the SDK can't build an authenticated request and raises a plain
`TypeError` ("Could not resolve authentication method") from inside that
same call, which the `except anthropic.APIError` clause never sees. That
crashed as a raw, unhandled Flask 500 instead of the intended clean 400.

Fixed in `analystos/l2/analyze.py` by checking the constructed client's
`api_key` *before* the call, only on the production path (`client=None`,
where a real `anthropic.Anthropic()` is built) - tests that patch in a
bare stand-in client have no `api_key` attribute at all, so
`getattr(client, "api_key", "present")` leaves them alone and this doesn't
change any existing test's behavior. Confirmed the exact `TypeError`
reproduces with the fix reverted and the new test in place, and that it's
gone with the fix applied.

## 2026-09-05 — Upload page: narrated analysis is now the default, not just the API's

Found while preparing a real live test: `site/upload.html` had a hardcoded
`<input type="hidden" name="template" value="income_statement">`, sent on
every submit regardless of the schema field's contents. `api/analyze.py`
already treats an omitted `template` as the new Slice 26 narrated-analysis
default, but the live page could never actually omit it - every upload,
table-shaped or not, was silently forced through the old column-by-column
path. A non-tabular document (a memo, a slide deck) would fail there since
there's no table to extract, which is exactly the case the new default
exists to handle.

Fixed by removing the hardcoded field. The page now defaults to the
narrated path (no `template`, no `schema` sent) and only sends
`template=income_statement` when a new "this file is a table shaped like an
income statement" checkbox is explicitly checked - which is also the only
case that shows the Detect columns/schema UI at all. `tests/test_upload_page.py`
updated to match: it no longer asserts a static `name="template"` attribute
exists (there isn't one any more) and instead asserts the checkbox and the
JS that conditionally sets `template` are both present.

## 2026-09-05 — Anthropic API failures fail clean, not with a raw 500

Follow-up to Slice 26, prompted by setting up the real `ANTHROPIC_API_KEY`
and a monthly spend cap: `analyze_document` only wrapped verification
failures in `ValueError`, which is what `api/analyze.py` converts to a
clean `400`. A failure in the API call itself - a hit spend limit, a bad or
revoked key, a rate limit, an Anthropic-side outage - raises some
`anthropic.APIError` subclass instead, which would have passed through
uncaught and surfaced as a raw, unhandled `500`. Fixed by catching
`anthropic.APIError` (the common base for every SDK-raised failure - status
errors and connection errors alike) around the one API call and re-raising
as a `ValueError` with a generic message ("analysis is temporarily
unavailable") - never the raw exception, which can carry account or request
detail that shouldn't reach a client response. Means hitting your own spend
cap now fails the same clean way every other pipeline error already does,
instead of looking like the site is broken.

## 2026-09-05 — Narrated analysis: read any document, verify every number (Slice 26)

Prompted directly by a live gap: the only template (`income_statement`)
requires a period-like column, so a file that's genuinely tabular but isn't
shaped like an income statement (a company/revenue/employee list, say)
failed cleanly rather than producing a report. Working through what "no
restrictions" should actually mean landed on a real architecture change,
not an addition - `docs/architecture.md`'s L2 was already described as
"retrieval + analysis... every claim points back into L0"; what shipped
through Slice 25 was a deliberately thin first slice of that, not its
ceiling.

**What changed, and why, in the order the design actually evolved during
building:**

- **Not forced into a table.** `analystos/l1/document_text.py` reads a
  document's real text content - paragraphs, bullet points, table cells
  rendered as readable text - the same way for all five supported formats.
  A memo or a slide deck with no table at all now reads the same as a
  spreadsheet; nothing requires row/column structure to exist.
- **A model reads the whole thing and decides what matters; it never
  supplies a number.** `analystos/l2/analyze.py` sends the real document
  text to Claude and gets back a structured list of segments (via strict
  tool use, not free text) - each a quote, a computed value, or plain
  connective prose. A quote gives `exact_text` the model claims is verbatim
  in the source; this code checks that with an actual substring match
  against the real text - not "the model says so." A computed value (a
  sum, a ratio, a growth rate, a share of total) gives its own raw operands
  the same way, *plus* the operation and the model's claimed result - and
  this code *independently recomputes* that arithmetic and checks it
  matches. This second check is the reason a citation alone isn't enough:
  it proves a quote is real, but says nothing about whether math performed
  on top of it is correct - a real gap surfaced explicitly while designing
  this, not caught by accident. Prose is scanned for stray digits and
  rejected if any appear - no number ever reaches the report without going
  through one of the two checks above. A segment that fails verification is
  dropped, not shown, not retried; a report where *nothing* survives is a
  real `ValueError`, never a silent partial success.
- **A number renders as a number when that's the point.** Each segment
  carries its own `"display"`: `"stat"` for a standalone labeled figure,
  `"inline"` for a sentence with context. The model chooses per figure,
  not a global setting.
- **Model: Claude Sonnet 5, not Opus 5** - overriding Anthropic's own
  default-to-Opus guidance for one disclosed, concrete reason:
  `api/analyze.py` runs as a Vercel function with a real 10-second
  wall-clock ceiling. Opus 5's always-on extended thinking makes that a
  real timeout risk for a bounded, structured-output task like this one;
  Sonnet 5 reliably finishes well inside it. A one-line change to revisit
  if the Vercel plan changes or quality disappoints.
- **A new required secret, `ANTHROPIC_API_KEY`, on Vercel** - separate from
  anything used to build this code - and a new, real, small, ongoing
  per-report dollar cost that didn't exist before this slice.
- **This is the new default, not a replacement.** `build_report` now runs
  this path when *neither* `asks` nor `template` is given at all - the
  original schema/table-driven path (explicit `asks`, or
  `template="income_statement"`) is completely unchanged and still costs
  nothing extra to run; this only fires when nothing else was specified,
  which is the new default for the live API/site.
- **Disclosed, accepted residual risk:** a text value from the source
  (e.g. a company name) still reaches the model as data it can quote or
  reason about, with an explicit system-prompt instruction that all such
  values are data, never instructions - a standard, imperfect mitigation.
  Verification catches every fabricated *number*; it cannot catch
  manipulated *wording* smuggled in through a text field the model quotes
  or paraphrases around.
- **Tested entirely against a mocked Anthropic client** - this session had
  no `ANTHROPIC_API_KEY` and no way to reach the real API, so the test
  suite verifies the logic (a fabricated quote is rejected, fabricated math
  is rejected even with real cited numbers, prose with a stray digit is
  rejected) deterministically, with no cost and no network dependency. Real
  output quality - whether Claude actually produces good, well-chosen
  analysis in practice - can only be confirmed once a real key is set and
  a real request is made.

## 2026-09-05 — Real production bug: /api/extract 404'd on Vercel

Confirmed live, right after `ANALYSTOS_ACCESS_CODE` was finally set on the
Vercel project (the one open item from Slice 22): `/api/extract` (Slice 25)
returned Vercel's own 404 page ("The page could not be found"), never
reaching our code at all - while every local test for it passed.

Root cause: exactly the file-based routing model researched and recorded
here for Slice 20 - one `.py` file in `api/` maps to one route matching
*its own path* (`api/analyze.py` -> `/api/analyze`), regardless of what
routes a file's Flask app defines internally. `/api/extract` was added to
the same shared app inside `api/analyze.py` instead of its own file, so
Vercel had no file to map that path to. Flask's test client bypasses this
entirely - it calls the app object directly - so nothing in the test suite
could have caught it; this was exactly the "only confirmable once deployed"
residual risk Slice 20's own entry already flagged, now realized for real.

Fix: `api/extract.py`, a one-line file that just re-exports the same shared
`app` object from `api/analyze.py`. Gives Vercel a matching file for
`/api/extract` while keeping exactly one implementation of every route -
two file-based doors into the identical app, not a second app or duplicated
logic. A regression test (`tests/test_api_vercel_routing.py`) checks both
files resolve to the identical app object with both routes registered, so
this can't silently regress if a third route gets added the same way.

## 2026-09-04 — Universal upload: auto-detected schema, PDF's constraint
generalized instead of special-cased (Slice 25)

Prompted directly by feedback that an analyst shouldn't have to know which
of 4 extensions were accepted or hand-type an exact JSON schema before the
system would touch their file - and that's correct once a table is
extracted, format has never mattered to L0/L2/L4. Two real changes:

- **Schema auto-detection, not elimination.** `analystos.l1.schema.guess_schema`
  guesses `"number"` vs `"text"` per column using the exact same
  `_clean_number_token` cleaning `apply_schema` already applies when typing
  a value - so a guessed schema and a hand-typed one behave identically once
  resolved. An explicit schema is still honored exactly as before; nothing
  is guessed when one is given. `analystos/scaffold.py`'s own CSV-only
  guessing heuristic (duplicated since Slice 9) was replaced by this shared
  one - a real behavior improvement in passing, since scaffold's own
  `float(value)` check missed `$`/comma/`%`/paren-formatted numbers that
  the shared cleaner already handled correctly.
- **PDF's real constraint (a table inferred from layout, not read from a
  real object, so it can be misread) doesn't go away - it becomes universal
  instead of PDF-only.** Every format now gets a preview step
  (`POST /api/extract`) before a report is generated, not just PDF; PDF's
  preview additionally carries a warning. This is what actually let PDF
  join `api/analyze.py`/`site/upload.html` for the first time - the
  "PDF needs its own review-step UI" gap Slices 20/21/23 all flagged is
  closed by this same mechanism, since every format already needed one.
  The confirm-before-cite gate itself (Slice 23) is unchanged in behavior;
  it's satisfied via a `pdf_confirmed` form field once the browser has
  shown the preview, the same way Slice 23's CLI job.json flag always did.

Found and fixed a real bug while building this: `guess_schema` originally
scanned its `numbered_raw_rows` argument once per header, silently starving
every header after the first when called with a one-shot generator
(`scaffold.py` passed `enumerate(rows, ...)` directly) - only the first
column ever got real data, everything else guessed "text". Fixed by
materializing the argument inside `guess_schema` itself, so no caller has
to know it's scanned more than once; a regression test
(`test_a_one_shot_iterator_still_works_for_every_header`) locks this in.

## 2026-09-04 — PDF output: reportlab put to its actual use (Slice 24)

`reportlab`, pinned since Slice 23 for test fixtures only, is now used for
its actual intended purpose: `analystos.l4.export.render_pdf` builds a real
generated `.pdf` from a rendered section - a title, one paragraph per
finding, a rule, then footnotes - mirroring `render_html`'s layout via a
shared `_parse_section` helper so there is exactly one place that parses a
section string, not two. Verified directly before finalizing this design:
built a real `reportlab` document with a superscript marker and a bold
footnote number, then read the exact expected text back out with
`pdfplumber` - title, body sentence, and footnote citation all present.

Scoped to L4/CLI only, matching Slice 23's own discipline: `api/analyze.py`
and `site/upload.html` are untouched. A real PDF *download* on the live
site is a genuine, separate product decision (a new API response shape, a
UI affordance) worth its own scoped slice, not a rider on this one - until
then the live MVP's only path to a PDF is still the browser's own Print.
`[n]` footnote markers render as plain superscripts in the PDF, not
clickable links like the HTML version's same-page anchors - a PDF has no
equivalent low-effort mechanism, a disclosed gap, not an oversight.

## 2026-09-04 — PDF input: pdfplumber, and pulling reportlab forward (Slice 23)

`pdfplumber==0.11.10` for table extraction — verified directly before
writing the extractor, not just read about: a real bordered table built with
`reportlab` and read back with `pdfplumber.page.extract_tables()` came back
as exactly the right rows. Installs with no system dependencies — its own
deps (`pdfminer.six`, `Pillow`, `pypdfium2`) all ship self-contained wheels,
no Poppler/Ghostscript/Java needed - the same Vercel-serverless-friendly
reasoning already used to pick `reportlab` over `weasyprint` for output.
Rejected `camelot` (needs Ghostscript) and `tabula-py` (needs Java) for that
same reason.

Also added `reportlab==5.0.1` now, a slice early — but for tests only. Every
other format extractor's tests build their own fixture file at test time
with that format's own writer library (`openpyxl` for `.xlsx`, etc.); a real
PDF table `pdfplumber` can reliably detect needs actual ruling lines, so
*something* has to write a real PDF for `tests/test_l1_extract_pdf.py`.
Using the PDF-writing library already decided on for Slice 24 beat inventing
a second, throwaway one just for tests. Slice 24 is still the slice that
wires `reportlab` into `analystos/l4/export.py` for real report output.

Because a PDF table is inferred from visual layout, not a real structured
object, `analystos.pipeline.build_report` refuses to build a report from a
`.pdf` source until the job explicitly says `"pdf_confirmed": true` - a
non-interactive flag, not a terminal prompt, since the CLI's execution model
has no `input()` anywhere and shouldn't gain one just for this. The error
raised without that flag includes the actual extracted table, so the
"confirm" step is real: whoever runs it sees exactly what needs reviewing
before they can flip the flag and re-run. Correcting a misread value isn't
supported yet - accept-as-extracted-or-don't-use-it - and `.pdf` stays
unsupported by `api/analyze.py`/`site/upload.html`, since a stateless HTTP
request has no natural place for this kind of human-in-the-loop gate without
a real review UI (already named in `ROADMAP.md` as the reason PDF was pushed
after the MVP).

## 2026-09-04 — Access gating: one shared code, not accounts (Slice 22)

`api/analyze.py` and `site/upload.html` went live in Slices 20-21 with no
access control at all, deliberately deferred to this slice. The gate: a
single shared secret, read from the `ANALYSTOS_ACCESS_CODE` environment
variable and required as an `X-Access-Code` header on every request,
compared with `hmac.compare_digest` and **fail-closed** (a `500`, not open
access) if the variable is ever unset.

- Real per-analyst accounts are out of scope here on purpose - this is a
  small, hands-on preview with a handful of real analysts (`ROADMAP.md`'s
  NOW milestone), not a public product. Accounts are R1/R2 work, once there's
  an actual cohort to manage identity for.
- No rate limiting on the code itself - accepted, disclosed tradeoff. The
  point is keeping this off search engines and drive-by visitors, not
  standing up to a targeted attacker who's decided to guess it.
- One manual step this repo's code can't do for itself: `ANALYSTOS_ACCESS_CODE`
  has to actually be set on the live Vercel project (dashboard -> Settings ->
  Environment Variables) before the deployed endpoint is gated for real -
  same category of "only confirmable post-deploy" residual risk Slices 20-21
  already flagged.

## 2026-09-04 — How Python actually deploys on Vercel (researched before Slice 20)

Checked Vercel's own docs rather than guessing, since the Root Directory
picker earlier already showed guessing wrong costs a real deploy cycle.
Findings, current as of this date:

- Vercel supports file-based Python functions in an `/api` directory:
  each `.py` file there becomes its own route (`api/analyze.py` ->
  `/api/analyze`). The file must define a top-level `app` (WSGI/ASGI) or
  `application` (WSGI) object, or a `handler` class extending
  `BaseHTTPRequestHandler`. Flask's `app` object satisfies this directly.
- **Caveat found in the same docs**: if Vercel detects a Python "framework
  preset" for the project (from a matching dependency in `requirements.txt`),
  the framework takes over *all* routing, and `/api/*.py` stops being
  treated as file-based functions. Our project was already configured as a
  static site (Output Directory override to `site/`, from the earlier
  Root Directory workaround) before `flask` was ever added to
  `requirements.txt` - the working assumption is that an already-configured
  project keeps its existing routing rather than being silently
  reclassified, since Vercel's own docs describe the file-based `/api` model
  specifically as being for "existing projects." **This is not confirmed by
  an actual deploy** - only verifiable once it's live.
- Added `vercel.json` with an explicit `functions` config for `api/*.py`
  (the exact pattern shown in Vercel's docs) rather than relying purely on
  auto-detection, to make the intent unambiguous.
- Chose the file-based `app.py`-style entrypoint (Flask, WSGI) specifically
  because it means requests are parsed through Flask's own `request.files`
  API - the same code path whether running via `flask run` locally or
  wrapped by Vercel's Python runtime - rather than hand-parsing multipart
  form data against a raw `BaseHTTPRequestHandler`, which would be Vercel
  runtime-specific and much easier to get subtly wrong.

## 2026-09-04 — Known risk: nothing verifies a "format" matches the data's real scale

Found while demoing Slice 17: an ask can declare `"format": "usd_millions"`
on a column whose values are actually raw dollars (or vice versa), and
nothing catches it. The result isn't an error - it's a confidently wrong
number (a $150,000 loss rendered as "($150.0B)"). This is exactly the
failure mode the whole hardening effort is meant to prevent, and it isn't
fixed yet. Candidate for the report-template slice (renumbered to 19 - moved
earlier when PDF was pushed after the MVP): a template that generates the
asks could also know - or sanity-check - the expected scale, rather than
leaving it to whoever writes `job.json` to get right by hand.

**Update, same day, demoing Slice 18:** hit the identical mistake again -
`usd_millions` on raw-dollar PowerPoint figures produced "$4,200.0B" instead
of "$4.2M", no error either time. Two for two. This is not a one-off typo
risk, it is a genuinely easy mistake, which raises the priority of fixing it
in Slice 19 rather than just documenting it.

## 2026-09-04 — First third-party dependencies: a live MVP, multi-format input

Ending the stdlib-only period from Slice 1. Reason: a live, browser-based MVP
("upload a document, get a report") needs things the standard library
genuinely doesn't do well — reading Excel/Word/PowerPoint/PDF files, and
running a web server.

- **Hosting: Python + Vercel**, not a separate always-on server (Render/Fly).
  Keeps everything on one host Caleb already knows. Consequence: Vercel's
  Python functions are WSGI, so the web layer will be **Flask**, not FastAPI.
  Free-tier functions time out at 10s — fine for CSV/Excel/Word/PowerPoint
  (sub-second), a real constraint once PDF extraction is in the request path;
  revisit hosting then if it becomes an issue.
- **Input formats, in order: Excel → Word → PowerPoint → PDF.** The first
  three are structured data (a cell/table object, not an inferred layout) —
  same reliability guarantee as CSV, no review step needed. **PDF is
  different**: table extraction infers column boundaries from a page's visual
  layout and can be wrong. Because the product's entire premise is "every
  number is defensible," a PDF-extracted table is never cited directly — it's
  shown to a person to confirm or correct first. Scanned/image PDFs (which
  need OCR) are explicitly out of scope: OCR is slow and would blow the
  10-second Vercel limit, and it's a different, heavier problem.
- **Output: a real generated `.pdf`**, not "open the HTML and print." Chosen
  library: **`reportlab`**, not `weasyprint` — weasyprint needs system
  graphics libraries (Cairo/Pango) that don't reliably install on Vercel's
  serverless functions; reportlab is pure Python with no system dependencies,
  so it won't work locally and silently fail in production.
- Each dependency is added in the slice that needs it, pinned exactly in
  `requirements.txt`, with the reason recorded here - not all at once.

## 2026-09-03 — Build in Python

Chosen over TypeScript / Node for the first slices.

- Python 3.14 and pip are already installed on the build machine; no setup cost.
- The hard parts of AnalystOS — document extraction (L1) and reasoning (L2) —
  have their strongest libraries in Python.
- Trade-off accepted: the FlashyOS mesh CLIs (`@flashyos/aao`, `@flashyos/agent`)
  are npm packages, so Node will be added later as its own slice when the
  manifest work (Slice 7) needs it.

## 2026-09-03 — Standard library only, for now

No third-party packages and no virtual environment until a slice explicitly
needs one (expected at Slice 4, document parsing). Keeps the skeleton trivial
to run and to review.
