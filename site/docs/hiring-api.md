# Hiring a role through the API (v2)

Base: `https://analystos.dev/api/v2`. People and agents use the same endpoints.
Price: to be determined. No price has been set for any role, and nothing is charged
through this API.

| Method and path | Auth | What |
|---|---|---|
| `GET /api/v2/catalog` | none | every role: family, boundary, how it was tested, what it delivers, and the questions it asks |
| `POST /api/v2/engagements/preflight` | none | the same checks as a hire, with no model call: would it be taken on, and what would it use at most |
| `POST /api/v2/engagements` | access code (`X-Access-Code`) | hire one role for one problem; answers in one request with the finished file |

## Hiring

```json
{
  "role": "management-consulting-analyst",
  "problem": "Our clinic chain's churn rose from 5% to 7% this year...",
  "answers": {"common.decision": "...", "common.deadline": "...", "consulting.success": "...", "...": "..."},
  "requested_by": {"kind": "agent", "ref": "buyer-agent-7"},
  "budget": {"max_model_calls": 1, "max_output_tokens_per_call": 6000}
}
```

- `answers` maps each question id from the role's catalog entry to your answer.
  A required question left unanswered is refused with `422 not_accepted` and the
  list of open questions, before any model call.
- `requested_by.kind` is `person` or `agent`. It is your own declaration and is not
  verified; left out, it is `{"kind": "person", "ref": "web"}`.
- The response is the role's file (`.pptx`, `.docx` or `.xlsx`, named in the
  `X-AnalystOS-Format` header). With `?format=json` it is a JSON object with the
  verified `spec`, `spec_sha256`, `output` {format, media_type, filename, base64},
  `receipt` and `receipt_sha256`.
- Every request that passes the checks makes a paid model call on the operator's
  account. The access code is what limits who can make one.

## Preflight

`POST /api/v2/engagements/preflight` takes exactly the body of a hire and runs the
same checks, in the same code: role, problem, requester, answers, acceptance and
budget. It makes no model call, reserves nothing, needs no access code and costs
nothing, so check a hire here before you send it. A JSON object with `answers`
(if any) as an object answers `200`; the exceptions are listed below:

```json
{
  "format": "analystos-preflight/1",
  "ready": false,
  "role": "management-consulting-analyst",
  "problems": ["budget.max_model_calls is 3, above this server's limit of 2; a budget can only narrow the limits",
               "still scoping: unanswered consulting.success"],
  "open_questions": ["consulting.success"],
  "budget": null,
  "limits": {"max_model_calls": 2, "max_output_tokens_per_call": 8192},
  "worst_case": null,
  "deliverable": {"format": "deck", "media_type": "...", "extension": "pptx"},
  "first_call": null,
  "pricing": "tbd",
  "model_calls_made": 0,
  "note": "..."
}
```

- `ready: true` means the hire, sent as is, would be taken on: it would pass
  every check and go on to the model, unless this server's own call limit is
  spent or the model is unavailable (then the hire answers `503`). The hire
  repeats every check, so a preflight is advice, not a reservation.
- `problems` and `open_questions` are the reasons the hire would refuse it, in
  the hire's own words. Intake stops at its first refusal (a bad role, problem,
  requester or answer), so fix that and check again; a refused budget is always
  reported alongside, and open questions are listed when intake got that far.
- `worst_case` is the most the hire could use: `model_calls`, and `output_tokens`
  (calls times the per-call token budget). `null` when the budget is refused.
- `first_call` (only when ready) gives the character counts of the system
  prompt and the message the first model call would send (exact), and of the
  tool definition as compact JSON (the wire format may differ by whitespace).
  These are characters, not tokens: AnalystOS reports a token count only when
  the model has reported one.
- Malformed JSON, or `answers` that is not an object, is `400`; a body over
  64,000 bytes is `413`; it is rate limited like every endpoint.

## Budget

`budget` is optional and can only narrow this server's limits:

| Field | Server limit | Meaning |
|---|---|---|
| `max_model_calls` | 2 | one attempt and one repair; `1` means no repair attempt |
| `max_output_tokens_per_call` | 8192 | the `max_tokens` each call asks the model for |

A value above a limit, an unknown field, or anything but a whole number of at
least 1 is refused with `422 bad_budget`, naming the limits, before any model
call. Nothing is clamped or widened silently. A smaller token budget can make the
model's answer too short to pass the checks; then nothing is delivered.

## Receipt

Every engagement that passes the checks and is taken on gets an
`analystos-receipt/1`, including ones where nothing was delivered and ones where
no model call could be made (then `model_calls` is 0):

```json
{
  "format": "analystos-receipt/1",
  "engagement_id": "...", "roles": ["management-consulting-analyst"],
  "requested_by": {"kind": "agent", "ref": "buyer-agent-7"},
  "started": "2026-11-26T15:04:05Z", "finished": "2026-11-26T15:05:12Z",
  "outcome": "delivered",
  "budget": {"max_model_calls": 2, "max_output_tokens_per_call": 8192},
  "usage": {"model": "...", "model_calls": 1, "input_tokens": 5012, "output_tokens": 3120,
            "calls": [{"input_tokens": 5012, "output_tokens": 3120, "stop_reason": "tool_use"}]},
  "spec_sha256": "...",
  "output": {"format": "deck", "media_type": "...", "bytes": 48213, "sha256": "..."},
  "pricing": "tbd", "charged_cents": 0, "signed": false
}
```

- `outcome` is `delivered`, `not_verified` (the work failed the checks, so nothing
  was delivered) or `unavailable` (a model call failed, or this server's own call
  limit is spent; a call that failed after being sent is counted, with unknown
  token counts).
- `usage` counts are what the model reported, per call sent. `input_tokens`
  includes any input written to or read from the prompt cache (none is used
  today). A total is `null` when any call did not report a count: it is never
  estimated. A call this server's limit refused before sending is not counted.
- `requested_by` is what the caller declared, not a verified identity.
- `output.sha256` is the sha256 of the exact bytes delivered; `spec_sha256` equals
  the `X-AnalystOS-Spec-Sha256` header.
- With the file response, the receipt is in `X-AnalystOS-Receipt` (base64url of
  its canonical JSON, no padding) and `X-AnalystOS-Receipt-Sha256`. On `502` and
  `503` it is in `error.receipt`, with `output: null`.
- `receipt_sha256` is the sha256 of the canonical JSON: keys sorted, separators
  `,` and `:`, UTF-8, with non-ASCII characters written as themselves (not
  `\u` escapes).
- **Receipts are not signed yet** (`signed: false`). A receipt is a record of what
  this server says it did, not an attestation a stranger can check. Signing waits
  for a published key; until then, do not treat one as proof.

## Errors

Errors from this endpoint are `{"error": {"code", "message", ...}}`, except the shared
access and rate checks (401, 429, 500), whose `error` is a plain string.

| Status | Code | When |
|---|---|---|
| 400 | `bad_request` | not a JSON object, or `answers` is not an object |
| 401 | - | missing or wrong access code |
| 413 | `too_large` | body over 64,000 bytes |
| 422 | `bad_budget` | the budget asks for more than the limits, or is malformed |
| 422 | `refused` | unknown role or question id, a bad `requested_by`, or text that cannot be taken |
| 422 | `not_accepted` | required questions unanswered; `open_questions` lists them |
| 429 | - | rate limited |
| 500 | - | the server has no access code configured |
| 502 | `not_verified` | the work failed the checks on every attempt the budget allowed; `problems` lists why |
| 503 | `unavailable` | a model call failed, or this server's call limit is spent; try again later |
