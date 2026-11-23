"""python3 -m analystos.l3 new --role ROLE [--role ROLE ...] [--agent REF | --person REF]

Builds an engagement from the problem on stdin (Slice 109) and prints, as JSON,
the record, its open scoping questions, and what the acceptance gate says.
Exit 0 on success, 2 when the input is refused (the reason goes to stderr)."""

import argparse
import json
import sys
from datetime import datetime, timezone

from analystos.catalog import load_catalog
from analystos.l3.engagement import accept, new_engagement, new_id, open_questions


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m analystos.l3")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", help="start an engagement; the problem is read from stdin")
    new.add_argument("--role", action="append", required=True, help="a catalog role id (repeatable)")
    who = new.add_mutually_exclusive_group()
    who.add_argument("--agent", metavar="REF", help="the request comes from this agent")
    who.add_argument("--person", metavar="REF", help="the request comes from this person (default: cli)")
    args = parser.parse_args(argv)

    catalog = load_catalog()
    requested_by = {"kind": "agent", "ref": args.agent} if args.agent else {"kind": "person", "ref": args.person or "cli"}
    try:
        engagement = new_engagement(
            engagement_id=new_id(),
            created=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            requested_by=requested_by,
            problem=sys.stdin.read(),
            roles=args.role,
            catalog=catalog,
        )
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    _, refusals = accept(engagement, catalog)
    print(json.dumps({
        "engagement": engagement,
        "open_questions": open_questions(engagement),
        "accept": {"accepted": False, "problems": refusals},
    }, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
