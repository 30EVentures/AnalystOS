"""L1 - pull a table out of a PDF and check it against a schema.

Unlike Excel/Word/PowerPoint, a PDF has no real table object - pdfplumber
*infers* column boundaries and row splits from the page's visual layout,
which can be wrong in ways the other extractors can't be (a misread column,
a merged cell). That's why a PDF-extracted table is never cited directly:
``analystos.pipeline.build_report`` refuses to build a report from one until
a person has reviewed it and confirmed it - see that module's docstring and
``specs/slice-23/spec.md``.

Finds tables across the document's pages, in page order, and reads one - the
first one found unless ``page`` and/or ``table_index`` narrow it down. Row 1
is the header, row 2 the first data row - the same convention as every other
extractor.

Type-checking and number parsing are shared with every other format-specific
extractor - see ``analystos.l1.schema``.
"""

import pdfplumber

from analystos.l1.schema import apply_schema


def _raw_rows(path, page=None, table_index=0, *, table=None):
    """Read one table from the PDF at ``path`` into ``(headers,
    numbered_raw_rows)`` - no schema applied yet. Shared by
    ``extract_table_pdf`` and, for schema auto-detection,
    ``analystos.l1.detect.extract_any``.

    Without ``page`` (0-based), every table across the document (in page
    order) is numbered 0, 1, ... and ``table_index`` picks among them. With
    ``page``, only tables on that one page are considered.

    ``table`` (Slice 85) is a table a caller has already extracted from the
    PDF (one ``page.extract_tables()`` entry): it is parsed exactly as the
    one found by index would be, and ``path``/``page``/``table_index`` are
    not used - no second open of the file, no re-extraction of every page.
    A document pass that already holds each page's tables passes them in, so
    the cost stays linear in pages instead of tables x pages.
    """
    if table is None:
        with pdfplumber.open(path) as pdf:
            pages = [pdf.pages[page]] if page is not None else list(pdf.pages)
            tables = [t for p in pages for t in p.extract_tables()]

        if table_index >= len(tables):
            where = f"page {page}" if page is not None else "the document"
            raise ValueError(
                f"found {len(tables)} table(s) in {where}; no table at index {table_index}"
            )
        table = tables[table_index]

    if not table:
        raise ValueError("table has no rows")

    headers = [(c or "").strip() for c in table[0]]

    numbered = []
    for row_num, row in enumerate(table[1:], start=2):
        if all(not (c or "").strip() for c in row):
            continue  # a blank row
        numbered.append((row_num, {h: (c or "").strip() for h, c in zip(headers, row)}))

    return headers, numbered


def all_tables(path):
    """Every table across the whole document, in page order, as
    ``[(headers, numbered_raw_rows), ...]`` - each parsed by the exact
    same ``_raw_rows`` the schema-driven path above already uses. A table
    with no rows is skipped, not fatal to the rest. The PDF is opened and
    each page's tables extracted once (Slice 85), not once per table.
    See specs/slice-44/spec.md.
    """
    with pdfplumber.open(path) as pdf:
        found = [t for p in pdf.pages for t in p.extract_tables()]
    tables = []
    for table in found:
        try:
            tables.append(_raw_rows(path, table=table))
        except ValueError:
            continue
    return tables


def extract_table_pdf(path, schema, page=None, table_index=0):
    """Read one table from the PDF at ``path``; return its rows as typed dicts.

    ``schema`` maps column name -> ``"number"`` or ``"text"``.

    Without ``page`` (0-based), every table across the document (in page
    order) is numbered 0, 1, ... and ``table_index`` picks among them. With
    ``page``, only tables on that one page are considered.

    Raises ``ValueError`` on an unknown schema type, a missing required
    column, a bad value, no table at the requested index, or an empty table.
    """
    headers, numbered = _raw_rows(path, page=page, table_index=table_index)
    return apply_schema(numbered, headers, schema)
