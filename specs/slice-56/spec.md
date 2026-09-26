# Slice 56 - the basis of a figure is shown wherever the figure is shown

## Goal

`docs/audit-2026-09-25.md` findings 5 and 6. The homepage says GAAP /
non-GAAP and forward-looking tags travel with a figure wherever it appears.
Rendering showed they appear in body paragraphs only: KPI tiles (HTML and
PDF) and chart bars carried none, and the `source: "image"` marker that
Slice 50 stores on image-derived facts was never drawn anywhere.

A figure's *basis* is now one shared definition
(`analystos/l4/basis.py`): a forward horizon (`guidance` / `projected`),
`non-GAAP`, and `from image`. It is shown in:

- body paragraphs (HTML and PDF) - `from image` is new; the other two
  already existed;
- KPI tiles (HTML and PDF), for the value fact and the delta fact;
- a chart's caption / a note under the chart (HTML and PDF), naming each
  point that has a basis;
- footnotes, for image-sourced facts: "Read from an image, not from
  extracted text."

## Not in this slice

- Enforcing that `horizon` / `gaap_status` are *correct*. They are labels the
  model assigns and no code checks them against the source; the default for a
  missing horizon is still "reported". That is stated in the audit and the
  homepage wording (Slice 57), not fixed here.
- Per-bar tags drawn inside the chart graphics.

## Done when

1. `basis_labels` returns the right labels for each combination.
2. A KPI tile for a non-GAAP figure, a guidance figure and an image-sourced
   figure shows the tag in the HTML, and the PDF text contains it.
3. A chart mixing a non-GAAP and a GAAP point names only the non-GAAP one in
   its basis note; a chart with no tagged point has no note.
4. A paragraph citing an image-sourced fact shows "from image" in HTML and
   `[FROM IMAGE]` in the PDF; its footnote says it was read from an image.
5. A figure with no basis renders exactly as before; the full suite is OK.
