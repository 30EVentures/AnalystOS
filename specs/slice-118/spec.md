# Slice 118 - the website: hire any of the 73 roles

## Goal

Owner's direction, 2026-11-23: the website carries every role by the end of
the day. A person (or an agent) picks a role, describes the problem, answers
the role's scoping questions and gets the verified deck back.

## What it adds

- `GET /api/v2/catalog` (public): every role with its family, boundary, how it
  was tested (`mock` or `live`), pricing (`tbd`: to be determined), what it delivers today,
  its native deliverables and the scoping questions it asks. One document for
  people and agents.
- `POST /api/v2/engagements` (access code, `X-Access-Code`, the same
  `ANALYSTOS_ACCESS_CODE` as `/api/analyze`; the same per-IP limiter): JSON in,
  intake, the acceptance gate, the verified pipeline, the renderer; the
  PowerPoint deck out, or the verified spec and deck as JSON with
  `?format=json`. Refusals: 401 bad code, 400 bad JSON, 413 body over 64 KB,
  422 refused input or an engagement the gate will not accept (with the open
  questions), 502 when the content fails verification twice (nothing is
  delivered), 503 when the model is unavailable.
- `site/hire.html`: role picker grouped by family, the role's boundary and how
  it was tested, the problem, the role's questions, the access code; download
  the deck. Linked from the homepage hero. Same studio chrome as every page; in
  the sitemap.
- `/api/v1` is untouched (the Flashy fence pins its contract).

## Money and limits, stated

Every request that passes the gate is a paid model call on the operator's
account (one call, at most one repair retry). What limits that is the access
code, the per-IP rate limiter (in memory, per instance) and
`ANALYSTOS_MAX_API_CALLS` (per process; a serverless instance restarts it). No
billing: price is to be determined; none has been set for any role. The serverless
function's time limit was not measured here; a slow model call may hit it.

## Done when

1. Tests (no paid call possible: the client factory is replaced) cover the
   public catalog, a deck returned for a worked example, the JSON form, the
   access code (missing, wrong, unconfigured), refusals before any model call,
   and a deck never delivered when verification fails twice.
2. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.
