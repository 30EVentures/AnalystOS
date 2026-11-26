"""Guards shared by the ops scripts that write to the FlashyOS mesh (Slice 132).

Two mistakes Flashy's 2026-11-25 plan measured, each of which a script here
would otherwise have made on its first real run:

- The write routes take the organisation's id, never its slug. A request to
  /api/v1/orgs/analystos/... answers 404. The id is public (Flashy's public
  directory) and is not a secret.
- A declared capability cannot be withdrawn. Flashy has no delete route yet
  (their F-MESH-2 is built, not deployed), and DepositX's only capability is
  a misspelling the platform accepted and cannot remove. So a value is checked
  against what the served charter actually says before anything is sent.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTER_PATH = ROOT / "site" / ".well-known" / "flashyos-charter.json"

# org/analystos on api.flashyos.com, read from the public directory 2026-11-23.
ANALYSTOS_ORG_ID = "cmtkurcbs00je12tigb1rc6t1"

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_OFFERS = 20  # Flashy keeps at most 20 offers and drops the rest without notice


def _charter():
    return json.loads(CHARTER_PATH.read_text(encoding="utf-8"))


# FlashyOS organisation ids are cuids: lowercase, start with "c", about 25 characters.
ORG_ID_RE = re.compile(r"^c[a-z0-9]{20,32}$")


def org_id_problem(org_id: str):
    """None if `org_id` can be sent, else the reason it cannot. Only an id shaped
    like FlashyOS's is accepted, so a slug, a prefixed id ("org/analystos"), an
    empty value or anything carrying a path character is refused."""
    if not isinstance(org_id, str) or not ORG_ID_RE.match(org_id):
        return (f"{org_id!r} is not a FlashyOS organisation id; the write routes take the id, "
                f"never the slug (for analystos: {ANALYSTOS_ORG_ID}). A slug in the path answers 404.")
    return None


def agent_name_problem(name: str):
    """Agent names go into the URL path, so only a slug is accepted."""
    if not isinstance(name, str) or not SLUG_RE.match(name):
        return f"{name!r} is not a lowercase hyphenated agent name"
    return None


def charter_capabilities():
    """Every capability the served charter answers for: role names and each
    role's x-capability (a string or a list)."""
    found = set()
    for role in _charter().get("roles", []):
        found.add(role["name"])
        extra = role.get("x-capability", [])
        found.update([extra] if isinstance(extra, str) else extra)
    return found


def capability_descriptions():
    """{capability: purpose of the charter role that answers for it}. The published
    @flashyos/agent client describes a declared capability with its role's purpose."""
    out = {}
    for role in _charter().get("roles", []):
        extra = role.get("x-capability", [])
        for cap in [role["name"], *([extra] if isinstance(extra, str) else extra)]:
            out[cap] = role.get("purpose", "")
    return out


def value_problems(kind: str, values):
    """Reasons the values cannot be declared; an empty list means they can."""
    problems = []
    for value in values:
        if not SLUG_RE.match(value):
            problems.append(f"'{value}' is not a lowercase hyphenated slug")
    if kind == "capabilities":
        unknown = sorted(set(values) - charter_capabilities())
        if unknown:
            problems.append("not in the served charter (a typo would be permanent): " + ", ".join(unknown))
    if kind == "offers" and len(set(values)) > MAX_OFFERS:
        problems.append(f"{len(set(values))} offers; Flashy keeps {MAX_OFFERS} and silently drops the rest")
    return problems


# What each refusal code from the join-grant routes means (Flashy, 2026-11-25).
GRANT_STATUS = {
    401: "the grant is invalid or expired",
    403: "the grant is for another organisation, or lacks this scope",
    404: "wrong path: usually the slug was sent instead of the organisation id",
    501: "join grants are switched off on this deployment (Flashy's side)",
}
