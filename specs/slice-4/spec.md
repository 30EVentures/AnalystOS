# Slice 4 — L1: extract one table to structured data

## Goal

Read a table out of a CSV file and return it as typed rows, checked against a
schema. If the data doesn't match the schema, fail clearly. The bottom of L1 —
turning a raw table into data the rest of the system can trust.

## Included

- `analystos/l1/extract.py` — an `extract_table(path, schema)` function
- `analystos/l1/__init__.py` — mark the new layer folder
- `tests/test_l1_extract.py` — tests, one per "Done when" check

## Done when

1. Given a well-formed CSV and a matching schema, `extract_table` returns a
   list of rows where each value is the type the schema says (numbers are
   numbers, text is text).
2. A CSV missing a required column → a clear error naming the missing column.
3. A value that can't be the schema's type ("seven" in a number column) → a
   clear error naming the column and the bad value.
4. Leading/trailing spaces in cells are trimmed before checking.
5. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Any format but CSV. PDF / Excel / HTML each need a third-party package —
  their own slices later.
- Reading the file from L0 by hash — the glue slice (Slice 8) wires that up;
  Slice 4 takes a path.
- More than one table per file, or finding a table inside a larger document.
- Fixing or guessing bad data — it only accepts or rejects.
- Dates, currencies, percentages as special types — just "number" and "text".
- Decimal-exact money. "number" is a float for now.

## Schema shape

A dict mapping column name to `"number"` or `"text"`, e.g.
`{"period": "text", "revenue": "number", "cogs": "number"}`.
Columns in the CSV that are not in the schema are ignored.
