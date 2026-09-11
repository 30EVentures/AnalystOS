"""L1 - pull a table out of a CSV and check it against a schema.

Row 1 is the header, row 2 is the first data row - CSV line numbers are used
directly as citation row numbers. A UTF-8 byte-order mark, which Excel
silently adds to "CSV UTF-8" exports and which otherwise corrupts the first
header's name, is stripped on read.

The actual type-checking and number parsing is shared with every other
format-specific extractor - see ``analystos.l1.schema``.
"""

import csv
from pathlib import Path

from analystos.l1.schema import apply_schema


def _raw_rows(path):
    """Read the CSV at ``path`` into ``(headers, numbered_raw_rows)`` - no
    schema applied yet. Shared by ``extract_table`` and, for schema
    auto-detection, ``analystos.l1.detect.extract_any``.
    """
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        numbered = [(row_num, dict(row)) for row_num, row in enumerate(reader, start=2)]
    return headers, numbered


def all_tables(path):
    """Every table in the source, as ``[(headers, numbered_raw_rows), ...]``
    - a CSV file is one table, always, so this is just ``[_raw_rows(path)]``.
    Exists so every format exposes the same "give me every real table"
    entry point (``analystos.l1.document_text`` uses this instead of its
    own separate parsing) - see specs/slice-44/spec.md.
    """
    return [_raw_rows(path)]


def extract_table(path, schema):
    """Read the CSV at ``path``; return its rows as a list of typed dicts.

    ``schema`` maps column name -> ``"number"`` or ``"text"``. Columns in the
    CSV that are not in the schema are ignored. Raises ``ValueError`` on an
    unknown schema type, a missing required column, or a bad value.
    """
    headers, numbered = _raw_rows(path)
    return apply_schema(numbered, headers, schema)
