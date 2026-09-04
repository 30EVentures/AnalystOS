# Slice 16 — L1: read a table from an Excel (.xlsx) sheet

## Goal

Give L1 a second, equally-exact input format: an Excel sheet. Same guarantee
as CSV — a cell is a cell, nothing is inferred from layout — so uploads
aren't limited to hand-made CSVs. This is also the project's first
third-party dependency (`openpyxl`), so it introduces `requirements.txt` and
a virtual environment.

## Included

- `analystos/l1/schema.py` — the type-checking and number-parsing logic
  moved out of `extract.py` so every format (CSV, Excel, and whatever comes
  next) shares one implementation instead of copies drifting apart
- `analystos/l1/extract.py` — refactored to call `schema.apply_schema`;
  behavior unchanged (all 11 existing tests pass with no edits)
- `analystos/l1/extract_xlsx.py` — `extract_table_xlsx(path, schema, sheet=None)`
- `requirements.txt` — `openpyxl==3.1.5`
- `.venv/` — local virtual environment (git-ignored already, from Slice 1)
- `tests/test_l1_extract_xlsx.py`
- `CLAUDE.md` — updated "how to run" for the venv + install step
- `docs/decisions.md` — why a dependency now, and what's coming next

## Done when

1. A well-formed sheet returns typed rows, same shape as `extract_table`.
2. A cell formatted as a percentage in Excel (stored as its fraction, e.g.
   `0.571`) is rescaled to match AnalystOS's own percent convention (`57.1`,
   not `0.571`) — otherwise a formatted column is silently 100x too small.
3. A blank row in the middle of the sheet is skipped, and row numbers in
   later error messages - *and in L2 citations built from these rows* -
   still reflect the sheet's real row, not a count that shifted because a
   row was skipped. (Caught in review: L2 previously derived a citation's
   row from a row's position in the list, which breaks the moment a row is
   skipped upstream. Fixed by having `analystos.l1.schema.Rows` carry the
   real row number per element, and L2 read it instead of guessing.)
4. A missing required column raises, naming it.
5. `sheet="..."` selects a named sheet; the first sheet is used otherwise.
6. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Not in this slice

- Word, PowerPoint, or PDF — their own slices.
- Multiple tables per sheet, or finding a table inside a larger layout.
- Formulas — `data_only=True` reads the last-calculated value; a sheet that
  has never been opened in Excel (formulas with no cached result) would read
  as blank. Edge case, not handled here.
- Any UI for picking a sheet — `sheet=` is a keyword argument for now.
