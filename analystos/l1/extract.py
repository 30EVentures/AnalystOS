"""L1 - pull a table out of a CSV and check it against a schema.

A *schema* is a dict of column name -> ``"number"`` or ``"text"``.
``extract_table`` returns the rows as typed dicts, or raises ``ValueError``
if the data does not fit the schema (a missing column, or a value that can't
be the stated type).
"""

import csv
from pathlib import Path

_TYPES = ("number", "text")


def _coerce(value, kind, column, row_num):
    """Trim ``value`` and turn it into ``kind``; raise ValueError if it can't."""
    value = (value or "").strip()
    if kind == "text":
        return value
    try:  # kind == "number"
        return float(value)
    except ValueError:
        raise ValueError(
            f"row {row_num}, column {column!r}: {value!r} is not a number"
        ) from None


def extract_table(path, schema):
    """Read the CSV at ``path``; return its rows as a list of typed dicts.

    ``schema`` maps column name -> ``"number"`` or ``"text"``. Columns in the
    CSV that are not in the schema are ignored. Raises ``ValueError`` on an
    unknown schema type, a missing required column, or a bad value.
    """
    bad_types = sorted({k for k in schema.values() if k not in _TYPES})
    if bad_types:
        raise ValueError(f"schema types must be one of {_TYPES}; got {bad_types}")

    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        missing = [c for c in schema if c not in headers]
        if missing:
            raise ValueError(f"CSV is missing required column(s): {missing}")

        rows = []
        for row_num, raw in enumerate(reader, start=2):  # row 1 is the header
            rows.append(
                {
                    col: _coerce(raw.get(col), kind, col, row_num)
                    for col, kind in schema.items()
                }
            )
    return rows
