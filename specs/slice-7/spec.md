# Slice 7 — the AAO manifest + a local check

## Goal

Add the `solwayholdings.aao.json` manifest and a pure-Python
`validate_manifest(dict)` that checks it against the AAO rules we care about.
The test suite then confirms the real manifest passes — "validated", locally,
no external tools.

## Included

- `solwayholdings.aao.json` — the manifest, at the repo root
- `analystos/aao/validate.py` — `validate_manifest(manifest)` -> list of
  problem strings (`[]` = OK), plus `load_manifest(path)`
- `analystos/aao/__init__.py` — mark the new folder
- `tests/test_aao_validate.py` — tests, one per "Done when" check

## Done when

1. `validate_manifest(load_manifest("solwayholdings.aao.json"))` returns `[]`.
2. A well-formed manifest returns `[]`.
3. A missing `accountableTo` is flagged.
4. A placeholder `accountableTo` (`"TODO"`) is flagged.
5. A bad `slug` (spaces / capitals / symbols) is flagged.
6. A role name that references a model vendor (`"claude-agent"`) is flagged.
7. A `humanApprovalAtOrAbove` outside `{NONE, LOW, MEDIUM, HIGH}` is flagged.
8. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- The real `@flashyos/aao` validator (npm / Node) — our check is a stand-in.
- Registering on the mesh, or anything over the network.
- A GitHub Actions CI service — the check runs in the local test suite for now.
- The exact canonical list of ten `family` values — we just require a
  lowercase word.
