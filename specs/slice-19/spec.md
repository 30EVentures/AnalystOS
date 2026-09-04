# Slice 19 — report templates, and closing two real gaps

## Goal

Auto-generate the standard analysis asks from a table's recognized columns,
so nobody hand-writes `job.json` for the common case (an income statement).
While building this, closed two gaps found live-testing earlier slices:
`run_job` never actually used the Excel/Word/PowerPoint extractors added in
Slices 16-18, and nothing verified a job's declared currency scale matched
its data (hit twice - see `docs/decisions.md`, 2026-09-04).

## Included

- `analystos/templates.py` — `recognize_columns`, `income_statement_asks`,
  `build_asks(name, rows)`
- `analystos/pipeline.py` — `run_job` now: (a) dispatches L1 extraction by
  the source file's extension (`.csv`/`.xlsx`/`.docx`/`.pptx`), not just CSV;
  (b) accepts `"template"` as an alternative to `"asks"`; (c) reads an
  optional job-level `"currency_unit"` and passes it to L4
- `analystos/l4/export.py` — `"usd_millions"` removed as a per-finding
  format; replaced by `render_section(..., currency_unit=...)`, one scale
  for every `"usd"` finding in the section, set once
- `docs/using-analystos.md`, `tests/test_docs.py` — templates + currency_unit
- `tests/test_templates.py`, plus new tests in `test_l4_export.py` and
  `test_pipeline.py`

## Done when

1. `recognize_columns` matches a fixed alias list case/underscore-insensitively;
   an unrecognized column is absent, never guessed.
2. `income_statement_asks` generates a lookup for each recognized line item
   at the latest period, YoY growth for revenue/net income when 2+ periods
   exist, and margins when their inputs are recognized; a missing line item
   is skipped, never invented; no period column raises.
3. `run_job` reads `.xlsx`/`.docx`/`.pptx` sources correctly (previously
   silently CSV-only); an unsupported extension raises clearly.
4. A job with `"template"` instead of `"asks"` runs end to end.
5. `render_section`'s `currency_unit` ("actual"/"thousands"/"millions")
   scales every `"usd"`-formatted finding in the section consistently; the
   old `"usd_millions"` per-finding format is gone.
6. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Not in this slice

- Auto-detecting `currency_unit` from the document's own text (a real
  statement usually says "$ in millions" as a caption) - real but riskier
  NLP-flavored work; the person declares it explicitly for now, which is
  slower but never silently wrong.
- Templates for anything but an income statement (balance sheet, cash flow).
- A cap on how many periods generate growth/margin asks - only the latest
  vs. previous period is covered; a long time series doesn't get a full
  trend automatically.
