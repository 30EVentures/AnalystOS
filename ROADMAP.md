# AnalystOS — roadmap

Working view. The boardroom version is the "Revision A" dossier; when they
disagree, **this file wins**. Windows are targets, not commitments.

## Blocked / needs input

Items the loop cannot do without you. Each says what is needed.

- [ ] **Confirm 30E Ventures controls the `analystos` org** - needs you to sign in at app.flashyos.com as that org (a credential only you hold).
- [ ] **Mint an agent token and declare capabilities (FlashyOS Level 3, the mark)** - needs the org sign-in above; the token is shown once and must be stored by you in a secret manager, never in the repo.
- [ ] **Publish the seal signing key's public half and set `ANALYSTOS_SEAL_KEY` on Vercel** - needs you to generate the key (`python3 -m analystos.l4.seal keygen`) and set the secret; also `ANALYSTOS_API_KEYS` before the API can be used.
- [ ] **Latency and cost per document type through the API** - needs your `ANTHROPIC_API_KEY` and real spend (the live suite has a $1.00 ceiling).
- [ ] **Enforce GAAP / guidance labels against the source** - a decision: checking only the citation text would strip true labels whose evidence sits in a table header, so the rule (drop, downgrade, or flag) needs your call and real failing examples.
- [ ] **Stance on Gord Holdings' interest in "a piece of everything built on top"** - a business decision (equity/IP).
- [ ] **Per-key spend caps and a durable rate limiter** - needs a durable store, which the Downloads-only decision deliberately avoids; revisit if the API gets real callers.
- [ ] **R3+ (KPMG pilot, SOC 2, multi-tenant control plane)** - out of scope for an unattended loop.

## Working queue (unblocked, in priority order)

Each item gets a `specs/slice-N/spec.md` first, tests, a commit, and a line in
the session log. Nothing here is pushed until you say so.

- [x] **Q1 - Round half up when displaying figures** (audit finding 11): a source `$1.95B` must not display as `$1.9B`; `12.25%` must not display as `12.2%`. Accept: a table of half-way cases across usd/percent/number formats renders half-up; existing outputs otherwise unchanged; suite OK.
- [x] **Q2 - Make the spec record honest** (audit finding 9): `specs/README.md` indexing every slice, naming slices 35-39 (built without a spec) and 14 (empty); fix the code comment that cites a nonexistent spec. Accept: no source file cites a missing spec; a test keeps it that way.
- [ ] **Q3 - Standalone verifier checks a quote's value against its citation** (closes the biggest gap in `docs/seal.md`): port the number parser, scale words, accounting negatives and document scale. Accept: differential test against the analyzer across a sample; a tampered value is caught even when hashes are rebuilt.
- [ ] **Q4 - Live-suite PASS means something** (audit finding 8): assert the expected tier and minimum fact counts, not only "did not raise". Accept: mocked tests prove a fallback fails the check; docs say what PASS means. (No paid run here.)
- [ ] **Q5 - Post-deploy smoke script** (`tools/smoke.py`): one command that checks every advertised URL on a live domain. Accept: passes against a local server of `site/`, fails on a missing file and a wrong content type.
- [ ] **Q6 - Stop hand-maintaining the homepage's test and spec counts**: a tool writes them and a test fails when they drift. Accept: `--check` and `--write` modes; suite enforces.
- [ ] **Q7 - Model name configurable** (R2 "model-swap"): one setting instead of four hard-coded strings. Accept: default unchanged; env override honoured everywhere the model is named.
- [ ] **Q8 - Cleanup pass** when the queue is empty: dead code, TODOs, coverage gaps.

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

### Since Slice 28 — quality, hardening, and the mesh groundwork

Recorded from the specs (`specs/slice-N/spec.md`) and `docs/decisions.md`.
Slices 35-39 were built without a spec of their own (see the audit).

- Slices 29-34 — extraction contract and horizon tags; the structured narrator
  wired end to end; dated events as verified facts; verification that survives
  real filings; the output-token ceiling.
- Slice 40 — repair instead of regenerate, for both quality gates.
- Slices 41-43 — per-IP rate limiting; an in-code API-call budget; L0
  encryption at rest and a retention policy.
- Slices 44-47 — one table-parsing standard; GAAP vs non-GAAP labels;
  boilerplate exclusion; organic-vs-inorganic splits; code-owned chart type.
