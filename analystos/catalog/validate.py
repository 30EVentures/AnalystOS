"""Validates the role catalog, ``analystos/catalog/roles.json`` (Slice 108).

Hand-rolled, like ``findings/validate.py``: the rules are few and specific, and
the one that matters most - a role is for hire only once its own evaluation
passed and it has an integer rate - is not something a generic schema says
well. Returns a list of human-readable problems; empty means valid. Never
raises on a malformed catalog, and never passes an empty one.
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
_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ROLE_KEYS = {
    "id", "title", "family", "wave", "boundary", "deliverables", "status", "eval",
    "rate_cents_per_engagement_hour", "human_decides", "gated_actions",
}
_REQUIRED_ROLE_KEYS = _ROLE_KEYS - {"human_decides", "gated_actions"}
_FAMILY_KEYS = {"id", "title", "skill", "wave", "roles"}


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def _nonempty_str_list(value):
    return isinstance(value, list) and value != [] and all(_nonempty_str(v) for v in value)


def _validate_eval(where, record, must_pass):
    if not isinstance(record, dict):
        return [f"{where}: eval must be an object recording the run"]
    problems = []
    if not _nonempty_str(record.get("set")):
        problems.append(f"{where}: eval.set must name the evaluation set that was run")
    if not isinstance(record.get("passed"), bool):
        problems.append(f"{where}: eval.passed must be true or false")
    elif must_pass and record["passed"] is not True:
        problems.append(f"{where}: is 'available' but its evaluation did not pass")
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

    if not (isinstance(role.get("id"), str) and _ID_RE.match(role["id"])):
        problems.append(f"{where}: id must be a lowercase slug")
    if not _nonempty_str(role.get("title")):
        problems.append(f"{where}: title must be a non-empty string")
    if role.get("family") not in family_ids:
        problems.append(f"{where}: unknown family {role.get('family')!r}")
    if not _is_int(role.get("wave")) or role.get("wave") not in WAVES:
        problems.append(f"{where}: wave must be one of {list(WAVES)}")

    deliverables = role.get("deliverables")
    if not isinstance(deliverables, list) or not deliverables:
        problems.append(f"{where}: deliverables must be a non-empty list")
    else:
        for d in deliverables:
            if d not in DELIVERABLES:
                problems.append(f"{where}: unknown deliverable {d!r}")

    boundary = role.get("boundary")
    if boundary not in BOUNDARIES:
        problems.append(f"{where}: unknown boundary {boundary!r}")
    if boundary == "human-decides" and not _nonempty_str_list(role.get("human_decides")):
        problems.append(f"{where}: a human-decides role must list the decisions that stay human (human_decides)")
    if boundary != "human-decides" and "human_decides" in role:
        problems.append(f"{where}: human_decides is only for human-decides roles")
    if boundary == "approval-gated" and not _nonempty_str_list(role.get("gated_actions")):
        problems.append(f"{where}: an approval-gated role must list the actions that need approval (gated_actions)")
    if boundary != "approval-gated" and "gated_actions" in role:
        problems.append(f"{where}: gated_actions is only for approval-gated roles")

    status = role.get("status")
    rate = role.get("rate_cents_per_engagement_hour")
    record = role.get("eval")
    if status not in STATUSES:
        problems.append(f"{where}: unknown status {status!r}")
    elif status in ("planned", "built"):
        if rate is not None:
            problems.append(f"{where}: a {status} role cannot carry a rate")
        if status == "planned" and record is not None:
            problems.append(f"{where}: a planned role cannot carry an eval record")
    else:
        problems.extend(_validate_eval(where, record, must_pass=(status == "available")))
        if status == "available":
            if not _is_int(rate) or rate <= 0:
                problems.append(f"{where}: an available role needs a positive integer rate in US cents "
                                f"(rate_cents_per_engagement_hour), got {rate!r}")
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
        if not (isinstance(fid, str) and _ID_RE.match(fid)):
            problems.append(f"family {i}: id must be a lowercase slug")
            continue
        if fid in family_ids:
            problems.append(f"family {fid!r}: duplicate id")
        family_ids.add(fid)
        if not _is_int(family["roles"]) or family["roles"] < 1:
            problems.append(f"family {fid!r}: roles must be a positive integer count")
        declared_counts[fid] = family["roles"]
        if not _is_int(family["wave"]) or family["wave"] not in WAVES:
            problems.append(f"family {fid!r}: wave must be one of {list(WAVES)}")
        if not (_nonempty_str(family["title"]) and _nonempty_str(family["skill"])):
            problems.append(f"family {fid!r}: title and skill must be non-empty strings")

    roles = doc.get("roles")
    if not isinstance(roles, list) or not roles:
        return problems + ["roles must be a non-empty list (an empty catalog is never valid)"]
    seen_ids, seen_titles, actual_counts = set(), set(), {}
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
        if role.get("family") in family_ids:
            actual_counts[role["family"]] = actual_counts.get(role["family"], 0) + 1
    for fid, declared in declared_counts.items():
        if actual_counts.get(fid, 0) != declared:
            problems.append(f"family {fid!r}: declares {declared} roles but the catalog lists {actual_counts.get(fid, 0)}")
    return problems


def load_catalog(path=CATALOG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def summary(doc):
    """Counts by wave and status, for people and agents reading the catalog."""
    roles = doc["roles"]
    return {
        "roles": len(roles),
        "by_wave": {str(w): sum(1 for r in roles if r["wave"] == w) for w in WAVES},
        "by_status": {s: sum(1 for r in roles if r["status"] == s) for s in STATUSES},
        "by_boundary": {b: sum(1 for r in roles if r["boundary"] == b) for b in BOUNDARIES},
    }
