# Slice 135 - preflight: check a hire before spending anything

Phase 6 of the rebuild (the front door), for agents first. Slice 133 lets a
caller bound and see what a hire spends; this slice lets it find out, for free,
whether a hire would be taken on at all, and what it would use at most.

## Goal

Today the only way to learn that an answer is missing, a budget is too wide, or
a role is unknown is to send the real hire: which needs the access code, and
which makes a paid model call the moment everything passes. An agent preparing
a hire for someone should be able to check it first, without access and without
cost, and learn what the hire would produce and its worst case.

`POST /api/v2/engagements/preflight` takes the same body as
`POST /api/v2/engagements` and runs the same checks (role, problem, requester,
answers, acceptance, budget), but never makes a model call, never reserves
anything and needs no access code. It answers 200 with an
`analystos-preflight/1`:

- `ready`: whether the hire, sent as is, would be taken on;
- `problems` and `open_questions`: the reasons the hire would refuse it, in its
  own words (intake stops at its first refusal; a refused budget is reported
  alongside);
- `budget`: the effective budget, and `worst_case`: model calls and output
  tokens at most (calls x the per-call token budget);
- `deliverable`: the format, media type and extension the role delivers;
- `first_call`: the character counts of the system prompt and message the first
  model call would send (exact), and of the tool definition as compact JSON
  (characters, not tokens:
  no token count is claimed before the model reports one);
- `pricing: "tbd"`, `model_calls_made: 0`.

## Done when

- [x] Preflight and hire share one intake path, so they cannot disagree: for a
  ready body the hire is taken on; for each kind of refusal (unknown role, bad
  requester, unknown question id, open questions, bad budget) preflight says
  `ready: false` with the reason, and the hire refuses for the same reason.
- [x] Preflight makes no model call (no client is made) and needs no access code;
  it is rate limited like the rest of the API; malformed JSON is 400, an
  oversized body 413.
- [x] `first_call` equals the lengths of what the real hire's first request sends
  (checked against the replay client's recorded request).
- [x] `worst_case` follows the effective budget.
- [x] `docs/hiring-api.md`, llms.txt and the glossary describe it.
- [x] `python3 -m unittest discover -s tests` OK; refresh, samples, studio
  chrome, site machine and the Flashy fence checks clean.

## Not in this slice

A token estimate (only the model's own count is ever reported), reserving
budget, or a hire-page change (the page would need a mock first).
