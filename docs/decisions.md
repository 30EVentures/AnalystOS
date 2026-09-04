# Decisions

Dated log, newest first. One entry per real choice, with the reason.

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
