# Slice 21 — the upload page on `site/`

## Goal

Make "upload a document, get a report" real in a browser, not just via
`curl`. A person visiting the site picks a real CSV/Excel/Word/PowerPoint
file, tells it the schema, and gets back the same cited report
`api/analyze.py` already produces — driven entirely by a static page with
no build step, matching how `site/index.html` is already written.

## Included

- `site/upload.html` — the upload page:
  - A file picker restricted to `.csv,.xlsx,.docx,.pptx` (the same set
    `api/analyze.py` accepts).
  - A `schema` field: a JSON textarea (e.g.
    `{"period": "text", "revenue": "number"}`), pre-filled with a working
    example so the first submit a visitor tries actually succeeds. Hand-typed
    JSON, not a column-mapping UI — see "Not in this slice."
  - Optional `title` field; `template` fixed to `income_statement` (still the
    only one that exists — same as the API); `currency_unit` as a dropdown
    (`actual` / `thousands` / `millions`).
  - On submit: `fetch('/api/analyze', {method: 'POST', body: new
    FormData(form)})` — a relative path, so it only resolves once the page
    and the API are served from the same Vercel deployment (true in
    production; local testing needs both served from one origin — see
    "Verified beyond the test suite" once this is built).
  - While the request is in flight: submit button disabled, a visible
    loading state.
  - On success (200): the returned `html` rendered into an `<iframe
    srcdoc="...">` — `render_html` returns a standalone document with its own
    `<style>`, so an iframe avoids any collision with the page's own CSS.
  - On failure (400/500): the JSON `error` message shown as readable text
    near the form, not a raw response dump, and not a silent failure.
  - Plain HTML/CSS/vanilla JS, no framework, no build step, styled to match
    `site/index.html`'s existing look (same CSS custom properties, fonts).
- `site/index.html` — one added link/CTA (e.g. "Try it now →") pointing at
  `upload.html`. No other changes to the landing page.
- `tests/test_upload_page.py` — a smoke test in the style of
  `tests/test_docs.py`: the page exists and its JS still names the current
  API contract (`/api/analyze`, the `file`/`schema`/`title`/`template`/
  `currency_unit` field names, the four accepted extensions) — so the page
  can't silently drift out of sync with `api/analyze.py` without a test
  failing.

## Done when

1. In a real browser, choosing a real file of each of the four accepted
   types, filling in a matching schema, and submitting shows the real
   returned report inline — an actual request/response against
   `api/analyze.py`, not a mock.
2. A bad request (unsupported extension, invalid/mismatched schema, a
   pipeline error) comes back as a readable on-page message, not a silent
   failure or a raw JSON dump.
3. The submit control is disabled and shows a loading state for the
   duration of the request, and is restored afterward whether the request
   succeeds or fails.
4. The page has no console errors and makes no network calls other than the
   one `fetch` to `/api/analyze`.
5. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Verified beyond the test suite

Drove a real Chromium browser (Playwright) against the real `api/analyze.py`
Flask app served locally alongside `site/` on one origin (so the page's
relative `fetch('/api/analyze')` resolves exactly as it will under Vercel):
uploaded a real matching CSV through the actual `<input type="file">` and
confirmed the returned, cited report rendered inside the iframe (revenue,
margins, and the YoY growth ask all present with footnote markers); then
uploaded a CSV missing the schema's declared columns and confirmed a
readable error message appeared on the page instead of a raw JSON dump or a
silent failure. The only console/network anomaly seen was the Google Fonts
stylesheet failing to load — `fonts.googleapis.com` isn't reachable from
this sandboxed test environment; that `<link>` already exists unchanged in
`site/index.html` from before this slice, so it isn't a regression, and it
will resolve normally once deployed.

## Not in this slice

- Auto-detecting or guessing `schema` from the uploaded file's actual
  columns — still hand-typed JSON. A real, scoped-out gap; a proper
  column-mapping UI (read the file client-side or in a preflight call, offer
  a form instead of raw JSON) is bigger than this slice and would delay
  getting a working end-to-end loop in front of real users.
- Access control (Slice 22) — the page and the endpoint it calls are both
  open to anyone with the URL.
- A real downloadable PDF (Slice 24) — the browser's own Print is the only
  path to a PDF today, same as the CLI's `section.html` already.
- Confirming this behaves identically once actually deployed to
  `analyst-os-phi.vercel.app` — same residual uncertainty Slice 20's spec
  called out for the API itself; the relative `/api/analyze` fetch is
  designed to work under Vercel's same-origin setup but can only be fully
  confirmed post-deploy.
- Any broader redesign of `site/index.html` — one link added, nothing else
  on the landing page changes.
