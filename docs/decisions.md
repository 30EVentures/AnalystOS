# Decisions

Dated log, newest first. One entry per real choice, with the reason.

## 2026-09-05 — Every segment field is required, not just "type" (real live 400)

The first real, paid call to `write_report` - after `ANTHROPIC_API_KEY` was
finally working and the previous logging fix let the real error surface -
came back `400 Bad Request: "Schema is too complex."` from Anthropic
itself, not from any bug this codebase's own error handling could catch.
The original `_TOOL["input_schema"]` required only `"type"` on each
segment, leaving twelve properties genuinely optional (`display`, `label`,
`value`, `operands`, `total_exact_text`, ...). Strict-mode tool use
compiles the schema into a grammar, and a schema with that many optional
properties on one object forces the compiler to represent every possible
combination of which ones are present - exactly the kind of blowup real
users have hit and reported upstream (this is a known, if under-documented,
strict/structured-output limitation, not unique to this schema).

No mocked test could have caught this - every test in
`tests/test_l2_analyze.py` patches `client.messages.create` directly, so
the real schema is never sent to Anthropic's real validator. This is the
first defect only a genuine, paid API call could surface.

Fixed by making every property required and replacing "is this key present"
with explicit `has_value`/`has_total` booleans - a segment that doesn't use
a field still supplies a placeholder (`""`, `0`, `[]`, `"none"`) and the
flag says whether to look at it. This removes the combinatorial optionality
entirely (every segment object now has exactly one shape) at the cost of a
longer system prompt and a few more required keys. `_verify_quote` and
`_verify_computed` in `analystos/l2/analyze.py` now branch on the explicit
flags instead of key absence; existing tests updated to set them. Added
dedicated positive/negative tests for `has_total` specifically, since that
branch (`percent_of_total`) had no direct test coverage before.

## 2026-09-05 — Log the real Anthropic failure server-side, not just a generic message

Found immediately after the previous fix went live: the client-facing
message ("analysis is temporarily unavailable") is deliberately generic -
it has to be, since `anthropic.APIError`'s own text can carry account/
request detail that shouldn't reach a client response. But that means a
bad key, missing billing, a rate limit, a wrong model name, and a real
Anthropic-side outage are now genuinely indistinguishable from the outside
- including to me, debugging this from outside Vercel's dashboard. Nothing
printed the real exception anywhere, so a handled `ValueError` left no
trace at all in the function logs.

Fixed by printing the real `anthropic.APIError` (`repr(exc)` - the SDK's
own error text, which does include the useful part like an HTTP status
code) to stderr before converting it, right where it's caught in
`analystos/l2/analyze.py`. Server logs only, never the response body -
that boundary is unchanged. Vercel's function logs are the actual next
diagnostic step for the real live-test failure this follows.

## 2026-09-05 — A missing API key must fail clean too, not just a bad call

Found via a real live test: the first Anthropic error-handling fix only
caught `anthropic.APIError` around `client.messages.create(...)`, on the
assumption that any auth problem would come back from Anthropic's server as
an API-shaped error (`AuthenticationError`, a subclass of `APIError`). A
completely missing or empty `ANTHROPIC_API_KEY` doesn't reach the server at
all - the SDK can't build an authenticated request and raises a plain
`TypeError` ("Could not resolve authentication method") from inside that
same call, which the `except anthropic.APIError` clause never sees. That
crashed as a raw, unhandled Flask 500 instead of the intended clean 400.

Fixed in `analystos/l2/analyze.py` by checking the constructed client's
`api_key` *before* the call, only on the production path (`client=None`,
where a real `anthropic.Anthropic()` is built) - tests that patch in a
bare stand-in client have no `api_key` attribute at all, so
`getattr(client, "api_key", "present")` leaves them alone and this doesn't
change any existing test's behavior. Confirmed the exact `TypeError`
reproduces with the fix reverted and the new test in place, and that it's
gone with the fix applied.

