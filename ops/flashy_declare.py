#!/usr/bin/env python3
"""Declare capabilities or offers on the live FlashyOS org, using a join-grant
token (Slice 102). NOT RUN BY THIS SESSION - no valid token exists here, and
this is an outward action that needs the owner's explicit yes regardless.
See ops/README.md.

    python3 ops/flashy_declare.py capabilities analysis evidence verification \
        --org-id analystos --agent-name analystos-agent \
        --token "$FLASHY_JOIN_GRANT_TOKEN"            # prints the request, does nothing

    ... --execute                                      # actually sends it (needs --execute AND a real token)

Endpoint (confirmed, from Flashy's 21 Nov reply): POST
/api/v1/orgs/{orgId}/agents/{agentName}/capabilities, header x-join-grant,
body {"capabilities": [...]}. The parallel "offers" command below uses the
same path shape with /offers in place of /capabilities and the offers:declare
scope Flashy named - but they gave us the SCOPE NAME, never the exact PATH for
offers. Confirm that path with Flashy before using --execute on it; this
script will print exactly what it would send either way, so the confirmation
is one question, not a guess you act on blind.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.flashyos.com"


def build_request(kind: str, org_id: str, agent_name: str, values: list, token: str) -> dict:
    """Returns {method, url, headers (token redacted), body} - never raises
    on bad input; validation happens in main() so this stays testable
    without needing a real token or network access."""
    path = "capabilities" if kind == "capabilities" else "offers"
    return {
        "method": "POST",
        "url": f"{API_BASE}/api/v1/orgs/{org_id}/agents/{agent_name}/{path}",
        "headers": {"x-join-grant": "<redacted, " + str(len(token)) + " characters>", "content-type": "application/json"},
        "body": {kind: sorted(set(values))},
    }


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
    parser.add_argument("--agent-name", required=True)
    parser.add_argument("--token", default=os.environ.get("FLASHY_JOIN_GRANT_TOKEN"), help="or set FLASHY_JOIN_GRANT_TOKEN")
    parser.add_argument("--execute", action="store_true", help="actually send it; default is to print and stop")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.token:
        print("no token given (--token or FLASHY_JOIN_GRANT_TOKEN) - cannot even build a redacted preview meaningfully")
        return 2

    if args.kind == "offers":
        print("WARNING: the /offers path is this script's own guess by analogy with /capabilities,")
        print("not a path Flashy's 21 Nov reply actually gave. Confirm it with them before --execute.")
        print()

    request = build_request(args.kind, args.org_id, args.agent_name, args.values, args.token)
    print(json.dumps(request, indent=2))

    if not args.execute:
        print("\n(dry run - pass --execute to actually send this)")
        return 0

    print("\nSending for real...")
    try:
        result = send_request(request, args.token)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
