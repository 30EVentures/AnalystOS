# Slice 18 — L1: read a table from a PowerPoint (.pptx) deck

## Goal

The last input format that needs no review step: a table on a slide is a
structured shape, not an inferred layout - same exactness guarantee as CSV,
Excel, and Word. Board decks are very often PowerPoint, so this closes the
gap between "structured formats" and what executives actually send around.

## Included

- `analystos/l1/extract_pptx.py` — `extract_table_pptx(path, schema, slide_index=None, table_index=0)`
- `requirements.txt` — adds `python-pptx==1.0.2`
- `tests/test_l1_extract_pptx.py`

## Done when

1. A well-formed table returns typed rows, same shape as the other extractors.
2. A blank row in the middle of the table is skipped, and a citation built
   from the returned rows (via L2) still names the table's real row - the
   same cross-layer guarantee as Slices 16 and 17.
3. A missing required column raises, naming it.
4. Without `slide_index`, the first table found anywhere in the deck (in
   slide order) is used.
5. `slide_index=` narrows the search to one slide; an out-of-range
   `table_index` on that slide raises, naming the slide.
6. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Not in this slice

- PDF - its own slice, with a review step (extraction there can be wrong).
- Text boxes, charts, or SmartArt "tables" that aren't a real table shape.
- Merged cells - not specially handled, as with Word.
