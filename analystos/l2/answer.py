"""L2 - answer a structured lookup over L1 rows, with a citation.

The smallest real reasoning step: given the typed rows from L1, find one value
and hand it back together with a citation that says exactly where it came from
- which source, which row, which column.
"""


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
