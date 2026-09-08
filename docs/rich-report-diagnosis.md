# Fortune-10 report quality — diagnosis and permanent-fix plan

Goal: every report AnalystOS generates, for any document, meets the bar by
default — not a hand-fix of one file.

`mock_rich_report_v3.html` is the **learning sample**. Its *structure*
(executive summary, sections, embedded charts, distinct outlook) is real
output from `analystos/l4/rich_export.py` (Slice 28). Its *prose* was
hand-authored to simulate what the narrator should produce — nothing in L2
generates that shape today. So the mock shows both the target and, by where
even a hand-crafted attempt falls short, the gaps.

---

## Where report writing actually lives in the codebase (current, post-sync)

The local checkout was 51 commits behind `origin/main` at the start of this
session; the picture below is the real current `main` (Slice 28, PR #43).

| Stage | File | What it does |
|---|---|---|
| L1 text | `analystos/l1/document_text.py` | any of 5 formats → plain document text |
| **L2 extract** | `analystos/l2/analyze.py` → `analyze_document()` | **model call #1** (`write_report` tool). Returns *verified* segments: `quote` (substring-checked), `computed` (one of `sum / average / ratio / growth_percent / percent_of_total`, independently recomputed), `prose` (no digits). |
| **L2 narrate** | `analystos/l2/narrate.py` → `write_narrative()` | **model call #2** (`write_narrative` tool). Returns ordered `paragraphs`, each free text with `{{N}}` placeholders into segment indices. The model picks structure/wording; it can't state a number. |
| L4 render (flat) | `analystos/l4/export.py` → `render_narrative_section()` | title + paragraphs + footnotes. **This is what ships today.** |
| L4 render (rich) | `analystos/l4/rich_export.py` → `render_rich_report()` | exec summary + sections + charts + outlook. **Exists, wired to nothing** — no L2 stage emits its input shape (Slice 28 spec deferred that). |
| pipeline | `analystos/pipeline.py` → `build_report()` | default path: L1 text → `analyze_document` → `write_narrative` → `render_narrative_section`; falls back to `render_narrated_section` on any narrator failure. |

**The five mechanisms are already written into `narrate.py`'s system
prompt** — near-verbatim to the five in the request ("Benchmark every
number…", "Name the specific mechanism… never a category word",
"Sequence past from future", legal-as-process, "State a triggering event and
its reaction together"). So this is mostly **not** a prompt-wording problem.
It is a problem of what the narrator is *given* to write from, what *shape* it
is allowed to return, and what actually gets *rendered*.

---

## Step 1 — Scoring the sample against the five mechanisms

`✓` present · `~` partial · `✗` missing

| Section | 1 Benchmark | 2 Mechanism | 3 Sequence | 4 Event narration | 5 Cause→effect |
|---|:--:|:--:|:--:|:--:|:--:|
| Executive summary | ✗ | ~ | ~ | ✗ | ~ |
| Revenue & Growth | ✓ | n/a | ~ | ✗ | ✗ |
| Segment Performance | ✗ | ~ | ✓ | ✗ | ✗ |
| Margin Trend | ~ | ✓ | ✓ | ~ | ✓ |
| Cost Structure | ✗ | ✗ | ✓ | ✗ | ✗ |
| Outlook | ~ | ✗ | ✓ | ✗ | ~ |

### 1 — Benchmarking

- **Revenue & Growth — the one strong case.** "$498.0M … up 9.5% from
  $455.0M the prior quarter and 23.9% from $402.0M a year earlier," plus a
  four-quarter trend. Three layers on one figure — the standard.
  - Still missing: the **sequential-growth series**. The trend levels are
    printed (410 → 432 → 455 → 498) but the QoQ rates they imply
    (+2.0%, +5.4%, +5.3%, **+9.5%**) are not, so "real acceleration" is
    asserted where "sequential growth roughly doubled" could be shown.
- **Segment Performance — the worst.** "it's Data Services specifically whose
  growth is outpacing the rest of the business" — a claim about *differential
  growth* with **zero growth figures**. Segments appear only as this
  quarter's $ and % of total; nothing compared to a prior period or to each
  other on a growth basis.
- **Margin Trend — partial.** 58.7% is set against three prior quarters, so
  direction is clear, but the magnitude is never in the standard unit
  (**−120 bps QoQ, −250 bps over four quarters**), the decline is not flagged
  as **accelerating** (−30 / −40 / −90 / −120 bps), and there is no
  segment-level margin, guided margin, or peer.
- **Cost Structure — none.** Opex lines are shown only as a share of opex
  itself — not vs prior periods, not as **% of revenue** (52.6%, computable
  from figures already on the page), not each line vs revenue. "Skews toward
  growth investment" has no number under it.
- **Outlook — partial.** Guidance ($1.95–1.98B) is a real target. But
  "implying continued acceleration" skips the arithmetic: YTD is $1,385M, so
  the guide **implies a Q4 of $565–595M — +13.5% to +19.5% sequential**, a
  further step up from the 9.5% just posted, and the most decision-relevant
  number in the report.

### 2 — Mechanism-naming

- **Margin Trend — the model section.** "the source is specific, not generic:
  continued investment in the Data Services buildout and one-time integration
  costs from the Q2 2026 acquisition, not a broad-based cost problem." Two
  named drivers *and* an explicit ruling-out of the generic story. One notch
  short: the two aren't split (one recurs, one reverses).
- **Executive summary — partial.** Names the thematic trade-off well, then
  leans on "once that platform matures" — no mechanism for *why* maturing
  eases it.
- **Segment Performance — partial.** Names the segment, not the mechanism.
  Never says the segment "outpacing the business" is the one that just
  absorbed an acquisition.
- **Cost Structure — missing.** "skews toward growth investment rather than
  fixed overhead" is a characterisation, not a mechanism.
- **Outlook — missing.** "as the Data Services platform reaches scale" is
  exactly the category-word class the discipline bans.

### 3 — Sequencing (history vs forward-looking)

- **The sample's strongest dimension** — a dedicated, visually distinct
  `.outlook` block with the caption "Interpretation, not a verified fact."
  Guidance and open questions live there; the four data sections are clean
  history.
- Gaps: the **executive summary blends the two** ("Guidance embeds an
  assumption … a specific bet management is making" sits above all the
  history); and the guidance figures are **cited with the same footnote
  style as reported actuals** — a projection and a result render identically.

### 4 — Event narration

- **Essentially absent.** The only event — "the Q2 2026 acquisition" —
  appears twice as a static fact: no name, date, price, description, or
  "what's next." A senior reader's first three questions (which deal, how
  much, when does the drag end) are unanswerable.

### 5 — Cause-effect linkage

- **Margin Trend does it:** cause (buildout + integration costs) and effect
  (four quarters of compression) in one sentence.
- **Left implicit elsewhere:** acquisition → Data Services revenue growth
  (never linked — the deal appears only as a *cost*); mix shift → margin
  (the Outlook asserts "the same storyline" but never sizes it); revenue
  acceleration → operating leverage (absent — no opex-growth or
  operating-income facts); debt-funded deal → interest → net income (absent —
  no net income anywhere in the sample).

---

## Step 2 — Root cause of each gap, mapped to the layer that must change

The five prompt disciplines are already present. Each remaining gap is one
of: **(A)** narrator prompt still too weak/narrow on a point; **(B)** the
narrator is never *given* the derived comparison to write from —
`analyze.py`'s extraction contract; **(C)** the narrator can't *return* the
needed structure — `narrate.py`'s output schema + `pipeline.py` wiring +
`rich_export.py`; **(D)** a true data limit no code can close.

| Gap (from Step 1) | Root cause | Layer / file to change |
|---|---|---|
| Sequential-growth series, bps deltas, trend rates not available | `analyze_document` extracts "important facts," not a *guaranteed* set of period-over-period deltas, ratios, and shares for every headline figure. `growth_percent` exists but is used at the model's discretion, one pair at a time. | **(B)** `analystos/l2/analyze.py` — extraction contract: for every headline metric with ≥2 periods present, require the deltas/trend as `computed` segments. Possibly a new `series` operation (ordered period-over-period), still independently recomputed. |
| "Differential segment growth" claimed with no segment growth numbers | Same as above, for segment tables: prior-period segment values are in the source but nothing forces them to be extracted and differenced. | **(B)** `analyze.py` — when a segment/category breakdown appears across periods, extract all periods and compute per-segment growth + mix shift (a `computed` `percent_of_total` delta). |
| Margin compression not in bps, not flagged as accelerating | No first-difference / second-difference operation; `ratio` is single-period. | **(B)** `analyze.py` — add a percentage-point-delta computed op (independently recomputed like the rest). |
| Guidance-implied Q4 not computed | Requires subtracting YTD actuals from a guidance range — `analyze.py` has `sum` but no "residual vs a stated target." | **(B)** `analyze.py` — allow a `computed` that benchmarks a stated target against the sum of stated actuals. |
| Guidance rendered identically to reported facts; exec summary blends past/future | Segments have no temporal nature. `quote`/`computed`/`prose` don't distinguish *reported* from *guided/projected*. | **(B)** `analyze.py` — add a `horizon` field (`reported` / `guidance` / `projected`) on every segment, verified the same way (a guidance quote still needs its `exact_text`). **(C)** `rich_export.py` — the outlook block is populated from `horizon`, not left to prose; a `guidance`/`projected` fact may not appear unmarked in a history section. |
| No executive summary / sections / charts / distinct outlook in live output | `write_narrative`'s tool schema returns a **flat `paragraphs` list**. `render_rich_report` (which has all of this) is wired to nothing. | **(C)** `analystos/l2/narrate.py` — new tool schema: `executive_summary`, `sections` (`heading`, `paragraphs`, optional `chart`), `outlook`. `pipeline.py` — call it, render via `render_rich_report`, keep the flat fallback. |
| No chart judgment | Slice 28 deferred it; nothing emits chart specs; `_resolve_chart` only defensively validates. | **(C)** `narrate.py` — the narrator proposes a `chart` per section as `{type, series:[{label, fact_index}]}`, referencing only citable numeric facts; validation (in range, numeric, ≥2 points, series shares a unit) moves into `narrate.py` next to the placeholder check. `rich_export._resolve_chart` stays as defence in depth. |
| Event ("the acquisition") left static; #4 discipline only covers *legal* | Prompt discipline #4 is scoped to "legal/regulatory content." A dated deal/launch/approval/closing isn't covered, and `analyze.py` has no structure for a dated event + its status + next step. | **(A)** `narrate.py` — broaden discipline #4 to *any* dated/sequential event. **(B)** `analyze.py` — a segment shape for a dated event (`date`, `what`, `status`, `next_step`), each field quote-verified. |
| Cause and effect not co-stated outside one section | Prompt discipline #5 is present but weakly enforced; the narrator often has the trigger and the consequence as two separate segments and states them in separate paragraphs. | **(A)** `narrate.py` — strengthen #5 with a worked example, and instruct that when two facts are causally linked in the source, they belong in one sentence. Mostly a prompt fix; **(B)** helps by tagging related segments. |
| Peer / sector / index benchmarks | The system sees one document. Peer data is usually not in it, and the verification guarantee forbids inventing it. | **(D)** Out of scope unless the user supplies a second source. The system should benchmark rigorously against everything the source *does* contain (prior periods, segments, guidance, targets) and never imply a peer comparison it can't cite. Record as a decision. |

### Summary of Step 2

- **Prompt-only fixes (A):** broaden discipline #4 beyond legal; strengthen
  discipline #5 with a worked example. Small.
- **The real work is (B) — `analyze.py`'s extraction contract.** Today it
  returns "interesting facts"; it must return a *complete, guaranteed* set of
  the comparisons a Fortune-10 reader expects — every delta, trend, ratio,
  share, and target-vs-actual that the source's own numbers support —
  each still independently recomputed. No prompt on the narrator can conjure
  a benchmark that was never computed.
- **(C) is mechanical but essential:** let the narrator return structure, and
  actually render it. The renderer already exists.
- **(D):** peer benchmarking is a known, stated boundary, not a bug.

Every (B) addition is a pure function of quoted source cells, independently
recomputed and checked before display — the verification guarantee is
unchanged, just applied to more derived values.

---

## Step 3 — Proposed slices (permanent, default behaviour)

Following the repo's one-slice-one-PR loop. Order matters: extraction feeds
narration feeds rendering.

- **Slice 29 — `analyze.py` extraction contract.** Guarantee the derived
  comparison set for every headline metric (period-over-period deltas,
  multi-period trend, share-of-total and its shift, percentage-point deltas
  for margins, target-vs-actual where a target is stated). Add the `horizon`
  field. All new computed kinds independently recomputed; all still drop on
  failed verification. Tests: a fixture document in → the delta/trend/horizon
  segments are present and correct; a doc with only one period → no spurious
  deltas.
- **Slice 30 — `narrate.py` structured output + broadened disciplines.** New
  tool schema (`executive_summary` / `sections` / `outlook` / per-section
  `chart`). Broaden discipline #4 to any dated event; strengthen #5. Move
  chart-spec validation here. `pipeline.py` renders via `render_rich_report`,
  falls back to flat on any failure. Tests: mock client → structured report
  validates and renders; a malformed structure → clean fallback.
- **Slice 31 — event handling + `rich_export` horizon wiring.** Dated-event
  segment shape in `analyze.py`; outlook block driven by `horizon`;
  `guidance`/`projected` facts refused in history sections. Tests as above.
- **Slice 32 (if needed) — mix/attribution op** (`answer_mix_bridge`-style):
  decompose a blended-metric change into mix vs rate, citing every segment
  cell in both periods, `mix + rate + cross == actual` checked.

---

## Step 4 — Proving it: blocker

`analyze_document` and `write_narrative` are **live model calls**. There is
**no `ANTHROPIC_API_KEY` in this environment**, so the updated pipeline
can't be run end-to-end locally. Options, for the user to choose:

1. Provide a key for a local run (real per-report cost, a few cents each).
2. Verify on Vercel (key already set there) after the slices merge — the
   normal path; I'd run two real uploads against the live endpoint.
3. Prove the verification + structure + rendering logic locally with a
   mock client (no model), then a single live smoke test on Vercel.

Also: `mock_rich_report_v3.html` has no committed source document — its
`report` dict was hand-authored. Step 4 needs two real input documents
(the Meridian-style income statement, rebuilt as a real CSV/XLSX, plus one
deliberately different — a different industry and data shape).
