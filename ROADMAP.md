# AnalystOS — roadmap

Working view. The boardroom version is the "Revision A" dossier; when they
disagree, **this file wins**. Windows are targets, not commitments.

## Blocked / needs input

Items the loop cannot do without you. Each says what is needed. Re-checked 2026-11-21
against the live GitHub history and the Flashy estate's 18/21 Nov integration documents
(session `flashyos-standardization-2026-11-21`); items resolved since the last pass are
struck through and dated, new ones from the Flashy exchange are added at the end.

- [x] ~~Publish the seal signing key's public half~~ - done, PR #89 (2026-11-20), `site/.well-known/analystos-seal-key.json`, key id `5d31bfc65a326e3c`.
- [x] ~~Set `ANALYSTOS_SEAL_KEY` and `ANALYSTOS_API_KEYS` on Vercel~~ - owner confirms both are set, 2026-11-22.
- [x] ~~Confirm 30E Ventures controls the `analystos` org~~ - owner confirms, 2026-11-22. Verified live: `npx @flashyos/agent init --org analystos --agent analystos-agent` resolved the existing org (`cmtkurcbs00je12tigb1rc6t1`), not a duplicate, and connected successfully.
- [x] ~~Declare capabilities (FlashyOS Level 3, the mark) - rotate the token, generate decision records~~ - both resolved 2026-11-22, Slice 104. **Token rotation**: no script needed - `@flashyos/agent`'s own README confirms re-minting an agent (same `init` command, same name) rotates its token; done for real, `analystos-agent`'s original never-expiring token is retired. **Decision records**: endpoint confirmed by reading `@flashyos/agent@0.21.0`'s own published source (not guessed) - `POST /api/v1/orgs/{orgId}/decisions`. `ops/flashy_decide.py` mirrors it, prepared and tested, not yet called against any real action (an outward decision, per-use, regardless of confirmation). Role names in the handshake were already declared, Slice 94. The third L3 criterion (verified domain) is Flashy's and has not started.
- [ ] **Re-mint and use the join-grant tokens Michael minted 2026-11-21** - the ones pasted into chat that day are compromised (they travelled through a terminal log into a conversation) and must not be used; ask Flashy to re-mint, store the replacements as secrets (one per business), then call `POST /api/v1/orgs/{orgId}/agents/{agentName}/capabilities` with each. Script prepared, not run (Slice 102): `ops/flashy_declare.py` (needs the token; dry-run by default, see `ops/README.md`).
- [ ] **Mint the other six role agents** against the seven-role charter, now live (`site/.well-known/flashyos-charter.json`, switched 2026-11-21, Slice 103) - the tier was raised FREE→GROWTH on Flashy's side 2026-11-21 (cap 5→50), so the ceiling is no longer the blocker; nothing on Flashy's side creates the agents. Needs the re-minted join-grant token above, and (for the four new roles' `x-capability` slugs to ever be declared) four endpoints that do not exist yet: coordination/intake, source-research, cross-document synthesis, client-delivery.
- [ ] **Latency and cost per document type through the API** - needs your `ANTHROPIC_API_KEY` and real spend (the live suite has a $1.00 ceiling).
- [x] ~~The unscaled-table-number rule~~ - owner's decision: scale it. Done, Slice 103 (2026-11-21): a bare table number under a declared scale now matches only the scaled value; `analystos/l4/seal_verify.py`'s independent implementation fixed the same way so the offline verifier still agrees with the analyzer.
- [ ] **Enforce GAAP / guidance labels against the source** - a decision: checking only the citation text would strip true labels whose evidence sits in a table header, so the rule (drop, downgrade, or flag) needs your call and real failing examples.
- [ ] **Stance on Gord Holdings' interest in "a piece of everything built on top"** - a business decision (equity/IP).
- [ ] **Per-key spend caps and a durable rate limiter** - needs a durable store, which the Downloads-only decision deliberately avoids; revisit if the API gets real callers.
- [ ] **Decide the fate of `solwayholdings.aao.json`** - a Slice 7 sample manifest for an org that does not exist (its description says otherwise); only `tests/test_aao_validate.py` uses it as a fixture. Delete it, or replace it with the AnalystOS charter?
- [ ] **R3+ (KPMG pilot, SOC 2, multi-tenant control plane)** - out of scope for an unattended loop.

### New from the Flashy estate's 18/21 Nov integration documents

- [x] ~~The seven-role charter: serve it, or keep three roles?~~ - owner's decision: serve it. Done, Slice 103 (2026-11-21): `site/.well-known/flashyos-charter.json` and `site/flashyos.roles.json` now serve the seven-role charter (byte-identical), the handshake's `capabilities` array lists all seven role names (never the four new roles' `x-capability` slugs - see the item above for what minting and endpoints still need). `drafts/README.md` updated; `drafts/flashyos-charter.team.json` kept as the validated source copy.
- [ ] **A named accountable person** - `defined/1`, `intent/1`, `directory/1` and the holding/1 log all need a `person/` id with a real name attached, which conflicts with this repo's own rule (Slice 80: one public identity, 30E Ventures / `30eventures@gmail.com`, no personal name). Decide the identifier and what is shown before Track C (the record plane) goes live; the draft files in this session use a placeholder.
- [ ] **Propose `drafts/measures.json`'s path/format to Flashy, then publish it** - computed for real from the audit log (Slice 96), asserts nothing false even in its current, honestly-empty state (production's audit log is dormant per Slice 84). Drafted because Flashy committed to pull a measures document but never confirmed where or in what shape; send them this proposal, then it is safe to publish regardless of their answer's exact shape.
- [ ] **Decide whether to use `drafts/playbook-document-analysis.json` in a real joint initiative** - validated against the real `@flashyos/playbook@0.2.0` and proven against this repo's own Flask app (Slice 97), but there is no live joint-initiative infrastructure on either side yet, and Flashy's `recipeKey` discovery path for a custom (non-catalogue) playbook is unconfirmed. `analystos/l4/acceptance.py::document_analysis_acceptance` is real, shipped product code regardless and needs no decision - a client can run it today.
- [ ] **Write the three `/defined/<slug>` basis pages, or decide to publish with 404 links** - `drafts/defined-analystos.json` (Slice 98) points its `basis` field at `https://analystos.dev/defined/analyst-agent` etc., and none of those pages exist in `site/` yet. The 18 Nov integration document named exactly this as mlgblockchain's own mistake (six dead `/defined/<slug>` links) and said not to repeat it; `tests/test_defined_fragment.py` fails if a page is ever added here without updating the test, so this cannot be silently closed by accident. Build the pages first, or decide to serve with 404s and record why - either way it is a choice, not a default. Checked against only a documented-rules proxy validator (`tools/defined_proxy_validator.py`), never a real one - `@flashyos/defined` is unpublished.
- [x] ~~Get real trademark advice on "decision-grade" before publishing `defined-analystos.json` or using the term anywhere public~~ - checked 2026-11-21: USPTO serial 87896620 is a live (status "suspended", not dead) 2018 application for the standard-character mark DECISION-GRADE in Class 042 (analytics services - AnalystOS's own category), owner not confirmed from public search snippets. Separately, Beroe Inc. uses "Decision Grade Intelligence" as core branding across its homepage headline, product copy and a 2026 article title, in procurement analytics - adjacent to, not the same as, AnalystOS's document-analysis category, but close enough to need a real opinion, not a web search. Owner's decision: drop the term rather than wait on counsel. Done, same day: `drafts/defined-analystos.json`'s "Decision-grade output" entry renamed to "Action-ready output" (`defined/analystos/action-ready-output`), same definition, id and `seeAlso` reference updated; nothing used the old name anywhere served.
- [ ] **Domain verification** - explicitly Flashy's to build (binds org ownership to a fetched handshake; closes the L3 register's three criteria together with the two items above). Not started on their side as of 2026-11-21; no date given. Nothing for us to do until it exists.
- [ ] **Flip `.shiplog/config.json`'s `visibility` to `"public"`, deploy, and hand the URLs to Flashy's fan-in** - shipped/1 and devlog/1 are genuinely adopted now (Slice 99): `flashy-shiplog adopt` + `node vendor-shiplog.mjs emit` ran for real against this repository's full git history (98 real entries), `flashy-shiplog check` reports every seal recomputed. Everything is `visibility: "private"` on purpose - the tool's own first state - so nothing is disclosed yet. Flipping it, deploying `drafts/devlog.fragment.json`'s served path to a real URL, and handing that URL to Flashy (one commit on their side) are three separate decisions, not a default. No checkpoint/1 tree head was attempted this session.
- [ ] **Hand the 24 audit findings to the register** - the finding content lives in the owner's local `flashy-audit` material, not in any repo reachable from this session. This session built the register's schema, validator and generator (Slice 101) against a clearly marked template entry (`F-00`, `status: "template"`) and tested every rule against synthetic fixtures - deliberately not against invented finding content. `tests/test_findings.py::RegistryContentTest` fails the moment a real entry is added without reading `findings/README.md`'s publishing section, by design. Needs the real write-ups, then a decision on where and when to publish them (findings/README.md's "Publishing" section).

