"""python3 -m analystos.catalog - validate the role catalog and print a summary.

Exit 0 and a JSON summary when valid; exit 1 and the list of problems otherwise."""

import json
import sys

from analystos.catalog import load_catalog, summary, validate_catalog


def main():
    try:
        doc = load_catalog()
    except (OSError, ValueError) as exc:
        print(f"role catalog unreadable: {exc}", file=sys.stderr)
        return 1
    problems = validate_catalog(doc)
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        return 1
    print(json.dumps(summary(doc), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
