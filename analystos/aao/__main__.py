"""``python3 -m analystos.aao <charter.json | ->`` - check a charter, print JSON.

Exit code: 0 valid (warnings allowed), 1 invalid, 2 unreadable input.
"""

import json
import sys
from pathlib import Path

from analystos.aao.validate import (
    SCHEMA_RETRIEVED, SCHEMA_SHA256, SCHEMA_SOURCE, ERROR, WARNING, validate_charter,
)


def main(argv=None, stdin=None, stdout=None):
    argv = sys.argv[1:] if argv is None else argv
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if len(argv) != 1:
        stdout.write(json.dumps({"error": "usage: python3 -m analystos.aao <charter.json | ->"}) + "\n")
        return 2
    try:
        text = stdin.read() if argv[0] == "-" else Path(argv[0]).read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, ValueError) as exc:
        stdout.write(json.dumps({"error": f"could not read a JSON document: {exc}"}) + "\n")
        return 2
    problems = validate_charter(doc)
    errs = [p.to_dict() for p in problems if p.level == ERROR]
    warns = [p.to_dict() for p in problems if p.level == WARNING]
    stdout.write(json.dumps({
        "valid": not errs,
        "errors": errs,
        "warnings": warns,
        "schema": {"source": SCHEMA_SOURCE, "retrieved": SCHEMA_RETRIEVED, "sha256": SCHEMA_SHA256},
        "note": "AnalystOS's own checker, not FlashyOS's official validator; codes are aao.* (ours).",
    }, indent=2) + "\n")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
