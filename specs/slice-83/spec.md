# Slice 83 - the signed seal says which model, which caller and which code made the report

## Goal

The seal's signed payload binds the facts, source, text, report and tier, but not who or what
produced the run: the model id, the calling API key and the code version appear only in the
unsigned audit log. An auditor holding only a seal cannot tell them, and a log line can be edited
without the seal noticing. Put the three into the signed payload, as an additive extension of
`analystos-seal/1`.

## Included

- `analystos/l4/seal.py` - `model_id` (from the run's trace), `caller_id` (new argument; the API-key
  name, or the constants `(cli)` / `(legacy-access-code)`), `code_version` (deployment environment:
  `ANALYSTOS_CODE_VERSION`, else `VERCEL_GIT_COMMIT_SHA`; `null` when neither is set; no git call).
- Callers: `/api/v1` (both routes) pass the key name; the legacy route and the CLI pass their constant.
- `analystos/l4/seal_verify.py` - accepts bundles with and without the fields; a present field must
  be null or a short non-empty string.
- `docs/seal.md`, the OpenAPI payload description.
- Tests, `docs/decisions.md`.

## Compatibility finding (checked, not assumed)

`seal_verify.py` requires a fixed set of payload keys but never rejects extra ones, the signature is
over the whole payload so it still verifies, and the only duplicate verifier in the tests re-derives
the Merkle root from facts alone. So the change is additive without a version bump. A third-party
port that rejects unknown payload keys would reject new seals; `docs/seal.md` now says ports must
ignore unknown payload fields.

## Done when

- [ ] A new seal's payload carries the three fields, and they are covered by the signature
      (changing one after signing fails verification).
- [ ] A seal made before this slice (fields absent) still verifies, signed and unsigned.
- [ ] A present field of the wrong type is a `structure` failure.
- [ ] `/api/v1` seals carry the key name; CLI and legacy seals carry their constants.
- [ ] `code_version` comes only from the environment; a malformed explicit value is an error.
- [ ] Existing tests pass unchanged.

## Not in this slice

- A version bump or a new seal format; publishing a key; trusting `code_version` beyond the signer.
