#!/usr/bin/env python3
"""A guard over the served devlog/1 projection (Slice 106; demoted in Slice 131).

Since Slice 131 the privacy rules run BEFORE sealing, in tools/emit_record.mjs,
because cleaning a sealed entry afterwards broke its seal. This tool stays as a
second check: `--check` must report "already clean". Do not use it to fix a
shipped/1 file; re-emit instead.

    python3 tools/redact_served_devlog.py              # fixes in place
    python3 tools/redact_served_devlog.py --check       # exit 1 if it would change anything

The vendored tool faithfully reproduces real git history - including things
that should never be public, found live 2026-11-22 right after flipping
visibility: (1) old merge-commit titles from when this repo lived under the
owner's personal GitHub fork name, baked straight into the PR merge message
by GitHub itself; (2) this session's own commit trailers
(`Co-Authored-By: ... <noreply@anthropic.com>`, `Claude-Session: ...`) riding
along inside `detail`, since that field is the full git commit message body.

Two fixes, not one, because they are different problems:
- An entry whose title or detail names the owner personally is DROPPED
  outright - there is no version of that entry safe to publish.
- An entry that only carries a commit trailer has its `detail` truncated at
  the trailer, keeping the real, human-written part of the message. Every
  commit in this repository gets that trailer per the session's own
  attribution rule, so dropping those entries too would gut the public
  record for no privacy gain - the trailer is not personal, it just has no
  place in a human-readable changelog.

tests/test_site_identity.py's existing, generic scan over every served file
is the regression test for this - it is not duplicated here on purpose.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVED_PATH = ROOT / "site" / ".well-known" / "devlog.fragment.json"
# Slice 131: the sealed shipped/1 record is checked too (check only: never rewrite a sealed file).
SHIPLOG_PATH = ROOT / "site" / ".well-known" / "shiplog.json"

_PERSONAL_RE = re.compile(r"(?i)caleb|solway")
_TRAILER_RE = re.compile(r"\n\s*(Co-Authored-By|Claude-Session):.*", re.DOTALL)


def _is_personal(value) -> bool:
    if isinstance(value, str):
        return bool(_PERSONAL_RE.search(value))
    if isinstance(value, dict):
        return any(_is_personal(v) for v in value.values())
    if isinstance(value, list):
        return any(_is_personal(v) for v in value)
    return False


def _strip_trailer(text: str) -> str:
    return _TRAILER_RE.sub("", text).rstrip()


def clean(document: dict) -> dict:
    """Returns a new document: entries naming the owner personally dropped,
    every remaining entry's free-text fields stripped of commit trailers."""
    kept = []
    for entry in document.get("entries", []):
        if _is_personal(entry):
            continue
        entry = dict(entry)
        for field in ("title", "detail"):
            if isinstance(entry.get(field), str):
                entry[field] = _strip_trailer(entry[field])
        kept.append(entry)
    return {**document, "entries": kept}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if SHIPLOG_PATH.exists():
        sealed = json.loads(SHIPLOG_PATH.read_text(encoding="utf-8"))
        if clean(sealed) != sealed:
            print("redact_served_devlog.py: site/.well-known/shiplog.json names the owner or carries a commit "
                  "trailer - re-emit with tools/emit_record.mjs; never edit a sealed record")
            return 1
    if not SERVED_PATH.exists():
        print(f"{SERVED_PATH} does not exist - nothing to clean")
        return 0
    current = json.loads(SERVED_PATH.read_text(encoding="utf-8"))
    cleaned = clean(current)
    if cleaned == current:
        print("redact_served_devlog.py: already clean")
        return 0
    if "--check" in argv:
        dropped = len(current.get("entries", [])) - len(cleaned["entries"])
        print(f"redact_served_devlog.py: STALE - would drop {dropped} entr{'y' if dropped == 1 else 'ies'} "
              "and/or strip commit trailers - run without --check")
        return 1
    SERVED_PATH.write_text(json.dumps(cleaned, indent=2) + "\n", encoding="utf-8")
    dropped = len(current.get("entries", [])) - len(cleaned["entries"])
    print(f"redact_served_devlog.py: cleaned ({dropped} entr{'y' if dropped == 1 else 'ies'} dropped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
