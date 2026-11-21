"""Derive site/.well-known/flashyos.json's capabilities from the served charter (Slice 94).

    python3 tools/build_flashyos_handshake.py           # regenerate
    python3 tools/build_flashyos_handshake.py --check   # exit 1 if stale, change nothing

Why this exists: on 2026-11-21 the Flashy estate's own reply resolved a question this
repo's docs/mesh-identity.md had left open. Their `auditProperty` grades a handshake
with no `capabilities` array at level 1 ("declares nothing it can do"), which looked
like a conflict with docs/mesh-identity.md's rule of withholding capabilities until an
endpoint is deployed and a token exists. It is not a conflict: a charter *role name* is
a governance fact already published in the charter, not an endpoint claim. Declaring
`["analysis", "verification", "evidence"]` restates the charter and promises nothing
callable; it took their own `auditProperty` from level 1 to level 2 with zero issues
when they ran it (see docs/decisions.md, Slice 94).

The *discovery slugs* each role's `x-capability` would carry (`document-analysis`,
`figure-verification`, `sealed-report`, ...) are a different thing - those really do
claim something is callable - and docs/mesh-identity.md's rule still applies to them:
they are added only once the endpoint is deployed and an agent token exists. This tool
never writes them.

Two files, so this never drifts: the charter is the only thing anyone hand-edits;
the handshake's `capabilities` array is always exactly the charter's role names, sorted,
derived here. A hand-typed `capabilities` array in flashyos.json would be a second copy
of a fact the charter already states, and the two would eventually disagree.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTER_PATH = ROOT / "site" / ".well-known" / "flashyos-charter.json"
HANDSHAKE_PATH = ROOT / "site" / ".well-known" / "flashyos.json"


def derive_capabilities(charter: dict) -> list:
    """Role names only - never x-capability slugs. See module docstring."""
    names = [role["name"] for role in charter.get("roles", [])]
    return sorted(set(names))


def build_handshake(charter_path: Path = CHARTER_PATH, existing_path: Path = HANDSHAKE_PATH) -> dict:
    charter = json.loads(charter_path.read_text())
    existing = json.loads(existing_path.read_text()) if existing_path.exists() else {}

    handshake = {
        "mesh": "flashyos/1",
        "org": {
            "slug": charter["slug"],
            "name": charter["name"],
            "profile": existing.get("org", {}).get("profile", "https://analystos.dev"),
        },
        "capabilities": derive_capabilities(charter),
    }
    # Carry forward any field this tool does not itself derive (e.g. "join"),
    # so a human can add one by hand without this tool deleting it.
    for key, value in existing.items():
        if key not in handshake:
            handshake[key] = value
    return handshake


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    check = "--check" in args

    computed = build_handshake()
    text = json.dumps(computed, indent=2) + "\n"

    current = HANDSHAKE_PATH.read_text() if HANDSHAKE_PATH.exists() else None
    if current == text:
        print("build_flashyos_handshake.py: flashyos.json capabilities match the charter")
        return 0
    if check:
        print(
            "build_flashyos_handshake.py: flashyos.json is STALE - "
            "run without --check to regenerate"
        )
        return 1

    HANDSHAKE_PATH.write_text(text)
    print("build_flashyos_handshake.py: flashyos.json regenerated from the charter")
    return 0


if __name__ == "__main__":
    sys.exit(main())
