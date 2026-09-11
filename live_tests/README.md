# live_tests/ — the deliberate, real-money test tier

`tests/` (451 tests as of Slice 51) is entirely mocked - fast, free, and
runs on every push. It's also structurally blind to anything only a
genuine model response can surface: found directly this session, a
report that passed every mock but produced an uncitable number live.

`live_tests/` is the deliberate, additive answer to that gap - a small
suite of **real, non-mocked** API calls against a fixed set of
structurally different documents. It is **not** a replacement for the
mocked suite and **never** runs as part of it:

```
python3 -m unittest discover -s tests -v   # unaffected - still free, still mocked
python3 live_tests/run_live_tests.py       # this directory - real money, run by hand
```

## Running it

```
source .venv/bin/activate
export ANTHROPIC_API_KEY=your-key-here     # your own key - this script never sees it beyond what the SDK reads
python3 live_tests/run_live_tests.py
```

Optional flags:

- `--ceiling 1.00` - the hard dollar ceiling for the whole run (default
  `$1.00`). The run stops *before* dispatching any call that would cross
  it - never mid-response, never over.
- `--log-file path/to/run.log` - also writes the full log to a file.

## What it costs

The ceiling is a safety net, not the expected spend. At current Sonnet 5
pricing ($2/MTok input, $10/MTok output - `_PRICE_PER_MTOK` in
`run_live_tests.py`, sourced from `claude.com/pricing`, checked
2026-09-11), a full run of all four documents typically costs a few
cents to a few tens of cents - well under the default `$1.00` ceiling.

**One honest limit on the ceiling's precision:** a call's real cost isn't
known until its response finishes (token usage isn't knowable upfront),
so the check is "has the ceiling already been reached by every
*completed* call so far" - not a mid-response abort. Worst case, total
spend can overshoot the ceiling by one call's own cost (bounded by that
call's `max_tokens`, a few cents at most for this pipeline's calls) - it
can never overshoot by an unbounded amount, and the moment the ceiling is
reached, every subsequent call is refused before dispatch.

## The fixed document set

`live_tests/fixtures/` (built by `build_fixtures.py` - regenerate with
`python3 live_tests/build_fixtures.py` if you ever need to rebuild them
from scratch, rather than hand-editing the binaries):

| file | path exercised |
|---|---|
| `income_statement.csv` | schema/template path - no model narrative at all |
| `quarterly_review.docx` | narrated-default path, plain single-column prose |
| `two_column_review.pdf` | narrated-default path over Slice 50's column-aware extraction |
| `chart_exhibit.pdf` | narrated-default path over Slice 50's image-fact (vision) extraction |

## Why this is separate from `tests/`

- **Cost.** Every run spends real money. `tests/` must stay free and
  runnable with zero configuration, including in CI.
- **Determinism.** A live model call can vary run to run in ways a mock
  never does - useful for catching the class of bug this suite exists
  for, but not something the deterministic regression suite should
  depend on.
- **Not CI-integrated, on purpose.** This is a human-triggered, on-demand
  check (see specs/slice-51/spec.md, "Not in this slice") - real money on
  every push is a deliberate non-goal.
