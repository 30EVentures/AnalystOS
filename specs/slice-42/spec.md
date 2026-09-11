# Slice 42 — in-code hard-stop budget on Anthropic API calls

## Goal

The only spend safety net today lives outside this repo entirely: a
monthly cap set on the Anthropic account itself (docs/decisions.md,
2026-09-05). That cap fails clean already (an `anthropic.APIError` becomes
a generic `ValueError`/`400`), but it's an *external* control this repo's
code can't see, configure, or test. This slice adds a second, in-code
layer: a hard ceiling this application enforces on itself, checked before
any API call is dispatched, so a runaway loop or an unexpectedly high
request volume hits an internal stop well before (or even without) ever
touching the account-level cap.

## Included

- `analystos/l2/analyze.py` — `_create_message` (the single choke point
  every Anthropic call in the codebase already goes through - shared by
  `analyze_document`, `write_narrative`, its paragraph-repair call, and
  `proofread_report`) now checks a configurable ceiling *before*
  dispatching the call:
  - Tracks **cumulative call count**, not dollar cost - the Anthropic
    Python SDK response does carry token-usage data, but turning that into
    a real dollar figure means embedding a per-model price table in this
    repo that goes silently stale the moment pricing changes. Call count
    is the metric this task explicitly sanctions as the fallback when cost
    isn't directly available, and it degrades safely: worst case, the
    ceiling trips a bit earlier or later than a dollar-based one would,
    never silently.
  - Configurable via `ANALYSTOS_MAX_API_CALLS` (an integer). **Unset means
    no internal ceiling** - this is a *second* layer on top of the
    existing account-level cap, not a replacement for it; forcing some
    arbitrary default ceiling on everyone by default risks breaking normal
    usage for no chosen reason. Set it, and it's enforced; leave it unset,
    and the account-level cap remains the only ceiling, same as today.
  - Over the ceiling → `ValueError` raised *before* `client.messages.create`
    is ever called - the same clean failure shape `analystos.pipeline` and
    `api/analyze.py` already turn a real `anthropic.APIError` into (never a
    raw `500`), so a caller can't tell the difference between "hit the
    account cap" and "hit the internal one" without reading server logs.
  - In-memory, per-process counter - the same category of tradeoff as
    Slice 41's rate limiter (not a distributed guarantee across many
    serverless instances at once), disclosed the same way.
- `docs/decisions.md` — records the call-count-not-dollars choice and why,
  and the "unset means no internal ceiling" default.
- `tests/test_l2_spend_budget.py` — isolates its own state (resets the
  counter in `setUp`/`tearDown`) so it can't leak into, or be polluted by,
  any other test file's calls through the same shared choke point.

## Done when

1. Once the tracked ceiling is exceeded, the next call is rejected with a
   clean `ValueError` - tested by confirming the underlying (mocked)
   `client.messages.create` is never invoked for that call once the budget
   is spent, proving the block happens *before* any API call is made.
2. The ceiling is configurable via `ANALYSTOS_MAX_API_CALLS` - tested by
   setting a small value and confirming the tracker actually uses it (not
   just an internal default).
3. A call made while under the ceiling behaves exactly as before this
   slice - unaffected.
4. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Real dollar-cost tracking from token usage - call count only, for the
  reason above. A token/price-based tracker is a real, separable
  follow-up if the account-level cap and this one both prove insufficient.
- A distributed/shared counter across multiple serverless instances - the
  same accepted tradeoff as Slice 41's rate limiter.
- Any UI for viewing or resetting the counter - this is a hard stop, not a
  dashboard.
