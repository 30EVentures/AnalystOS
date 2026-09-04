# AnalystOS — working notes for Claude

## What this is

AnalystOS: an operating system for the analyst's core loop. The layered
design is in `docs/architecture.md`; the plan is in `ROADMAP.md`.

## How to run

- This repo lives at the nested path `~/AnalystOS/AnalystOS`. `cd` there first.
- Language: Python 3 (developed on 3.14).
- Since Slice 16, AnalystOS has third-party dependencies (see `requirements.txt`
  and `docs/decisions.md`). Set up the virtual environment once:

  ```
  python3 -m venv .venv
  source .venv/bin/activate
  python3 -m pip install -r requirements.txt
  ```

  `source .venv/bin/activate` again at the start of every session before
  running tests or the app — a fresh terminal doesn't have it active.
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
- The `gh` CLI is not installed. After `git push`, open the pull request from
  the URL git prints, and merge it in the browser.
- Every analytical conclusion must eventually carry a citation to its source.
  Not relevant yet — no analysis code exists — but it is the core rule.

## Boundaries — ask before changing

- `fixtures/golden/` is the regression set. Add cases; do not edit existing ones.
- Dependencies are now allowed when a slice's explicit point is adding one
  (Slice 16 opened this). Pin an exact version in `requirements.txt` and
  record *why* in `docs/decisions.md` every time - don't add one quietly.

## Where things are

- `analystos/`            — the code, one folder per layer (`l0/`, `l1/`, …)
- `docs/architecture.md`  — the L0–L6 layer model
- `docs/decisions.md`     — dated log of choices and why
- `specs/<slice>/spec.md` — what each slice does and how it's checked
