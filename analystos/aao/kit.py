"""A ``conformance-kit`` line-protocol adapter for the AAO charter checker.

    npx @flashyos/conformance-kit <corpus.json> -- python3 -m analystos.aao.kit

Reads one JSON object per line on stdin ``{"id", "set", "input"}`` and writes
one per line on stdout ``{"id", "valid", "codes"}``. A document with only
warnings is valid (the kit's own README: refusing on a warning "confuses
advice with a rule"). A line that is not JSON, or has no id, is not answered.
"""

import json
import sys

from analystos.aao.validate import errors, validate_charter


def serve(lines, out):
    for line in lines:
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except ValueError:
            continue
        if not isinstance(case, dict) or "id" not in case:
            continue
        refusals = errors(validate_charter(case.get("input")))
        out.write(json.dumps({
            "id": case["id"],
            "valid": not refusals,
            "codes": sorted({p.code for p in refusals}),
        }) + "\n")
        out.flush()


if __name__ == "__main__":
    serve(sys.stdin, sys.stdout)
