# AnalystOS — working notes for Claude

## What this is

AnalystOS: an operating system for the analyst's core loop. The layered
design is in `docs/architecture.md`; the plan is in `ROADMAP.md`.

## How to run

- Language: Python 3 (developed on 3.14). Standard library only for now.
- Tests:

  ```
  python3 -m unittest discover -s tests -v
  ```

  Must report `OK` before any commit.

## Conventions

- Work one slice at a time. Each slice gets a folder under `specs/` with a
  `spec.md` (goal + "Done when" checks) written *before* any code.
- Small commits on a branch; open a pull request for review. Never commit to
  `main` directly.
- Every analytical conclusion must eventually carry a citation to its source.
  Not relevant yet — no analysis code exists — but it is the core rule.

## Boundaries — ask before changing

- `fixtures/golden/` is the regression set. Add cases; do not edit existing ones.
- Do not add third-party packages or a virtual environment unless that is the
  explicit point of the slice.

## Where things are

- `docs/architecture.md`  — the L0–L6 layer model
- `docs/decisions.md`     — dated log of choices and why
- `specs/<slice>/spec.md` — what each slice does and how it's checked
