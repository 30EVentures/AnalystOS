# Slice 73 - a human review, recorded (agent-native queue, item 1 of 3)

## Goal

The intended shape going forward: a human prompts an agent to produce an
analysis; the agent is the one that calls AnalystOS (`POST /api/v1/analyses`)
and gets the report back; the human's role is oversight, not operating the
API. Today that oversight happens, if at all, entirely outside the system -
nothing in AnalystOS records that a human looked at a delivered report, or
what they decided. This slice makes that one fact real and auditable,
without changing how an agent calls the API.

- A new endpoint, `POST /api/v1/reports/{id}/review`, marks a stored report
  as reviewed: who (the caller key that reviewed it), when, and an optional
  `approved` boolean. Same authentication and ownership rule as
  `GET /api/v1/reports/{id}` - only the key that created the report may
  review it, and someone else's report is indistinguishable from a missing
  one (matches the existing `GET`/`POST /links` behaviour).
- Idempotent: reviewing again overwrites who/when/approved with the latest
  call.
- The review state is surfaced back via `GET /api/v1/verify/{id}` (the one
  existing endpoint that already exposes stored metadata alongside the seal),
  as `"reviewed": {"caller", "at", "approved"} | null`.
- One audit event per review (`type: "review"`), same shape/place as the
  existing `analysis`, `view` and `link` events (`docs/api.md`,
  `analystos/api_v1/audit.py`).

## Not in this slice

- **No enforcement.** A report is deliverable and verifiable whether or not
  it was ever reviewed; this slice makes oversight visible, not mandatory.
  Gating delivery on review is a policy decision (`docs/architecture.md`'s
  "not built: ... a policy engine") for later, once there is a real caller
  to learn from.
- **No agent/human distinction on API keys.** Any caller holding the
  creating key can record a review; there is no way yet to require the
  reviewer be a *different*, human-held key. That is the natural next
  policy layer, not this slice.
- **No change to the charter's published measures** (`docs/mesh-identity.md`)
  - the three existing measures are untouched; a review is a new,
  separately-queryable audit event type, not folded into them.
- Async jobs and a published fact-record schema - queued next in the
  same sequence (see `ROADMAP.md`, "agent-native queue").

## Done when

1. `POST /api/v1/reports/{id}/review` with a valid creator key records
   `{caller, at, approved}` against that report and appends a `review`
   audit event; an absent/invalid `approved` (present but not boolean) is a
   400; wrong caller or unknown id is a 404, identical to `GET /reports/{id}`;
   an expired report is 410; no store configured is 503.
2. `GET /api/v1/verify/{id}` includes `"reviewed"` - `null` until reviewed,
   then the recorded `{caller, at, approved}`.
3. `openapi.json` documents the new route; `docs/api.md` describes it.
4. Full suite OK (`python3 -m unittest discover -s tests -v`).
