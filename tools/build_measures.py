"""Wrap the existing `python3 -m analystos.api_v1 measures` output (Slice 61) in a
measures/1 envelope - window, computed timestamp, charter URL - for FlashyOS to pull
(Slice 96).

    python3 tools/build_measures.py                      # writes drafts/measures.json
    python3 tools/build_measures.py --check               # exit 1 if stale, change nothing
    python3 tools/build_measures.py --store-dir PATH       # read a real audit.jsonl
    python3 tools/build_measures.py --since ISO --until ISO

This tool does no arithmetic of its own: `analystos.api_v1.audit.measures()` already
computes exactly these three numbers from the audit log (numerator, denominator,
share - `None` when the denominator is zero, never a made-up 100%), and already has
its own tests in tests/test_api_v1.py::MeasuresTest. What was missing was a document
shape FlashyOS can pull: a stated window (never derived from the clock at read time),
the charter's own measure sentence (not a second hand-typed copy of it), and a path.

With no --store-dir, the output is honestly empty: every denominator is 0 and every
value is null, because there is nothing to compute from. That is not a placeholder
bug - Slice 84 recorded that the audit log is dormant in production until
ANALYSTOS_STORE_DIR is a persistent volume, so a live deployment's real answer today
is "no data yet", and this tool says exactly that rather than inventing a number.

Written to drafts/, not site/.well-known/, for the same reason as
drafts/flashyos-charter.team.json (see drafts/README.md): Flashy's 21 Nov reply
committed to *pull* a measures document but named neither its path nor its format,
so this is a proposal to validate and discuss - even though its content can never
assert anything false, every number being computed, or honestly null.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analystos.api_v1.audit import measures as compute_role_measures  # noqa: E402
from analystos.api_v1.store import FileStore  # noqa: E402

CHARTER_PATH = ROOT / "site" / ".well-known" / "flashyos-charter.json"
OUTPUT_PATH = ROOT / "drafts" / "measures.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_measures_document(charter: dict, audit_events: list, window: tuple, computed: str) -> dict:
    """``window`` is ``(since, until)``, both stated verbatim in the output."""
    since, until = window
    by_role = compute_role_measures(audit_events)  # {role: {numerator, denominator, share, measure}}

    roles_out = []
    for role in charter.get("roles", []):
        name = role["name"]
        entry = {"role": name, "measure": role["measure"], "window": f"{since}/{until}"}  # charter's own sentence
        computed_role = by_role.get(name)
        if computed_role is None:
            entry.update({"numerator": None, "denominator": None, "value": None, "instrumented": False})
        else:
            entry.update({
                "numerator": computed_role["numerator"],
                "denominator": computed_role["denominator"],
                "value": computed_role["share"],
                "instrumented": True,
            })
        roles_out.append(entry)

    return {
        "measures": "1",
        "org": charter["slug"],
        "charter": f"https://{charter['slug']}.dev/.well-known/flashyos-charter.json",
        "computed": computed,
        "window": f"{since}/{until}",
        "roles": roles_out,
    }


def build(store_dir: str | None, since: str | None, until: str | None, computed: str) -> dict:
    charter = json.loads(CHARTER_PATH.read_text())
    events = FileStore(store_dir).read_audit() if store_dir else []

    event_timestamps = [e["ts"] for e in events if "ts" in e]
    since = since or (min(event_timestamps) if event_timestamps else computed)
    until = until or computed

    return build_measures_document(charter, events, (since, until), computed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--store-dir", default=None)
    parser.add_argument("--since", default=None)
    parser.add_argument("--until", default=None)
    args = parser.parse_args(argv)

    if args.check:
        # "computed" and an open-ended "window" are, by design, "now" at build
        # time, so a fresh run can never byte-match an earlier one on those
        # two fields alone. --check instead replays the SAME window and the
        # SAME store and asks whether the charter and the data still produce
        # what is on disk - catching a charter edited since, or a store that
        # changed under it, without ever failing merely because time passed.
        if not OUTPUT_PATH.exists():
            print("build_measures.py: drafts/measures.json does not exist - run without --check")
            return 1
        on_disk = json.loads(OUTPUT_PATH.read_text())
        since_disk, until_disk = on_disk["window"].split("/", 1)
        replayed = build(args.store_dir, since_disk, until_disk, on_disk["computed"])
        if replayed != on_disk:
            print("build_measures.py: drafts/measures.json is STALE - run without --check")
            return 1
        print("build_measures.py: drafts/measures.json matches the charter and the given store")
        return 0

    computed_doc = build(args.store_dir, args.since, args.until, _now_iso())
    OUTPUT_PATH.write_text(json.dumps(computed_doc, indent=2) + "\n")
    print(f"build_measures.py: wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
