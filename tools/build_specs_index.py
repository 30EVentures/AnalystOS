"""Regenerate ``specs/README.md`` from the ``specs/slice-N/spec.md`` files.

    python3 tools/build_specs_index.py           # write
    python3 tools/build_specs_index.py --check   # exit 1 if stale

A slice with a spec gets a linked row (title from the spec's first line). The
slices that have no spec are listed in ``GAPS`` with where the work is actually
recorded; ``tests/test_specs_index.py`` fails if a gap appears that is not here.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs"

GAPS = {
    14: ("(no slice 14 - the roadmap goes from Slice 13 to Slice 15; an empty folder existed locally and was never in git)", "none"),
    35: ("L2 data for the v4 report: computed arithmetic and event milestones (commit `149ca4d`)", "none - see `docs/decisions.md` and the commit"),
    36: ("the v4 report renderer, all 8 reference patterns (commit `e3bae95`)", "none - see the commit"),
    37: ("Download PDF button via the browser's print dialog, on every report (commit `6c84b9d`)", "none - see the commit"),
    38: ("Gate 1 correctness checks and Gate 2 blind language pass (commits `815c6e6`, `c74f384`)", "none - `docs/decisions.md` 2026-09-11 \"Two mandatory quality gates\""),
    39: ("growth_percent operand order made order-independent (commit `0ce4908`)", "none - `docs/decisions.md` 2026-09-11"),
}

HEAD = '''# Specs

One folder per slice: `specs/slice-N/spec.md` holds the goal, what is and is not
included, and the "Done when" checks, written before the code. This index lists
every slice number so a gap is visible rather than silent. Regenerate it with
`python3 tools/build_specs_index.py`.

**Known gaps.** Slices 35-39 were built without a spec of their own (the work is
recorded in git and in `docs/decisions.md`; see their rows). There is no Slice 14.
A test (`tests/test_specs_index.py`) keeps this list truthful: every existing
spec folder must appear below, and every slice without one must be marked.

| Slice | What | Spec |
|---|---|---|
'''


def build():
    numbers = sorted(int(p.parent.name.split("-")[1]) for p in SPECS.glob("slice-*/spec.md"))
    rows = {}
    for n in numbers:
        first = (SPECS / f"slice-{n}" / "spec.md").read_text(encoding="utf-8").splitlines()[0].strip()
        title = re.sub(r"^#\s*Slice\s*\d+\s*[—\-–:]\s*", "", first)
        rows[n] = f"| {n} | {title} | [spec](slice-{n}/spec.md) |"
    for n in range(1, max(numbers) + 1):
        if n not in rows:
            what, where = GAPS.get(n, ("(unrecorded gap)", "none"))
            rows[n] = f"| {n} | {what} | {where} |"
    return HEAD + "\n".join(rows[n] for n in sorted(rows)) + "\n"


def main(argv=None):
    check = "--check" in (sys.argv[1:] if argv is None else argv)
    text, path = build(), SPECS / "README.md"
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if check:
        print("specs index is up to date" if current == text else "specs/README.md is stale")
        return 0 if current == text else 1
    path.write_text(text, encoding="utf-8")
    print("wrote specs/README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
