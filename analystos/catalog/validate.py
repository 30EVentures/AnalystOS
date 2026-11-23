"""Validates the role catalog, ``analystos/catalog/roles.json`` (Slice 108).

Hand-rolled, like ``findings/validate.py``: the rules are few and specific, and
the one that matters most - a role is marked for hire only with a recorded
passing evaluation and an integer rate - is not something a generic schema says
well. Returns a list of human-readable problems; empty means valid. Never
raises on any JSON value, and never passes an empty catalog.

What this does NOT prove: an ``eval`` record is a recorded claim, not evidence.
Binding it to a sealed evaluation run a stranger can re-check comes with the
first real evaluation (roadmap Phase 4). Nothing serves the catalog yet.
"""

import json
import re
from pathlib import Path

FORMAT = "analystos-role-catalog/1"
CATALOG_PATH = Path(__file__).resolve().parent / "roles.json"

STATUSES = ("planned", "built", "evaluated", "available")
BOUNDARIES = ("deliverable-only", "approval-gated", "human-decides")
WAVES = (1, 2, 3, 4)
DELIVERABLES = (
    "brief", "report", "deck", "workbook", "memo", "register", "reconciliation",
    "case-file", "draft", "plan", "code",
)
_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# Largest integer a JSON reader in JavaScript keeps exactly (2**53 - 1): a rate
# an agent's client would silently round is refused.
MAX_RATE_CENTS = 2**53 - 1
_TOP_KEYS = {"format", "description", "statuses", "boundaries", "waves", "families", "roles"}
_EVAL_KEYS = {"set", "passed", "method"}
# How a role's evaluation was run: "mock" = a worked example written for this role and
# checked in a working session (no model call); "mock-family" = the same, but the example
# was written for another role in its family (Slice 119: the honest label for 60 of the
# 73 roles); "live" = the production model on the eval set.
EVAL_METHODS = ("mock", "mock-family", "live")
# The owner's decision, 2026-11-23: no price has been set for any role yet; pricing is to be determined.
PRICE_TBD = "tbd"
# What a role delivers today, as opposed to its native deliverables (which may not exist yet).
DELIVERS_TODAY = ("verified-deck",)
_ROLE_KEYS = {
    "id", "title", "family", "wave", "boundary", "deliverables", "status", "eval",
    "rate_cents_per_engagement_hour", "human_decides", "gated_actions", "delivers_today",
}
_REQUIRED_ROLE_KEYS = _ROLE_KEYS - {"human_decides", "gated_actions", "delivers_today"}
_FAMILY_KEYS = {"id", "title", "skill", "wave", "roles"}


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_slug(value):
    return isinstance(value, str) and _ID_RE.fullmatch(value) is not None


def _nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def _nonempty_str_list(value):
    return isinstance(value, list) and value != [] and all(_nonempty_str(v) for v in value)


def _validate_eval(where, record, must_pass):
    if not isinstance(record, dict):
        return [f"{where}: eval must be an object recording the run"]
    problems = [f"{where}: unknown eval field {k!r}" for k in sorted(set(record) - _EVAL_KEYS, key=str)]
    if not _nonempty_str(record.get("set")):
        problems.append(f"{where}: eval.set must name the evaluation set that was run")
    if not isinstance(record.get("passed"), bool):
        problems.append(f"{where}: eval.passed must be true or false")
    elif must_pass and record["passed"] is not True:
        problems.append(f"{where}: is 'available' but its evaluation did not pass")
    if not isinstance(record.get("method"), str) or record.get("method") not in EVAL_METHODS:
        problems.append(f"{where}: eval.method must be one of {list(EVAL_METHODS)}")
    return problems


