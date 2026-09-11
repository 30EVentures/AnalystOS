"""L1 - pull a table out of a PowerPoint (.pptx) deck and check it against a schema.

Finds tables across the deck's slides, in slide order, and reads one - the
first one found unless ``slide_index`` and/or ``table_index`` narrow it down.
Row 1 is the header, row 2 the first data row - the same convention as every
other extractor.

A table on a slide is a structured shape - a real table object with real
cells - not an inferred layout. Same reliability guarantee as CSV, Excel, and
Word; no review step needed.

Type-checking and number parsing are shared with every other format-specific
extractor - see ``analystos.l1.schema``.
"""

from pptx import Presentation

from analystos.l1.schema import apply_schema


def _tables_on(slide):
    return [shape.table for shape in slide.shapes if shape.has_table]


def _raw_rows(path, slide_index=None, table_index=0):
    """Read one table from the deck at ``path`` into ``(headers,
    numbered_raw_rows)`` - no schema applied yet. Shared by
    ``extract_table_pptx`` and, for schema auto-detection,
    ``analystos.l1.detect.extract_any``.

    Without ``slide_index``, every table in the deck (in slide order) is
    numbered 0, 1, ... and ``table_index`` picks among them. With
    ``slide_index`` (0-based), only tables on that one slide are considered.
    """
    prs = Presentation(path)
    slides = [prs.slides[slide_index]] if slide_index is not None else list(prs.slides)

    tables = [t for slide in slides for t in _tables_on(slide)]
    if table_index >= len(tables):
        where = f"slide {slide_index}" if slide_index is not None else "the deck"
        raise ValueError(
            f"found {len(tables)} table(s) in {where}; no table at index {table_index}"
        )
    table = tables[table_index]

    rows_list = list(table.rows)  # pptx's row collection doesn't support slicing
    if not rows_list:
        raise ValueError("table has no rows")

    headers = [c.text.strip() for c in rows_list[0].cells]

    numbered = []
    for row_num, row in enumerate(rows_list[1:], start=2):
        cells = row.cells
        if all(not c.text.strip() for c in cells):
            continue  # a blank row
        numbered.append((row_num, {h: c.text.strip() for h, c in zip(headers, cells)}))

    return headers, numbered


def all_tables(path):
    """Every table across the whole deck, in slide order, as
    ``[(headers, numbered_raw_rows), ...]`` - each extracted through the
    exact same ``_raw_rows`` the schema-driven path above already uses.
    A table with no rows is skipped, not fatal to the rest. See
    specs/slice-44/spec.md.
    """
    prs = Presentation(path)
    total = sum(len(_tables_on(slide)) for slide in prs.slides)
    tables = []
    for i in range(total):
        try:
            tables.append(_raw_rows(path, table_index=i))
        except ValueError:
            continue
    return tables


def extract_table_pptx(path, schema, slide_index=None, table_index=0):
    """Read one table from the deck at ``path``; return its rows as typed dicts.

    ``schema`` maps column name -> ``"number"`` or ``"text"``.

    Without ``slide_index``, every table in the deck (in slide order) is
    numbered 0, 1, ... and ``table_index`` picks among them. With
    ``slide_index`` (0-based), only tables on that one slide are considered.

    Raises ``ValueError`` on an unknown schema type, a missing required
    column, a bad value, no table at the requested index, or an empty table.
    """
    headers, numbered = _raw_rows(path, slide_index=slide_index, table_index=table_index)
    return apply_schema(numbered, headers, schema)
