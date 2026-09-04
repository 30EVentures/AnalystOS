# Slice 15 — harden for real-world data and executive-ready numbers

## Goal

Three things stood between the pipeline and something you'd hand a Fortune 10
executive: it broke on how real spreadsheets format numbers, it rendered
numbers ugly, and its growth math could silently produce a misleading result.
This slice fixes all three, without changing anything's tested behaviour that
already worked.

## Included

- `analystos/l1/extract.py` — accept `$`, `%`, thousands commas, and
  parenthesized negatives when parsing a number cell; read CSVs with
  `utf-8-sig` so an Excel-added byte-order mark doesn't corrupt the first
  header.
- `analystos/l2/answer.py` — `answer_growth` refuses a negative base value
  with a clear error instead of returning a misleading percent.
- `analystos/l4/export.py` — an optional `"format"` key on a finding
  (`number` / `percent` / `usd` / `usd_millions`); negative values render in
  parentheses. Omitted `"format"` behaves exactly as before.
- `analystos/pipeline.py` — passes an ask's `"format"` through to its finding.
- `tests/` — new tests across `test_l1_extract.py`, `test_l2_answer.py`,
  `test_l4_export.py`.

## Done when

1. `extract_table` accepts `"$4,200,000"`, `"57.1%"`, and `"(4,368)"` (→
   `-4368.0`) in a number column.
2. A CSV with a UTF-8 BOM parses its header correctly.
3. A value that's still not a number after cleaning raises, showing the
   **original** (uncleaned) text in the error.
4. `answer_growth` from a negative base raises a clear error naming the
   problem, instead of returning a number.
5. `render_section` with `"format": "usd_millions"` on a finding renders
   `130497.0` as `$130.5B`; `"percent"` renders `57.142857` as `57.1%`;
   negative values render in parentheses; an unknown format raises.
6. A finding with no `"format"` key renders exactly as it did before this
   slice (backward compatible).
7. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Currency/locale beyond USD.
- Auto-detecting which columns are dollars vs. plain counts — the job author
  states the format explicitly, per ask.
- A guard on `answer_ratio` for negative inputs — a negative margin (a net
  loss as % of revenue) is legitimate and should render, not error.
- Re-checking whether existing `jobs/*/job.json` files use the new formats —
  the NVIDIA job gets updated as part of validating this slice, but that's
  content, not code.
