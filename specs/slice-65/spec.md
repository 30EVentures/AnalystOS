# Slice 65 - an honest spec record (roadmap Q2)

## Goal

Audit finding 9: process claims outran the record. Slices 35-39 were built
without a spec folder, there is no Slice 14, and a code comment cited
`specs/slice-38/spec.md`, which does not exist.

- `specs/README.md` lists every slice number 1-65, links each spec that exists,
  and marks each gap with where the work is actually recorded (commit, decision
  log) instead of leaving it silent.
- The code comment in `analystos/pipeline.py` now points at the decision-log
  entry that does exist.
- `tests/test_specs_index.py` keeps it true: every existing spec folder is in
  the index; every slice number up to the highest is either a spec or a marked
  gap; and no source file, test or doc cites a spec path that does not exist.

## Not in this slice

- Writing specs retroactively for slices 35-39. They would be reconstructions, not
  the plan that preceded the code, which is what a spec is for.

## Done when

1. The index and the test exist and pass.
2. The dangling citation is gone, and the test would catch a new one.
3. Full suite OK.
