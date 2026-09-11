# Slice 40 — repair instead of regenerate, for both quality gates

## Goal

Live-tested twice in a row after Slice 39 and both runs fell back to the
plain renderer with zero trace of why - `analystos.pipeline`'s except
clause swallowed the reason entirely. Diagnosing it live (the only way to
find out what Gate 1/Gate 2 actually objected to) surfaced a deeper,
structural problem: on any rejection, `write_narrative` threw away the
*entire* report and asked the model to regenerate everything from scratch.
A report this size (exec summary + 3-5 sections + KPIs + outlook) has
enough sentences that a full reroll is a fresh chance to break a
*different* rule everywhere else, even while correctly fixing the
originally-reported one - watched happen live, back to back, several
times. This slice replaces "reject and reroll the whole document" with
"repair just the one flagged piece" for both gates, and closes the
specific rule-precision and prompt gaps the live diagnosis actually found.

## Included

- `analystos/pipeline.py` — every Gate 1/Gate 2 fallback reason is now
  logged to stderr (previously silent); Gate 2 issues get their own
  repair pass (`repair_language_issues`, below) with a bounded number of
  repair-then-recheck rounds (`_MAX_GATE2_REPAIR_ROUNDS`) before falling
  back, instead of an instant, unconditional fallback on any language
  issue.
- `analystos/l2/narrate.py`:
  - `_locate_problem` — finds the single paragraph responsible for a
    validation failure (get/set closures for in-place repair) instead of
    only a human-readable reason string; `_assemble_report` now uses it as
    its single source of truth.
  - `_repair_paragraph` — a small, scoped call that fixes one rejected
    paragraph in place, given the exact rejection reason, instead of
    rewriting the whole report. `write_narrative`'s retry loop now tries
    this first (bounded by `_MAX_REPAIR_ATTEMPTS`, chasing a second
    problem the first repair exposes), falling back to a full regenerate
    (`_MAX_RETRIES`, widened from 1 to 2) only if repair doesn't converge
    or the problem is structural (no single paragraph to target).
  - `repair_language_issues` — the same repair principle applied to Gate 2:
    locates a flagged issue's text in the assembled report (exact-match
    only; an ambiguous, non-unique location is left alone rather than
    risking a patch to the wrong sentence) and repairs it, re-validating
    against Gate 1's own rules so a wording fix can never quietly
    reintroduce a correctness violation.
  - Three closed validator/prompt gaps found live: a missing rule (an "N
    consecutive quarters" claim needs N+1 citations, now stated in the
    prompt, not just checked after the fact); a scoping bug in the
    direction-word check (a direction word separated from a "difference"
    fact by another placeholder was wrongly flagged as describing it); a
    new `_redundant_unit_problem` check (a placeholder followed by a
    spelled-out unit like "million" is always wrong - the rendered value
    already carries one, and for a non-numeric event fact it silently
    misuses it as though it had a value at all).
- `analystos/l2/analyze.py` — an event's `status`/`next_step` text can
  legitimately contain a real, standalone figure the model can see but
  has no `{{N}}` for (found live: an acquisition's integration-cost peak
  and step-down, described in prose but never surfaced as its own citable
  fact). The extraction prompt now asks for that figure to also be
  emitted as its own separate `quote` segment when it's material enough
  to report on its own.
- `tests/test_l2_narrate.py`, `tests/test_pipeline.py` — one test per
  mechanism above, using mocked clients (no real API calls).

## Done when

1. `python3 -m unittest discover -s tests -v` passes.
2. A single bad paragraph in an otherwise-valid report is repaired without
   a full-document regenerate call (proven directly: the mocked
   `write_narrative` tool is invoked once, `fixed_paragraph` once).
3. A Gate 2 (language-quality) failure is repaired rather than an instant
   fallback, proven the same way - the rich HTML path is reached, not the
   flat fallback.
4. An ambiguous Gate 2 issue location (matching more than one field) is
   left unpatched rather than guessed at.
5. Live-verified against the actual test document that originally
   triggered this slice: confirmed producing the full rich report (KPI
   strip, charts, outlook) end to end, not just passing the mocked test
   suite.

## Not in this slice

- A deeper fix to the L2 analysis layer's fact-selection logic beyond the
  one targeted prompt addition above (which quote/computed facts get
  selected among a document's real numbers at all) - out of scope; this
  slice only closes the specific gap the live diagnosis found.
- Any change to the account-level or in-code spend/rate-limit safety
  nets - unrelated infrastructure, covered separately (Slices 41-43).
