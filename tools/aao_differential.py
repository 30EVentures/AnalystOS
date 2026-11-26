#!/usr/bin/env python3
"""Run FlashyOS's public AAO charter corpus against AnalystOS's checker (Slice 133,
Flashy plan C-MESH-9).

    python3 tools/aao_differential.py [corpus.json]

The corpus is FlashyOS's own (Apache-2.0), served at
https://flashyos.com/.well-known/conformance/aao-0.1.json and snapshotted in
conformance/flashyos-aao-0.1.json with its sha256 and retrieval date below, so the
comparison runs offline and a change on their side is a visible diff here.

Only the verdict (`valid`) is compared. FlashyOS's expected `codes` are its own
question ids and, for some cases, English sentences; AnalystOS's are stable rule
codes (`aao.*`). They name the same findings in two vocabularies, which is why a
shared corpus needs stable codes (Flashy's F-MESH-6). Each case's codes from both
sides are printed so a reader can match them by eye.

Exit 0 when every verdict agrees, 1 when any disagrees, 2 when the corpus is
unreadable or has no cases (a differential over nothing must not pass).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analystos.aao.validate import errors, validate_charter  # noqa: E402

CORPUS_PATH = ROOT / "conformance" / "flashyos-aao-0.1.json"
SNAPSHOT_SHA256 = "9bf33dc5e74d4dd5dbbc4e1f8216940b3ffaffb509be52ff11bc8ee92b97f1da"
SNAPSHOT_RETRIEVED = "2026-11-26"


def compare(corpus: dict):
    rows = []
    for case_set in corpus.get("sets", []):
        if case_set.get("kind") != "validate":
            continue
        for case in case_set.get("cases", []):
            found = errors(validate_charter(case.get("input"), questions=True))
            ours = {"valid": not found, "codes": [p.code for p in found]}
            rows.append({"id": case["id"], "expect": case["expect"], "ours": ours,
                         "agree": ours["valid"] == case["expect"].get("valid")})
    return rows


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else CORPUS_PATH
    try:
        corpus = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {path}: {exc}")
        return 2
    rows = compare(corpus)
    if not rows:
        print("no validate cases in the corpus: refusing to report agreement over nothing")
        return 2
    for row in rows:
        mark = "agree   " if row["agree"] else "DISAGREE"
        print(f"{mark} {row['id']}: theirs valid={row['expect'].get('valid')} {row['expect'].get('codes', [])} | "
              f"ours valid={row['ours']['valid']} {row['ours']['codes']}")
    agreed = sum(r["agree"] for r in rows)
    print(f"{agreed}/{len(rows)} verdicts agree")
    return 0 if agreed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
