# Slice 132 - signing keys as a JWKS, two mesh mistakes made impossible, and the charter differential

Phase 0 of the AnalystOS x Flashy two-sided plan (2026-11-25): C-ID-6, the
org-id half of C-MESH-1, C-MESH-6, and C-MESH-9.

## Goal

1. **Keys a stranger's tooling can read.** The seal key is served in
   AnalystOS's own format (`analystos-seal-key/1`). Flashy's key reader, and
   any JOSE library, read a standard JWKS. Serve the same key as one.
2. **The declare script would have failed on its first real run.** Its
   documented example passes the slug as `--org-id`; Flashy measured that a
   slug in the path answers 404. And a declared capability cannot be
   withdrawn, so a typo would be permanent (DepositX already has one).
3. **`llms.txt` says the charter has three roles.** It has had seven since
   Slice 103.
4. **Two charter checkers, never run on one corpus.** FlashyOS now serves its
   AAO corpus; every disagreement between it and `analystos/aao` is a defect
   in one of them.

## Done when

1. `tools/build_jwks.py` derives `site/.well-known/jwks.json` from
   `analystos-seal-key.json`: one `{kty: OKP, crv: Ed25519, x, kid, use: sig,
   alg: EdDSA}` per active key, `kid` equal to `key_id`, no private part. It is
   a `tools/refresh.py` step with `--check`, and served with the JSON/CORS
   headers. One key only: a key per purpose is added when something signs with
   it, never before.
2. `ops/mesh_ids.py` holds the analystos org id and two guards used by
   `ops/flashy_declare.py` (and the org-id one by `ops/flashy_decide.py`):
   the slug is refused as an org id, naming the id; a capability not in the
   served charter (role name or `x-capability`), a non-slug value, or more
   than 20 offers is refused before anything is built or sent. A live refusal
   code (401, 403, 404, 501) is explained.
3. `llms.txt` derives the role count from the charter and links the JWKS.
4. `tools/aao_differential.py` runs FlashyOS's corpus (snapshotted with its
   sha256 in `conformance/flashyos-aao-0.1.json`) through `analystos/aao` and
   compares verdicts; it refuses to pass over an empty corpus. Every verdict
   agrees. Each disagreement found on the way is fixed on whichever side is
   wrong, and `docs/aao.md` records the table and the five divergent inputs.
5. Owner's decision, 2026-11-26 ("do Flashy's list"): the handshake advertises
   the eight `x-capability` slugs beside the seven role names (C-MESH-6), derived
   from the charter; `docs/mesh-identity.md`'s Slice 94 rule is changed to say so;
   Flashy's published `auditProperty` still grades the pair level 2, no issues.
6. Nothing is sent to `api.flashyos.com`. The freeze moves once, with the
   reason logged, and the full suite reports OK.

## Not in this slice

- Agent-assertion, organisation-signing or invoice keys (later slices).
- Declaring anything. Which capabilities to declare is the owner's decision.
- Declaring anything on the live mesh (C-MESH-2): an outward, permanent act
  that needs the owner's yes on the exact requests.
