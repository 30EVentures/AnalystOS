# Slice 9 — scaffold a job.json from a CSV

## Goal

Generate a ready-to-edit `job.json` (and job folder) from a CSV, so the only
manual step is tweaking the title and questions - nobody hand-writes JSON.

## Included

- `analystos/scaffold.py` — `scaffold(csv_path, dest_dir)` plus a
  `python3 -m analystos.scaffold` entry point
- `tests/test_scaffold.py` — tests, one per "Done when" check
- `.gitignore` — add `jobs/` (ad-hoc job folders with real data stay off GitHub)

## Done when

1. `scaffold(csv, dest)` creates `dest/` with a copy of the CSV and a `job.json`.
2. The generated schema marks all-numeric columns `"number"`, the rest `"text"`.
3. The generated `job.json` runs through `run_job` with no error and produces
   at least one footnoted finding.
4. Scaffolding into a folder that already exists → a clear error.
5. `python3 -m analystos.scaffold <csv> <dest>` returns exit 0 and prints the
   next command to run.
6. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Smart question generation — the example asks are simple placeholders to edit.
- Any format but CSV.
- Detecting dates / currencies — still just `number` / `text`.
- A GUI or interactive prompts — one command, arguments only.