def _validate_role(index, role, family_ids):
    where = f"role {index}"
    if not isinstance(role, dict):
        return [f"{where}: must be an object"]
    if isinstance(role.get("id"), str):
        where = f"role {role['id']!r}"
    problems = []
    for key in sorted(_REQUIRED_ROLE_KEYS - set(role)):
        problems.append(f"{where}: missing {key!r}")
    for key in sorted(set(role) - _ROLE_KEYS):
        problems.append(f"{where}: unknown field {key!r}")

    if not _is_slug(role.get("id")):
        problems.append(f"{where}: id must be a lowercase slug")
    if not _nonempty_str(role.get("title")):
        problems.append(f"{where}: title must be a non-empty string")
    if not (isinstance(role.get("family"), str) and role["family"] in family_ids):
        problems.append(f"{where}: unknown family {role.get('family')!r}")
    wave = role.get("wave")
    if not _is_int(wave) or wave not in WAVES:
        problems.append(f"{where}: wave must be one of {list(WAVES)}")

    if "delivers_today" in role and role["delivers_today"] not in DELIVERS_TODAY:
        problems.append(f"{where}: delivers_today must be one of {list(DELIVERS_TODAY)}")
    deliverables = role.get("deliverables")
    if not isinstance(deliverables, list) or not deliverables:
        problems.append(f"{where}: deliverables must be a non-empty list")
    else:
        for d in deliverables:
            if not isinstance(d, str) or d not in DELIVERABLES:
                problems.append(f"{where}: unknown deliverable {d!r}")

    boundary = role.get("boundary")
    if not isinstance(boundary, str) or boundary not in BOUNDARIES:
        problems.append(f"{where}: unknown boundary {boundary!r}")
    if boundary == "human-decides" and not _nonempty_str_list(role.get("human_decides")):
        problems.append(f"{where}: a human-decides role must list the decisions that stay human (human_decides)")
    if boundary != "human-decides" and "human_decides" in role:
        problems.append(f"{where}: human_decides is only for human-decides roles")
    if boundary == "approval-gated" and not _nonempty_str_list(role.get("gated_actions")):
        problems.append(f"{where}: an approval-gated role must list the actions that need approval (gated_actions)")
    if boundary != "approval-gated" and "gated_actions" in role:
        problems.append(f"{where}: gated_actions is only for approval-gated roles")
    # Waves are defined by what blocks the build (see the catalog's "waves"):
    # wave 3 is exactly the roles that act in client tools; a wave-4 role's core
    # output is a regulated decision, so it is always human-decides.
    if _is_int(wave) and boundary in BOUNDARIES:
        if (wave == 3) != (boundary == "approval-gated"):
            problems.append(f"{where}: wave 3 is exactly the approval-gated roles (wave {wave}, {boundary})")
        if wave == 4 and boundary != "human-decides":
            problems.append(f"{where}: a wave-4 role must be human-decides")

    status = role.get("status")
    rate = role.get("rate_cents_per_engagement_hour")
    record = role.get("eval")
    if not isinstance(status, str) or status not in STATUSES:
        problems.append(f"{where}: unknown status {status!r}")
    elif status in ("planned", "built"):
        if rate is not None:
            problems.append(f"{where}: a {status} role cannot carry a rate")
        if record is not None:
            problems.append(f"{where}: a {status} role cannot carry an eval record (that makes it evaluated)")
    else:
        problems.extend(_validate_eval(where, record, must_pass=(status == "available")))
        if status == "available":
            if rate != PRICE_TBD and (not _is_int(rate) or not 0 < rate <= MAX_RATE_CENTS):
                problems.append(f"{where}: an available role needs a positive integer rate in US cents, or "
                                f"{PRICE_TBD!r} (rate_cents_per_engagement_hour), got {rate!r}")
        elif rate is not None:
            problems.append(f"{where}: an evaluated role is not for hire yet and cannot carry a rate")
    return problems


