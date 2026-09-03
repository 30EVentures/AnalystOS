# Slice 1 — Repo skeleton + test harness

## Goal

Create the project's folder structure and a test command that runs, so every
later slice has a place to live and a way to be checked.

## Included

- `README.md`, `CLAUDE.md`, `ROADMAP.md`
- `docs/architecture.md`, `docs/decisions.md`
- `specs/slice-1/spec.md` (this file)
- `fixtures/golden/README.md` (placeholder — real test data comes in a later slice)
- `tests/test_smoke.py` — one trivial passing test
- `.gitignore` for Python

## Done when

1. `python3 -m unittest discover -s tests -v` runs and reports one test, `OK`.
2. A fresh session can find and run that command using only `CLAUDE.md`.
3. The folders `docs/`, `specs/`, `fixtures/golden/`, `tests/` all exist in git.

## Not in this slice

- No L0 / L1 / L2 code. No document handling. No FlashyOS manifest.
- No virtual environment or third-party packages — added later, when a slice
  actually needs one.
