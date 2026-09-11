# Slice 48 — a real server-side PDF for the rich (v4) report

## Goal

The v4 rich report (KPI strip, inline-SVG charts, outlook, disclosure-gap
callouts - `analystos.l4.rich_export`) has no server-generated PDF today,
only the browser's own `window.print()`. The flat/plain report already has
a real one (`analystos.l4.export.render_pdf`, via `reportlab` - Slice 24),
but that renderer only knows the flat title/paragraphs/footnotes shape;
it has no concept of a KPI grid, a chart, or a boxed interpretation block.
This slice builds the rich report's own PDF renderer, matching
`render_pdf`'s existing contract (bytes in, bytes out, `reportlab`, no new
dependency - confirmed available: `reportlab.graphics.shapes` and
`reportlab.graphics.charts` are already importable from the pinned
version) and its own visual system as faithfully as a print medium allows.

## Included

- A new module, `analystos/l4/rich_pdf.py` - `render_rich_pdf(report,
  segments, source_hash, currency_unit="actual") -> bytes`, the same
  four-argument signature `render_rich_report` already takes, so both
  renderers are called from the exact same verified inputs; no data is
  re-derived or re-parsed from the HTML.
- KPI strip -> a `reportlab.platypus.Table`, one row, one column per KPI,
  bordered like the HTML grid, value + delta stacked in each cell.
- Charts -> **not** the existing inline-SVG strings from
  `analystos.l4.charts` (`reportlab` doesn't render SVG) - a parallel,
  PDF-native drawer using `reportlab.graphics.shapes`
  (`Drawing`/`Rect`/`Line`/`String`) for bar/line/waterfall, built once
  and shared by both the resolved `(labels, values)` `_detect_chart_type`
  already produces (Slice 47) - so the PDF and HTML charts are driven by
  the exact same shape-detection decision, never a second guess at type.
- Outlook / disclosure-gap / executive-insight "boxed" treatment -> a
  single-cell `Table` with a background color and border via
  `TableStyle`, matching each block's HTML color role (interpretation =
  amber, disclosure gap = dashed panel).
- Pagination: every chart card and every boxed block wrapped in
  `reportlab.platypus.KeepTogether` - `reportlab` pushes the whole
  flowable to the next page rather than splitting it if it doesn't fit,
  the same guarantee CSS's `break-inside:avoid` gives the print
  stylesheet already used for `window.print()`.
- Typography: **open decision, see below.**
- Integration point (how a caller actually gets these bytes):
  **open decision, see below.**

## Decisions (made before build, both the recommended option)

1. **Typography fidelity: (a) bundled real IBM Plex fonts.** Six TTF
   files (Sans/Serif/Mono, Regular + SemiBold, OFL-licensed) live in
   `analystos/l4/fonts/` alongside their `LICENSE.txt`, registered at
   import time via `pdfmetrics.registerFont`/`registerFontFamily`. The
   PDF's typography is the same families and weights as the HTML, not a
   base-14 stand-in.
2. **Integration point: (b) an opt-in second call.** `build_report`
   gained `want_pdf=False`. Every existing caller and test is
   untouched - the default return is still a bare string. Passing
   `want_pdf=True` returns `(section_text, pdf_bytes)` instead, for
   *every* path (rich HTML + `render_rich_pdf`, the plain fallback +
   the existing flat `render_pdf`, and the schema/template path +
   `render_pdf`) - one pipeline run, never a second. `run_job` passes
   `want_pdf` straight through, and `main()` now always asks for it, so
   the CLI writes a real `section.pdf` next to `section.html` for the
   rich path too (previously only the flat path got a PDF).

## Done when

1. A test generates a PDF from a real, representative multi-section rich
   report (KPIs, at least one chart, an outlook, a disclosure gap) and
   confirms it's a structurally valid PDF (parseable page count, real
   content streams - not just "some bytes came back").
2. A representative multi-section report's chart(s) and any table are
   never split across a page boundary - proven by constructing a report
   dense enough to force a page break near a chart, and confirming (via
   the built PDF's own page-content extraction, not a manual visual
   check) that the chart's content is wholly on one page.
3. The KPI strip and the outlook section are both present in the PDF
   output and visually distinct from plain body paragraphs - proven
   programmatically (distinct styling/background applied, not just "the
   text appears somewhere").
4. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Pixel-identical rendering to the HTML/browser-print version - a
  different medium with different constraints (no CSS grid, no native
  SVG); "matching visual fidelity" means the same components, the same
  color roles, the same information hierarchy, not byte-identical
  output.
- Donut chart PDF rendering - Slice 47 didn't auto-select donut either;
  nothing currently produces that chart type to render.

## Built (post-implementation note)

All four "Done when" checks are covered by `tests/test_l4_rich_pdf.py`
(8 tests) plus a new `tests/test_pipeline.py` test proving the
`want_pdf=True` integration end to end:

- Validity: `RichPdfValidityTest` - real `%PDF-` bytes, parseable,
  correct title/KPI/chart-title text.
- Pagination: `RichPdfChartPaginationTest` - a dense, 24-filler-paragraph
  report forces a real page break, and the waterfall chart's rects are
  proven (via `pdfplumber`) to land wholly on exactly one page, never
  split. The pre-existing HTML-path safety layer (Slice 47's post-hoc
  waterfall tie-out check) is proven independently on the PDF path too:
  forcing `_detect_chart_type` to lie and say "waterfall" for
  non-tying-out data, then confirming no waterfall-bar fill color
  (`_VERIFIED`, `_NEG`, or the positive-component green) appears
  anywhere in the output - the chart is refused, not drawn wrong.
- KPI/outlook distinctness: `RichPdfKpiAndOutlookTest` - the KPI value's
  characters are individually inspected for font name (`SemiBold`) and
  size (`>=14`); the outlook and executive-insight panels' rects are
  matched by exact RGB against their real color constants
  (`_INTERP_BG`, `_PANEL`).
- Full suite: 423/423 passing after this slice, including the new
  `build_report(..., want_pdf=True)` integration test.
