# AnalystOS — roadmap

Working view. The boardroom version is the "Revision A" dossier; when they
disagree, **this file wins**. Windows are targets, not commitments.

## NOW — the thin slice (Sept 2026)

Prove the core loop on one real document set, in front of 3–5 real analysts.

- Slice 1 — repo skeleton + test harness            ✓ done (PR #1)
- Slice 2 — L0: store one source, return its hash    ✓ done (PR #2)
- Slice 3 — L0: retrieve a source by its hash        ✓ done (PR #3)
- Slice 4 — L1: extract one table to structured data ✓ done (PR #4)
- Slice 5 — L2: answer one question with a citation  ✓ done (PR #5)
- Slice 6 — L4: export one working-paper section with the citation trail  ✓ done (PR #6)
- Slice 7 — the AAO manifest + a local Python check  ✓ done (PR #7)
- Slice 8 — glue: one command runs L0→L4 on the golden set  ✓ done (PR #8)

**Build complete (8/8).** **Milestone done when:** a real analyst completes one
real task end to end and reaches for it again unprompted.

Run it: `python3 -m analystos fixtures/golden`

### NOW+ — make it usable by an analyst (not just a developer)

- Slice 9  — scaffold a job.json from a CSV                 ✓ done (PR #9)
- Slice 10 — write the section to a file automatically      ✓ done (PR #10)
- Slice 11 — a one-page "how to use this"                   ✓ done (PR #11)
- Slice 12 — L2 computed metrics (growth %, ratio %)        ✓ done (PR #12)
- Slice 13 — styled section.html that auto-opens (→ PDF via Print)  ✓ done (PR #13)
- Slice 15 — harden for real-world data + executive-ready numbers   ✓ done (PR #16)

### Site

- `site/` — early-access landing page, live at
  [analyst-os-phi.vercel.app](https://analyst-os-phi.vercel.app) (PR #14, #17),
  deploys automatically from `main`.

### Live MVP — upload a document, get a report, in a browser

Decision record: `docs/decisions.md`, 2026-09-04. Python + Vercel (Flask, not
FastAPI); structured formats (Excel/Word/PowerPoint) trusted directly, PDF
extraction always confirmed by a person before it's cited; real `.pdf`
output via `reportlab`.

Reordered 2026-09-04: PDF (input + output) moved to *after* the MVP ships,
not before — it needs its own review-step UI and shouldn't gate a live,
testable product that already covers four real document formats.

- Slice 16 — L1: Excel (.xlsx) input, first dependency (`openpyxl`)  ✓ done (PR #18)
- Slice 17 — L1: Word (.docx) table input  ✓ done (PR #19)
- Slice 18 — L1: PowerPoint (.pptx) table input  ✓ done (PR #20)
- Slice 19 — report templates: auto-generate the standard asks from
  recognized columns; also fixes the format-scale risk (see decisions.md)  ✓ done (PR #21)
- Slice 20 — the API: `api/analyze.py` (Flask, on Vercel)  ✓ done (PR #22)
- Slice 21 — the upload page on `site/`  ✓ done (PR #23)
- Slice 22 — access gating (not public on day one)  ✓ done (PR #25)

**→ MVP live here: upload a CSV/Excel/Word/PowerPoint file in a browser,
get a cited report back.**

- Slice 23 — L1: PDF input — extraction + human confirm-before-cite step  ✓ done (PR #27)
- Slice 24 — L4: real `.pdf` output (`reportlab`)  ✓ done (PR #29)

### Beyond the original MVP — no format/shape restrictions

Prompted by live use: the original MVP's one template (`income_statement`)
only worked on data shaped like an income statement. Fixed in two steps,
both recorded in full in `docs/decisions.md`, 2026-09-05.

- Slice 25 — universal upload: auto-detected schema (no more hand-typed
  JSON), every format treated the same, PDF joins the live site/API for
  the first time  ✓ done (PR #31)
- Slice 26 — narrated analysis: read any document, table-shaped or not;
  a model chooses what's worth reporting, but every number is either a
  real quote verified against the source or a computed value with its
  arithmetic independently recomputed - never taken on the model's word.
  New required secret (`ANTHROPIC_API_KEY`, on Vercel) and a real, small,
  ongoing per-report cost  ✓ done (PR #33)

**→ Any of the five supported formats, any shape of data, now produces a
real, cited report - the original "income statement only" limit is gone.**

### Toward Fortune 10 exec-quality reports

Backend-first plan agreed 2026-09-06: raise writing quality, let the user
choose the output shape, add a feedback/revision loop, harden for scale,
then build the frontend controls last. Full plan in `docs/decisions.md`.

- Slice 27 — a second, narrower model call decides how to write about
  Slice 26's already-verified facts (real structure/grouping instead of
  one paragraph per fact in extraction order); it can only reference a
  fact by placeholder, never state a number, and any failure falls back
  to Slice 26's plain rendering rather than losing the report  ✓ done
  (PR #39) - live-tested repeatedly (Tests #2/#3); found and fixed a real
  verification gap and a false-positive digit-ban rule along the way
  (PRs #40, #41, #42) - a real narrative-pass success is still unconfirmed
- Slice 28 — rich report rendering: real inline-SVG charts, section-by-
  section structure with an executive summary, and a visually distinct
  "outlook" block that can't be mistaken for a verified fact. Builds only
  the rendering side (`analystos/l4/charts.py`, `rich_export.py`),
  proven against a hand-authored mock run through the real render code -
  deliberately does not yet wire a model into deciding chart placement/
  section structure, which is its own follow-up  ✓ done (PR #43) - not
  yet live-tested (no L2 stage produces this shape yet)

## R1 — trusted on one desk (Oct–Dec 2026)

Attestation v1 (answers the seven AAO questions); weekly test cohort ~15;
first analysis calls fulfilled for other AAOs on the mesh.

## R2 — hardened at Gord (Q1–Q2 2027)

Policy engine, append-only audit, model-swap, SOC 2 Type I track; runs
unattended on a Gord production workflow; external security review.

## R3 — KPMG pilot (Q3 2027 – Q1 2028)

Methodology templates, single-tenant deployment, review workflow; one service
line, 2–3 geographies, ~500 analysts.

## R4 — KPMG global + open attestation format (2028–2029)

Multi-member-firm control plane, residency, SOC 2 Type II; the
analysis-attestation wire format published open with a conformance suite.

## R5 — the analysis layer of the mesh (2030+)

Public multi-tenant, module SDK, discovery + delegation across AAOs.

## Cadence

- **Every session:** one slice through the full loop; one branch, one PR, one note.
- **Every week:** real users on the real build; update the friction log;
  re-rank the next slices; re-check flashyos.com/aao, /standard, /open.
- **Every phase:** check the gate number; tag a release; refresh the dossier.
