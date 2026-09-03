# Slice 8 — glue: one command runs the whole rush

## Goal

One command that runs L0 store → L1 extract → L2 answer → L4 render for one
"job", end to end, plus a test that locks its output to a golden answer key.

## A "job"

A directory holding `job.json` (title, source filename, schema, and a list of
asks) and the source CSV. Each ask is
`{"text": "... {answer} ...", "where": [column, value], "select": column}`.

## Included

- `fixtures/golden/income_statement.csv` — a mini income statement
- `fixtures/golden/job.json` — the title, schema, and three asks
- `fixtures/golden/expected_section.md` — the answer key (generated once, then
  checked in)
- `analystos/pipeline.py` — `run_job(job_dir, evidence_dir=None)` → section string
- `analystos/__main__.py` — so `python3 -m analystos <job-dir>` prints the section
- `tests/test_pipeline.py` — tests, one per "Done when" check

## Done when

1. `run_job("fixtures/golden")` returns a string equal to `expected_section.md`.
2. The section's footnotes contain the real SHA-256 hash of
   `income_statement.csv`, computed independently in the test — proof the
   layers are actually wired, not faked.
3. Editing the CSV changes the output (the answer-key lock bites).
4. `python3 -m analystos fixtures/golden` prints that same section, exit code 0.
5. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- L3 (workspace) — there is none; the pipeline goes L0→L1→L2→L4.
- Wiring `extract_table` to read the source from L0 by hash — it reads by path
  and also stores; the hash link is a later refinement.
- Multiple sources / sections / schemas per job.
- Real document parsing (CSV only), natural-language asks, number formatting.
- Writing output to a file — `__main__` prints it; redirect with `>` for a file.
