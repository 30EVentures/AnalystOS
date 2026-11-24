#!/usr/bin/env python3
"""Build the homepage's sample deck (Slice 122).

    python3 tools/build_sample_deck.py          # write site/samples/sample-consulting-deck.pptx
    python3 tools/build_sample_deck.py --check  # exit 1 if the served file is not this build

The deck is the churn worked example (fixtures/consulting/churn-clinics, a synthetic
client) run through the real pipeline with a replayed answer: build_deck_spec verifies
every figure, render_deck draws it. No model call is made. --check compares the deck's
spec digest (recorded in the file) rather than its bytes, because a .pptx is a zip with
timestamps.
"""

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pptx import Presentation  # noqa: E402

from analystos.catalog import load_catalog  # noqa: E402
from analystos.l3 import engagement as eng  # noqa: E402
from analystos.l4 import deck  # noqa: E402
from analystos.packs import consulting  # noqa: E402
from analystos.packs.replay import ReplayClient  # noqa: E402

EXAMPLE = ROOT / "fixtures" / "consulting" / "churn-clinics"
OUT = ROOT / "site" / "samples" / "sample-consulting-deck.pptx"


def build():
    catalog = load_catalog()
    client = json.loads((EXAMPLE / "client.json").read_text())
    record = eng.new_engagement(engagement_id="5a" * 16, created="2026-11-23T00:00:00Z",
                                requested_by=client["requested_by"], problem=client["problem"],
                                roles=client["roles"], catalog=catalog)
    for qid, text in client["answers"].items():
        record = eng.answer(record, qid, text)
    record, problems = eng.accept(record, catalog)
    if problems:
        raise SystemExit("the sample engagement is not accepted: " + "; ".join(problems))
    response = json.loads((EXAMPLE / "response.json").read_text())
    spec = consulting.build_deck_spec(record, catalog, client=ReplayClient([response]))
    return spec, deck.render_deck(spec, record, catalog)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    spec, data = build()
    if "--check" in argv:
        if not OUT.is_file():
            print(f"{OUT.relative_to(ROOT)} is missing")
            return 1
        served = Presentation(str(OUT)).core_properties.keywords or ""
        if f"spec sha256 {deck.spec_digest(spec)}" not in served:
            print(f"{OUT.relative_to(ROOT)} is stale: run python3 tools/build_sample_deck.py")
            return 1
        print("sample deck is current")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(data)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(Presentation(io.BytesIO(data)).slides)} slides)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
