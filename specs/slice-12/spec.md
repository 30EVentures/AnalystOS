# Slice 12 — L2 computed metrics (growth %, ratio %)

## Goal

Add the one bit of arithmetic an income-statement report always needs - a
year-over-year percent change and a same-row percentage (margin, cost ratio) -
so the pipeline can produce derived numbers, each still citing the input cells
it was computed from.

## Included

- `analystos/l2/answer.py` — `answer_growth(...)`, `answer_ratio(...)` plus
  shared helpers (`_cell`, `_require_columns`, `_row_index`)
- `analystos/l4/export.py` — `_footnote` renders a list-of-cells citation as
  `[n] computed from: <cell>; <cell>`; single-cell citations unchanged
- `analystos/pipeline.py` — dispatch each ask by its `kind`
  (`"lookup"` default, `"growth"`, `"ratio"`)
- `tests/test_l2_answer.py`, `tests/test_l4_export.py`, `tests/test_pipeline.py`
  — new tests

## Ask shapes

- `{"kind": "growth", "text": "...{answer}...", "key_column": "period",
  "from": "FY2023", "to": "FY2024", "value_column": "revenue"}`
- `{"kind": "ratio", "text": "...{answer}...", "key_column": "period",
  "key": "FY2024", "numerator": "gross_profit", "denominator": "revenue"}`

## Done when

1. `answer_growth` returns the percent change between the two rows' cell,
   rounded to one decimal, with `citation` = a list of the two input cells.
2. `answer_ratio` returns `numerator / denominator` for one row as a percent,
   one decimal, `citation` = a list of the two cells.
3. Both raise a clear `ValueError` on an absent column, no/many matching rows,
   or a zero divisor.
4. `render_section` footnotes a list citation as `[n] computed from: ...`;
   single-cell citations render exactly as before.
5. `run_job` dispatches asks by `kind`; an unknown kind is a clear error.
6. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Any metric beyond growth and ratio — no CAGR, multi-year averages, per-share.
- Number formatting beyond rounding to one decimal — no `,` separators, no `$`.
- Natural-language asks — you still spell out `key_column` / `from` / `to` etc.
- Chained metrics (a metric computed from another metric).
