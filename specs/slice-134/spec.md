# Slice 134 - the public record refreshes itself after every merge

Flashy's two-sided plan, C-REC-9. Owner's go-ahead, 2026-11-26.

## Goal

Slice 131 made the record correct, but only a person running the emitter adds
new merges to it: the served record stopped at Slice 130 while #110 and #112
merged after it. A record that lags is a record that says less than is true.

## Done when

1. `.github/workflows/record.yml` runs on every push to `main` (and by hand):
   full history (`fetch-depth: 0`), `node tools/emit_record.mjs` (append-only,
   privacy before sealing), `vendor-checkpoint.mjs emit`, then verifies every
   seal, every leaf and the redact guard before anything is committed.
2. When the record changed, it commits the four record files to `main` as
   `github-actions[bot]` with the exact subject `shipped/1: refresh the log`,
   which the vendored emitter treats as its own bookkeeping, so a refresh never
   appears in the record it refreshes. No skip marker: the refresh deploys.
3. If `main` moved on during the run, the rejected push stands down cleanly
   (the newer push's run refreshes the record); any other push failure fails
   the job.
4. An unchanged record is neither rebuilt nor committed: the checkpoint head
   carries its build time, so it is rebuilt only when the record changed
   (found in review; the first version committed and deployed on every push).
   Only `main` can run the job, so a manual run from another branch cannot push
   that branch's state to `main`.
5. Rehearsed locally on `origin/main` (679f478) before merge, the full sequence
   three times: the first run commits one refresh (47 entries, every seal and
   leaf verifies), the next two change nothing and commit nothing.
6. `tests/test_record_workflow.py` pins those properties; the freeze moves once
   with the reason logged; the full suite reports OK.

## Not in this slice

- Any change to the emitter, the record's content or its served paths.
- Branch protection: `main` is unprotected today, which is what lets the job
  push. If protection is added later, the job needs a rule that allows it.

## The decision this asks of the owner

This is the repository's first GitHub Actions workflow and the first automated
commit to `main`. The convention "never commit to `main` directly" applies to
people and sessions; merging this slice says it does not apply to this one job.
