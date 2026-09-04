"""L2 - answers over L1 rows, each carrying a citation.

``answer_lookup`` finds one cell. ``answer_growth`` and ``answer_ratio`` do the
one bit of arithmetic an income-statement report always needs - a year-over-year
percent change and a same-row percentage (margin, cost ratio) - and cite the
input cells they were computed from.
"""


def _cell(source, i, column):
    """A citation to one cell: CSV line number is the row index + 2 (header = 1)."""
    return {"source": source, "row": i + 2, "column": column}


def _require_columns(rows, *columns):
    if not rows:
        raise ValueError("no rows to search")
    have = list(rows[0].keys())
    for col in columns:
        if col not in have:
            raise ValueError(f"column {col!r} is not in the rows (have: {have})")


def _row_index(rows, key_column, key):
    """Index of the single row where ``key_column == key``; raise otherwise."""
    hits = [i for i, row in enumerate(rows) if row[key_column] == key]
    if not hits:
        raise ValueError(f"no row where {key_column!r} == {key!r}")
    if len(hits) > 1:
        raise ValueError(
            f"{len(hits)} rows where {key_column!r} == {key!r}; expected exactly one"
        )
    return hits[0]


def answer_lookup(rows, *, source, where, select):
    """Return ``{"answer": value, "citation": {...}}`` for a single-cell lookup.

    ``where``  - a ``(column, value)`` pair used to find the row.
    ``select`` - the column whose value is the answer.
    ``source`` - the hash of the L0 source these rows came from.

    The citation is ``{"source": <hash>, "row": <n>, "column": <name>}`` where
    ``row`` is the CSV line number (header = 1, first data row = 2).

    Raises ``ValueError`` if a named column is absent, if no row matches, or if
    more than one row matches.
    """
    match_col, match_val = where

    if not rows:
        raise ValueError("no rows to search")

    columns = list(rows[0].keys())
    for col in (match_col, select):
        if col not in columns:
            raise ValueError(f"column {col!r} is not in the rows (have: {columns})")

    hits = [i for i, row in enumerate(rows) if row[match_col] == match_val]
    if not hits:
        raise ValueError(f"no row where {match_col!r} == {match_val!r}")
    if len(hits) > 1:
        lines = [i + 2 for i in hits]
        raise ValueError(
            f"{len(hits)} rows where {match_col!r} == {match_val!r} "
            f"(lines {lines}); expected exactly one"
        )

    i = hits[0]
    return {
        "answer": rows[i][select],
        "citation": {"source": source, "row": i + 2, "column": select},
    }


def answer_growth(rows, *, source, key_column, from_key, to_key, value_column):
    """Percent change in ``value_column`` from the ``from_key`` row to the
    ``to_key`` row, rounded to one decimal place.

    ``citation`` is a list of the two input cells. Raises ``ValueError`` on an
    absent column, no/many matching rows, a zero base value, or a negative
    base value - a percent change computed from a loss (or any negative
    base) is mathematically defined but routinely misleading (a move from a
    $50M loss to a $30M profit is not "-160% growth"), so it is refused
    rather than silently reported.
    """
    _require_columns(rows, key_column, value_column)
    i_from = _row_index(rows, key_column, from_key)
    i_to = _row_index(rows, key_column, to_key)
    base = rows[i_from][value_column]
    if base == 0:
        raise ValueError(f"cannot compute growth: {value_column!r} is 0 in the base row")
    if base < 0:
        raise ValueError(
            f"cannot compute a percent change from a negative base "
            f"({value_column!r} = {base} in the {from_key!r} row) - state the "
            f"change in absolute terms instead"
        )
    pct = round((rows[i_to][value_column] - base) / base * 100, 1)
    return {
        "answer": pct,
        "citation": [
            _cell(source, i_from, value_column),
            _cell(source, i_to, value_column),
        ],
    }


def answer_ratio(rows, *, source, key_column, key, numerator, denominator):
    """``numerator / denominator`` for one row, as a percent, one decimal place.

    ``citation`` is a list of the two input cells. Raises ``ValueError`` on an
    absent column, no/many matching rows, or a zero denominator.
    """
    _require_columns(rows, key_column, numerator, denominator)
    i = _row_index(rows, key_column, key)
    den = rows[i][denominator]
    if den == 0:
        raise ValueError(f"cannot compute ratio: {denominator!r} is 0")
    pct = round(rows[i][numerator] / den * 100, 1)
    return {
        "answer": pct,
        "citation": [_cell(source, i, numerator), _cell(source, i, denominator)],
    }
