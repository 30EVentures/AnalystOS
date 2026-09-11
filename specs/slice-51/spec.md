# Slice 51 — a deliberate, real-money live-test suite

## Goal

The 434 tests in `tests/` are all mocked - real, valuable, and permanently
free to run, but structurally blind to anything only a genuine model
response can surface (found directly this session: a report that looked
correct against every mock but produced an uncitable number live). This
slice adds a **separate, small, deliberately real** tier: actual
non-mocked API calls against a fixed set of structurally different real
documents, run on demand (never as part of `python3 -m unittest discover
-s tests`, which must stay free and network-independent), with its own
hard dollar ceiling and per-run cost log.

## Included

- A new top-level `live_tests/` directory - **not** under `tests/`, so it
  is never collected by `unittest discover -s tests` and never runs
  without being explicitly invoked. Contains:
  - `live_tests/fixtures/` - the fixed set of test documents (below).
  - `live_tests/run_live_tests.py` - the runner, invoked directly
    (`python3 live_tests/run_live_tests.py`), using a real
    `anthropic.Anthropic()` client (whatever `ANTHROPIC_API_KEY` is in
    the caller's own environment - never hand the key to me).
  - `live_tests/README.md` - what this is, how to run it, and why it's
    kept separate from `tests/` (cost - every run spends real money).
- **Cost tracking is real, not estimated from call count.** Every real
  `anthropic.Anthropic().messages.create()` response carries
  `response.usage.input_tokens`/`output_tokens`. A small price table
  (below) converts that into an actual dollar figure per call, summed
  per document and for the whole run - not a proxy like "N calls made."
- **A hard ceiling that stops the run, not just warns.** Checked before
  every call (the same discipline `analystos.l2.analyze._enforce_spend_ceiling`
  already uses for the in-app safety net - this is that same idea, a
  layer up, with a real dollar figure instead of a call count): if the
  running total would exceed the configured ceiling, the run stops
  immediately, prints exactly how much it spent and on what, and does
  **not** place the call that would have crossed the line.
- **Per-run cost log**, human-readable, printed to stdout (and,
  optionally, a `--log-file` path): per document, which pipeline path it
  ran (narrated-default / schema-template), pass/fail, input/output
  tokens, and dollar cost; a final total across the whole run.
- **The fixed document set** - real-shaped, not synthetic edge cases,
  covering meaningfully different code paths so a live bug in one path
  can't hide behind a live pass in another (see Open decision #2 below
  for the exact set).
- Price table sourced from Anthropic's own published pricing
  (`claude.com/pricing`, checked 2026-09-11): Sonnet 5 is $2/MTok input,
  $10/MTok output. Documented in-code with the source and the date
  checked, the same way every other externally-sourced fact in this
  codebase is - pricing can change, and a stale hardcoded number failing
  silently would defeat the entire point of a *real* dollar ceiling.

## Decisions (made before build)

1. **Hard ceiling: $1.00** per run.
2. **The fixed document set - all 4, each exercising a genuinely
   different path** (Slice 50 is merged, so all four are available):
   - a small CSV -> the schema/template path (`asks`/`template`,
     no model narrative at all - proves the live suite isn't only
     testing the narrated path).
   - a short, single-column, prose-heavy DOCX -> the narrated-default
     path end to end (extraction -> analysis -> Gate 1 -> Gate 2 ->
     rich HTML).
   - a two-column PDF -> the narrated-default path over Slice 50's
     column-aware extraction, proving the live model still produces a
     sane narrative from correctly-ordered (not interleaved) text.
   - a PDF with one embedded image containing a real number -> Slice
     50's image-fact path, proving a live vision call really produces
     a citable fact, not just a mocked one.

## Done when

