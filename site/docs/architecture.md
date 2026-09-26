# Architecture

AnalystOS is a layered stack. Each layer adds one thing; the layer below it is
its source of truth.

| Layer | Name | What it does |
|-------|------|--------------|
| L0 | Evidence kernel | Every source stored once, addressed by a hash of its content. Immutable. |
| L1 | Structure layer | Turns documents and tables into typed, validated data. Corrections train it. |
| L2 | Reasoning layer | Retrieval + analysis over the evidence graph. Every claim points back into L0. |
| L3 | Workspace | Where the analyst works: canvas, model, memo, review. Reads like a document. |
| L4 | Deliverable & attestation | Exports working papers etc. with a verifiable evidence trail attached. |
| L5 | Distribution | Multi-tenant control plane: KPMG, Gord, public. Per-tenant isolation. |
| L6 | AAO manifest & mesh | AnalystOS as an actor on the FlashyOS mesh, callable by other agents. |

Running through every layer: identity & access, an append-only audit log, a
policy engine (which data may reach which model), and observability.

## Frozen bits

- **The L0 provenance model.** Once analysis code depends on how sources are
  hashed and referenced, that scheme does not change. Flag problems; do not
  redesign it.

## Current state

What exists, by layer (code in `analystos/`; roadmap in `ROADMAP.md`).
"Built" means implemented and tested here; it says nothing about production.

| Layer | Status | Where |
|---|---|---|
| L0 Evidence kernel | Built: SHA-256 content addressing, Fernet encryption at rest (key you set; a public development fallback if you do not), retention purge | `analystos/l0/` |
| L1 Structure | Built: CSV, Excel, Word, PowerPoint, PDF (multi-column, image-derived facts), table unification, footnotes, boilerplate stripping | `analystos/l1/` |
| L2 Reasoning | Built: a model proposes facts, code verifies them (quote, computed, event, prose); a narrator writes from verified facts; Gate 1 validators; a blind Gate 2 proofreader | `analystos/l2/` |
| L3 Workspace | Not built | - |
| L4 Deliverable and attestation | Built: HTML and PDF reports, charts, a zero-model deterministic floor, basis tags, **sealed reports** with a standalone verifier | `analystos/l4/` |
| L5 Distribution | Not built: one shared access code plus per-caller API keys; no tenants | `api/`, `analystos/api_v1/` |
| L6 AAO and mesh | Partly built: an AAO checker, a `flashyos/1` handshake and charter (in the repo, not deployed), an agent-callable API. No org, token or capability on the network | `analystos/aao/`, `site/.well-known/`, `analystos/api_v1/` |

Cross-cutting: an append-only audit log (API only), a per-IP rate limiter
(in-memory), an in-code API-call budget. Not built: identity and access beyond
API keys, a policy engine, observability.

Where to read next: [`api.md`](api.md) (calling it), [`seal.md`](seal.md)
(checking a report), [`aao.md`](aao.md) and [`mesh-identity.md`](mesh-identity.md)
(the FlashyOS side), `docs/decisions.md` (in the repository) (why), and the code-verified
`docs/audit-2026-09-25.md` (in the repository).
