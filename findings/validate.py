"""Validates findings/registry.json entries against the rules in schema.json
(Slice 101). Hand-rolled, not a generic JSON Schema engine - this repo's own
convention (see tests/test_l4_seal_schema.py) for a schema small enough that a
dependency would be the wrong trade. schema.json stays the documentation of
record; this is what actually enforces it.
"""

import re
from datetime import date

_ID_RE = re.compile(r"^F-[0-9]{2,3}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ALLOWED_TOP_KEYS = {
    "id", "title", "discovered", "published", "status", "severity",
    "affected", "summary", "reproducer_exists", "fix_commit_url", "note",
}
_REQUIRED_KEYS = {"id", "title", "discovered", "status", "severity", "affected", "summary", "reproducer_exists"}
_STATUSES = {"open", "fixed", "disputed", "withdrawn", "template"}
_SEVERITIES = {"High", "Medium", "Low", "not-rated"}


def _valid_date(value) -> bool:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_entry(entry) -> list:
    """Returns a list of human-readable problems; empty means the entry is
    well-formed. Never raises on a malformed entry."""
    if not isinstance(entry, dict):
        return [f"entry must be an object, got {type(entry).__name__}"]

    problems = []

    unknown = set(entry) - _ALLOWED_TOP_KEYS
    if unknown:
        problems.append(f"unknown key(s): {sorted(unknown)}")

    missing = _REQUIRED_KEYS - set(entry)
    if missing:
        problems.append(f"missing required key(s): {sorted(missing)}")
        return problems  # further checks would just restate this

    if not _ID_RE.match(entry["id"]):
        problems.append(f"id {entry['id']!r} must match F-NN or F-NNN")

    if not isinstance(entry["title"], str) or not (10 <= len(entry["title"]) <= 140):
        problems.append("title must be a string of 10-140 characters")

    if not _valid_date(entry["discovered"]):
        problems.append(f"discovered {entry.get('discovered')!r} must be a YYYY-MM-DD date")

    published = entry.get("published")
    if published is not None and not _valid_date(published):
        problems.append(f"published {published!r} must be a YYYY-MM-DD date or null")
    if published is not None and _valid_date(published) and _valid_date(entry["discovered"]):
        if date.fromisoformat(published) < date.fromisoformat(entry["discovered"]):
            problems.append("published is before discovered - a finding cannot be published before it exists")

    if entry["status"] not in _STATUSES:
        problems.append(f"status {entry['status']!r} must be one of {sorted(_STATUSES)}")

    if entry["severity"] not in _SEVERITIES:
        problems.append(f"severity {entry['severity']!r} must be one of {sorted(_SEVERITIES)}")

    affected = entry["affected"]
    if not isinstance(affected, dict) or set(affected) - {"package", "version"} or not {"package", "version"} <= set(affected):
        problems.append("affected must be an object with exactly 'package' and 'version'")
    else:
        if not isinstance(affected["package"], str) or not affected["package"]:
            problems.append("affected.package must be a non-empty string")
        if not isinstance(affected["version"], str) or not affected["version"]:
            problems.append("affected.version must be a non-empty string")

    if not isinstance(entry["summary"], str) or not (40 <= len(entry["summary"]) <= 1000):
        problems.append("summary must be a string of 40-1000 characters")

    if not isinstance(entry["reproducer_exists"], bool):
        problems.append("reproducer_exists must be true or false")

    fix_url = entry.get("fix_commit_url")
    if fix_url is not None and not (isinstance(fix_url, str) and fix_url.startswith("https://")):
        problems.append("fix_commit_url must be an https:// URL or null")

    if entry["status"] == "fixed" and not fix_url:
        problems.append("status is 'fixed' but fix_commit_url is not set - the discipline needs a citable commit")

    return problems


def validate_registry(registry) -> dict:
    """Returns {finding_id_or_index: [problems]} for every entry that has
    any; an empty dict means the whole registry is clean. Also checks for
    duplicate ids across the registry."""
    if not isinstance(registry, list):
        return {"<registry>": [f"registry must be a list, got {type(registry).__name__}"]}

    problems_by_entry = {}
    seen_ids = []
    for i, entry in enumerate(registry):
        key = entry.get("id", f"<entry {i}>") if isinstance(entry, dict) else f"<entry {i}>"
        problems = validate_entry(entry)
        if problems:
            problems_by_entry[key] = problems
        if isinstance(entry, dict) and "id" in entry:
            seen_ids.append(entry["id"])

    duplicates = {x for x in seen_ids if seen_ids.count(x) > 1}
    if duplicates:
        problems_by_entry["<registry>"] = [f"duplicate id(s): {sorted(duplicates)}"]

    return problems_by_entry
