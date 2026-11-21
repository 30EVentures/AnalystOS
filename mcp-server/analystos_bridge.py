"""The only Python this MCP server runs: a thin stdin/stdout bridge to the
real, already-tested verifier and acceptance check (Slice 100). The server
never reimplements verification logic in JavaScript - it calls this.

    python3 mcp-server/analystos_bridge.py verify      < {"bundle":...,"source_text":...}
    python3 mcp-server/analystos_bridge.py acceptance  < {"bundle":...,"source_text":...}
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analystos.l4.acceptance import document_analysis_acceptance  # noqa: E402
from analystos.l4.seal_verify import verify_bundle  # noqa: E402


def main(argv):
    if len(argv) != 2 or argv[1] not in ("verify", "acceptance"):
        print(json.dumps({"error": "usage: analystos_bridge.py verify|acceptance"}))
        return 2

    try:
        request = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid JSON on stdin: {exc}"}))
        return 2

    bundle = request.get("bundle")
    source_text = request.get("source_text")

    if argv[1] == "verify":
        print(json.dumps(verify_bundle(bundle, source_text=source_text)))
    else:
        print(json.dumps({"reasons": document_analysis_acceptance(bundle, source_text)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
