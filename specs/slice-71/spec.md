# Slice 71 - cleanup pass (roadmap Q8)

## Goal

The queue was empty, so: dead code, tooling friction, and coverage gaps.

- Removed three unused imports (`csv` in `l1/document_text.py`, `re` in
  `l2/proofread.py`, `os` in `api_v1/__main__.py`) and one dead function
  (`analyze._parse_number`, superseded by `_parse_numbers`).
- `tools/refresh.py` regenerates every generated artifact (machine files, spec index,
  homepage counts) in the order that works, with a `--check` mode. Adding a slice used
  to mean remembering three commands and getting the order right; it hit this session
  five times.
- `aao.validate.is_valid` is documented in `docs/aao.md` but nothing exercised it:
  now tested.

## Not in this slice

- `solwayholdings.aao.json`: a Slice 7 sample manifest whose description claims an org
  that does not exist. It is only a test fixture, but deleting a checked-in root file is
  the owner's call (logged under "Blocked / needs input").

## Done when

1. No unused import or unreferenced module-level function remains in `analystos/`,
   `api/`, `tools/`, `live_tests/` (route handlers excepted) - checked by a test.
2. `tools/refresh.py` regenerates and `--check`s all three generators and detects a
   stale one.
3. `is_valid` has tests.
4. Full suite OK.