## 2026-09-05 — Upload page: narrated analysis is now the default, not just the API's

Found while preparing a real live test: `site/upload.html` had a hardcoded
`<input type="hidden" name="template" value="income_statement">`, sent on
every submit regardless of the schema field's contents. `api/analyze.py`
already treats an omitted `template` as the new Slice 26 narrated-analysis
default, but the live page could never actually omit it - every upload,
table-shaped or not, was silently forced through the old column-by-column
path. A non-tabular document (a memo, a slide deck) would fail there since
there's no table to extract, which is exactly the case the new default
exists to handle.

Fixed by removing the hardcoded field. The page now defaults to the
narrated path (no `template`, no `schema` sent) and only sends
`template=income_statement` when a new "this file is a table shaped like an
income statement" checkbox is explicitly checked - which is also the only
case that shows the Detect columns/schema UI at all. `tests/test_upload_page.py`
updated to match: it no longer asserts a static `name="template"` attribute
exists (there isn't one any more) and instead asserts the checkbox and the
JS that conditionally sets `template` are both present.

## 2026-09-05 — Anthropic API failures fail clean, not with a raw 500

Follow-up to Slice 26, prompted by setting up the real `ANTHROPIC_API_KEY`
and a monthly spend cap: `analyze_document` only wrapped verification
failures in `ValueError`, which is what `api/analyze.py` converts to a
clean `400`. A failure in the API call itself - a hit spend limit, a bad or
revoked key, a rate limit, an Anthropic-side outage - raises some
`anthropic.APIError` subclass instead, which would have passed through
uncaught and surfaced as a raw, unhandled `500`. Fixed by catching
`anthropic.APIError` (the common base for every SDK-raised failure - status
errors and connection errors alike) around the one API call and re-raising
as a `ValueError` with a generic message ("analysis is temporarily
unavailable") - never the raw exception, which can carry account or request
detail that shouldn't reach a client response. Means hitting your own spend
cap now fails the same clean way every other pipeline error already does,
instead of looking like the site is broken.

## 2026-09-05 — Narrated analysis: read any document, verify every number (Slice 26)

Prompted directly by a live gap: the only template (`income_statement`)
requires a period-like column, so a file that's genuinely tabular but isn't
shaped like an income statement (a company/revenue/employee list, say)
failed cleanly rather than producing a report. Working through what "no
restrictions" should actually mean landed on a real architecture change,
not an addition - `docs/architecture.md`'s L2 was already described as
"retrieval + analysis... every claim points back into L0"; what shipped
through Slice 25 was a deliberately thin first slice of that, not its
ceiling.

**What changed, and why, in the order the design actually evolved during
building:**

- **Not forced into a table.** `analystos/l1/document_text.py` reads a
  document's real text content - paragraphs, bullet points, table cells
  rendered as readable text - the same way for all five supported formats.
  A memo or a slide deck with no table at all now reads the same as a
  spreadsheet; nothing requires row/column structure to exist.
- **A model reads the whole thing and decides what matters; it never
  supplies a number.** `analystos/l2/analyze.py` sends the real document
  text to Claude and gets back a structured list of segments (via strict
  tool use, not free text) - each a quote, a computed value, or plain
  connective prose. A quote gives `exact_text` the model claims is verbatim
  in the source; this code checks that with an actual substring match
  against the real text - not "the model says so." A computed value (a
  sum, a ratio, a growth rate, a share of total) gives its own raw operands
  the same way, *plus* the operation and the model's claimed result - and
  this code *independently recomputes* that arithmetic and checks it
  matches. This second check is the reason a citation alone isn't enough:
  it proves a quote is real, but says nothing about whether math performed
  on top of it is correct - a real gap surfaced explicitly while designing
  this, not caught by accident. Prose is scanned for stray digits and
  rejected if any appear - no number ever reaches the report without going
  through one of the two checks above. A segment that fails verification is
  dropped, not shown, not retried; a report where *nothing* survives is a
  real `ValueError`, never a silent partial success.
- **A number renders as a number when that's the point.** Each segment
  carries its own `"display"`: `"stat"` for a standalone labeled figure,
  `"inline"` for a sentence with context. The model chooses per figure,
  not a global setting.
- **Model: Claude Sonnet 5, not Opus 5** - overriding Anthropic's own
  default-to-Opus guidance for one disclosed, concrete reason:
  `api/analyze.py` runs as a Vercel function with a real 10-second
  wall-clock ceiling. Opus 5's always-on extended thinking makes that a
  real timeout risk for a bounded, structured-output task like this one;
  Sonnet 5 reliably finishes well inside it. A one-line change to revisit
  if the Vercel plan changes or quality disappoints.
- **A new required secret, `ANTHROPIC_API_KEY`, on Vercel** - separate from
  anything used to build this code - and a new, real, small, ongoing
  per-report dollar cost that didn't exist before this slice.
- **This is the new default, not a replacement.** `build_report` now runs
  this path when *neither* `asks` nor `template` is given at all - the
  original schema/table-driven path (explicit `asks`, or
  `template="income_statement"`) is completely unchanged and still costs
  nothing extra to run; this only fires when nothing else was specified,
  which is the new default for the live API/site.
- **Disclosed, accepted residual risk:** a text value from the source
  (e.g. a company name) still reaches the model as data it can quote or
  reason about, with an explicit system-prompt instruction that all such
  values are data, never instructions - a standard, imperfect mitigation.
  Verification catches every fabricated *number*; it cannot catch
  manipulated *wording* smuggled in through a text field the model quotes
  or paraphrases around.
- **Tested entirely against a mocked Anthropic client** - this session had
  no `ANTHROPIC_API_KEY` and no way to reach the real API, so the test
  suite verifies the logic (a fabricated quote is rejected, fabricated math
  is rejected even with real cited numbers, prose with a stray digit is
  rejected) deterministically, with no cost and no network dependency. Real
  output quality - whether Claude actually produces good, well-chosen
  analysis in practice - can only be confirmed once a real key is set and
  a real request is made.

## 2026-09-05 — Real production bug: /api/extract 404'd on Vercel

Confirmed live, right after `ANALYSTOS_ACCESS_CODE` was finally set on the
Vercel project (the one open item from Slice 22): `/api/extract` (Slice 25)
returned Vercel's own 404 page ("The page could not be found"), never
reaching our code at all - while every local test for it passed.

Root cause: exactly the file-based routing model researched and recorded
here for Slice 20 - one `.py` file in `api/` maps to one route matching
*its own path* (`api/analyze.py` -> `/api/analyze`), regardless of what
routes a file's Flask app defines internally. `/api/extract` was added to
the same shared app inside `api/analyze.py` instead of its own file, so
Vercel had no file to map that path to. Flask's test client bypasses this
entirely - it calls the app object directly - so nothing in the test suite
could have caught it; this was exactly the "only confirmable once deployed"
residual risk Slice 20's own entry already flagged, now realized for real.

Fix: `api/extract.py`, a one-line file that just re-exports the same shared
`app` object from `api/analyze.py`. Gives Vercel a matching file for
`/api/extract` while keeping exactly one implementation of every route -
two file-based doors into the identical app, not a second app or duplicated
logic. A regression test (`tests/test_api_vercel_routing.py`) checks both
files resolve to the identical app object with both routes registered, so
this can't silently regress if a third route gets added the same way.

## 2026-09-04 — Universal upload: auto-detected schema, PDF's constraint
generalized instead of special-cased (Slice 25)

Prompted directly by feedback that an analyst shouldn't have to know which
of 4 extensions were accepted or hand-type an exact JSON schema before the
system would touch their file - and that's correct once a table is
extracted, format has never mattered to L0/L2/L4. Two real changes:

- **Schema auto-detection, not elimination.** `analystos.l1.schema.guess_schema`
  guesses `"number"` vs `"text"` per column using the exact same
  `_clean_number_token` cleaning `apply_schema` already applies when typing
  a value - so a guessed schema and a hand-typed one behave identically once
  resolved. An explicit schema is still honored exactly as before; nothing
  is guessed when one is given. `analystos/scaffold.py`'s own CSV-only
  guessing heuristic (duplicated since Slice 9) was replaced by this shared
  one - a real behavior improvement in passing, since scaffold's own
  `float(value)` check missed `$`/comma/`%`/paren-formatted numbers that
  the shared cleaner already handled correctly.
- **PDF's real constraint (a table inferred from layout, not read from a
  real object, so it can be misread) doesn't go away - it becomes universal
  instead of PDF-only.** Every format now gets a preview step
  (`POST /api/extract`) before a report is generated, not just PDF; PDF's
  preview additionally carries a warning. This is what actually let PDF
  join `api/analyze.py`/`site/upload.html` for the first time - the
  "PDF needs its own review-step UI" gap Slices 20/21/23 all flagged is
  closed by this same mechanism, since every format already needed one.
  The confirm-before-cite gate itself (Slice 23) is unchanged in behavior;
  it's satisfied via a `pdf_confirmed` form field once the browser has
  shown the preview, the same way Slice 23's CLI job.json flag always did.

Found and fixed a real bug while building this: `guess_schema` originally
scanned its `numbered_raw_rows` argument once per header, silently starving
every header after the first when called with a one-shot generator
(`scaffold.py` passed `enumerate(rows, ...)` directly) - only the first
column ever got real data, everything else guessed "text". Fixed by
materializing the argument inside `guess_schema` itself, so no caller has
to know it's scanned more than once; a regression test
(`test_a_one_shot_iterator_still_works_for_every_header`) locks this in.

## 2026-09-04 — PDF output: reportlab put to its actual use (Slice 24)

`reportlab`, pinned since Slice 23 for test fixtures only, is now used for
its actual intended purpose: `analystos.l4.export.render_pdf` builds a real
generated `.pdf` from a rendered section - a title, one paragraph per
finding, a rule, then footnotes - mirroring `render_html`'s layout via a
shared `_parse_section` helper so there is exactly one place that parses a
section string, not two. Verified directly before finalizing this design:
built a real `reportlab` document with a superscript marker and a bold
footnote number, then read the exact expected text back out with
`pdfplumber` - title, body sentence, and footnote citation all present.

Scoped to L4/CLI only, matching Slice 23's own discipline: `api/analyze.py`
and `site/upload.html` are untouched. A real PDF *download* on the live
site is a genuine, separate product decision (a new API response shape, a
UI affordance) worth its own scoped slice, not a rider on this one - until
then the live MVP's only path to a PDF is still the browser's own Print.
`[n]` footnote markers render as plain superscripts in the PDF, not
clickable links like the HTML version's same-page anchors - a PDF has no
equivalent low-effort mechanism, a disclosed gap, not an oversight.

## 2026-09-04 — PDF input: pdfplumber, and pulling reportlab forward (Slice 23)

`pdfplumber==0.11.10` for table extraction — verified directly before
writing the extractor, not just read about: a real bordered table built with
`reportlab` and read back with `pdfplumber.page.extract_tables()` came back
as exactly the right rows. Installs with no system dependencies — its own
deps (`pdfminer.six`, `Pillow`, `pypdfium2`) all ship self-contained wheels,
no Poppler/Ghostscript/Java needed - the same Vercel-serverless-friendly
reasoning already used to pick `reportlab` over `weasyprint` for output.
Rejected `camelot` (needs Ghostscript) and `tabula-py` (needs Java) for that
same reason.

Also added `reportlab==5.0.1` now, a slice early — but for tests only. Every
other format extractor's tests build their own fixture file at test time
with that format's own writer library (`openpyxl` for `.xlsx`, etc.); a real
PDF table `pdfplumber` can reliably detect needs actual ruling lines, so
*something* has to write a real PDF for `tests/test_l1_extract_pdf.py`.
Using the PDF-writing library already decided on for Slice 24 beat inventing
a second, throwaway one just for tests. Slice 24 is still the slice that
wires `reportlab` into `analystos/l4/export.py` for real report output.

Because a PDF table is inferred from visual layout, not a real structured
object, `analystos.pipeline.build_report` refuses to build a report from a
`.pdf` source until the job explicitly says `"pdf_confirmed": true` - a
non-interactive flag, not a terminal prompt, since the CLI's execution model
has no `input()` anywhere and shouldn't gain one just for this. The error
raised without that flag includes the actual extracted table, so the
"confirm" step is real: whoever runs it sees exactly what needs reviewing
before they can flip the flag and re-run. Correcting a misread value isn't
supported yet - accept-as-extracted-or-don't-use-it - and `.pdf` stays
unsupported by `api/analyze.py`/`site/upload.html`, since a stateless HTTP
request has no natural place for this kind of human-in-the-loop gate without
a real review UI (already named in `ROADMAP.md` as the reason PDF was pushed
after the MVP).

## 2026-09-04 — Access gating: one shared code, not accounts (Slice 22)

`api/analyze.py` and `site/upload.html` went live in Slices 20-21 with no
access control at all, deliberately deferred to this slice. The gate: a
single shared secret, read from the `ANALYSTOS_ACCESS_CODE` environment
variable and required as an `X-Access-Code` header on every request,
compared with `hmac.compare_digest` and **fail-closed** (a `500`, not open
access) if the variable is ever unset.

- Real per-analyst accounts are out of scope here on purpose - this is a
  small, hands-on preview with a handful of real analysts (`ROADMAP.md`'s
  NOW milestone), not a public product. Accounts are R1/R2 work, once there's
  an actual cohort to manage identity for.
- No rate limiting on the code itself - accepted, disclosed tradeoff. The
  point is keeping this off search engines and drive-by visitors, not
  standing up to a targeted attacker who's decided to guess it.
- One manual step this repo's code can't do for itself: `ANALYSTOS_ACCESS_CODE`
  has to actually be set on the live Vercel project (dashboard -> Settings ->
  Environment Variables) before the deployed endpoint is gated for real -
  same category of "only confirmable post-deploy" residual risk Slices 20-21
  already flagged.

## 2026-09-04 — How Python actually deploys on Vercel (researched before Slice 20)

Checked Vercel's own docs rather than guessing, since the Root Directory
picker earlier already showed guessing wrong costs a real deploy cycle.
Findings, current as of this date:

- Vercel supports file-based Python functions in an `/api` directory:
  each `.py` file there becomes its own route (`api/analyze.py` ->
  `/api/analyze`). The file must define a top-level `app` (WSGI/ASGI) or
  `application` (WSGI) object, or a `handler` class extending
  `BaseHTTPRequestHandler`. Flask's `app` object satisfies this directly.
- **Caveat found in the same docs**: if Vercel detects a Python "framework
  preset" for the project (from a matching dependency in `requirements.txt`),
  the framework takes over *all* routing, and `/api/*.py` stops being
  treated as file-based functions. Our project was already configured as a
  static site (Output Directory override to `site/`, from the earlier
  Root Directory workaround) before `flask` was ever added to
  `requirements.txt` - the working assumption is that an already-configured
  project keeps its existing routing rather than being silently
  reclassified, since Vercel's own docs describe the file-based `/api` model
  specifically as being for "existing projects." **This is not confirmed by
  an actual deploy** - only verifiable once it's live.
- Added `vercel.json` with an explicit `functions` config for `api/*.py`
  (the exact pattern shown in Vercel's docs) rather than relying purely on
  auto-detection, to make the intent unambiguous.
- Chose the file-based `app.py`-style entrypoint (Flask, WSGI) specifically
  because it means requests are parsed through Flask's own `request.files`
  API - the same code path whether running via `flask run` locally or
  wrapped by Vercel's Python runtime - rather than hand-parsing multipart
  form data against a raw `BaseHTTPRequestHandler`, which would be Vercel
  runtime-specific and much easier to get subtly wrong.

## 2026-09-04 — Known risk: nothing verifies a "format" matches the data's real scale

Found while demoing Slice 17: an ask can declare `"format": "usd_millions"`
on a column whose values are actually raw dollars (or vice versa), and
nothing catches it. The result isn't an error - it's a confidently wrong
number (a $150,000 loss rendered as "($150.0B)"). This is exactly the
failure mode the whole hardening effort is meant to prevent, and it isn't
fixed yet. Candidate for the report-template slice (renumbered to 19 - moved
earlier when PDF was pushed after the MVP): a template that generates the
asks could also know - or sanity-check - the expected scale, rather than
leaving it to whoever writes `job.json` to get right by hand.

**Update, same day, demoing Slice 18:** hit the identical mistake again -
`usd_millions` on raw-dollar PowerPoint figures produced "$4,200.0B" instead
of "$4.2M", no error either time. Two for two. This is not a one-off typo
risk, it is a genuinely easy mistake, which raises the priority of fixing it
in Slice 19 rather than just documenting it.

## 2026-09-04 — First third-party dependencies: a live MVP, multi-format input

Ending the stdlib-only period from Slice 1. Reason: a live, browser-based MVP
("upload a document, get a report") needs things the standard library
genuinely doesn't do well — reading Excel/Word/PowerPoint/PDF files, and
running a web server.

- **Hosting: Python + Vercel**, not a separate always-on server (Render/Fly).
  Keeps everything on one host Caleb already knows. Consequence: Vercel's
  Python functions are WSGI, so the web layer will be **Flask**, not FastAPI.
  Free-tier functions time out at 10s — fine for CSV/Excel/Word/PowerPoint
  (sub-second), a real constraint once PDF extraction is in the request path;
  revisit hosting then if it becomes an issue.
- **Input formats, in order: Excel → Word → PowerPoint → PDF.** The first
  three are structured data (a cell/table object, not an inferred layout) —
  same reliability guarantee as CSV, no review step needed. **PDF is
  different**: table extraction infers column boundaries from a page's visual
  layout and can be wrong. Because the product's entire premise is "every
  number is defensible," a PDF-extracted table is never cited directly — it's
  shown to a person to confirm or correct first. Scanned/image PDFs (which
  need OCR) are explicitly out of scope: OCR is slow and would blow the
  10-second Vercel limit, and it's a different, heavier problem.
- **Output: a real generated `.pdf`**, not "open the HTML and print." Chosen
  library: **`reportlab`**, not `weasyprint` — weasyprint needs system
  graphics libraries (Cairo/Pango) that don't reliably install on Vercel's
  serverless functions; reportlab is pure Python with no system dependencies,
  so it won't work locally and silently fail in production.
- Each dependency is added in the slice that needs it, pinned exactly in
  `requirements.txt`, with the reason recorded here - not all at once.

## 2026-09-03 — Build in Python

Chosen over TypeScript / Node for the first slices.

- Python 3.14 and pip are already installed on the build machine; no setup cost.
- The hard parts of AnalystOS — document extraction (L1) and reasoning (L2) —
  have their strongest libraries in Python.
- Trade-off accepted: the FlashyOS mesh CLIs (`@flashyos/aao`, `@flashyos/agent`)
  are npm packages, so Node will be added later as its own slice when the
  manifest work (Slice 7) needs it.

## 2026-09-03 — Standard library only, for now

No third-party packages and no virtual environment until a slice explicitly
needs one (expected at Slice 4, document parsing). Keeps the skeleton trivial
to run and to review.
