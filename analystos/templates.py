"""Report templates - generate the standard asks from a table's recognized
columns, instead of hand-writing job.json for the common case.

One template so far: ``income_statement_asks``. It recognizes common aliases
for the standard line items (revenue, cost of revenue, gross profit,
operating expenses, operating income, net income) and a period-like key
column, then builds: the latest period's figure for each recognized line
item, year-over-year growth for revenue and net income (latest vs. the
period before it, if there is one), and gross/operating margin for the
latest period (if their inputs are present).

Recognition matches a fixed alias list, case-insensitively, treating spaces
and underscores the same. A column that isn't recognized is left out of the
generated asks - nothing is guessed or invented. Every generated ask uses
``"format": "usd"`` or ``"percent"``; the caller supplies ``currency_unit``
to `analystos.l4.export.render_section` separately (see that module's
docstring for why scale is never decided per-ask).
"""

_ALIASES = {
    "period": {"period", "fiscal year", "fy", "year", "quarter"},
    "revenue": {"revenue", "total revenue", "net revenue", "sales", "net sales"},
    "cost_of_revenue": {"cost of revenue", "cogs", "cost of goods sold", "cost of sales"},
    "gross_profit": {"gross profit"},
    "operating_expenses": {"operating expenses", "opex", "total operating expenses"},
    "operating_income": {"operating income", "income from operations", "operating profit"},
    "net_income": {"net income", "net earnings", "net profit"},
}

_LINE_ITEMS = (
    # concept, label, verb - "expenses" is plural ("were"); the rest are not
    ("revenue", "revenue", "was"),
    ("cost_of_revenue", "cost of revenue", "was"),
    ("gross_profit", "gross profit", "was"),
    ("operating_expenses", "operating expenses", "were"),
    ("operating_income", "operating income", "was"),
    ("net_income", "net income", "was"),
)


def _normalize(name):
    return name.strip().lower().replace("_", " ")


def recognize_columns(columns):
    """Map each recognized concept to the real column name that means it.

    ``columns`` is the table's actual column names. Returns e.g.
    ``{"revenue": "Total Revenue", "net_income": "net_income"}`` - a concept
    with no matching column is simply absent, never guessed.
    """
    normalized = {_normalize(c): c for c in columns}
    found = {}
    for concept, aliases in _ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                found[concept] = normalized[alias]
                break
    return found


def income_statement_asks(rows):
    """Build the standard income-statement asks from L1's typed ``rows``.

    Returns a list of ask dicts in the shape ``analystos.pipeline.run_job``
    expects. Raises ``ValueError`` if no period-like column is recognized, or
    if there are no rows to build a template from.
    """
    if not rows:
        raise ValueError("no rows to build a template from")

    found = recognize_columns(rows[0].keys())
    if "period" not in found:
        raise ValueError(
            "no period-like column recognized "
            f"(tried: {sorted(_ALIASES['period'])}; have: {sorted(rows[0].keys())})"
        )
    key_column = found["period"]
    periods = [r[key_column] for r in rows]
    latest = periods[-1]
    previous = periods[-2] if len(periods) > 1 else None

    asks = []
    for concept, label, verb in _LINE_ITEMS:
        if concept in found:
            asks.append(
                {
                    "text": f"{latest} {label} {verb} {{answer}}.",
                    "format": "usd",
                    "where": [key_column, latest],
                    "select": found[concept],
                }
            )

    if previous is not None:
        for concept, label in (("revenue", "Revenue"), ("net_income", "Net income")):
            if concept in found:
                asks.append(
                    {
                        "kind": "growth",
                        "format": "percent",
                        "text": f"{label} grew {{answer}} from {previous} to {latest}.",
                        "key_column": key_column,
                        "from": previous,
                        "to": latest,
                        "value_column": found[concept],
                    }
                )

    if "gross_profit" in found and "revenue" in found:
        asks.append(
            {
                "kind": "ratio",
                "format": "percent",
                "text": f"Gross margin was {{answer}} in {latest}.",
                "key_column": key_column,
                "key": latest,
                "numerator": found["gross_profit"],
                "denominator": found["revenue"],
            }
        )

    if "operating_income" in found and "revenue" in found:
        asks.append(
            {
                "kind": "ratio",
                "format": "percent",
                "text": f"Operating margin was {{answer}} in {latest}.",
                "key_column": key_column,
                "key": latest,
                "numerator": found["operating_income"],
                "denominator": found["revenue"],
            }
        )

    return asks


_TEMPLATES = {"income_statement": income_statement_asks}


def build_asks(template_name, rows):
    """Look up and run a template by name. Raises ``ValueError`` if unknown."""
    if template_name not in _TEMPLATES:
        raise ValueError(
            f"unknown template {template_name!r}; expected one of {sorted(_TEMPLATES)}"
        )
    return _TEMPLATES[template_name](rows)
