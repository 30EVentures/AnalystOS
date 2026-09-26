# Decisions

Dated log, newest first. One entry per real choice, with the reason.

## 2026-09-25 - the AAO checker now follows the published schema (Slice 58)

`analystos/aao/validate.py` was a stand-in written before the published
schema was read: it invented a tier (`NONE`), rejected the real `CRITICAL`,
required two optional fields, refused the `x-` extension convention, and
disagreed with the schema on 15 of 21 probes. Replaced by a pinned copy of
`https://flashyos.com/aao.schema.json` (sha256 in code and test), a
keyword-limited JSON Schema checker (no new dependency; a test fails if the
schema starts using a keyword it lacks), the schema's documented cross-field
rules, and the documented naming rules. Problems now carry `aao.*` codes so the
checker can speak the conformance-kit line protocol. The codes are ours
because FlashyOS's aao/0.1 corpus is not public; that is stated in
`docs/aao.md` rather than implied. Rejected: adding `jsonschema` as a
dependency - the keyword subset is small and a dependency would add a
second thing to keep in step with the pinned schema.

## 2026-09-25 - public claims corrected to match the code (Slice 57)

The audit found the homepage describing the local command line ("stays on
your machine", "encrypted at rest") on a page whose main call to action is
the hosted upload, and promising more than the code checks ("never lost",
tags "wherever a figure appears", "real documents", "a retrospective in every
spec"). Copy corrected; `tests/test_site_claims.py` keeps the retired phrases
from coming back. Chosen over hiding the detail: the mesh outreach points at
the homepage Trust section, so it has to be the honest version.

## 2026-09-25 - one definition of a figure's basis, shown on every surface (Slice 56)

Audit findings 5-6: GAAP/guidance tags were shown in body paragraphs but not
on KPI tiles or chart bars, and the `source: "image"` marker from Slice 50
was stored and never drawn. `analystos/l4/basis.py` is now the single
definition (forward horizon, non-GAAP, from image) used by the HTML and PDF
body text, KPI tiles and chart notes, plus an image note in footnotes.
Chart basis is a note under the chart naming the tagged points, not a mark
per bar - four chart types times two renderers would have meant touching
every drawing routine for a marginal gain. Still not enforced: that the
model's `horizon`/`gaap_status` labels are right (the audit lists that; the
homepage wording in Slice 57 says so).

## 2026-09-25 - Gate 1 now checks relationships and spelled-out quantities (Slice 55)

The code-verified audit (`docs/audit-2026-09-25.md`, findings 1-2) showed that
"every number is proven" was true but weaker than it sounds. A real run passed
both gates with "Gross margin moved (4.7%) points to 54.2% from 55.8%": three
individually-correct figures joined by a wrong relationship (55.8 -> 54.2 is
1.6 points; 4.7 is the four-quarter change). Separately, "grew twenty percent",
"roughly doubled" and "about two-thirds" got through because only digits were
banned.

Two deterministic checks were added to `_validate_paragraph` (no model call,
no dependency): a change fact's named endpoints must be its own two operands,
and spelled-out amounts, fractions and multipliers are refused outside a
placeholder. Deliberately narrow (explicit "from"/"to" wording only; two-operand
`growth_percent`/`difference` only) so a false positive costs one repair call,
not a lost report. Not claimed: that all wrong relationships are now caught.

## 2026-09-12 — the deterministic floor didn't recognize "Q3 FY2026" (Slice 54)

A newly-generated test document ("Orion Industrial Group") hit Gate 1/
Gate 2 failure on a live run (a different, non-deterministic outcome
than an earlier run of the same document) and fell to Slice 52's
deterministic floor - which then produced a visibly broken result: a
KPI strip listing "Revenue" five times across five different quarters,
a jumbled chart mixing unrelated facts, and no trend sentence despite
five consecutive quarters of real growth in the data.

Root cause: the model labelled quarters "Q2 FY2027" (quarter + "FY" +
year combined) - a real, common fiscal-quarter convention this
codebase's period-detection regex only half-recognized, matching just
the trailing "FY2027" and silently losing the quarter number. That one
lost token broke three things that all depend on it: metric-key
deduplication (every quarter of "Revenue" looked like a different
metric), chronological sort order, and time-series/trend grouping. The
identical gap existed in `rich_export._PERIOD_LABEL_RE` (Slice 47's
chart-type detector) too, not only the deterministic tier - fixed in
both places, since a model-declared chart using this same label
convention would have hit the identical misclassification on the
best-case rich-narrative path.

Confirmed by reconstructing the exact real segment set visible in the
captured Test #10 output and running it through the fixed code
directly - no second live API call needed, since the real data was
already fully visible in what the user had already captured.

## 2026-09-12 — root cause found: a fake, non-numeric placeholder (Slice 53)

The actual reason Test #4/#8 fell back to the flat renderer, deliberately
left unresolved through Slice 52's own floor (that floor guarantees a
*good* output; it doesn't explain or fix why the *best* output failed).
A real, captured live run showed the model writing `{{5.0M}}` - not a
real `{{N}}` manifest index, a literal value dressed up to look like
one - for a real, source-stated figure ("...projected to decline to
approximately $5.0 million...") that had no verified segment behind it
to cite. `_PLACEHOLDER_RE` correctly never matches a non-digit token
like this, so its digits were already caught by the generic
"digit outside any {{N}} placeholder" check - but that message doesn't
say *why*, and 3 single-paragraph repair attempts plus 2 full retries
all failed, each producing a new variation of the same underlying
mistake, because nothing told the writer or the repair pass what
actually went wrong.

Added `_fake_placeholder_problem` - a specific, named check for this
exact failure class, distinct from the generic digit check - plus
explicit prompt guidance in both `_SYSTEM_PROMPT` and
`_REPAIR_SYSTEM_PROMPT`: a placeholder is always a bare manifest index,
never a value or unit; a number with no matching fact must be dropped
or described qualitatively, never approximated inside fake braces. The
repair prompt's prior guidance for this exact situation was scoped only
to a digit from an event's date/status/next_step text - generalized to
any missing fact, since the real failure here was an ordinary quote/
computed fact that simply wasn't extracted, not an event digit.

Deliberately not attempted: making extraction guarantee it never misses
a real number in the source text. Not achievable with certainty for an
LLM-driven extraction step, and not the actual point of failure -
Gate 1's job is refusing an uncited number through, not guaranteeing
every real number gets extracted; the fix belongs in how the writer/
repair handle a genuinely missing fact, not in trying to make extraction
perfect.

Confirmed via a mocked reproduction of the exact captured failure text,
not a second live API call - the user's explicit requirement going in
was not needing to run this more than once to get it fixed.

## 2026-09-12 — a mandatory, deterministic "advanced" floor (Slice 52)

Gate 1/Gate 2 rejecting the model's narrative previously meant a bare,
chart-less, KPI-less text fallback - the safety behavior was right (never
show a narrative that couldn't be verified) but what it fell back *to*
had no charts and no KPI strip at all, because those were entirely the
model's own narrative JSON to produce. Added
`analystos/l4/deterministic_report.py` - a second, zero-model-call tier
between the rich narrative and true bare text: a KPI strip, at least one
chart, and analytical sentences (benchmarking, trend, relationship,
disclosure-gap) assembled entirely from already-verified segments, using
a fixed-template approach rather than a bounded model call - reasoned
through explicitly before building: none of the four sentence types
require *discovering* a relationship (that's already done by extraction
or the existing chart-shape detector), only *phrasing* one already
known, which templates handle without needing any generative step that
could itself need a quality gate.

Produces the *exact* report-dict shape `write_narrative` already
returns, so `render_rich_report`/`render_rich_pdf` render it completely
unchanged - no new rendering code, no visual "degraded" signal, by
construction rather than convention.

One correction made before building, not after: the task's framing
assumed disclosure-gap detection was "already code-driven, reusable" -
it wasn't. `disclosure_gaps` was, until this slice, content the *model*
wrote inside `write_narrative`'s own response; nothing detected a gap
independently of that. Built a genuinely new, fixed checklist detector
instead (EPS, cash flow, gross margin, etc., keyword-matched) rather
than silently assuming code that didn't exist.

Two real bugs surfaced only by running an actual document through this
tier (not by any hand-built fixture) - both instructive, both now
covered by regression tests built directly from the failure:

1. Determining which of a computed fact's two cited quotes was the
   "current" one by *citation position* seemed reasonable but wasn't -
   `analyze.py`'s own `growth_percent` verification already tries
   operands in either order and accepts whichever matches, proving a
   model is never actually constrained to one order. A real document
   produced "Net Income Q3 2025 was $22.4M, a change of $-2.8M" -
   attached to the older quarter. Fixed by determining "current" from
   each quote's own period token (chronology), never from position.
2. `_select_bridge` treated any 2-citation `difference`/`remainder` as
   a bridge, producing a nonsensical "moved from X to Y" sentence for
   an ordinary two-point YoY comparison with no named component at all.
   Fixed by requiring 3+ citations - a genuine start/components/end
   bridge, never a plain two-point difference.

Confirmed via the pattern already established this session: engineered-
failure automated tests (a permanently broken `write_narrative` mock
still yields a full rich-rendered report with all four sentence types,
zero model dependency) *and* a real live run against the actual Meridian
document behind Test #8/#9, read directly, not asserted to work.

## 2026-09-11 — a deliberate, real-money live-test suite (Slice 51)

The 458 tests in `tests/` are entirely mocked - valuable and permanently
free, but structurally blind to anything only a genuine model response
can surface (found directly this session: a report that looked correct
against every mock but produced an uncitable number live). Added
`live_tests/` - outside `tests/` on purpose, so it is never collected by
`unittest discover -s tests` and never runs without being explicitly
invoked - a small, fixed set of 4 structurally different documents (the
schema/template path, the narrated path over plain prose, over Slice
50's column-aware extraction, and over Slice 50's image-fact
extraction), run against a real, non-mocked `anthropic.Anthropic()`
client.

Cost tracking is real, not a proxy: `CostTrackingClient` wraps the real
client so every actual `response.usage` becomes a real dollar figure via
a price table sourced from Anthropic's own published pricing
(`claude.com/pricing`, checked 2026-09-11 - $2/MTok in, $10/MTok out for
Sonnet 5), logged per call and per document. A **$1.00 hard ceiling**
(your call - conservative against an expected real cost of a few cents
to a few tens of cents for the whole run) is checked before every
dispatch; once reached, every further call is refused before it's ever
sent, and the run stops rather than continuing to spend. One honest,
disclosed limit: a call's cost isn't known until its response completes,
so the ceiling can only be checked against *completed* calls - total
spend can overshoot by at most one call's own bounded cost, never
unbounded, and this is stated plainly in `live_tests/README.md` rather
than glossed over.

The runner's own logic (price table, cost accumulation, the ceiling
correctly refusing and never dispatching the call that would exceed it)
is proven by 7 ordinary mocked tests in `tests/` - this codebase's usual
discipline of proving logic before it ever touches a real key - fully
separate from the live run itself, which is the actual, human-triggered
proof this slice exists to produce.

## 2026-09-11 — multi-column PDF reading order + image-derived facts (Slice 50)

Two audit-flagged gaps: PDF text extraction read pages in `pdfplumber`'s
default order, which - confirmed by direct experiment - interleaves a
genuine two-column layout line by line rather than reading one column
fully before the next; and an embedded image/chart was completely
invisible to the system, no OCR, no vision call, anywhere.

**Column detection** (`analystos/l1/pdf_columns.py`) works from words'
own bounding boxes: the largest empty horizontal gap on the page,
requiring it span a real minimum fraction of the page width and split a
real minimum number of words on each side, is treated as a column
gutter. No such gap -> falls back to the exact pre-Slice-50 behavior, so
every existing single-column document (the overwhelming majority) is
provably unaffected - tested directly against the same fixtures used
before this slice.

**Image-derived facts** (`analystos/l1/image_facts.py`): `tesseract`
isn't installed on this machine and a system-level binary is a bigger
ask than any dependency this repo has taken on - vision via the
existing `anthropic` client needed nothing new. The model's only job is
a literal, verbatim transcription (never "extract the revenue figure")
- that transcript is then treated as ordinary document text and flows
through `analyze_document` *completely unmodified*: a fact "from" an
image is verified exactly as rigorously as any other quote, an exact
substring of something real, here a transcript instead of digitally-
extracted text. The one honest, disclosed gap - a transcript is a model
output, not a byte-exact extraction - is why every such segment gets a
new, purely additive `source: "image"` tag, applied *after*
verification, never folded into or weakening it.

A document with zero embedded images never resolves an Anthropic
client at all, proven directly (with the API key cleared) - a plain
PDF costs nothing extra and needs no key just because this code now
sits on the extraction path.

`Pillow` is now pinned explicitly in `requirements.txt` (it was already
an implicit transitive dependency of `pdfplumber`/`reportlab`; this
slice's tests import it directly to build embedded-image fixtures).

## 2026-09-11 — Gate 2's full prose-quality rubric (Slice 49)

Gate 2 (`analystos.l2.proofread`) previously judged language mechanics
only - spelling, grammar, duplication, leftover artifacts. Raised its
bar to three further criteria (no filler, genuine cross-section
synthesis clearly labeled, plain-language disclosure gaps), each
grounded in a worked example in the system prompt the same way every
other rule in this codebase's prompts already is - a bare adjective
("check for filler") produces inconsistent model judgment; a concrete
good/bad example doesn't.

One check moved out of the LLM's hands entirely: whether
`executive_insight`/`outlook_interpretation` cites at least two distinct
`{{N}}` facts is mechanically verifiable, so it's now a deterministic
Gate-1-style check in `analystos.l2.narrate` (`_synthesis_problem`),
not asked of the model at all - this codebase's established preference
wherever a rule can be checked in code instead of only judged. Gate 2
still separately judges whether an insight that *does* cite two facts
actually connects them into a real judgment (a mechanical count can't
tell "margin fell and guidance held, together suggesting X" from
"margin fell. guidance held." - both cite two facts) - the two checks
catch different failure modes of the same instruction, deliberately not
redundant.

`_TOOL`'s schema gained `has_filler`/`has_synthesized_insight`/
`disclosure_gaps_clear` (booleans) so a specific criterion's outcome is
directly inspectable rather than inferred by string-matching `problem`
text. These are logged for auditability only - `passed` stays the
single, sole signal for whether a report ships, deliberately never
combined with the new booleans into a second, competing pass/fail path;
a test proves this holds even when the two would disagree (a mocked
`passed=True` response with `has_filler=True` still ships).

Live-tested (not offline-simulated) per the task's own before/after
requirement: same underlying facts run through a real `proofread_report`
call twice. The "before" version - a generic-sentiment filler sentence,
two facts stated side by side with no connecting judgment, and a vague
disclosure gap - failed with exactly those three reasons, verbatim from
the model. The "after" version, same facts rewritten to state a specific
gap and read the two facts together into one judgment, passed cleanly.
Full transcript in `specs/slice-49/spec.md`'s "Built" section.

## 2026-09-11 — a real server-side PDF for the rich report (Slice 48)

The rich (v4) report had no server-generated PDF, only the browser's own
`window.print()`; the flat report's `render_pdf` (Slice 24) only knows
the flat title/paragraphs/footnotes shape and has no concept of a KPI
grid, a chart, or a boxed interpretation block. Added
`analystos/l4/rich_pdf.py` (`render_rich_pdf`), a parallel PDF renderer
built on `reportlab` (already pinned - no new dependency) that consumes
the exact same `(report, segments, source_hash, currency_unit)` inputs
as `render_rich_report`, so nothing is re-derived or re-parsed from the
HTML.

Two real choices, made up front rather than discovered mid-build:

- **Bundled real IBM Plex font files** (OFL-licensed, redistributable)
  rather than `reportlab`'s base-14 fonts. "Matching visual fidelity"
  was the task's own stated goal; a Helvetica/Times stand-in would not
  meet it. Six TTFs (Sans/Serif/Mono x Regular/SemiBold) live in
  `analystos/l4/fonts/`, registered at import time.
- **Charts are redrawn, not reused.** `reportlab` has no SVG renderer,
  so the existing inline-SVG chart strings (`analystos.l4.charts`)
  can't be reused directly. A parallel PDF-native drawer
  (`reportlab.graphics.shapes`) mirrors the same layout logic, but both
  renderers call the *same* `_detect_chart_type` (Slice 47) on the same
  resolved `(labels, values)` - so HTML and PDF can never disagree on
  what shape a chart is, only how it's drawn. The waterfall tie-out
  safety check (Slice 47) is reimplemented independently on the PDF
  path too, and proven independent the same way: forcing the detector
  to lie and confirming the chart still gets refused.
- **Pipeline integration is opt-in, not a contract change.**
  `build_report` gained `want_pdf=False`; every existing caller and
  test still gets a bare string back unchanged. Passing
  `want_pdf=True` runs the pipeline exactly once and returns
  `(text, pdf_bytes)` for every path (rich, plain-fallback, and the
  schema/template path alike). Considered instead making
  `build_report` always return a pair, or wiring PDF generation only
  into `main()`/`api/analyze.py` with pipeline logic duplicated there -
  both were more disruptive for no real benefit. `main()` now always
  passes `want_pdf=True`, so the CLI writes a real `section.pdf` next
  to `section.html` for the rich path too, closing a gap where only the
  flat path ever got one.

Pagination (`reportlab.platypus.KeepTogether` around every chart and
boxed block) is proven, not assumed: a test builds a report dense
enough to force a real page break near a chart and confirms via
`pdfplumber`'s own rect-per-page reading that the chart's bars are
wholly on one page, never split.

## 2026-09-11 — code, not the model, decides chart type (Slice 47, Task 2)

The writer model previously declared `chart.type` directly; `_chart_html`
now derives it itself from the resolved, verified `(labels, values)` and
ignores whatever the model put in that field. A start -> components ->
end bridge (the exact tie-out property the existing waterfall check
already required) is a waterfall; three or more period-labelled points
are a line; anything else is a bar.

This changed one existing test's expected behavior, on purpose:
`test_a_waterfall_that_does_not_tie_out_is_dropped` previously asserted
that breaking a declared waterfall's bridge made the whole chart vanish.
Under auto-detection, that data is simply never classified as a
waterfall in the first place - it renders as an honest bar comparison of
the same real numbers instead. No chart lost, and no misleading bridge
shown either - arguably safer than the old behavior, not a regression.
Added a new, separate test proving the existing tie-out check is still a
genuinely independent safety layer: mocked the detector to force
"waterfall" onto purpose-broken bridge data, confirmed the untouched
check still refused to render it.

Donut ("parts of a stated whole") is not auto-detected - deliberately
out of scope, not silently dropped. Nothing available to the detector (a
plain resolved value list, no associated "total") reliably distinguishes
that shape from an ordinary categorical comparison without a new signal;
falls back to bar, a safe default, until that signal is designed.

## 2026-09-11 — "remainder": organic-vs-inorganic as a real operation (Slice 47, Task 1)

The Meridian Data Services bridge (total growth, minus Halyard's stated
contribution, equals organic growth) was previously only ever produced
ad hoc through the model's own `"difference"` usage. Added `"remainder"`
as its own named operation - identical arithmetic to `"difference"`
(operands[0] minus the sum of the rest), but kept separate so this
specific "total change minus a named, disclosed component" pattern is
recognizable downstream rather than just another generic magnitude.
Verified the same way every operation is: independently recomputed from
already-checked operand values, dropped if the claimed result doesn't
match - proven directly, not asserted (a wrong claimed remainder, and an
operand not actually in the source, both correctly fail).

Given the same cautious treatment `"difference"` already has in the
direction-word gate: nothing verifies operand[0] genuinely is "the
total" rather than just the first number listed, so its sign is exactly
as unreliable, and a directional word next to a `remainder` fact is
refused the same way.

## 2026-09-11 — legal boilerplate exclusion, not a keyword blocklist (Slice 46)

A forward-looking-statements/safe-harbor disclaimer is dense with words
("forward-looking," "risk," "future") that also appear constantly in
ordinary, substantive business prose - a single-keyword filter would
either miss real disclaimers phrased slightly differently or wrongly
strip legitimate content that happens to use one of those words once.
Built `analystos/l1/boilerplate.py` around two structurally different
signals instead: a canonical section heading (this genre's heading
phrasing is a genuine, standardized legal-drafting convention, not
something that varies freely) OR a *density* of specific statutory
phrase patterns (citing the actual securities-law sections, the "actual
results...differ materially" formulation, "undertake no obligation to
update") - several must co-occur before content-only detection fires.
Verified directly: a document using "forward-looking" or "risk" once in
an ordinary sentence is left untouched; a real disclaimer, headed or not,
is fully removed.

Wired into `analystos.pipeline.build_report` between
`extract_document_text` and `analyze_document` - the narrated-default
path only. The old schema/template path never reads prose at all, so
there is nothing for this to act on there.

Also closed a proof gap in Slice 45 (GAAP/non-GAAP): that slice's own
tests used hand-typed prose fixtures, never a real table. Built
`tests/test_l1_l2_gaap_table_integration.py` - a genuine `.docx`
reconciliation table, run through the real unified extraction path
(spied to confirm `extract_docx._raw_rows` actually parsed it), proving
both figures verify against the real table text and are linked by a
verified reconciling gap, with a fabricated third figure correctly
failing verification. No production code changed for this part - Slice
45's mechanism was already correct; this proved it against the harder,
realistic case instead of only the fixture that was convenient to type.

## 2026-09-11 — detect and label GAAP vs. non-GAAP figures (Slice 45)

SEC Reg G requires a filer to label a non-GAAP figure as such wherever it
appears - a genuinely detectable signal already in the source text, not
something to infer from a number's size or direction. Added `gaap_status`
("gaap"/"non_gaap"/"n/a") alongside the existing `horizon` field on every
segment, verified the same way: trusted only when the source's own
wording states it, defaulting safely to "n/a" (not "gaap") on anything
missing or malformed - unlike `horizon`, where the safe default
("reported") is what most segments genuinely are, defaulting a malformed
gaap_status to "gaap" would risk silently presenting an unlabelled
adjusted figure as the audited one, exactly what this slice exists to
prevent.

Planned a new Gate 1 validator (a non-GAAP fact cited without its tag
gets rejected) before building it, then found it unnecessary during
implementation: the tag is attached by `rich_export.py`'s renderer
straight from the segment's `gaap_status`, the identical mechanism
`⟦guidance⟧`/`⟦projected⟧` already use - reusing `_TAG_RE`'s existing
generic rendering branch and the already-generic `.horizon-tag` CSS
class needed no new styling either. The model cannot omit the tag any
more than it can omit a guidance marker; a validator would have only
checked something already structurally guaranteed. Dropped the checker,
kept the guarantee - a stronger property than the originally-scoped
plan, found by building it rather than assumed going in.

## 2026-09-11 — one real table-parsing standard + real footnote detection (Slice 44)

Foundation work for GAAP/non-GAAP detection, which needs real typed table
structure and real footnoted adjustments to reason about - neither existed
on the narrated-default path before this. `document_text.py` maintained
its own separate, weaker table flattening (raw cell text joined directly)
instead of the real, type-aware `_raw_rows` every format module already
had for the schema-driven path. Unified: every `_text_from_*` function now
calls that same `_raw_rows` directly. Proved genuine, not just asserted -
stashed this slice's changes, reran the five unification tests, watched
all five fail (each for "the real parsing function was never called"),
restored the fix, watched them pass.

One real bug this fixes, not just a refactor: Excel stores a percentage-
formatted cell as its fraction (`0.571` for what displays as "57.1%").
The schema-driven path already rescaled this correctly; the old narrated-
path flattening showed the raw fraction verbatim - a person reading the
narrated text would see a number 100x too small. Fixed by construction,
not a special case, once both paths go through the same function.

Footnote detection: built real, structural marker-to-content linking for
`.docx` only. Word's OOXML format has a genuine structural relationship
(a footnote reference element with an `id`, linked to real content in a
separate `footnotes.xml` part) - the same kind of unambiguous link a
table's real cell/row structure has. Checked every other supported format
against the same bar before building anything, not after: PDF has no
reliable structural footnote concept through `pdfplumber` (or through most
real-world PDFs, which aren't tagged) - only a font-size/position
heuristic is possible, and that's guesswork, not structural detection, so
it's deliberately not built as part of this. PPTX has no footnote
mechanism at all. XLSX's closest analog (cell comments) is a different
relationship entirely (attached to a cell, not a marker in running body
text). CSV is flat data with no markup. `python-docx` itself exposes no
public API for footnotes, so the reader parses `word/document.xml` and
`word/footnotes.xml` directly - and the test fixture needed a real
footnote built by hand (`lxml`-level XML injection into a python-docx
document plus a hand-assembled `footnotes.xml`/relationship/content-type),
since neither a committed fixture nor `python-docx`'s API could produce
one.

## 2026-09-11 — evidence encryption at rest + a retention window (Slice 43)

`evidence/` has held plain, unencrypted copies of every uploaded source
since Slice 2, kept indefinitely. Both gaps closed together: `store` now
writes `Fernet(key).encrypt(...)` to disk instead of raw bytes, and
`purge_expired_evidence` deletes anything past a configurable retention
window. `hash_of` deliberately still hashes the *plaintext*, before
encryption - Fernet's fresh random nonce means the same source would file
under a different address every time otherwise, breaking the whole
"same bytes -> same name" point of a content-addressed store.

Added `cryptography` as a direct, pinned dependency
(`requirements.txt`) - it was already present transitively (via `anthropic`
and/or `flask`'s dependency tree), so this makes an existing implicit
dependency explicit rather than adding real new surface. `Fernet`
specifically: the standard, well-audited choice in this library for
"encrypt a blob with one symmetric key," no need to hand-roll AES modes or
authentication.

Key source: `ANALYSTOS_EVIDENCE_KEY` if set - a real per-deployment secret,
the same pattern as `ANALYSTOS_ACCESS_CODE` (Slice 22). If unset, a stable,
repo-known fallback derived from a fixed local constant, so the store is
never plaintext-by-default in a dev environment - but this fallback is
explicitly *not* a secret (anyone with this source can derive it) and must
never be relied on where real data matters. This differs from Slice 22's
access code, which fails *closed* (500) when unconfigured - encryption
fails *soft* to a known-weak default instead, because the alternative
(refusing to store anything without a real key configured) would silently
break every existing caller and test that has never needed to think about
this. Documented, not hidden - anyone auditing this file sees exactly
where the weaker default is.

Retention: `ANALYSTOS_EVIDENCE_RETENTION_DAYS` unset means no expiry
enforced - the same opt-in pattern Slices 41/42 already use for their own
ceilings, not a surprise auto-deletion policy. Deletion, not archiving, for
simplicity (the task's own framing allowed either). `store()` runs the
cleanup pass itself on every call (best-effort - never lets a cleanup
problem break the store it's riding along with), so retention is actually
enforced over time with no external cron job needed, while
`purge_expired_evidence` stays independently callable for a script or a
test.

Not migrated: any evidence already on disk from before this change, stored
under the old plaintext format. `evidence/` is git-ignored dev/test data at
this stage, and `retrieve()` (the only thing that would ever try to
decrypt an old file) isn't currently called anywhere in the live pipeline -
confirmed by inspection, not assumption - so this has no live-behavior
impact today.

## 2026-09-11 — an in-code spend hard-stop, second layer over the account cap (Slice 42)

The only spend safety net before this was external to the repo entirely: a
monthly cap set on the Anthropic account itself (see the 2026-09-05 entry
below). Real, but this repo's code can't see, configure, or test it.
Added a second layer inside `_create_message` - the one choke point every
Anthropic call in the codebase already goes through - checked *before*
dispatching a call, so a runaway loop hits an internal stop before (or
even without) ever touching the account-level cap.

Tracks **call count, not dollar cost**. Considered token-usage-based
tracking (the SDK response does carry `usage.input_tokens`/
`output_tokens`), but that means embedding a per-model price table in this
repo that goes silently stale the moment Anthropic's pricing changes -
exactly the kind of drift a safety net shouldn't have. Call count degrades
safely instead: worst case the ceiling trips a bit earlier or later than a
dollar-exact one would, never silently and never wrong-currency.

`ANALYSTOS_MAX_API_CALLS` unset means **no internal ceiling** - this is a
second layer on top of the account-level cap, not a replacement forced on
every deployment by default. Set it, and it's enforced with the same
clean `ValueError` a real `anthropic.APIError` already produces, so a
caller can't tell "hit the account cap" from "hit the internal one"
without reading server logs.

## 2026-09-11 — per-IP rate limiting on the access-code endpoints (Slice 41)

Slice 22 explicitly deferred this ("an accepted, disclosed tradeoff for
this stage, not an oversight"). Added as defense in depth, not a redesign
of auth: the shared-code, no-accounts model is unchanged. In-memory,
per-process fixed-window counter keyed by client IP
(`X-Forwarded-For`'s first hop, else `request.remote_addr`), checked
*before* the access-code comparison so a wrong-code guess still counts
against the budget - the actual point of rate-limiting this endpoint is
slowing down someone trying to brute-force the shared code, not just
capping legitimate traffic. Configurable via `ANALYSTOS_RATE_LIMIT_MAX`
(default 30) and `ANALYSTOS_RATE_LIMIT_WINDOW_SECONDS` (default 60); an
unset or unparseable value falls back to the default rather than raising -
a throttle must never be the reason the whole service goes down.

In-memory per-process, not a shared store (Redis, etc.): correct for a
single Vercel function instance, not guaranteed across many concurrent
instances under real distributed load. Accepted for this stage - the same
category of tradeoff Slice 22 already made for the access code itself
(good enough to keep this off casual abuse, not hardened against a
determined distributed attacker). A real shared-store limiter is future
work if the threat model changes.

## 2026-09-11 — repair the one flagged piece, not a full regenerate (Slice 40)

Live-tested Slice 39's fix twice more, back to back, and both runs still
fell back to the plain renderer with zero trace of why -
`analystos.pipeline`'s except clause swallowed the fallback reason
entirely. Fixed the logging gap first (now every Gate 1/Gate 2 fallback
reason prints to stderr), which is what made the rest of this diagnosable
live at all.

What the logs then showed, repeatedly: `write_narrative` throws away the
*entire* report on any rejection and asks the model to regenerate
everything from scratch. A report this size (exec summary + 3-5 sections +
KPIs + outlook) has enough sentences that a full reroll is a fresh chance
to break a *different* rule anywhere else in the document, even while
correctly fixing the one that was actually reported - watched happen live,
several times in a row, on the same test document. Replaced "reject and
reroll the whole document" with "repair just the one flagged paragraph in
place" for both gates: `write_narrative` now tries a scoped, small repair
call first (chasing a second problem the first repair's fix exposes,
within a bounded budget) before falling back to a full regenerate; Gate 2
(language quality) gets the same treatment instead of an instant,
unconditional fallback on any wording issue.

A repair is only ever kept if it still satisfies Gate 1's own paragraph
validator - a wording fix must never quietly reintroduce a correctness
violation. And a Gate 2 issue's flagged location is only patched if it
matches exactly one field in the report; an ambiguous match (a short,
generic quote that could be more than one sentence) is left alone rather
than risking a patch to the wrong one - safer to leave an issue unfixed
than to guess and rewrite something that wasn't actually broken.

Also closed three specific validator/prompt gaps the live diagnosis
surfaced along the way, each a real, separately-found live bug, not
speculative hardening: a missing rule (an "N consecutive quarters" claim
needs N+1 citations - now stated in the prompt itself, not just checked
after the fact); a false positive in the direction-word check (a
direction word separated from a "difference" fact by another placeholder
was wrongly flagged as describing that fact instead of the comparison it
actually modified); and a new check for a placeholder followed by a
spelled-out unit ("million," "percent") - always wrong, since a rendered
value already carries its own unit, and for a non-numeric fact (an event)
it was silently being used as though it had a value at all. The last of
these traced back one layer further, to L2's extraction prompt: an
event's `status`/`next_step` text can legitimately contain a real,
material figure (an acquisition's integration-cost peak and step-down)
that the model could see but had no `{{N}}` to cite - now asked to also
surface such a figure as its own separate citable fact.

## 2026-09-11 — growth_percent operand order made order-independent (Slice 39)

Live-tested Slice 38 immediately after merge: a report that should have
been rich fell all the way back to plain text. The log showed the real
cause - every `growth_percent` computed segment in that run failed
verification, e.g. `recomputed growth_percent = -8.63 does not match the
model's result 9.45`. Checked both orderings of the same two operands by
hand: `(498-455)/455 = 9.45` - the model's math was correct; it had just
listed the operands as `[current, prior]` instead of the `[prior,
current]` `_recompute` assumed. With no citable growth fact left, the
narrator wrote a raw, uncited dollar figure instead, which tripped the
existing digit check and took the whole report down to the flat fallback.

Root cause is Slice 38 itself: the new "use growth_percent for every
directional claim" prompt rule (replacing "difference," which has no
reliable sign) made the model attempt `growth_percent` far more often -
so an operand-order mixup that used to surface occasionally now hit on
every attempt in one run. Fixing the sign-word bug amplified a different,
pre-existing one.

**Fixed at the verification layer, not the prompt** - a prompt
clarification was added too, but a prompt instruction had already failed
4 times in this exact run and shouldn't be trusted alone.
`_verify_computed` now tries both operand orderings for `growth_percent`
and accepts whichever one matches the model's own claimed result. Both
operands are already independently verified real numbers at that point,
so this stays entirely inside the guarantee - it is still the real
percent change between the same two real numbers, computed the other
legitimate way, never a third or fabricated value. `difference` is left
order-sensitive (unchanged) since Slice 38 already bans a direction word
next to it regardless of sign.

## 2026-09-11 — Two mandatory quality gates: correctness and language, independent (Slice 38)

A real PDF from the live site (`Downloads/Test #5 to download pdf.pdf`)
had four distinct defects even though every number in it individually
traced to a real source: a net-income decline described as "rose... up
$2.8M"; an event's full composed timeline leaking verbatim into prose
6+ times, "next:" artifact and all; a footnote whose displayed operand
("$1.9B") didn't actually support its own displayed result ("$565.0M");
and a fragile, unchecked class of "N consecutive quarters" claims. All
four are root-caused and fixed in `analystos/l2/narrate.py` and
`analystos/l4/{export,rich_export}.py` - see the Slice 38 commit for the
full breakdown per bug.

**Gate 1 (correctness)** is enforced inside `write_narrative`'s existing
validation (`_validate_paragraph`), so a violation gets the same
retry-then-fallback treatment a stray digit already did - never a special
code path. **Gate 2 (language quality)** is a new, separate, independent
model call (`analystos/l2/proofread.py`) that sees only the assembled
prose - never segments, citations, or values - so it cannot be swayed by
whether the facts are right, and can never be quietly satisfied just
because Gate 1 already passed. Wired into `pipeline.py` to run after Gate
1, before rendering; either gate failing takes the identical fallback
path to the plain renderer.

This is a third model call per narrated report (real added latency and
cost, on top of `analyze_document` and `write_narrative`) - a deliberate
trade explicitly asked for over a general-purpose grammar library, which
is a poor fit for a Vercel serverless function (most need a JVM or a
native binary neither of which reliably run there).

Each of the four checks has a dedicated test reproducing the live defect
and confirming the fix catches it (not just "the code changed"). The
exact Meridian figures behind the broken PDF were also rebuilt as
verified segments and run through the real `write_narrative` +
`proofread_report` + `render_rich_report` end to end (mocked client) -
both gates pass, and the corrected output was converted to a real PDF
via headless Chrome for a direct before/after comparison. Whether a
*real* model reliably produces content this clean, and whether Gate 2
actually catches a real model's language slips, is the still-open,
unverifiable-without-the-API question - same caveat as every model-facing
change this session.

Also true but out of scope here, and deferred to a follow-up per the
request's own ordering: chart-type diversity and table formatting.

## 2026-09-09 — The output-token ceiling on a dense document (Slice 34)

Slice 33 fixed how verification matches; the realistic earnings release
still returned "no verifiable content survived" once deployed. The tell:
that request ran **1m38s** on Vercel - a single Sonnet call on an
8.5k-char document should take 20-40s. 98s is the signature of hitting
the output ceiling. `max_tokens` was 4096; a dense filing (four tables)
makes the model emit 20+ segments in the verbose all-required schema, it
overruns 4096, and the tool call is truncated mid-JSON - the segment
list comes back short or with a half-written last entry, and little or
nothing verifies. Meridian (5 paragraphs, ~7 segments) never came close.

- **`_MAX_TOKENS` 4096 -> 8192** in `analyze_document` and
  `write_narrative` (a rich report over a dense document can also
  outgrow 4096). Direct fix.
- **`stop_reason == "max_tokens"` is now logged** to stderr, and the
  "no verifiable content" log flags `(RESPONSE WAS TRUNCATED at
  max_tokens)` - the failure that had no fingerprint now has an obvious
  one.
- **Prompt caps output at 20 segments** and says not to transcribe
  tables - prefer a computed comparison or a prose point tying figures
  together. Keeps the response in budget and makes a better report.
- **Schema shape left alone.** Slimming the all-required per-segment
  schema (the reason each segment is verbose) risks re-triggering
  Slice 26's "400 Schema is too complex"; the token bump plus the cap
  solve it without that risk. Revisit only if 8192 + a 20-cap still
  truncates.

## 2026-09-09 — Verification that survives a real filing's tables and scale (Slice 33)

A realistic fictional earnings release, uploaded to the live site,
returned **"no verifiable content survived"** — every segment the model
returned was dropped. `analyze_document`'s checks were tuned to Meridian
(five prose paragraphs, every figure spelled out "$498.0 million"); a real
condensed income statement is a pipe-delimited table headed "In millions
of U.S. dollars", and against that the checks reject everything.

- **Byte-exact substring citation was the wrong bar.** A model reasons
  about a figure and re-expresses it — `1,842.0` in the table becomes
  `$1,842.0 million` / `$1,842` / `1842.0` — and an exact `in` check drops
  each. Fixed with `_match_key` (folds case, dashes, `$`, the `|` our L1
  rendering inserts, and thousands separators — never the digits) plus a
  trailing-scale-word fallback in `_really_in_document`. A model that
  prepends a row label to a *non-leading* cell still fails, on purpose:
  tying a label to a distant number by proximity risks accepting a
  *mislabelled* one, and a false "verified" is the one thing this must
  never do.
- **No notion of a table's declared scale.** `_detect_scale` reads "in
  millions" / "in thousands" once; `_value_matches_text` now accepts the
  model's `value` at face value *or* times the declared scale, and returns
  whichever matched (canonical value) — so a figure the model scaled to
  its real magnitude verifies and is stored/rendered correctly, and one
  left unscaled still verifies (no regression). Sign preserved, so the
  Slice 29 sign-flip guard holds. The user message also states the
  detected scale and that per-share amounts, percentages and share counts
  are not scaled.
- **The failure logged nothing about *why*** — the same "no clue why"
  hole Slice 27 closed for the narrative pass. `_verify_*` now return
  `(segment, None)` or `(None, reason)`; a total failure logs the first
  several reasons to stderr (Vercel logs), never the client response.
- Verified beyond the suite: the real L1 extraction of the document that
  failed live, fed a hand-authored model response mimicking real
  table-citation behaviour — 8 of 10 segments verified (was 0), dollar
  cells stored at real magnitude, per-share values untouched, a
  fabricated figure and wrong arithmetic dropped with logged reasons.
  Meridian and every prior fixture unaffected (a document declaring no
  unit has `doc_scale == 1` and the new checks collapse to the old ones).
- Not fixed here, its own slice: column-aware L1 extraction (keep a cell
  tied to its row label / column header) so a "RowLabel Cell" citation of
  any column verifies. This slice makes that citation fail *safely and
  visibly*, not silently.

## 2026-09-08 — Dated events as a verified, structured fact (Slice 32)

The system was rigorous with numbers and weak with events - an
acquisition or a regulatory step could be mentioned as a plain quote, but
nothing captured *when*, *where it stands*, and *what's next*, so the
report said "an acquisition closed during the quarter." This adds an
`event` segment type to `analyze_document` - the last piece of the
diagnosis's Mechanism 4.

- **`event` is a fourth segment type** (`quote` / `computed` / `event` /
  `prose`), carrying no numeric value. Its four parts - `what` / `date` /
  `status` / `next_step` - sit in a nested `event` object on the tool
  schema, every field required (Slice 26 all-required rule; nesting was
  never the problem, optionality was - Slice 30's nested chart schema
  already proves it).
- **The model copies, never composes.** `what` must be a verbatim
  substring and is required; `date` / `status` / `next_step` are each
  either `""` or a verbatim substring. `_verify_event` drops the whole
  event if `what` isn't real, or if any *supplied* part isn't - a
  half-verified timeline is worse than none.
- **The model never types an event's date into prose either.** The
  narrator references an event with `{{N}}` like any citable fact; L4's
  new `event_line` composes the verified parts into a timeline string
  (`what (date) — status — next: next_step`, omitting absent parts). Every
  digit on an event line is a verified substring. This extends the "model
  never writes a number" guarantee to "model never writes a date." Slice
  27's calendar carve-out still lets the model write "into 2027" as
  connective prose; the *event's own* dates come through the verified
  channel.
- **Slice 31's `horizon` marker applies** - a `projected` event (a
  planned/expected one) renders its line with the `(projected)` /
  `PROJECTED` marker unchanged. Charts are untouched: an event has no
  `value`, so `_resolve_chart` already excludes it.
- `coverage_summary` gains an `events` count.
- `rich_export.py` needed **no change** - `_substitute` already routes
  through `display_value`, which now knows `event`.
- 280 tests, mocked client only. Hand-authored end-to-end run: two events
  (one reported, one projected) verified, the reported one rendered as a
  full dated timeline, the projected one with `— next: …` and the Slice
  31 marker, `coverage_summary` reporting `events: 2`. Real-model
  behaviour is the still-owed live Vercel smoke test.
- **Not in this slice:** numeric reasoning about a deal (size, %
  accretion) stays a `quote`/`computed`; multi-event chronology ordering;
  and the long-standing carve-outs (mix-vs-rate bridge, share-of-total
  shift, peer benchmarks, a real `.pdf` of the rich layout).

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
