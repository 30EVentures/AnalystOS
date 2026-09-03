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

Nothing built yet. Slice 1 is the skeleton. See [`../ROADMAP.md`](../ROADMAP.md).
