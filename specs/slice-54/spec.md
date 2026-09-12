# Slice 54 — the deterministic floor didn't recognize "Q3 FY2026"

## Goal

Found live 2026-09-12 against a real document (the Orion Industrial
Group test document, "Test #10"): Gate 1/Gate 2 failed on this run (a
different, non-deterministic outcome than an earlier local run of the
same document), so Slice 52's deterministic floor rendered instead - and
its output was visibly broken: a KPI strip listing "Revenue" five times
across five different quarters instead of once, a chart mixing five
quarters of revenue and an unrelated segment figure together in one
jumbled bar chart, and no trend sentence at all despite 5 consecutive
quarters of growth in the data.

Root cause: this document's model labelled quarters as **"Q2 FY2027"**
(quarter + "FY" + year combined) - a real, common fiscal-quarter
convention. `analystos/l4/deterministic_report.py`'s period-token
extraction only recognized "Q2 2027" (quarter + bare year) or "FY2027"
alone as separate patterns; against "Q2 FY2027 Revenue" it silently
matched only the trailing "FY2027" part, losing the quarter number
entirely. That one dropped token broke three things at once, since all
three depend on it: `_metric_key` (every quarter of "Revenue" looked
like a *different* metric, since only "FY2027"/"FY2026" was stripped,
leaving "Q2"/"Q1"/etc. still embedded and differentiating each label),
`_period_sort_key` (no quarter to sort by, so chronological ordering
inside a fiscal year was arbitrary), and `_select_time_series` (no 3+
group of the same metric ever formed, so no trend, and the chart
fallback lumped unrelated same-format facts together instead).

The same gap exists in `analystos/l4/rich_export.py`'s `_PERIOD_LABEL_RE`
(Slice 47's chart-type auto-detection) - if the *model's own* narrative
ever labels a chart's points "Q2 FY2027" instead of "Q2 2027", the rich
narrative path would hit the identical bug (a real trend chart wrongly
rendered as a bar). Fixed there too, not just in the deterministic tier.

## Included

- `rich_export._PERIOD_LABEL_RE` gains a new alternative, tried first:
  `Q[1-4]\s*'?\s*FY\s*'?\s*\d{2,4}` ("Q3 FY2026", "Q3 FY'26").
- `deterministic_report._PERIOD_TOKEN_RE` gains the identical combined
  alternative, ordered before the bare-quarter and bare-FY alternatives
  it would otherwise partially match instead.
- `deterministic_report._QUARTER_RE` (used by `_period_sort_key` to
  parse a token back into `(year, quarter)`) accepts an optional `FY`
  between the quarter and the year, so "Q3 2026" and "Q3 FY2026" parse
  to the identical sort key.

## Not in this slice

- An exhaustive catalogue of every real-world fiscal-period spelling
  (e.g. "2Q27", "FQ3'26") - fixed the specific, confirmed real gap; a
  future genuinely different format is a future, separately-diagnosed
  fix, not guessed at here.

## Done when

1. `_period_token`/`_PERIOD_LABEL_RE` recognize "Q3 FY2026" (and
   variants) as a real period, proven directly.
2. `_period_sort_key` orders "Q3 FY2026" correctly among other periods
   in the same and different fiscal years.
3. A reconstruction of the exact real segment set behind Test #10
   (same labels, same values, same computed facts) now produces: KPIs
   deduplicated to one per distinct metric, both growth facts correctly
   attached to the current (Q2 FY2027) quarter, a genuine 4-consecutive-
   period trend sentence, and a clean same-metric revenue line chart -
   confirmed locally against the real captured data, not a second live
   API call.
4. `python3 -m unittest discover -s tests -v` passes.

## Built (post-implementation note)

Both regexes fixed as specified. Verified locally (before writing the
formal tests) by reconstructing the exact real segment set from the
Test #10 PDF's own visible values/labels/footnotes and calling
`build_deterministic_report` directly - confirmed all four symptoms
gone: 2 correctly-deduplicated KPIs (Revenue, Industrial Systems),
both growth facts attached to Q2 FY2027, a real "grown for 4
consecutive periods" trend sentence, and a clean 5-point revenue-only
line chart (`_detect_chart_type` correctly resolves to "line", not
"bar"). No second live API call was needed to confirm the fix - all
the real data was already visible in the captured output.

Tests: `tests/test_l4_deterministic_report.py::FiscalYearPeriodFormatTest`
(4 tests, using the exact real Test #10 values/labels) and
`tests/test_l4_rich_export.py::ChartTypeAutoDetectionTest::test_the_combined_quarter_fy_year_label_is_also_recognized_as_a_period`
(the same gap fixed on the rich-narrative chart-detection path too,
since a model-declared chart using this label format would have hit
the identical misclassification). Full suite: 503/503 passing.