def validate_catalog(doc):
    """Every problem with ``doc``; an empty list means the catalog is valid."""
    if not isinstance(doc, dict):
        return ["catalog must be a JSON object"]
    problems = []
    if doc.get("format") != FORMAT:
        problems.append(f"format must be {FORMAT!r}")
    for key in sorted(set(doc) - _TOP_KEYS, key=str):
        problems.append(f"unknown top-level field {key!r}")
    if doc.get("statuses") != list(STATUSES):
        problems.append(f"statuses must be exactly {list(STATUSES)}")
    if not isinstance(doc.get("boundaries"), dict) or set(doc["boundaries"]) != set(BOUNDARIES):
        problems.append(f"boundaries must describe exactly {list(BOUNDARIES)}")
    if not isinstance(doc.get("waves"), dict) or set(doc["waves"]) != {str(w) for w in WAVES}:
        problems.append(f"waves must describe exactly {[str(w) for w in WAVES]}")

    families = doc.get("families")
    family_ids, declared_counts = set(), {}
    if not isinstance(families, list) or not families:
        problems.append("families must be a non-empty list")
        families = []
    for i, family in enumerate(families):
        if not isinstance(family, dict) or set(family) != _FAMILY_KEYS:
            problems.append(f"family {i}: must have exactly the fields {sorted(_FAMILY_KEYS)}")
            continue
        fid = family["id"]
        if not _is_slug(fid):
            problems.append(f"family {i}: id must be a lowercase slug")
            continue
        if fid in family_ids:
            problems.append(f"family {fid!r}: duplicate id")
        family_ids.add(fid)
        if not _is_int(family["roles"]) or family["roles"] < 1:
            problems.append(f"family {fid!r}: roles must be a positive integer count")
        else:
            declared_counts[fid] = family["roles"]
        if not _is_int(family["wave"]) or family["wave"] not in WAVES:
            problems.append(f"family {fid!r}: wave must be one of {list(WAVES)}")
        if not (_nonempty_str(family["title"]) and _nonempty_str(family["skill"])):
            problems.append(f"family {fid!r}: title and skill must be non-empty strings")

    roles = doc.get("roles")
    if not isinstance(roles, list) or not roles:
        return problems + ["roles must be a non-empty list (an empty catalog is never valid)"]
    seen_ids, seen_titles, actual_counts, earliest = set(), set(), {}, {}
    for i, role in enumerate(roles):
        problems.extend(_validate_role(i, role, family_ids))
        if not isinstance(role, dict):
            continue
        rid, title = role.get("id"), role.get("title")
        if isinstance(rid, str):
            if rid in seen_ids:
                problems.append(f"role {rid!r}: duplicate id")
            seen_ids.add(rid)
        if isinstance(title, str):
            if title in seen_titles:
                problems.append(f"role {rid!r}: duplicate title {title!r}")
            seen_titles.add(title)
        if isinstance(role.get("family"), str) and role["family"] in family_ids:
            actual_counts[role["family"]] = actual_counts.get(role["family"], 0) + 1
            if _is_int(role.get("wave")):
                earliest[role["family"]] = min(earliest.get(role["family"], 5), role["wave"])
    for fid, declared in declared_counts.items():
        if actual_counts.get(fid, 0) != declared:
            problems.append(f"family {fid!r}: declares {declared} roles but the catalog lists {actual_counts.get(fid, 0)}")
    for family in families:
        fid = family.get("id") if isinstance(family, dict) else None
        if isinstance(fid, str) and fid in earliest and family.get("wave") != earliest[fid]:
            problems.append(f"family {family['id']!r}: wave must be the earliest wave of its roles "
                            f"({earliest[family['id']]}), got {family.get('wave')!r}")
    return problems


def _no_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate JSON key {key!r}")
        seen[key] = value
    return seen


def load_catalog(path=CATALOG_PATH):
    """Parse the catalog, refusing duplicate keys (JSON's last-one-wins would
    let a second "status" silently override the first)."""
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)


def summary(doc):
    """Counts by wave and status, for people and agents reading the catalog."""
    roles = doc["roles"]
    return {
        "roles": len(roles),
        "by_wave": {str(w): sum(1 for r in roles if r["wave"] == w) for w in WAVES},
        "by_status": {s: sum(1 for r in roles if r["status"] == s) for s in STATUSES},
        "by_boundary": {b: sum(1 for r in roles if r["boundary"] == b) for b in BOUNDARIES},
    }