- Slices 48-54 — a real server-side PDF; Gate 2's prose rubric; multi-column
  PDFs and image-derived facts; the paid live-test suite; the mandatory
  deterministic floor and two root-cause fixes to it.
- Slice 55 — Gate 1 checks a change's named endpoints and refuses
  spelled-out quantities.
- Slice 56 — one definition of a figure's basis, shown on KPI tiles, charts,
  text and footnotes.
- Slice 57 — public claims corrected to match the code.
- Slice 58 — an AAO checker that follows the published schema, with rule codes.
- Slice 59 — the `flashyos/1` handshake and AAO charter, in the repo (not
  deployed).
- Slice 60 — narrated reports are sealed (Merkle root, optional Ed25519) with a
  standalone verifier.
- Slice 61 — `/api/v1`: analyses, stored reports, signed links, verification,
  OpenAPI (storage not durable on Vercel).
- Slice 62 — machine navigation (`llms.txt`, API catalog, docs as markdown) and
  documentation brought up to date.
- Slice 63 — reports are handed back as files for the reader's Downloads folder
  (PDF and seal returned by the API; three download buttons on the upload page);
  server-side storage is off by default.

**Deployed 2026-09-26** (Slices 55-63). Verified live: the well-known files, headers,
API routes and rewrites, and FlashyOS Level 2. Not yet exercised in production: a
real analysis upload and the new download buttons.

## R1 — trusted on one desk (Oct–Dec 2026)

Attestation v1; weekly test cohort ~15.

Mesh, in this order (evidence and open questions:
`docs/flashyos-alignment-2026-09-25.md`):

1. Resolve the `analystos` org that already exists on the FlashyOS network
   (created ~2026-09-03, 0 agents, capability `analytics`, owner unknown) -
   claim it or agree its fate before creating anything. **Answered by the owner
   (30E Ventures, 2026-09-26); confirm by signing in as that org.**
2. Serve `/.well-known/flashyos.json` and `/.well-known/flashyos-charter.json`
   on the production domain. **Done: deployed 2026-09-26 (Slices 59-63).**
3. Run `npx @flashyos/conformance <domain> --level 2`. Levels 1-2 are
   self-claimed and need no account. Level 3 (authorized / revocable /
   auditable) is read from FlashyOS's register and cannot be declared. **Run
   2026-09-26: Level 1 and Level 2 pass** (`@flashyos/conformance` 0.2.3). Level 3
   is not attempted.
4. Replace the invented rules in `analystos/aao/validate.py` with the published
   schema plus its documented cross-field rules, emitting machine-readable
   codes. **Done (Slice 58).**
5. Only then: sign in at app.flashyos.com, mint an agent token, declare a real
   capability. **Not started**; the callable endpoint it would point at exists
   (Slice 61) but is not deployed, and its storage is not durable.

Not in R1: "analysis calls fulfilled for other AAOs" through the mesh. The
endpoint and the signed, expiring report URL exist (Slice 61), but they need
durable storage, a deployment, and a counterparty. Open questions are in the
alignment doc, section 8.

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

Public multi-tenant, module SDK. Cross-organization discovery and delegation
as FlashyOS actually specifies them today
(`docs/flashyos-spec-notes-2026-09-25.md`):

- Discovery: an org that is public and declares at least one capability
  appears in the public directory; matching is exact on the canonical
  capability tag.
- Delegation: an agent joins an ACTIVE joint initiative, claims a task, and
  completes it with an https evidence URL (optionally plus a `shipEvidence`
  `{entryId, sha256}`). A human at each org must consent to the initiative;
  agents cannot propose one.
- Governance v1 records decisions but does not enforce them, so any control
  has to live in AnalystOS's own runtime.

None of this is buildable until R1's mesh steps are done.

## Cadence

- **Every session:** one slice through the full loop; one branch, one PR, one note.
- **Every week:** real users on the real build; update the friction log;
  re-rank the next slices; re-check flashyos.com/aao, /standard, /open.
- **Every phase:** check the gate number; tag a release; refresh the dossier.

## Session log

One line per completed item (newest last).

- 2026-09-27 - queue and blocked list written; loop started on branch `roadmap-loop-2026-09-27` (nothing pushed).
- 2026-09-27 - Q1 done (Slice 64): displayed figures round half up; 683 tests.
- 2026-09-27 - Q2 done (Slice 65): specs/README.md index with marked gaps (14, 35-39); dangling spec citation fixed; 687 tests.
