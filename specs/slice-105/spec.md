# Slice 105 - the coordination role's accept/assign/schedule/escalate, honestly

## Goal

The live seven-role charter's `coordination` role (Slice 103) claims four
capabilities - `accept`, `assign`, `schedule`, `escalate` - and a measure,
"Engagements delivered by the date agreed at acceptance, as a share of
engagements accepted". None of this is backed by real code yet: `worksIn`
names `analystos`, but the async job API (Slice 74) already does accept
(`POST /jobs`) and schedule (`POST /jobs/{id}/run`) implicitly, with no
agreed-delivery date, no explicit role assignment, and no escalation path.
This slice makes those four verbs real, honestly scoped to what this
codebase can actually do today - one real worker role (`analysis`), not a
multi-role dispatcher that does not exist.

## Done when

1. `POST /api/v1/jobs` takes an optional `agreed_by` field (an ISO date,
   `YYYY-MM-DD`) - a malformed one is refused with `400`, not silently
   dropped or stored broken.
2. Every job record carries `assigned_role: "analysis"` always - the only
   real worker role this codebase has. Not a free-text field, not a choice:
   assigning to anything else would be a label with no code behind it.
3. `POST /api/v1/jobs/{id}/escalate` moves a **pending** job to `escalated`
   and keeps it there - `run_job` already refuses anything not `pending`, so
   an escalated job is blocked from running until a human deals with it
   through some channel outside this codebase (there is no review dashboard
   here; escalating only stops automatic progress, it does not notify
   anyone - a real limitation, stated, not hidden). Idempotent on an
   already-escalated job; `409` from any other status.
4. `analystos.api_v1.audit.measures()` gains a `coordination` entry, computed
   the same honest way as the other three: numerator is deliveries that beat
   their own `agreed_by`, denominator is accepted engagements that had an
   `agreed_by` at all (an engagement accepted with no agreed date cannot be
   scored against one). `None` share when the denominator is zero, same rule
   as every other measure.
5. `docs/api.md` and `analystos/api_v1/openapi.py` document the new field and
   endpoint; `tests/test_api_v1.py::test_openapi_covers_every_route_and_method`
   still passes with no exceptions carved out for it.
6. `vercel.json` gets the same query-param rewrite pattern `run` already has,
   so this works identically behind a real Vercel deploy and in tests.

## Not in this slice

- Declaring `coordination`'s `x-capability` (`engagement-coordination`) in the
  live handshake. `docs/mesh-identity.md`'s rule stands: a discovery slug
  waits for the endpoint to be deployed and proven, not merely merged to
  `main`. That is a separate, later step once this is live and smoke-tested.
- A real multi-role dispatcher, a review dashboard for escalated jobs, or any
  notification when one is escalated. `assigned_role` is a constant because
  `analysis` is the only role with working code; building the other three
  (research, synthesis, client-delivery) is its own, much bigger slice.
- Changing what `/analyses` (the synchronous path) does - it has no concept
  of an agreed delivery date and this slice does not add one there.
