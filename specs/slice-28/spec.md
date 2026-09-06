# Slice 28 — rich report rendering: charts, sections, a distinct outlook block

## Goal

Slice 27 fixed *how the words read*. This slice fixes *what the report
looks like*: real visual structure (an executive summary, section-by-
section body, not one undifferentiated block), charts where the data
supports them, and a forward-looking "outlook" block that's visually
impossible to mistake for a verified fact. The bar stated directly: a
Fortune 10 executive should see something their own strategy/IR team
would produce, not a wall of paragraphs however well-written.

**Scope, stated precisely, because it matters:** this slice builds the
*rendering capability* - real L4 code that can take a structured report
(exec summary, sections with optional charts, an outlook block) and
render it as real, polished HTML, with every chart data point held to
the exact same verification guarantee as every number in prose. It does
**not** build the L2 layer that would have a model actually decide
section structure, chart placement, and outlook content from a real
document - that's a new prompt/schema/tool-use design in its own right,
and it needs its own live test before it's trusted, the same as every
other model-facing change today. The mock in this slice proves the
rendering side works by hand-authoring the input a future L2 stage would
produce and running it through the real render code - not by writing
throwaway HTML.

## Design

- **New module, `analystos/l4/charts.py`** - pure SVG generation, no new
  dependency. Checked `requirements.txt` first per the instruction to use
  what's already available: no charting library exists yet, and pulling
  in `matplotlib` would add real weight for Vercel's serverless functions
  for something plain inline SVG does natively in any browser with zero
  JS. `reportlab` (already a dependency) has `reportlab.graphics.charts`
  for a PDF equivalent - explicitly deferred to a later slice, see below.
  Three chart types, matching the three shapes real financial writing
  actually uses: `bar_chart_svg` (category comparison - segment/peer/
  region), `line_chart_svg` (a trend across periods), `donut_chart_svg`
  (composition/mix). Each takes already-resolved `(label, value)` pairs
  and a format spec - these functions know nothing about verification,
  same separation `format_number` already has from the segments that
  feed it.
- **New module, `analystos/l4/rich_export.py`** - the actual renderer,
  `render_rich_report(report, segments, source_hash, currency_unit)`.
  `report` is `{"executive_summary": [...], "sections": [{"heading",
  "paragraphs", "chart"}, ...], "outlook": [...] | None}` - paragraphs
  use the exact same `{{N}}` placeholder mechanism Slice 27 already
  built and verifies; a `chart` is `{"type", "title", "series": [{"label",
  "fact_index"}, ...]}`.
- **A chart data point gets no separate verification step - it inherits
  Slice 26's, by construction.** `fact_index` can only point into
  `segments`, which is already 100% verified facts by the time anything
  reaches L4 (exactly how `{{N}}` already works). `_resolve_chart` checks
  each `fact_index` is in range and points at a *quantitative* fact (a
  `quote` with `has_value` or a `computed` segment - not `prose`, not a
  qualitative quote with no number) - not a new trust check, the same
  structural check `_validate_paragraph` already does for placeholders.
  A bad reference drops that one point; a chart left with fewer than two
  points is dropped entirely rather than rendered as something
  misleading - a one-bar "comparison" isn't one.
- **Outlook is visually a different thing, not a different font.**
  Distinct background, a explicit "Outlook" label, and copy stating
  plainly that this section is interpretation, not verified fact -
  reusing the exact same digit-ban rule Slice 27's connective prose
  already has (calendar references excepted), since outlook prose still
  must never state a raw, uncited number.
- **Citations are a designed part of the layout, not an afterthought.**
  Every `[n]` marker carries a native `title` attribute with the actual
  citation text, so the source is visible on hover with zero JavaScript
  - still jumps to the shared footnotes panel at the bottom on click,
  same mechanism `render_html` already has, just no longer the only way
  to see what's behind a number.
- **One shared footnote sequence across the whole document** - executive
  summary, then each section in reading order, then outlook - not reset
  per section, mirroring the single-footnotes-block convention every
  other renderer here already uses.

## Not in this slice

- **The L2 stage that would have a model actually produce this
  structure from a real document.** Needs its own prompt, its own tool
  schema, and its own live test - explicitly scoped out so this slice
  can be reviewed and merged on the strength of its rendering alone.
- **PDF chart rendering.** The concrete ask for this round was an HTML
  draft; `reportlab.graphics.charts` is the natural next step for PDF
  parity, given `reportlab` is already a dependency, but doing it well
  is its own piece of work, not a rushed add-on here.
- **Any change to `analystos/l2/narrate.py`, `analyze.py`, or the
  verification logic.** Untouched - this slice is rendering only.

## Done when

1. `bar_chart_svg`/`line_chart_svg`/`donut_chart_svg` each return valid,
   well-formed SVG for a normal input.
2. A chart spec referencing an out-of-range or non-quantitative
   `fact_index` drops that point, not the render.
3. A chart left with fewer than two valid points is omitted from the
   report entirely, not rendered half-empty.
4. `render_rich_report` renders an executive summary, section headings,
   embedded charts, and a visually distinct outlook block from one
   `report` structure.
5. Every citation marker carries a hover-visible `title` with the real
   citation text, in addition to the existing jump-to-footnote link.
6. Footnote numbers are assigned once, in document reading order, shared
   across the executive summary, every section, and the outlook block.
7. `python3 -m unittest discover -s tests -v` passes (with the venv
   active) - no model call anywhere in this slice's own tests.

## Verified beyond the test suite

A hand-authored mock report (a clearly-labeled draft/template earnings
report, placeholder company and figures - not a real client's data) run
through the real `render_rich_report`, not hand-written HTML, to prove
the rendering path actually produces the target shape before any of this
touches a live model call. See `docs/decisions.md`, 2026-09-06.
