# AnalystOS — roadmap

Working view. The boardroom version is the "Revision A" dossier; when they
disagree, **this file wins**. Windows are targets, not commitments.

## NOW — the thin slice (Sept 2026)

Prove the core loop on one real document set, in front of 3–5 real analysts.

- Slice 1 — repo skeleton + test harness            ✓ done (PR #1)
- Slice 2 — L0: store one source, return its hash    ✓ done (PR #2)
- Slice 3 — L0: retrieve a source by its hash        ✓ done (PR #3)
- Slice 4 — L1: extract one table to structured data ✓ done (PR #4)
- Slice 5 — L2: answer one question with a citation  ← in progress
- Slice 6 — L4: export one working-paper section with the citation trail
- Slice 7 — the FlashyOS AAO manifest, validated in CI
- Slice 8 — glue: run slices 2–6 on the golden set with one command

**Done when:** a real analyst completes one real task end to end and reaches
for it again unprompted.

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
