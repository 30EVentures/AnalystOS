# Slice 67 - a live-suite PASS means the report was good, not that nothing raised (roadmap Q4)

## Goal

Audit finding 8: `live_tests/run_live_tests.py` printed PASS whenever
`build_report` returned without raising - including when the written report
failed both quality gates and the run silently fell back to the template
report or the plain list. A live run that degraded looked identical to one that
did not, so the suite could not detect the very regression it exists to catch.

Each document now declares what a good run looks like, and a pure, offline
`evaluate(expectation, trace)` grades the run's trace into one of three outcomes:

- **PASS** - the expected tier, at least the minimum verified facts, and the
  sealed report re-verifies end to end (`content_checked`) with its own text;
- **DEGRADED** - it worked and every figure is verified, but it fell to a lower
  tier than expected (the reason is printed). Not a crash, not a pass;
- **FAIL** - it raised, produced fewer verified facts than the minimum, or its
  seal does not verify.

Exit status is non-zero on any FAIL or a budget stop; `--strict` also fails on
DEGRADED. The summary lists the three outcomes separately. The minimum-fact
thresholds are deliberately conservative starting points to be tuned from the
first real run (stated in `live_tests/README.md`).

## Not in this slice

- A paid run (needs your key and spend). Everything here is proved with synthetic
  traces; the real-API proof stays a live run.
- Latency and per-document cost statistics beyond what the suite already prints.

## Done when

1. `evaluate` returns PASS for a good trace of each expected tier, DEGRADED for a
   fallback, and FAIL for too few facts, a bad seal, and an error.
2. The table path expects tier `table` and is never asked for a seal.
3. `--strict` and the exit codes behave as described.
4. The README says what each outcome means.
5. Full suite OK (no network, no cost).
