#!/usr/bin/env python3
"""Log a consequential decision to FlashyOS's governance feed (Slice 104).
NOT RUN BY THIS SESSION against any real action - this is an outward action
that needs the owner's explicit yes each time, regardless of how confirmed
the endpoint is. See ops/README.md.

    python3 ops/flashy_decide.py "deploy the seven-role charter" --tier 2 \
        --org-id analystos --agent-name analystos-agent \
        --token "$FLASHYOS_AGENT_TOKEN"        # prints the request, sends nothing

    ... --execute                                # actually sends it (needs --execute AND a real token)

Endpoint confirmed by reading @flashyos/agent@0.21.0's own published source
(the npm tarball's dist/chunk-*.mjs, not the README's prose alone, and not
guessed): POST /api/v1/orgs/{orgId}/decisions, body
{orgId, token, agentName, summary, impact}. LOW impact clears immediately
(AUTO_APPROVED); MEDIUM and above sit PENDING until a human with OWNER or
ADMIN role on the org resolves it in the dashboard.

As the package's own docs say plainly: this RECORDS the decision - it does
not block anything. v1 is visibility and an audit trail, not enforcement
(their docs point at docs/roadmap.md Phase 2.75 for that). A caller that
wants a hard gate has to check the response and wait itself; this script
does not do that for you.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.flashyos.com"

TIER_TO_IMPACT = {1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}
STATUS_TO_STATE = {
    "AUTO_APPROVED": "auto",
    "PENDING": "pending",
    "APPROVED": "reviewed",
    "REJECTED": "reviewed",
}


def build_request(org_id: str, agent_name: str, action: str, impact: str, owner: str, token: str) -> dict:
    """Returns {method, url, headers (unused by this endpoint - credentials
    travel in the body, matching the SDK's agent-token path), body (token
    redacted)} - never raises on bad input; validation happens in main() so
    this stays testable without needing a real token or network access."""
    summary = f"{action} (owner: {owner})" if owner else action
    return {
        "method": "POST",
        "url": f"{API_BASE}/api/v1/orgs/{org_id}/decisions",
        "body": {
            "orgId": org_id,
            "token": "<redacted, " + str(len(token)) + " characters>",
            "agentName": agent_name,
            "summary": summary,
            "impact": impact,
        },
    }


def send_request(request: dict, token: str) -> dict:
    """The only function that touches the network. Never called unless
    --execute is passed; see main(). Raises urllib.error.HTTPError on a
    non-2xx response rather than swallowing it - this script surfaces
    failure, it does not retry or guess."""
    body = dict(request["body"])
    body["token"] = token
    req = urllib.request.Request(
        request["url"], data=json.dumps(body).encode("utf-8"), method=request["method"],
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return {"status": resp.status, "body": json.loads(resp.read().decode("utf-8"))}


def parse_state(response_body: dict) -> dict:
    """Mirrors @flashyos/agent@0.21.0's own requestApproval() parsing exactly,
    so a caller reading this script's output gets the same {id, state, status,
    recorded} shape the SDK would have returned - never a made-up 'auto' for
    a response the server didn't actually send."""
    decision = (response_body or {}).get("decision") or {}
    if not decision.get("id") or not decision.get("status"):
        return {"id": None, "state": "pending", "status": None, "recorded": False}
    return {
        "id": decision["id"],
        "state": STATUS_TO_STATE.get(decision["status"], "pending"),
        "status": decision["status"],
        "recorded": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", help="e.g. 'deploy the seven-role charter'")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], default=2,
                         help="1 LOW (auto-approves) .. 4 CRITICAL; default 2 MEDIUM")
    parser.add_argument("--owner", default="", help="e.g. @mara - passed through verbatim, not interpreted here")
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--agent-name", required=True)
    parser.add_argument("--token", default=os.environ.get("FLASHYOS_AGENT_TOKEN"), help="or set FLASHYOS_AGENT_TOKEN")
    parser.add_argument("--execute", action="store_true", help="actually send it; default is to print and stop")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.token:
        print("no token given (--token or FLASHYOS_AGENT_TOKEN) - cannot even build a redacted preview meaningfully")
        return 2

    impact = TIER_TO_IMPACT[args.tier]
    request = build_request(args.org_id, args.agent_name, args.action, impact, args.owner, args.token)
    print(json.dumps(request, indent=2))

    if not args.execute:
        print("\n(dry run - pass --execute to actually send this)")
        print("(this only RECORDS a decision on FlashyOS's side - it does not block anything in AnalystOS)")
        return 0

    print("\nSending for real...")
    try:
        result = send_request(request, args.token)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}")
        return 1
    state = parse_state(result.get("body", {}))
    print(json.dumps({"response": result, "state": state}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
