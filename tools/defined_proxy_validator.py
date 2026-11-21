"""A PROXY validator for the undocumented, unpublished `defined/1` format (Slice 98).

`@flashyos/defined` is not on the npm registry (404, checked 2026-11-21) and has no
publicly readable source - unlike every other FlashyOS format this repo validates
against in `tools/flashyos-check/`, there is no real package to run here. This
module checks `drafts/defined-analystos.json` against the *documented* rules from
Flashy's 18 Nov integration document (itself describing their private source), not
against their actual code. Treat every check here as an informed guess, not a
conformance guarantee - the real answer only comes from their real checker, which
does not exist publicly to run.

Documented rules this implements:
- a definition is 40-700 characters
- `expires` must equal `asserted` plus exactly 365 days (never hand-set differently -
  "expiry-not-derived": a writer that could nudge its own expiry keeps a dead term
  current forever)
- `basis` must be `https://`
- fourteen key names are refused on an entry at any depth: digest, seal, sealed,
  hash, signature, signed, merkle, proof, score, rank, ranking, weight, confidence,
  authority_score (a grade you can compute is a grade you can game)
- a citation carries no definition text: definition, text, body, html, description,
  summary, excerpt are refused on a citation at any depth
"""

import re
from datetime import date, timedelta

ENTRY_FORBIDDEN_KEYS = {
    "digest", "seal", "sealed", "hash", "signature", "signed", "merkle", "proof",
    "score", "rank", "ranking", "weight", "confidence", "authority_score",
}
CITATION_FORBIDDEN_KEYS = {"definition", "text", "body", "html", "description", "summary", "excerpt"}

_ID_RE = re.compile(r"^(org|person|agent)/[a-z0-9][a-z0-9._-]*$")
_ENTRY_ID_RE = re.compile(r"^defined/[a-z0-9-]+/[a-z0-9-]+$")


def _find_forbidden_keys(value, forbidden, path=""):
    """Recursively scans ``value`` for any of ``forbidden`` as a dict key, at
    any depth - returns a list of dotted paths where one was found."""
    found = []
    if isinstance(value, dict):
        for key, sub in value.items():
            here = f"{path}.{key}" if path else key
            if key in forbidden:
                found.append(here)
            found.extend(_find_forbidden_keys(sub, forbidden, here))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found.extend(_find_forbidden_keys(item, forbidden, f"{path}[{i}]"))
    return found


def _check_entry(entry: dict) -> list:
    problems = []

    entry_id = entry.get("id", "")
    if not _ENTRY_ID_RE.match(entry_id):
        problems.append(f"id {entry_id!r} does not match defined/<authority>/<slug>")

    definition = entry.get("definition", "")
    if not (40 <= len(definition) <= 700):
        problems.append(f"definition is {len(definition)} characters, must be 40-700")

    for field in ("authority", "assertedBy"):
        value = entry.get(field, "")
        if not _ID_RE.match(value):
            problems.append(f"{field} {value!r} does not look like org/person/agent + a slug")

    try:
        asserted = date.fromisoformat(entry.get("asserted", ""))
        expires = date.fromisoformat(entry.get("expires", ""))
        if expires != asserted + timedelta(days=365):
            problems.append(
                f"expires ({expires}) is not exactly asserted+365d ({asserted + timedelta(days=365)}) "
                "- expiry-not-derived"
            )
    except ValueError:
        problems.append("asserted/expires must be YYYY-MM-DD dates")

    basis = entry.get("basis", "")
    if not basis.startswith("https://"):
        problems.append(f"basis {basis!r} must be https://")

    if not isinstance(entry.get("rev"), int) or entry.get("rev", 0) < 1:
        problems.append("rev must be a positive integer")

    for keypath in _find_forbidden_keys(entry, ENTRY_FORBIDDEN_KEYS):
        problems.append(f"forbidden key at {keypath!r} - a grade you can compute is a grade you can game")

    return problems


def _check_citation(citation: dict) -> list:
    problems = []
    for keypath in _find_forbidden_keys(citation, CITATION_FORBIDDEN_KEYS):
        problems.append(f"citation carries definition text at {keypath!r} - a citation links, it never restates")
    return problems


def validate(fragment: dict) -> list:
    """Returns a list of human-readable problems; an empty list means the
    fragment passes every documented rule this proxy knows about. Never
    raises on a malformed fragment."""
    if not isinstance(fragment, dict):
        return [f"fragment must be an object, got {type(fragment).__name__}"]

    problems = []
    if fragment.get("contract") != "defined/1":
        problems.append(f"contract must be 'defined/1', got {fragment.get('contract')!r}")

    authority = fragment.get("authority", "")
    if not _ID_RE.match(authority):
        problems.append(f"top-level authority {authority!r} does not look like org/person/agent + a slug")

    entries = fragment.get("entries")
    if not isinstance(entries, list) or not entries:
        problems.append("entries must be a non-empty array")
        entries = []

    seen_ids = []
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append(f"entry is not an object: {entry!r}")
            continue
        for problem in _check_entry(entry):
            problems.append(f"{entry.get('id', '?')}: {problem}")
        seen_ids.append(entry.get("id"))
        if entry.get("authority") != authority:
            problems.append(f"{entry.get('id', '?')}: authority differs from the fragment's top-level authority")

    if len(seen_ids) != len(set(seen_ids)):
        problems.append("duplicate entry id in this fragment")

    for i, citation in enumerate(fragment.get("citations", [])):
        for problem in _check_citation(citation):
            problems.append(f"citations[{i}]: {problem}")

    return problems