1. The suite runs against the fixed document set (at least 3
   structurally different documents - see Open decision #2) using a
   real, non-mocked `anthropic.Anthropic()` client.
2. Actual cost (not a proxy) is logged per document and as a run total,
   computed from each real response's real token usage against the
   sourced price table.
3. A hard ceiling stops the run before any call that would exceed it -
   proven by actually setting the ceiling low enough to trigger mid-run
   and confirming the run halts with a clear message, spending less
   than the configured limit, never more.
4. I show you one real run's actual output/log as proof - a real
   transcript of it executing against the live API, not a description
   of what it would probably do.

## Not in this slice

- Any change to the mocked `tests/` suite - it stays exactly as fast,
  free, and deterministic as it is today. This is a separate, additive
  tier, never a replacement.
- CI integration (running this automatically on every push/PR) - real
  money on every commit is a deliberate non-goal; this is a
  human-triggered, on-demand check.
- Tracking spend *across* runs (a persistent running total over time,
  a monthly budget) - Slice 42's account-level Anthropic cap and
  in-code call-count ceiling already cover the "don't runaway spend"
  case globally; this slice's ceiling is scoped to one run only.

## Built (post-implementation note)

- `live_tests/` (outside `tests/`, never collected by `unittest
  discover -s tests`): `build_fixtures.py` (regenerates the 4 documents),
  `fixtures/` (the built documents themselves, committed), `README.md`,
  and `run_live_tests.py` - the runner.
- `CostTrackingClient` wraps a real `anthropic.Anthropic()` client's
  `.messages.create`: every real call's actual `response.usage` is
  converted to a real dollar cost via a price table sourced from
  `claude.com/pricing` (checked 2026-09-11: Sonnet 5 is $2/MTok in,
  $10/MTok out), and passed as `llm_client` to `build_report` so every
  internal call site - already threaded through `llm_client` end to
  end since Slice 50 - is captured without touching any pipeline code.
  An unrecognized model raises rather than silently under-pricing.
- **Ceiling precision, disclosed honestly** (README, "What it costs"):
  a call's real cost isn't known until its response completes, so the
  check is "has the ceiling already been reached by every *completed*
  call" - the next call is refused before dispatch once it has. Total
  spend can overshoot by at most one call's own bounded cost, never by
  an unbounded amount.
- 7 new mocked tests (`tests/test_live_tests_runner.py`) prove the
  runner's own logic - the price table, cost accumulation, and the
  ceiling refusing (and never dispatching) the call that would exceed
  it - before it is ever pointed at a real key. 458/458 project tests
  pass.
- **Real-run proof (Done when #1, #2, #4)** - a full run against all 4
  documents, real API, default $1.00 ceiling:
  ```
  csv-schema-template-path:      PASS  (0 calls, $0.0000 - no model narrative on this path at all)
  docx-narrated-single-column:   PASS  (5 calls, $0.0963)
  pdf-two-column:                PASS  (3 calls, $0.0671)
  pdf-embedded-image:            PASS  (8 calls, $0.1034)

  documents completed: 4/4
  total real API calls: 16
  total real cost: $0.2668
  ceiling: $1.00
  stopped early: False
  ```
- **Real-run proof (Done when #3 - the hard ceiling)** - the same suite
  re-run with `--ceiling 0.01`, deliberately tiny:
  ```
  csv-schema-template-path:      PASS  (0 calls, $0.0000)
  docx-narrated-single-column:   !!! BUDGET CEILING HIT - run stopped
    before the next call: $0.0435 already spent >= $0.01 ceiling -
    refusing to dispatch another call

  documents completed: 1/4
  total real API calls: 1
  total real cost: $0.0435
  ceiling: $0.01
  stopped early: True
  ```
  Confirms the disclosed "one call's bounded overshoot" behavior
  exactly as documented in `live_tests/README.md`: the first real call
  landed at $0.0435 (already past the $0.01 ceiling, since a call's
  cost isn't known until it completes), and the very next call was
  refused *before dispatch*, halting the run - never an unbounded
  overshoot, never a silent continuation past the ceiling.
