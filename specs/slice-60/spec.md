# Slice 60 - seal every narrated report so a stranger can re-verify it

## Goal

Roadmap Phase 2, the receipt: an agent that receives a report must be able to
check it without trusting AnalystOS, offline. The charter's `evidence` role
("seals each delivered report so a stranger can re-verify it offline") is only
true once this exists.

- `analystos/l4/seal_verify.py` - the seal, in executable form, **stdlib
  only** (Ed25519 optionally via `cryptography`), importing nothing else from
  AnalystOS. A stranger can port it from `docs/seal.md`.
- `analystos/l4/seal.py` - builds the bundle from a run's trace and signs it
  when `ANALYSTOS_SEAL_KEY` is set. **No default key**: unsigned bundles say
  so. (The audit's finding 4 was a public fallback encryption key; this must
  not repeat it.)
- `build_report(..., trace=dict)` and `analyze_document(..., stats=dict)`
  record what a run did (tier, facts, report structure, extracted text,
  proposed/verified/dropped counts) without changing any return value.
- The CLI writes `section.seal.json` next to `section.html` for narrated runs.

The construction follows Flashy's own published provenance code
(`flashyos-wdk/packages/wallet-wdk/src/provenance.ts`): leaf
`sha256(0x00 || "<key>\0<fact hash>")`, node `sha256(0x01 || left || right)`,
leaves sorted by key, an odd node promoted, an Ed25519-signed canonical-JSON
root payload. Every number in a sealed record is written as a string so no
verifier depends on float formatting.

## What a pass does and does not mean

Three levels, never merged into one flag: `ok` (internally consistent),
`authentic` (signature valid under a key **you** supplied - a key inside the
bundle proves nothing), `content_checked` (with the extracted text: it is the
sealed text, every citation is in it, every calculation recomputes).

Not checked by the standalone verifier: that a quote's numeric `value` agrees
with the number in its citation (the pipeline checks that when it accepts the
fact; the seal records the outcome), and events' inner dates.

## Not in this slice

- Storing or serving bundles (Slice 61), publishing the public key, a seal
  sequence/chain across reports.
- Sealing the schema/template (table) path: it has no proposed facts.

## Done when

1. An independent re-implementation of the construction inside the test
   reproduces the module's root, and a hard-coded known-answer root pins the
   format.
2. Each kind of tampering (a fact, the root, a dropped fact, the report, the
   tier, a wrong key) is refused by the check that should catch it.
3. A bundle rebuilt around a wrong calculation passes integrity and fails
   `calculations`; a citation absent from the text fails `citations_in_text`.
4. Unsigned and unpinned bundles report `ok` but not `authentic`.
5. `seal_verify` imports only the standard library (plus optional
   `cryptography`) and runs as its own command.
6. The verifier's text folding, recomputation and citation matching agree with
   the analyzer's on a differential sample.
7. A real (mocked-model) pipeline run's trace seals and fully verifies for the
   written and deterministic tiers.
8. Full suite OK.
