"""Metered hiring (Slice 133): a caller's budget, which only narrows, and the receipt
every engagement taken on gets.

No money is involved. No price has been set for any role, so a receipt records
``pricing: "tbd"`` and ``charged_cents: 0``, and meters work in model calls and
tokens. Receipts are not signed yet (``signed: false``): a verifier must not treat
one as attested by AnalystOS until a published key signs them.
"""

import base64
import hashlib
import json

from analystos.packs import consulting

FORMAT = "analystos-receipt/1"
LIMITS = {"max_model_calls": consulting.MAX_MODEL_CALLS, "max_output_tokens_per_call": consulting.MAX_TOKENS}
OUTCOMES = ("delivered", "not_verified", "unavailable")


def parse_budget(raw):
    """``(budget, problems)``. ``budget`` is the effective budget: the server's limits,
    narrowed by each value the caller sent. A value above a limit is refused, never
    clamped; so is an unknown key or anything but a positive integer."""
    budget = dict(LIMITS)
    if raw is None:
        return budget, []
    if not isinstance(raw, dict):
        return None, ["budget must be an object"]
    problems = []
    for key, value in raw.items():
        if key not in LIMITS:
            problems.append(f"budget has no field {key!r}; the fields are {', '.join(LIMITS)}")
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            problems.append(f"budget.{key} must be a whole number of at least 1")
        elif value > LIMITS[key]:
            problems.append(f"budget.{key} is {value}, above this server's limit of {LIMITS[key]}; "
                            "a budget can only narrow the limits")
        else:
            budget[key] = value
    return (None, problems) if problems else (budget, [])


def usage_of(meter):
    """Totals over the metered calls. A total is ``None`` when any call's count was not
    reported by the model - never a guess."""
    def total(name):
        values = [call[name] for call in meter]
        return sum(values) if values and all(isinstance(v, int) for v in values) else (0 if not values else None)
    return {"model": consulting.model_name(), "model_calls": len(meter),
            "input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
            "calls": [dict(call) for call in meter]}


def canonical(receipt):
    return json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(receipt):
    return hashlib.sha256(canonical(receipt)).hexdigest()


def header_value(receipt):
    """The receipt for an HTTP header: base64url of its canonical JSON, without padding."""
    return base64.urlsafe_b64encode(canonical(receipt)).decode("ascii").rstrip("=")


def build(engagement, outcome, budget, meter, finished, spec_sha256=None, output=None, fmt=None):
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}")
    if (outcome == "delivered") != (output is not None):
        raise ValueError("a receipt names an output exactly when the work was delivered")
    return {
        "format": FORMAT,
        "engagement_id": engagement["id"],
        "roles": list(engagement.get("roles", [])),
        "requested_by": engagement.get("requested_by"),
        "started": engagement.get("created"),
        "finished": finished,
        "outcome": outcome,
        "budget": dict(budget),
        "usage": usage_of(meter),
        "spec_sha256": spec_sha256,
        "output": None if output is None else {
            "format": fmt["name"], "media_type": fmt["media_type"],
            "bytes": len(output), "sha256": hashlib.sha256(output).hexdigest()},
        "pricing": "tbd",
        "charged_cents": 0,
        "signed": False,
    }
