"""Build a measures/1 document from the charter and a store's audit log (Slice 96).

    python3 tools/build_measures.py                      # writes drafts/measures.json
    python3 tools/build_measures.py --check               # exit 1 if stale, change nothing
    python3 tools/build_measures.py --store-dir PATH       # read a real audit.jsonl
    python3 tools/build_measures.py --since ISO --until ISO

With no --store-dir, the output is honestly empty: every denominator is 0 and
every value is null, because there is nothing to compute from. That is not a
placeholder bug - Slice 84 recorded that the audit log is dormant in
production until ANALYSTOS_STORE_DIR is a persistent volume, so a live
deployment's real answer is "no data yet", and this tool says exactly that
rather than inventing a number.

Written to drafts/, not site/.well-known/, for the same reason as
drafts/flashyos-charter.team.json (see drafts/README.md): Flashy's 21 Nov
reply committed to *pull* a measures document but named neither its path nor
its format, so this is a proposal to validate and discuss, not something to
publish before that is settled - even though its content can never assert
anything false (every number is computed, or honestly null).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analystos.api_v1.measures import compute_measures  # noqa: E402
from analystos.api_v1.store import FileStore  # noqa: E402

CHARTER_PATH = ROOT / "site" / ".well-known" / "flashyos-charter.json"
OUTPUT_PATH = ROOT / "drafts" / "measures.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(store_dir: str | None, since: str | None, until: str | None, computed: str) -> dict:
    charter = json.loads(CHARTER_PATH.read_text())
    events = FileStore(store_dir).read_audit() if store_dir else []

    event_timestamps = [e["ts"] for e in events if "ts" in e]
    since = since or (min(event_timestamps) if event_timestamps else computed)
    until = until or computed

    return compute_measures(charter, events, (since, until), computed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--store-dir", default=None)
    parser.add_argument("--since", default=None)
    parser.add_argument("--until", default=None)
    args = parser.parse_args(argv)

    if args.check:
        # "computed" and the open end of "window" are, by design, "now" at
        # build time - a fresh run can never byte-match an earlier one on
        # those two fields alone. So --check instead asks a narrower, real
        # question: replaying the SAME window and the SAME store, does the
        # charter (role names, measure sentences) and the data (audit
        # events) still produce the numbers on disk? That catches a charter
        # edited after the file was built, or a store that changed under it,
        # without ever failing merely because time passed.
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
