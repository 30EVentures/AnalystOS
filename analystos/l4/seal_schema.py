"""JSON Schema for one sealed fact record (Slice 76).

The shape of ``facts[].record`` in an ``analystos-seal/1`` bundle, written
down once. ``analystos/api_v1/openapi.py`` publishes it as
``components.schemas.SealFact``.

It describes a record *as sealed*: rule 1 of ``docs/seal.md`` has already
turned every number into a string. ``required`` lists what a verifier reads
to run its checks; extra properties are allowed. Fitting this schema is a
statement about shape only - it says nothing about whether the record's
citations or arithmetic hold.
"""

OPERATIONS = ["sum", "average", "ratio", "growth_percent", "percent_of_total", "difference", "remainder"]

_NUMBER = {"type": "string", "pattern": r"^-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?$",
           "description": "a number, sealed as a string (rule 1)"}
_COMMON = {
    "horizon": {"enum": ["reported", "guidance", "projected"]},
    "gaap_status": {"enum": ["gaap", "non_gaap", "n/a"]},
}
_PRESENTED = {
    "display": {"enum": ["inline", "stat"]},
    "label": {"type": ["string", "null"]},
    "format": {"enum": ["usd", "percent", "number", "text"]},
}


def _record(kind, required, properties, description):
    return {"type": "object", "description": description,
            "required": ["type"] + required,
            "properties": {"type": {"const": kind}, **_COMMON, **properties}}


SEAL_FACT_SCHEMA = {
    "description": "One sealed fact: `facts[].record` of an analystos-seal/1 bundle. Discriminated by `type`.",
    "oneOf": [
        _record("quote", ["citation"], {
            **_PRESENTED,
            "citation": {"type": "string", "description": "exact text from the document"},
            "value": {**_NUMBER, "description": "present when the quote carries a figure; must equal a number `citation` spells"},
            "sentence": {"type": "string", "description": "with a value: the sentence, holding one {value} placeholder"},
            "text": {"type": "string", "description": "without a value: the quoted text itself"},
        }, "A claim backed by an exact substring of the document."),
        _record("computed", ["operation", "value", "operands", "total", "citation"], {
            **_PRESENTED,
            "operation": {"enum": OPERATIONS},
            "sentence": {"type": "string"},
            "value": {**_NUMBER, "description": "the result; must recompute from `operands` (and `total`)"},
            "operands": {"type": "array", "items": _NUMBER, "description": "in the order given; `citation[i]` is operand i"},
            "total": {"anyOf": [_NUMBER, {"type": "null"}], "description": "the denominator for percent_of_total, else null; its citation follows the operands'"},
            "citation": {"type": "array", "items": {"type": "string"}},
        }, "A figure recomputed from cited operands."),
        _record("event", ["what", "citation"], {
            "what": {"type": "string"},
            "date": {"type": "string", "description": "empty when the document gave none"},
            "status": {"type": "string"},
            "next_step": {"type": "string"},
            "milestones": {"type": "array", "items": {
                "type": "object", "required": ["date", "detail"],
                "properties": {"date": {"type": "string"}, "detail": {"type": "string"}}}},
            "citation": {"type": "string", "description": "equals `what`"},
        }, "A timeline item; every part is a substring of the document."),
        _record("prose", ["text"], {
            "text": {"type": "string", "description": "carries no figure: the pipeline refuses a digit outside a calendar reference"},
        }, "Connective text with no figure."),
    ],
}
