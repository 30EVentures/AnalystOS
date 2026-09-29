# Slice 76 - a published schema for a sealed report's facts (agent-native queue, item 3 of 3)

## Goal

A seal's `facts[].record` has four shapes (`quote`, `computed`, `event`,
`prose`). Until now they lived only in `analystos/l4/seal_verify.py` and
`analystos/l2/analyze.py`, plus one worked example in `docs/seal.md`, and
`SealBundle.facts` in `openapi.json` was an untyped `array`. A non-Python
agent had to reverse-engineer the shape instead of validating against it.

- One schema, `SealFact`, in `analystos/l4/seal_schema.py` - the single
  source. `openapi.json` references it (`SealBundle.facts` becomes an array
  of `SealFact`), so it is published at `/api/v1/openapi.json` with no new
  route and no new file to serve.
- It describes the record **as sealed**: after rule 1 every number is a
  string, so `value`, `operands` and `total` are numeric strings.
- `required` lists only what a verifier reads to run its checks, not
  everything the producer happens to emit; unknown extra properties are
  allowed so a later field is not a breaking change.
- `docs/seal.md` gains a "Fact records" section: a table per type and a
  pointer to the schema.

## Not in this slice

- **No change to the seal format, the verifier, or any hash.** `analystos-seal/1`
  is unchanged; this only writes down what it already is.
- **Schema validity is not seal validity.** A record that fits `SealFact`
  can still fail every content check (`citations_in_text`,
  `values_match_citations`, `calculations`). The schema checks shape only.
- No `jsonschema` dependency. The test uses a small stdlib validator for the
  subset this schema uses (`type`, `const`, `enum`, `required`, `properties`,
  `items`, `oneOf`, `pattern`), so a dependency is not added quietly.
- No schema for `report` (the narrated layout) - a separate, larger shape.

## Done when

1. `SealFact` is a `oneOf` over `quote`, `computed`, `event`, `prose`,
   discriminated by `type`; every property name, enum (`horizon`,
   `gaap_status`, `display`, `format`, `operation`) and numeric-string rule
   matches what the pipeline emits.
2. Every fact record produced by the real narration path's four verify
   functions (`_verify_quote` with and without a value, `_verify_computed`,
   `_verify_prose`, `_verify_event`), once normalized, validates against
   `SealFact` - and exactly one branch matches.
3. Malformed records fail: unknown `type`, a raw JSON number where a string
   is required, an `operation` outside the seven, a `computed` missing
   `operands`.
4. `SealBundle.facts` in `openapi.json` is `items: {"$ref": SealFact}`;
   `test_openapi_is_self_consistent` still passes.
5. `docs/seal.md` documents all four types and names the schema.
6. Full suite OK; `tools/refresh.py` leaves nothing stale.