## Working queue (unblocked, in priority order)

Each item gets a `specs/slice-N/spec.md` first, tests, a commit, and a line in
the session log. Nothing here is pushed until you say so.

- [x] **Q1 - Round half up when displaying figures** (audit finding 11): a source `$1.95B` must not display as `$1.9B`; `12.25%` must not display as `12.2%`. Accept: a table of half-way cases across usd/percent/number formats renders half-up; existing outputs otherwise unchanged; suite OK.
- [x] **Q2 - Make the spec record honest** (audit finding 9): `specs/README.md` indexing every slice, naming slices 35-39 (built without a spec) and 14 (empty); fix the code comment that cites a nonexistent spec. Accept: no source file cites a missing spec; a test keeps it that way.
- [x] **Q3 - Standalone verifier checks a quote's value against its citation** (closes the biggest gap in `docs/seal.md`): port the number parser, scale words, accounting negatives and document scale. Accept: differential test against the analyzer across a sample; a tampered value is caught even when hashes are rebuilt.
- [x] **Q4 - Live-suite PASS means something** (audit finding 8): assert the expected tier and minimum fact counts, not only "did not raise". Accept: mocked tests prove a fallback fails the check; docs say what PASS means. (No paid run here.)
- [x] **Q5 - Post-deploy smoke script** (`tools/smoke.py`): one command that checks every advertised URL on a live domain. Accept: passes against a local server of `site/`, fails on a missing file and a wrong content type.
- [x] **Q6 - Stop hand-maintaining the homepage's test and spec counts**: a tool writes them and a test fails when they drift. Accept: `--check` and `--write` modes; suite enforces.
- [x] **Q7 - Model name configurable** (R2 "model-swap"): one setting instead of four hard-coded strings. Accept: default unchanged; env override honoured everywhere the model is named.
- [x] **Q9 - Say out loud when the evidence store uses the public development key** (audit finding 4): one stderr line per process; behaviour otherwise unchanged. Accept: warns once on fallback, silent with a key, existing files still decrypt.
- [x] **Q8 - Cleanup pass** when the queue is empty: dead code, TODOs, coverage gaps.

