"""L1 - one entry point that reads any format AnalystOS can extract from,
guessing a schema when the caller doesn't supply one.

Every format-specific extractor already produces the exact same typed-row
shape once a schema is applied. This is the "universal upload" piece: once a
schema is chosen - given explicitly, or guessed here from the raw data via
``analystos.l1.schema.guess_schema`` - everything downstream (L0 citation,
L2 answers, L4 rendering) is completely unaware of which format the source
was. See ``specs/slice-25/spec.md``.
"""

from analystos.l1 import extract, extract_docx, extract_pdf, extract_pptx, extract_xlsx
from analystos.l1.schema import apply_schema, guess_schema

_RAW_EXTRACTORS = {
    ".csv": lambda path, opts: extract._raw_rows(path),
    ".xlsx": lambda path, opts: extract_xlsx._raw_rows(path, sheet=opts.get("sheet")),
    ".docx": lambda path, opts: extract_docx._raw_rows(
        path, table_index=opts.get("table_index", 0)
    ),
    ".pptx": lambda path, opts: extract_pptx._raw_rows(
        path, slide_index=opts.get("slide_index"), table_index=opts.get("table_index", 0)
    ),
    ".pdf": lambda path, opts: extract_pdf._raw_rows(
        path, page=opts.get("page"), table_index=opts.get("table_index", 0)
    ),
}

SUPPORTED_EXTENSIONS = tuple(sorted(_RAW_EXTRACTORS))


def extract_any(source_path, schema=None, extract_options=None):
    """Extract a table from ``source_path``, whatever format it is.

    Dispatches by extension to the matching raw extractor. If ``schema`` is
    given, it's used exactly as every format-specific extractor already uses
    one - nothing is guessed. If it's omitted (``None``), a schema is
    guessed from the raw data itself.

    Returns ``(resolved_schema, rows)`` - the schema actually used (given or
    guessed) alongside the typed rows, so a caller can show what was
    detected. Raises ``ValueError`` for an unsupported extension or anything
    the underlying extractor itself raises for.
    """
    suffix = source_path.suffix.lower()
    if suffix not in _RAW_EXTRACTORS:
        raise ValueError(
            f"unsupported source file type {suffix!r}; "
            f"expected one of {sorted(SUPPORTED_EXTENSIONS)}"
        )

    headers, numbered = _RAW_EXTRACTORS[suffix](source_path, extract_options or {})
    resolved_schema = schema if schema is not None else guess_schema(numbered, headers)
    rows = apply_schema(numbered, headers, resolved_schema)
    return resolved_schema, rows
