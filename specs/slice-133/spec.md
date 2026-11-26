# Slice 133 - metered hiring: a budget that only narrows, usage, and a receipt

Phase 5 of the rebuild (hiring), without prices. The owner has set no price for
anything, so this slice meters work in model calls and tokens, never in money.
Slices 131 and 132 were the Flashy Phase 0 session's; it released 133 for this slice.

## Goal

A caller of `POST /api/v2/engagements` - a person's browser or an agent - cannot
today bound what one hire may spend, does not learn what it did spend, and gets
nothing that ties the delivered file to the engagement except three headers. An
agent hiring on someone's behalf needs all three before it can be trusted with
the job.

1. **A budget that only narrows.** The request may carry
   `budget: {max_model_calls, max_output_tokens_per_call}`. Each value may be at
   most the server's own limit (2 calls: one attempt and one repair; 8192 output
   tokens per call). A value above the limit, an unknown key, or a non-integer is
   refused before any model call - the server never silently widens or clamps.
   `max_model_calls: 1` means no repair attempt: if the first attempt fails the
   checks, nothing is delivered.
2. **Usage, measured.** Every model call is metered: input and output tokens as
   the model reports them. When a count was not reported (a replayed response, a
   call that failed), the total is `null`, never a guess.
3. **A receipt.** Every engagement taken on gets an
   `analystos-receipt/1`: the engagement, role, requester, times, outcome
   (`delivered`, `not_verified` or `unavailable`), the effective budget, the
   usage, the spec digest, and the delivered file's format, size and sha256.
   `pricing: "tbd"`, `charged_cents: 0`. `signed: false` - signing waits for a
   published key (the Flashy session's key work); a verifier must not treat an
   unsigned receipt as attested. Failed engagements get a receipt too: the calls
   were made even though nothing was delivered.

## Done when

- [ ] `budget` is validated as a closed schema; over-limit, unknown, boolean and
  non-integer values are refused with 422 and the limits named; no model call is
  made (the replay client records zero requests).
- [ ] `max_model_calls: 1` stops after one call when the checks fail (502, one
  request recorded); the default still allows exactly one repair.
- [ ] `max_output_tokens_per_call` is the `max_tokens` sent on every call.
- [ ] Usage totals come from the model's reported usage; any unreported call
  makes the total `null`.
- [ ] The JSON response carries `receipt` and `receipt_sha256` (sha256 of the
  canonical JSON); the file response carries the same in `X-AnalystOS-Receipt`
  (base64url) and `X-AnalystOS-Receipt-Sha256`; 502 and 503 responses carry a
  receipt with no output.
- [ ] The receipt's output sha256 equals the sha256 of the bytes delivered, and
  its spec digest equals `X-AnalystOS-Spec-Sha256`.
- [ ] `docs/hiring-api.md` documents the request, budget, receipt and errors; it
  is served, listed in llms.txt, linked from the "For agents" menu, and the
  glossary defines Budget and Receipt.
- [ ] `python3 -m unittest discover -s tests` OK; refresh, samples, studio
  chrome and the Flashy fence checks clean.

## Not in this slice

Prices, payment, or any charge; signing receipts; a status endpoint or stored
engagements (the API still answers in one request); hours as a unit (an
engagement hour will be defined over these measured units once a price exists).
