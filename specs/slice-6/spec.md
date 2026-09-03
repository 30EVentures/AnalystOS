# Slice 6 — L4: export one working-paper section with the citation trail

## Goal

Turn a list of L2 findings (each an answer + a citation) into one
working-paper section: prose with `[n]` markers, and a footnote block that
maps each marker back to its source. Returns text; doesn't write a file.

## Included

- `analystos/l4/export.py` — `render_section(title, findings)`
- `analystos/l4/__init__.py` — mark the new layer folder
- `tests/test_l4_export.py` — tests, one per "Done when" check

## A "finding"

```
{
  "text": "FY2024 revenue was {answer}.",   # must contain {answer}
  "answer": 4200000.0,
  "citation": {"source": <hash>, "row": 3, "column": "revenue"},
}
```

## Done when

1. `render_section(title, findings)` returns a string with: the title as a
   heading; each finding's `text` with `{answer}` filled in and a ` [n]`
   marker; a `---` separator; one footnote line per finding —
   `[n] source <hash> - row <r>, column "<c>"`.
2. Footnote numbers run 1, 2, 3… in finding order, and every `[n]` in the
   body has a matching footnote line.
3. A finding whose `text` has no `{answer}` → a clear `ValueError`.
4. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Generating the prose (no LLM) — the caller supplies the sentence templates.
- Number formatting (commas, currency, decimals) — `{answer}` → `str(answer)`.
- De-duplicating identical citations — every finding gets its own number.
- Multiple sections / heading hierarchy / a whole document — one flat section.
- Writing a file or export formats (docx/pdf) — returns a string; the glue
  slice (Slice 8) writes it.
- Showing a snippet of the cited source — citation stays source + row + column.
