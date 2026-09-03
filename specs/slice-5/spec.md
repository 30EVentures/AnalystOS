# Slice 5 — L2: answer one question with a citation

## Goal

Given the typed rows from L1, answer one single-cell lookup and return the
answer together with a citation — which source, which row, which column. The
smallest real reasoning step: an answer that carries its proof.

## Included

- `analystos/l2/answer.py` — `answer_lookup(rows, *, source, where, select)`
- `analystos/l2/__init__.py` — mark the new layer folder
- `tests/test_l2_answer.py` — tests, one per "Done when" check

## Done when

1. Given rows, a source hash, `where=(column, value)`, and `select=column`,
   it returns
   `{"answer": <the value>, "citation": {"source": <hash>, "row": <n>, "column": <name>}}`.
2. The citation's row number matches the CSV line (header = 1, first data
   row = 2).
3. No row matches `where` → a clear error saying so.
4. A named column isn't in the rows → a clear error naming it.
5. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- English / natural-language questions — structured lookups only.
- Any math over rows (sums, growth %, ratios) — one cell, one answer.
- Reading rows from L1 or files from L0 — the caller passes `rows` and
  `source`; the glue slice (Slice 8) wires it.
- Citations that point into a PDF page or region — just source + row + column.
- Silently picking one when several rows match — that is an error (ambiguous).

## Citation shape

`{"source": <64-char hash>, "row": <int>, "column": <str>}` — enough to
trace back: which file (retrievable via L0), which row, which column.