## Agent-native queue (2026-09-28)

The intended shape going forward: a human prompts an agent, the agent is the
one that calls AnalystOS, the human's role is oversight. Sequenced from a
repo survey against that framing (full findings in the session that started
it; not written down separately - see the specs for what each item covers).

- [x] **1. A human review, recorded** (Slice 73): `POST /api/v1/reports/{id}/review`
  records who reviewed a delivered report and when, surfaced at
  `GET /api/v1/verify/{id}`. Not enforced - a report is deliverable whether
  or not it was reviewed; that's a policy decision for later.
- [x] **2. Async analysis jobs** (Slice 74): `POST /api/v1/jobs` +
  `POST /api/v1/jobs/{id}/run` + `GET /api/v1/jobs/{id}` split submit from
  run from collect, so an agent isn't forced to hold one connection open for
  the whole pipeline. Does not raise the platform's per-call time ceiling -
  `/run` is still one bounded call, same as `/analyses` - that needs a real
  queue and worker (new infrastructure) or a much larger, riskier rewrite of
  the pipeline's own internal model calls into resumable steps; neither is
  attempted here. See `specs/slice-74/spec.md` for the full reasoning.
- [x] **3. A published JSON Schema for a sealed report's `facts`** (Slice 76):
  `SealFact` (`quote`/`computed`/`event`/`prose`) is published in
  `openapi.json` and documented in `docs/seal.md`. Shape only - fitting it
  says nothing about whether the citations or arithmetic hold.

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
- 2026-09-27 - Q3 done (Slice 66): verifier checks quote values and operands against citations; differential-tested; 703 tests.
- 2026-09-27 - Q4 done (Slice 67): live-suite runs graded PASS/DEGRADED/FAIL from the trace (no paid run); 712 tests.
- 2026-09-27 - Q5 done (Slice 68): tools/smoke.py; 54/54 against live analystos.dev; emulated-Vercel tests for broken deployments; 731 tests.
- 2026-09-27 - Q6 done (Slice 69): tools/site_counts.py generates the homepage's test/spec counts (7 figures); test enforces; 740 tests, 63 specs.
- 2026-09-27 - Q7 done (Slice 70): ANALYSTOS_MODEL replaces four hard-coded constants; recorded in trace and audit event; 751 tests.
- 2026-09-27 - Q8 done (Slice 71): cleanup - 3 unused imports and 1 dead function removed; tools/refresh.py; hygiene test; 756 tests.
- 2026-09-27 - Q9 done (Slice 72): evidence store warns once per process when using the public development key; 760 tests.
- 2026-09-27 - loop finished: every unblocked item done (Q1-Q9); remaining work is under "Blocked / needs input" at the top. 760 tests, 21 commits on `roadmap-loop-2026-09-27`, nothing pushed.
- 2026-09-28 - agent-native queue item 1 done (Slice 73): `POST /api/v1/reports/{id}/review` records a human review, surfaced at `GET /api/v1/verify/{id}`; not enforced. 770 tests, pushed on branch `slice-73-report-review` (PR opened).
- 2026-09-28 - agent-native queue item 2 done (Slice 74): `/api/v1/jobs` (+`/run`, poll) split submit/run/collect for an agent caller; `/run` is still one bounded call, same ceiling as `/analyses` - true background async still needs a queue/worker, not attempted. 783 tests, on branch `slice-74-async-jobs` (stacked on `slice-73-report-review`), nothing pushed.
- 2026-09-28 - fixed a slice-numbering collision from two concurrent sessions: an unrelated seal-verifier-fidelity fix was independently built and merged as "Slice 73" (PR #70) around the same time as this session's real Slice 73 (report review). The merge (PR #71) concatenated both `specs/slice-73/spec.md` files into one, both `specs/README.md` rows, and both `site/index.html` stat/card/FAQ blocks - the deployed homepage was showing duplicate content and the suite was failing (5 tests) on `main`. Split the seal-verifier-fidelity work out to Slice 75 (its own spec, and every code/test comment citing "Slice 73" renamed to "Slice 75"), deduplicated `site/index.html` by hand, then regenerated everything. 794 tests, on branch `fix-slice-73-numbering-collision`.
- 2026-09-28 - PR #71 merged (Slices 73 and 74): a human review of a delivered report is recorded and surfaced at `GET /api/v1/verify/{id}`, and `/api/v1/jobs` splits submit / run / poll for an agent caller. 783 tests.
- 2026-09-28 - PR #72 merged (Slice 75 and the collision fix above): citation matching no longer accepts a number inside a bigger one (`$22.4 million` was found in `$122.4 million`); the duplicated spec, index rows and homepage blocks from the "Slice 73" collision are repaired. 794 tests.
- 2026-09-29 - PR #73 merged (Slice 76): a published JSON Schema, `SealFact`, for a sealed report's facts (`analystos/l4/seal_schema.py`), referenced from `/api/v1/openapi.json`; this completes the agent-native queue (3 of 3). 803 tests.
- 2026-09-29 - PR #74 merged (Slice 77): `tools/seal_facts_check.mjs`, a dependency-free Node checker written against the published schema only, to test the claim that a non-Python agent can validate a seal's facts. 807 tests.
- 2026-09-29 - PR #75 merged (Slice 78): a shared 30E Ventures studio bar and footer on the public pages, defined once in `tools/studio_chrome.py`. 820 tests.
- 2026-09-29 - PR #76 merged (Slice 79): the homepage credits 30E Ventures instead of an individual, and drops "solo". 825 tests.
- 2026-09-29 - PR #77 merged (Slice 80): one public identity - every `mailto:` under `site/` is `30eventures@gmail.com`, and a test scans `site/` for a personal name or email. 829 tests.
- 2026-10-01 - PR #78 merged (Slice 81): an upload's filename never decides where it is saved (`_upload_path` in `api/analyze.py`); closes a path traversal on `/api/extract` and `/api/analyze`. 836 tests.
- 2026-10-02 - PR #79 merged (Slices 82-85, hardening): text from a document or a caller is treated as data by the narrator (82); the signed seal names the model, caller and code version (83); the audit log is a hash chain signed with the seal key, dormant in production until `ANALYSTOS_STORE_DIR` is a persistent volume (84); a PDF's image count and extraction time are capped, the cap counting distinct images of at least 36 pt with a default of 40 (85). 912 tests.
- 2026-10-02 - PR #80 merged (Slice 86): the public seal-key file format (`analystos-seal-key/1`), a fail-closed `--key-file` verifier path, `tools/seal_key_file.py`, and `smoke.py --seal`. **No real signing key exists or is published**, so production seals remain unsigned; turning it on is the owner's step (`docs/seal.md`, "Turning it on"). 963 tests.
- 2026-10-08 - PR #81 merged (Slices 87-89): a refusal-first conformance corpus for seal and audit-log verification (it found and fixed `verify_bundle` crashes on hostile shapes, including a 500 from `POST /api/v1/verify`), a test that the site's machine-readable surface agrees with itself (`robots.txt` now allows `/api/v1` and `/api/v1/openapi.json`), and `smoke.py --deployed`, which after the deploy reported all 16 files SAME. Two audit-log gaps are recorded in `docs/decisions.md` and not fixed: a duplicate JSON key is read last-wins, and a `NaN` literal is accepted. 1024 tests, 83 specs.
- 2026-10-09 - this log brought up to date through Slice 89 (it had stopped at 2026-09-28). PR numbers, dates and test counts above are from the merge commits and the homepage counts committed with each; slice-to-PR mapping is from git ancestry.
- 2026-11-18 - log brought up to date from git and GitHub (origin/main `076cdd9`). PR #83 merged 2026-10-12 (Slice 90): the seal key is pinned out of band, a hidden seed prompt, `--require-authentic`. PR #85 merged 2026-10-14: an overnight bug hunt, 18 fixes across six lenses (uploads, verifier, LLM boundary, numbers, API, tests); its STATE.md reports 1051 to 1122 tests. PR #84 merged 2026-10-16 (Slice 91): the homepage's machine-discovery links are absolute. **Open, not merged:** PR #86 (Slice 92: size cap before the paid call, no upload text in the audit log, a logged verifier fault). Tests at `076cdd9`: 1123, OK on six of seven runs on 2026-11-18; the one failing run was not captured or reproduced, so its cause is unknown. The "Blocked / needs input" list above was not re-checked today.
- 2026-11-19 - PR #86 merged (Slice 92): the size cap, audit-log redaction and logged verifier fault described above. 1133 tests (homepage-committed count).
- 2026-11-20 - PR #87 merged (Slice 93): audit lines are strict JSON (refuses a duplicate key, `NaN`/`Infinity`/`-Infinity`, and an overflow-to-infinity float at write and verify time); 9 new conformance-corpus cases, including the sealed `inf`/`nan`/`-inf` and 400-digit-citation cases the overnight run proposed and did not add. Closes both `known_gap` annotations from Slice 87. Of the overnight run's six PROPOSALS, only the unscaled-table-number rule (item 1, an owner decision) is still open. PR #88 merged the same day (doc only: this log brought forward through PR #86). PR #89 merged 2026-11-20: the seal public key published (`analystos-seal-key/1`, key id `5d31bfc65a326e3c`) - the matching Vercel secrets are still unverified from a repo-only view. 1141 tests, 87 specs (confirmed 2026-11-21 by `python3 -m unittest discover -s tests` and `tools/refresh.py --check`).
- 2026-11-21 - session `flashyos-standardization-2026-11-21`, working from Flashy's 18 Nov integration document, its 21 Nov reply, and the "Engageable Workforce" document. Re-checked the live npm registry: `@flashyos/aao@0.4.2`, `@flashyos/conformance@0.2.3` (unchanged), `@flashyos/shiplog@0.2.0`, `@flashyos/countersign@0.1.1` and `@flashyos/mcp@0.7.0` (all three version numbers now match what Michael's 21 Nov message described as "in final CI" - **only the version was checked, not that the F-01 fence is actually inside 0.7.0's content**, which is exactly the registry-vs-content distinction the Reference Integration document itself warns about; do not repeat that version number as if it were a verified fact). `@flashyos/defined` is still unpublished (404). Deepened this checkout from a shallow depth-1 clone to get real git history (needed for Slice 99). Nothing pushed. Slices 94-100 built and tested in this session (see `specs/slice-94` through `specs/slice-100` and `docs/decisions.md` for what each actually does): the handshake now declares the charter's role names (94); a validated seven-role team charter draft (95); a measures/1 document wrapping the existing `audit.measures()` (96); a playbook and acceptance check for the document-analysis offer (97); a defined/1 fragment for AnalystOS's three owned terms (98); a real shipped/1 + devlog/1 record, adopted and committed, `visibility: private` (99); AnalystOS's own MCP server with fenced untrusted text, proven against a real prompt-injection probe (100). Plus: a trademark check on "decision-grade" found a live, non-dead USPTO filing in the same services class. 1,224 Python tests + 9 Node MCP tests, all OK; see the Blocked list above for exactly what still needs the owner or Flashy, and why.
