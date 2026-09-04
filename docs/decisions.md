# Decisions

Dated log, newest first. One entry per real choice, with the reason.

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
