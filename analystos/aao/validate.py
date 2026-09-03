"""Local checks for an AAO manifest - pure Python, no network, no npm.

``validate_manifest(manifest)`` returns a list of problem strings; an empty
list means the manifest passes the checks we enforce here. It stands in for
the FlashyOS ``@flashyos/aao`` validator - close enough to catch obvious
mistakes while everything is still local.
"""

import json
import re
from pathlib import Path

_AAO_VERSION_RE = re.compile(r"^\d+\.\d+$")
_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,23}$")
# role name: lowercase, hyphen-separated, at most 3 words
_ROLE_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+){0,2}$")
_FAMILY_RE = re.compile(r"^[a-z]+$")

_APPROVAL_TIERS = {"NONE", "LOW", "MEDIUM", "HIGH"}
_VENDOR_WORDS = {"claude", "gpt", "openai", "anthropic", "gemini", "llama", "bard"}
_PLACEHOLDERS = {
    "", "todo", "tbd", "test", "test-agent", "someone", "placeholder", "changeme",
}

_TOP_KEYS = ("aao", "name", "slug", "description", "accountableTo", "roles")
_ROLE_KEYS = ("name", "purpose", "capabilities", "family", "humanApprovalAtOrAbove")


def load_manifest(path):
    """Load a manifest JSON file and return the dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_manifest(manifest):
    """Return a list of problems with ``manifest`` (a dict). Empty list == OK."""
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]

    problems = [f"missing top-level key: {k!r}" for k in _TOP_KEYS if k not in manifest]

    aao = manifest.get("aao")
    if "aao" in manifest and (not isinstance(aao, str) or not _AAO_VERSION_RE.match(aao)):
        problems.append(f'"aao" must look like "0.1"; got {aao!r}')

    slug = manifest.get("slug")
    if isinstance(slug, str) and not _SLUG_RE.match(slug):
        problems.append(
            f'"slug" must be lowercase a-z/0-9/-, 3-24 chars; got {slug!r}'
        )

    who = manifest.get("accountableTo")
    if not isinstance(who, str) or who.strip().lower() in _PLACEHOLDERS:
        problems.append('"accountableTo" must name a real person, never a placeholder')

    roles = manifest.get("roles")
    if not isinstance(roles, list) or not roles:
        problems.append('"roles" must be a non-empty list')
    else:
        for i, role in enumerate(roles):
            problems.extend(_role_problems(i, role))

    return problems


def _role_problems(i, role):
    where = f"roles[{i}]"
    if not isinstance(role, dict):
        return [f"{where} must be an object"]

    out = [f"{where}: missing key {k!r}" for k in _ROLE_KEYS if k not in role]

    name = role.get("name")
    if isinstance(name, str):
        if not _ROLE_NAME_RE.match(name) or not (3 <= len(name) <= 24):
            out.append(
                f"{where}: name {name!r} must be lowercase, hyphenated, <=3 words, 3-24 chars"
            )
        if set(name.split("-")) & _VENDOR_WORDS:
            out.append(f"{where}: name {name!r} must not reference a model vendor")
        if name.lower() in _PLACEHOLDERS:
            out.append(f"{where}: name {name!r} is a placeholder")

    caps = role.get("capabilities")
    if not isinstance(caps, list) or not caps:
        out.append(f"{where}: capabilities must be a non-empty list")

    tier = role.get("humanApprovalAtOrAbove")
    if tier not in _APPROVAL_TIERS:
        out.append(
            f"{where}: humanApprovalAtOrAbove must be one of "
            f"{sorted(_APPROVAL_TIERS)}; got {tier!r}"
        )

    fam = role.get("family")
    if not isinstance(fam, str) or not _FAMILY_RE.match(fam):
        out.append(f"{where}: family must be a lowercase word; got {fam!r}")

    return out
