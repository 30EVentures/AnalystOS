#!/usr/bin/env python3
"""Declare capabilities or offers on the live FlashyOS org, using a join-grant
token (Slice 102). NOT RUN BY THIS SESSION - no valid token exists here, and
this is an outward action that needs the owner's explicit yes regardless.
See ops/README.md.

    python3 ops/flashy_declare.py capabilities analysis evidence verification \
        --org-id cmtkurcbs00je12tigb1rc6t1 --agent-name analystos-agent \
        --token "$FLASHY_JOIN_GRANT_TOKEN"            # prints the request, does nothing

    ... --execute                                      # actually sends it (needs --execute AND a real token)

Request shapes, taken from the published @flashyos/agent@0.21.0 client
(`declareCapabilities` and `declareOffers`), after the first live call on
2026-11-26 answered 400 "capability and description are required" to the shape
Flashy's 21 Nov reply had described ({"capabilities": [...]}):

  capabilities: one request per capability,
      POST /api/v1/orgs/{orgId}/agents/{agentName}/capabilities
      body {"capability": "<slug>", "description": "<text>"}
      The description is the purpose of the charter role that answers for the
      capability (as the client's declareFromCharter does), or --description.
  offers: one request for the organisation, replacing its whole list,
      POST /api/v1/orgs/{orgId}/offers   body {"offers": [...]}

Header x-join-grant on both. A 400 is a validation refusal: nothing is written.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

try:  # run as `python3 ops/<script>.py`, or imported as `ops.<script>` by the tests
    from mesh_ids import GRANT_STATUS, agent_name_problem, capability_descriptions, org_id_problem, value_problems
except ImportError:
    from ops.mesh_ids import GRANT_STATUS, agent_name_problem, capability_descriptions, org_id_problem, value_problems

API_BASE = "https://api.flashyos.com"


def build_requests(kind: str, org_id: str, agent_name: str, values: list, token: str,
                   descriptions: dict = None) -> list:
    """Every request a declaration needs, as {method, url, headers (token
    redacted), body}. Never raises on bad input; validation happens in main()."""
    headers = {"x-join-grant": "<redacted, " + str(len(token)) + " characters>", "content-type": "application/json"}
    if kind == "offers":
        return [{"method": "POST", "url": f"{API_BASE}/api/v1/orgs/{org_id}/offers",
                 "headers": headers, "body": {"offers": sorted(set(values))}}]
    descriptions = descriptions or {}
    return [{"method": "POST",
             "url": f"{API_BASE}/api/v1/orgs/{org_id}/agents/{agent_name}/capabilities",
             "headers": dict(headers),
             "body": {"capability": value, "description": (descriptions.get(value) or value).strip()}}
            for value in sorted(set(values))]


def send_request(request: dict, token: str) -> dict:
    """The only function that touches the network. Never called unless
    --execute is passed; see main(). Raises urllib.error.HTTPError on a
    non-2xx response rather than swallowing it."""
    body = json.dumps(request["body"]).encode("utf-8")
    req = urllib.request.Request(
        request["url"], data=body, method=request["method"],
        headers={"x-join-grant": token, "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return {"status": resp.status, "body": json.loads(resp.read().decode("utf-8"))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=["capabilities", "offers"])
    parser.add_argument("values", nargs="+", help="e.g. analysis evidence verification")
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--agent-name", required=True, help="the role's agent; unused for offers, which are org-level")
    parser.add_argument("--description", help="override the charter role's purpose as the description")
    parser.add_argument("--token", default=os.environ.get("FLASHY_JOIN_GRANT_TOKEN"), help="or set FLASHY_JOIN_GRANT_TOKEN")
    parser.add_argument("--execute", action="store_true", help="actually send it; default is to print and stop")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.token:
        print("no token given (--token or FLASHY_JOIN_GRANT_TOKEN) - cannot even build a redacted preview meaningfully")
        return 2

    problem = org_id_problem(args.org_id) or agent_name_problem(args.agent_name)
    if problem:
        print(f"refused: {problem}")
        return 2
    problems = value_problems(args.kind, args.values)
    if problems:
        print("refused - nothing was built or sent:")
        for p in problems:
            print(f"  - {p}")
        return 2

    descriptions = capability_descriptions()
    if args.description:
        descriptions = {value: args.description for value in args.values}
    requests = build_requests(args.kind, args.org_id, args.agent_name, args.values, args.token, descriptions)
    print(json.dumps(requests, indent=2))

    if not args.execute:
        print("\n(dry run - pass --execute to actually send this)")
        if args.kind == "capabilities":
            print("(a declared capability cannot be withdrawn yet: check every spelling above first)")
        return 0

    print("\nSending for real, one at a time, stopping at the first refusal...")
    for request in requests:
        label = request["body"].get("capability") or "offers"
        try:
            result = send_request(request, args.token)
        except urllib.error.HTTPError as exc:
            print(f"{label}: HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}")
            if exc.code in GRANT_STATUS:
                print(f"  meaning: {GRANT_STATUS[exc.code]}")
            return 1
        print(f"{label}: HTTP {result['status']} {json.dumps(result['body'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
