"""L1 - shared schema application: raw rows -> typed, validated rows.

Every format-specific extractor (CSV, Excel, ...) reads its source into the
same intermediate shape - a list of ``(row_num, {header: raw_string})`` pairs
- and hands it to ``apply_schema``, which does the one thing every format
needs: check the required columns are present and coerce each cell to the
schema's declared type. This is the single place that logic lives, so a rule
added here (a new accepted number format, say) applies to every source format
at once instead of needing to be copied into each extractor.

A *schema* is a dict of column name -> ``"number"`` or ``"text"``. Numbers are
parsed the way spreadsheets actually export them: a thousands comma, a
leading ``$``, a trailing ``%``, or parentheses for a negative value
(``"(1,234)"`` -> ``-1234.0``) are all accepted.
"""

_TYPES = ("number", "text")


class Rows(list):
    """What ``apply_schema`` returns: a plain list of typed row dicts for
    every normal purpose (indexing, iteration, equality against a plain
    list) - plus ``row_nums[i]``, the *real* row number that produced
    ``self[i]`` (a CSV line, a sheet row).

    Extraction skips rows that aren't real data (a blank spreadsheet row),
    so a row's position in this list is not its position in the source. Any
    code building a citation from an index must use ``row_nums[i]``, never
    ``i`` itself - that's the whole reason this class exists instead of a
    plain list.
    """

    def __init__(self, rows, row_nums):
        super().__init__(rows)
        self.row_nums = row_nums


def _clean_number_token(value):
    """Normalize a spreadsheet-style number string before parsing as a float.

    Strips thousands commas, a ``$``, a trailing ``%``, and turns
    parenthesized values negative - the accounting convention for a loss.
    The ``$`` can sit outside the parentheses ("$(4,368)") or inside
    ("($4,368)") - real documents use both - so the negative-parens check
    runs after stripping an *outer* ``$``, and again for an inner one.
    """
    v = value.strip()
    if v.startswith("$"):
        v = v[1:].strip()
    if v.endswith("%"):
        v = v[:-1].strip()
    negative = v.startswith("(") and v.endswith(")")
    if negative:
        v = v[1:-1].strip()
        if v.startswith("$"):
            v = v[1:].strip()
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


def apply_schema(numbered_raw_rows, headers, schema):
    """Check ``headers`` against ``schema`` and coerce each row.

    ``numbered_raw_rows`` is an iterable of ``(row_num, raw)`` where ``raw``
    maps column name to its value as a string (or a native int/float, which
    is stringified before parsing). ``row_num`` is whatever the source format
    uses to identify the row to a person (a CSV line number, a sheet row) -
    it is never inferred by position, so a citation stays accurate even when
    rows were skipped (e.g. a blank spreadsheet row).

    Returns a list of typed dicts, one per row. Raises ``ValueError`` on an
    unknown schema type, a missing required column, or a value that can't be
    its declared type.
    """
    bad_types = sorted({k for k in schema.values() if k not in _TYPES})
    if bad_types:
        raise ValueError(f"schema types must be one of {_TYPES}; got {bad_types}")

    missing = [c for c in schema if c not in headers]
    if missing:
        raise ValueError(f"table is missing required column(s): {missing}")

    rows = []
    row_nums = []
    for row_num, raw in numbered_raw_rows:
        rows.append(
            {
                col: _coerce(_as_str(raw.get(col)), kind, col, row_num)
                for col, kind in schema.items()
            }
        )
        row_nums.append(row_num)
    return Rows(rows, row_nums)


def _as_str(value):
    """A ragged CSV row or a blank spreadsheet cell can hand us None here."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)
