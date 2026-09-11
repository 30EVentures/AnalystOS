# Slice 41 — per-IP rate limiting on the access-code endpoints

## Goal

Slice 22 explicitly deferred this: "Rate limiting or brute-force protection
on the code itself... an accepted, disclosed tradeoff for this stage, not
an oversight." This slice closes that gap as defense in depth, on top of
the existing shared-code gate — not a redesign of auth. The shared-code,
no-accounts model stays exactly as-is; this only throttles how fast any one
client can hit the endpoints, right code or wrong.

## Included

- `api/analyze.py` — a small in-memory, per-process fixed-window rate
  limiter, checked first on every request to `POST /api/analyze` and
  `POST /api/extract`, *before* the access-code check — so a wrong-code
  guess still counts against the budget (brute-force protection), not just
  successful requests.
  - Keyed by client IP: `X-Forwarded-For`'s first entry if present (the
    real client behind Vercel's proxy), else `request.remote_addr`.
  - Configurable via two env vars: `ANALYSTOS_RATE_LIMIT_MAX` (requests per
    window, default 30) and `ANALYSTOS_RATE_LIMIT_WINDOW_SECONDS` (default
    60). An unset or unparseable value falls back to the default rather
    than raising — this is a throttle, not a gate; it must never be the
    reason the whole service goes down.
  - Over the limit → a clean `429` with a `{"error": "..."}` body, the same
    shape every other error response already uses — never a `500`, and the
    check never touches the uploaded file.
- `docs/decisions.md` — records the choice (in-memory per-process, not a
  shared store like Redis) and why: this is a defense-in-depth throttle
  against casual abuse and brute-forcing the shared code, not a guarantee
  against a distributed attacker across many serverless instances — that
  would need a shared store, out of scope for this stage.
- `tests/test_api_rate_limit.py` — isolates its own state (clears the
  limiter's in-memory buckets in `setUp`/`tearDown`) so it can't leak into,
  or be polluted by, any other test file's requests against the same app.

## Done when

1. Exceeding the configured limit returns a clean `429`, never a `500` —
   tested by driving requests past a deliberately low limit set via the env
   var.
2. The limit is configurable via `ANALYSTOS_RATE_LIMIT_MAX` /
   `ANALYSTOS_RATE_LIMIT_WINDOW_SECONDS` — tested by setting a small value
   and confirming the limiter actually uses it.
3. Normal usage under the limit is completely unaffected — tested by
   confirming every request up to (and including) the limit still gets its
   normal status code (200 for a valid request, 401 for a bad code), not a
   429.
4. A wrong access code still counts against the same budget as a correct
   one (brute-force protection is the actual point of gating this
   endpoint specifically).
5. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- A distributed/shared rate-limit store (Redis, etc.) for correctness
  across multiple serverless instances — in-memory per-process is an
  accepted, disclosed tradeoff at this stage, the same category Slice 22
  already accepted for the access code itself.
- Per-access-code (as opposed to per-IP) limiting, or banning/blocklisting
  an abusive IP beyond the current window.
- Rate limiting the static landing page — unchanged from Slice 22, it
  stays public and ungated.
