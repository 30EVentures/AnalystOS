# Slice 74 - async analysis jobs (agent-native queue, item 2 of 3)

## Goal

`POST /api/v1/analyses` holds one HTTP connection open for the whole
pipeline - upload, extraction, model calls, verification, narration,
sealing - bounded by the platform's real per-invocation wall-clock ceiling
(`docs/decisions.md`: a real 10-second ceiling drove the Sonnet-vs-Opus
choice in Slice 26). Vercel runs no background worker between requests, so
true "submit and the server keeps going regardless of the client" async
needs a queue and a worker - new infrastructure this repo doesn't have and
this slice does not add (same reason "a durable rate limiter" and "durable
hosted storage" are on `ROADMAP.md`'s Blocked list, not built here either).

What *is* buildable now, with the existing (non-durable, `ANALYSTOS_STORE_DIR`)
file store and no new infrastructure: split "submit" from "run" from
"collect," so an agent isn't forced to hold one large multipart upload
connection open for the full analysis duration.

- `POST /api/v1/jobs` - same upload as `/analyses` (`file`, optional `title`,
  `include_pdf`). Fast: stores the upload and a `pending` job record, no
  model calls. Returns `202 {"id", "status": "pending"}`.
- `POST /api/v1/jobs/{id}/run` - runs the *existing, unmodified*
  `build_report` pipeline for that job, exactly as `/analyses` does today
  (same fallback cascade, same gates, same time ceiling for this one call).
  On success: stores the result through the *existing* report store (so
  `GET /reports/{id}`, `POST /reports/{id}/review`, links and verify all
  work on it for free) and marks the job `done` with `report_id`. On
  failure: marks it `failed` with the error. Calling `/run` again on a
  non-`pending` job is idempotent - it just returns the current status,
  never re-runs.
- `GET /api/v1/jobs/{id}` - cheap, instant status read. Never executes
  anything.
- The uploaded file is deleted once `/run` finishes (success or failure) -
  same "nothing kept longer than it has to be" rule as `/analyses`, just
  delayed until the job actually runs instead of the end of one request.
- A successful run's audit event is the same `analysis` shape `/analyses`
  emits (so it counts toward the charter's existing measures identically),
  plus `"via": "job"`. `job_created` and `job_failed` are new event types.

## Not in this slice

- **Does not raise the per-call time ceiling.** A document whose analysis
  alone exceeds one invocation's limit fails at `/run` exactly as it would
  at `/analyses` today. Closing that gap for real needs either a queue and
  a worker (new infrastructure - a decision for `ROADMAP.md`'s Blocked
  list, not this repo alone) or splitting the pipeline's own internal model
  calls into resumable steps (a much larger, riskier rewrite of
  `analystos/pipeline.py`'s well-tested fallback logic - deliberately not
  attempted here; `build_report` is called whole, unmodified).
- **No locking against a concurrent double `/run`.** Matches the file
  store's existing non-durability caveats elsewhere in this API.
- **No expiry/purge for stale `pending` jobs that are never run.** Reports
  already purge on TTL; jobs reuse that mechanism only once they complete
  (they become a normal stored report). A `pending` job whose upload is
  never consumed sits until the store is cleared by hand. Worth a follow-up
  once there's a real caller to learn the right TTL from.
- A published JSON Schema for the seal's fact shape - item 3 of the queue,
  next.

## Done when

1. `POST /api/v1/jobs` stores the upload and returns `202` with a
   `pending` job id; unsupported extension is 415; no file is 400; no store
   configured is 503; requires the same bearer auth as `/analyses`.
2. `POST /api/v1/jobs/{id}/run` executes the pipeline once, produces a
   report retrievable exactly like one from `/analyses` (`GET /reports/{id}`,
   `POST /reports/{id}/review`, `POST /links`, `GET|POST /verify`), deletes
   the upload, and is idempotent on repeat calls once no longer `pending`.
3. `GET /api/v1/jobs/{id}` reports `pending` / `done` (+ `report_id`,
   `links`) / `failed` (+ `error`); wrong caller or unknown id is 404,
   identical to the reports routes.
4. `openapi.json` documents all three routes; `docs/api.md` describes the
   flow and states the ceiling caveat plainly.
5. Full suite OK.
