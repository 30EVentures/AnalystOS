"""Compute a measures/1 document from the charter and the audit log (Slice 96).

Every number here is read back from events `analystos/api_v1/store.py` already
writes for Slices 61/82-84 (`type == "analysis"`, carrying `tier`, `proposed`,
`verified`, `dropped`, `seal_ok`) - nothing new is instrumented. The three
measures map onto those fields exactly:

- **analysis** - "reports delivered at the written tier, with both quality
  gates passed, as a share of reports delivered". `tier == "written"` is only
  reached in `analystos/pipeline.py` after both Gate 1 (facts) and Gate 2
  (proofread_report) pass; every other tier is a fallback. So:
  `count(tier == "written") / count(any analysis event)`.
- **verification** - "facts refused for failing verification, as a share of
  facts proposed". Each analysis event already carries `proposed` and
  `dropped` (a fact `analyze_document` dropped for failing the L2 proof):
  `sum(dropped) / sum(proposed)`.
- **evidence** - "delivered reports whose seal re-verifies offline, as a
  share of reports delivered". Each event's `seal_ok` is the *result of
  actually running* `verify_bundle` against the freshly sealed bundle at
  delivery time (`analystos/api_v1/blueprint.py`), not a claim:
  `count(seal_ok is True) / count(any analysis event)`.

An empty denominator is `null`, never 0% or 100% - Flashy's own stated rule,
which this repo already follows elsewhere (`docs/decisions.md`). This module
answers only AnalystOS's own three roles; a role this charter does not have
is simply absent from the output, never guessed at.
"""

MEASURE_FORMULAS = {
    "analysis": lambda events: _ratio(
        sum(1 for e in events if e.get("tier") == "written"),
        len(events),
    ),
    "verification": lambda events: _ratio(
        sum(e.get("dropped", 0) for e in events),
        sum(e.get("proposed", 0) for e in events),
    ),
    "evidence": lambda events: _ratio(
        sum(1 for e in events if e.get("seal_ok") is True),
        len(events),
    ),
}


def _ratio(numerator: int, denominator: int):
    if denominator <= 0:
        return {"numerator": numerator, "denominator": 0, "value": None}
    return {"numerator": numerator, "denominator": denominator, "value": round(numerator / denominator, 4)}


def compute_measures(charter: dict, audit_events: list, window: tuple, computed: str) -> dict:
    """``window`` is ``(since_iso, until_iso)``, both required and both stated
    verbatim in the output - never derived from the clock at read time, so a
    cached or replayed document cannot silently claim to be current."""
    since, until = window
    analysis_events = [e for e in audit_events if e.get("type") == "analysis"]

    roles_out = []
    for role in charter.get("roles", []):
        name = role["name"]
        formula = MEASURE_FORMULAS.get(name)
        entry = {
            "role": name,
            "measure": role["measure"],  # byte-identical to the charter, never retyped
            "window": f"{since}/{until}",
        }
        if formula is None:
            entry.update({"numerator": None, "denominator": None, "value": None, "instrumented": False})
        else:
            entry.update(formula(analysis_events))
            entry["instrumented"] = True
        roles_out.append(entry)

    return {
        "measures": "1",
        "org": charter["slug"],
        "charter": f"https://{charter['slug']}.dev/.well-known/flashyos-charter.json",
        "computed": computed,
        "window": f"{since}/{until}",
        "roles": roles_out,
    }
