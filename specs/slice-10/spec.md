# Slice 10 — write the section to a file automatically

## Goal

Running the pipeline writes `<job-dir>/section.md` alongside printing it, so
an analyst always ends up with a file to open and send.

## Included

- `analystos/pipeline.py` — `main()` writes `<job-dir>/section.md`. The pure
  `run_job` is unchanged: it still just returns a string and writes nothing.
- `tests/test_pipeline.py` — new tests for the file-writing

## Done when

1. `python3 -m analystos <job-dir>` writes `<job-dir>/section.md` with exactly
   what it prints.
2. Re-running overwrites `section.md` with fresh content (no error).
3. `run_job(...)` on its own still writes no file — other callers and tests
   are unaffected.
4. The command still prints the section and exits 0.
5. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Choosing the filename or format — always `section.md`.
- HTML / PDF / docx export.
- Writing anywhere but the job folder, or a flag to suppress the file.
