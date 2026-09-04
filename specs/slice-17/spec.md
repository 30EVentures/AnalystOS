# Slice 17 — L1: read a table from a Word (.docx) document

## Goal

A third input format with the same exactness guarantee as CSV and Excel: a
table in a `.docx` file is structured XML - a real table object with real
cells - not a layout to infer. No review step needed, same as Excel.

## Included

- `analystos/l1/extract_docx.py` — `extract_table_docx(path, schema, table_index=0)`
- `requirements.txt` — adds `python-docx==1.2.0`
- `tests/test_l1_extract_docx.py`

## Done when

1. A well-formed table returns typed rows, same shape as the other extractors.
   Spreadsheet-style number formats (`$`, commas, parenthesized negatives)
   are accepted, same as CSV and Excel, because it reuses `analystos.l1.schema`.
2. A blank row in the middle of the table is skipped, and a citation built
   from the returned rows (via L2) still names the table's real row - the
   same cross-layer guarantee Slice 16 added, re-verified here since this is
   a different code path.
3. A missing required column raises, naming it.
4. `table_index=` selects a table other than the first, for documents with
   more than one table (a cover page table before the real data, say).
5. An out-of-range `table_index`, or a document with no tables, raises
   clearly.
6. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Not in this slice

- PowerPoint or PDF - their own slices.
- Merged cells - python-docx repeats the same cell for every position a
  merge spans; not specially handled, and not expected to come up in a
  simple data table.
- Finding a table inside a document that also has none, one, or several -
  the caller is expected to know roughly which table they want.
