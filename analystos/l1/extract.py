"""L1 - pull a table out of a CSV and check it against a schema.

A *schema* is a dict of column name -> ``"number"`` or ``"text"``.
``extract_table`` returns the rows as typed dicts, or raises ``ValueError``
if the data does not fit the schema (a missing column, or a value that can't
be the stated type).

Numbers are parsed the way spreadsheets actually export them: a thousands
comma, a leading ``$``, a trailing ``%``, or parentheses for a negative value
(``"(1,234)"`` -> ``-1234.0``) are all accepted. A UTF-8 byte-order mark, which
Excel silently adds to "CSV UTF-8" exports and which otherwise corrupts the
first header's name, is stripped on read.
"""

import csv
from pathlib import Path

_TYPES = ("number", "text")


def _clean_number_token(value):
    """Normalize a spreadsheet-style number string before parsing as a float.

    Strips thousands commas, a leading ``$``, a trailing ``%``, and turns
    parenthesized values negative - the accounting convention for a loss.
    """
    v = value.strip()
    negative = v.startswith("(") and v.endswith(")")
    if negative:
        v = v[1:-1].strip()
    if v.startswith("$"):
        v = v[1:].strip()
    if v.endswith("%"):
        v = v[:-1].strip()
    v = v.replace(",", "")
    if negative and v and not v.startswith("-"):
        v = "-" + v
    return v


def _coerce(value, kind, column, row_num):
    """Trim ``value`` and turn it into ``kind``; raise ValueError if it can't."""
    value = (value or "").strip()
    if kind == "text":
        return value
    try:  # kind == "number"
        return float(_clean_number_token(value))
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

    with Path(path).open(newline="", encoding="utf-8-sig") as f:
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
