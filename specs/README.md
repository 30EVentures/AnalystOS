# Specs

One folder per slice: `specs/slice-N/spec.md` holds the goal, what is and is not
included, and the "Done when" checks, written before the code. This index lists
every slice number so a gap is visible rather than silent. Regenerate it with
`python3 tools/build_specs_index.py`.

**Known gaps.** Slices 35-39 were built without a spec of their own (the work is
recorded in git and in `docs/decisions.md`; see their rows). There is no Slice 14.
A test (`tests/test_specs_index.py`) keeps this list truthful: every existing
spec folder must appear below, and every slice without one must be marked.

| Slice | What | Spec |
|---|---|---|
| 1 | Repo skeleton + test harness | [spec](slice-1/spec.md) |
| 2 | L0: store one source, return its hash | [spec](slice-2/spec.md) |
| 3 | L0: retrieve a source by its hash | [spec](slice-3/spec.md) |
| 4 | L1: extract one table to structured data | [spec](slice-4/spec.md) |
| 5 | L2: answer one question with a citation | [spec](slice-5/spec.md) |
| 6 | L4: export one working-paper section with the citation trail | [spec](slice-6/spec.md) |
| 7 | the AAO manifest + a local check | [spec](slice-7/spec.md) |
| 8 | glue: one command runs the whole rush | [spec](slice-8/spec.md) |
| 9 | scaffold a job.json from a CSV | [spec](slice-9/spec.md) |
| 10 | write the section to a file automatically | [spec](slice-10/spec.md) |
| 11 | a one-page guide for analysts | [spec](slice-11/spec.md) |
| 12 | L2 computed metrics (growth %, ratio %) | [spec](slice-12/spec.md) |
| 13 | styled HTML output that auto-opens | [spec](slice-13/spec.md) |
| 14 | (no slice 14 - the roadmap goes from Slice 13 to Slice 15; an empty folder existed locally and was never in git) | none |
| 15 | harden for real-world data and executive-ready numbers | [spec](slice-15/spec.md) |
| 16 | L1: read a table from an Excel (.xlsx) sheet | [spec](slice-16/spec.md) |
| 17 | L1: read a table from a Word (.docx) document | [spec](slice-17/spec.md) |
| 18 | L1: read a table from a PowerPoint (.pptx) deck | [spec](slice-18/spec.md) |
| 19 | report templates, and closing two real gaps | [spec](slice-19/spec.md) |
| 20 | the API: `api/analyze.py` (Flask, on Vercel) | [spec](slice-20/spec.md) |
| 21 | the upload page on `site/` | [spec](slice-21/spec.md) |
| 22 | access gating (not public on day one) | [spec](slice-22/spec.md) |
| 23 | L1: PDF input, extraction + human confirm-before-cite step | [spec](slice-23/spec.md) |
| 24 | L4: real `.pdf` output (`reportlab`) | [spec](slice-24/spec.md) |
| 25 | universal upload: no hand-typed schema, every format treated the same | [spec](slice-25/spec.md) |
| 26 | narrated analysis: read any document, verify every number | [spec](slice-26/spec.md) |
| 27 | a second pass writes the narrative; verification stays untouched | [spec](slice-27/spec.md) |
| 28 | rich report rendering: charts, sections, a distinct outlook block | [spec](slice-28/spec.md) |
| 29 | L2 extraction contract: guarantee the comparisons, tag the horizon | [spec](slice-29/spec.md) |
| 30 | structured narrator, wired end to end | [spec](slice-30/spec.md) |
| 31 | horizon made visible in the rendered report | [spec](slice-31/spec.md) |
| 32 | dated events as a verified, structured fact | [spec](slice-32/spec.md) |
| 33 | verification that survives a real filing's tables and scale | [spec](slice-33/spec.md) |
| 34 | the output-token ceiling on a dense document | [spec](slice-34/spec.md) |
| 35 | L2 data for the v4 report: computed arithmetic and event milestones (commit `149ca4d`) | none - see `docs/decisions.md` and the commit |
| 36 | the v4 report renderer, all 8 reference patterns (commit `e3bae95`) | none - see the commit |
| 37 | Download PDF button via the browser's print dialog, on every report (commit `6c84b9d`) | none - see the commit |
| 38 | Gate 1 correctness checks and Gate 2 blind language pass (commits `815c6e6`, `c74f384`) | none - `docs/decisions.md` 2026-09-11 "Two mandatory quality gates" |
| 39 | growth_percent operand order made order-independent (commit `0ce4908`) | none - `docs/decisions.md` 2026-09-11 |
| 40 | repair instead of regenerate, for both quality gates | [spec](slice-40/spec.md) |
| 41 | per-IP rate limiting on the access-code endpoints | [spec](slice-41/spec.md) |
| 42 | in-code hard-stop budget on Anthropic API calls | [spec](slice-42/spec.md) |
| 43 | L0 encryption at rest + a retention/expiry policy | [spec](slice-43/spec.md) |
| 44 | one real table-parsing standard + footnote detection | [spec](slice-44/spec.md) |
| 45 | detect and correctly label GAAP vs. non-GAAP figures | [spec](slice-45/spec.md) |
| 46 | GAAP/non-GAAP table proof + legal boilerplate exclusion | [spec](slice-46/spec.md) |
| 47 | organic-vs-inorganic derived splits + code-owned chart type | [spec](slice-47/spec.md) |
| 48 | a real server-side PDF for the rich (v4) report | [spec](slice-48/spec.md) |
| 49 | Gate 2's full prose-quality rubric | [spec](slice-49/spec.md) |
| 50 | multi-column PDF reading order + image/OCR-derived facts | [spec](slice-50/spec.md) |
| 51 | a deliberate, real-money live-test suite | [spec](slice-51/spec.md) |
| 52 | a mandatory, deterministic "advanced" floor | [spec](slice-52/spec.md) |
| 53 | root cause: a fake, non-numeric placeholder | [spec](slice-53/spec.md) |
| 54 | the deterministic floor didn't recognize "Q3 FY2026" | [spec](slice-54/spec.md) |
| 55 | Gate 1 checks the relationships between numbers, not only the numbers | [spec](slice-55/spec.md) |
| 56 | the basis of a figure is shown wherever the figure is shown | [spec](slice-56/spec.md) |
| 57 | public claims match what the code does | [spec](slice-57/spec.md) |
| 58 | an AAO checker that follows the published schema, with rule codes | [spec](slice-58/spec.md) |
| 59 | AnalystOS publishes who it is (mesh identity files) | [spec](slice-59/spec.md) |
| 60 | seal every narrated report so a stranger can re-verify it | [spec](slice-60/spec.md) |
| 61 | an API an agent can call: analyses, sealed reports, verification | [spec](slice-61/spec.md) |
| 62 | navigable by machines; documentation brought up to date | [spec](slice-62/spec.md) |
| 63 | reports go to the reader's own Downloads, not to a server | [spec](slice-63/spec.md) |
| 64 | displayed figures round half up (roadmap Q1) | [spec](slice-64/spec.md) |
| 65 | an honest spec record (roadmap Q2) | [spec](slice-65/spec.md) |
| 66 | the standalone verifier checks each quote's value against its citation (roadmap Q3) | [spec](slice-66/spec.md) |
| 67 | a live-suite PASS means the report was good, not that nothing raised (roadmap Q4) | [spec](slice-67/spec.md) |
| 68 | a post-deploy smoke script (roadmap Q5) | [spec](slice-68/spec.md) |
| 69 | the homepage's test and spec counts are generated, not typed (roadmap Q6) | [spec](slice-69/spec.md) |
| 70 | the model is one setting, and every report says which one made it (roadmap Q7) | [spec](slice-70/spec.md) |
| 71 | cleanup pass (roadmap Q8) | [spec](slice-71/spec.md) |
| 72 | the evidence store says out loud when it uses the public key (roadmap Q9) | [spec](slice-72/spec.md) |
| 73 | a human review, recorded (agent-native queue, item 1 of 3) | [spec](slice-73/spec.md) |
| 74 | async analysis jobs (agent-native queue, item 2 of 3) | [spec](slice-74/spec.md) |
| 73 | citation matching stops accepting a number inside a bigger one | [spec](slice-73/spec.md) |
