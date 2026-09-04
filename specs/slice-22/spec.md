# Slice 22 — access gating (not public on day one)

## Goal

`api/analyze.py` and `site/upload.html` are both live and wide open right
now — anyone with the URL can use them, as flagged explicitly in Slices 20
and 21's specs. This slice closes that gap the way it fits this stage of
the project: a small, hands-on preview with a handful of real analysts, not
a public product yet. One shared access code, checked server-side, is
enough to keep it off random visitors and search engines without building
real accounts — that's R1/R2 territory per `ROADMAP.md`, not this slice.

## Included

- `api/analyze.py` — every request to `POST /api/analyze` must carry an
  `X-Access-Code` header matching the `ANALYSTOS_ACCESS_CODE` environment
  variable:
  - Checked first, before the file/schema are even looked at.
  - Compared with `hmac.compare_digest` (constant-time — no timing side
    channel on a secret comparison, cheap to do right).
  - Missing or wrong code → `401`, a clean message, same shape as the
    existing `{"error": "..."}` responses — never echoes the code back.
  - **Fail closed**: if `ANALYSTOS_ACCESS_CODE` isn't set at all (e.g.
    forgotten on a fresh Vercel deploy), every request is rejected with
    `500` and a message saying gating isn't configured — never silently
    open.
  - The code is never logged and never appears in a response body.
- `site/upload.html` — one added field: "Access code," entered once. On
  successful submit, the code is remembered (`localStorage`) so the analyst
  doesn't retype it on every report; it's sent as the `X-Access-Code`
  header on every `fetch('/api/analyze')` call. A `401` (missing/wrong
  code) surfaces through the same readable error element the page already
  has for `400`s — not a special case.
- `docs/decisions.md` — records the choice (shared code via env var, not
  accounts) and why, and names the Vercel dashboard step this can't do for
  itself: setting `ANALYSTOS_ACCESS_CODE` on the actual deployment.
- `tests/test_api_analyze.py` (or a new `tests/test_api_access.py`) — sets
  `ANALYSTOS_ACCESS_CODE` in `setUp`/tears it down after, so the existing
  Slice 20 tests keep passing with the correct header added, plus new
  cases for missing, wrong, and unset-env-var requests.

## Done when

1. A request with no `X-Access-Code` header, or the wrong one, gets a clean
   `401` — never a crash, never proceeds to touch the file.
2. A request with the correct code behaves exactly as Slice 20 specified —
   all of that slice's "Done when" checks still hold once the header is
   added.
3. If `ANALYSTOS_ACCESS_CODE` is unset, every request — even one carrying a
   header — gets a clean `500`, not silent access.
4. The code is compared with `hmac.compare_digest`, never with `==`, and
   never appears in a log line or a response body.
5. In a real browser: entering the code once, submitting successfully, then
   reloading the page and submitting again does *not* require re-entering
   it (persisted client-side); an empty or wrong code shows the same
   on-page error treatment Slice 21 already built for a `400`.
6. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Not in this slice

- Real user accounts, per-analyst identity, or anything that could answer
  "who submitted this" — one shared secret for the whole preview cohort.
  Real accounts are R1/R2 work (`ROADMAP.md`), well past the thin-slice MVP.
- Rate limiting or brute-force protection on the code itself. A shared code
  keeps this off search engines and drive-by visitors; it isn't meant to
  withstand a targeted attacker guessing it, and that's an accepted,
  disclosed tradeoff for this stage, not an oversight.
- Rotating or expiring the code automatically — done by hand, by changing
  the env var in the Vercel dashboard, whenever it needs to change.
- Actually setting `ANALYSTOS_ACCESS_CODE` on the live
  `analyst-os-phi.vercel.app` deployment — a manual dashboard step outside
  this repo's code, same category of residual step Slice 20/21 already
  flagged for anything that can only be confirmed post-deploy.
- Gating the static landing page (`site/index.html`) itself — it stays
  public; only the upload flow and the API it calls are behind the code.
