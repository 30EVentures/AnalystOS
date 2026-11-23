# Slice 114 - charts and a "so what" on every finding

## Goal

Owner's feedback on the first deck (2026-11-23): it looks good; add some
graphs, and a tiny bit more text, not a lot.

## What changes

1. **Charts, from verified figures only.** Each issue-tree branch may carry one
   bar chart: `{"title", "figure_ids", "labels"}` - 2 to 6 distinct figures that
   already passed verification, all in the same unit, with one short label per
   bar. The model chooses which figures to chart; it cannot introduce a value,
   because a bar's height is the figure's verified value, read by code. The
   chart's title and labels go through the same number rule as every other
   sentence (a number needs its `[F#]` tag). Charted figures count as used.
2. **A "so what" per finding.** Each branch gets one sentence (at most 200
   characters) stating what the finding means for the decision. Same number
   rule.
3. **Rendering.** A finding with a chart shows it as a native, editable
   PowerPoint column chart in place of the number tiles: data labels formatted
   by unit (7%, 3 pts, $30,600), assumption bars in grey. The "so what" sits
   under the bullets, set apart. Findings without a chart keep the tiles.

## Done when

1. `verify_content` refuses a chart with fewer than 2 or more than 6 figures,
   an unknown or repeated figure, mixed units, a label count that does not match,
   an over-long label, a non-sentence title or an untagged number in a title or
   label; and refuses a missing, empty, over-long or untagged "so what".
2. The recorded churn case has a chart on each finding and a "so what" on each;
   the rendered deck has one native chart per finding whose values equal the
   charted figures' verified values, in order.
3. The "renderer adds no numbers" test still passes, and a new test checks that
   every chart value is a verified figure value.
4. Every slide previewed as an image and checked by eye.
5. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.

## Not in this slice

- Line, pie or waterfall charts; charts outside findings.
- More text elsewhere ("a tiny bit", per the owner).
