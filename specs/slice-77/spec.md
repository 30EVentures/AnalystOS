# Slice 77 - a non-Python checker for a seal's facts

## Goal

Slice 76 published `SealFact`, claiming a non-Python agent could validate a
bundle's facts against it instead of reverse-engineering the shape. This
slice tests that claim from outside Python: `tools/seal_facts_check.mjs`, a
single dependency-free Node file, written against the published schema only
(not against `seal_schema.py`).

    node tools/seal_facts_check.mjs bundle.json [openapi.json | https://analystos.dev/api/v1/openapi.json]

- Reads the bundle, loads `components.schemas.SealFact` from the given
  OpenAPI document (a file or URL; default is the live one), and validates
  every `facts[].record` against it.
- Prints JSON `{"ok", "checked", "problems": [{"key", "problem"}]}`.
  Exit `0` all fit, `1` some do not, `2` unreadable input.
- Implements only the keywords the schema uses (`type`, `const`, `enum`,
  `required`, `properties`, `items`, `oneOf`, `anyOf`, `pattern`) and says so
  in an error if the schema ever uses another, rather than silently passing.

## Not in this slice

- **Shape only**, like the schema: no hash, Merkle, signature or content
  checks. That is `analystos.l4.seal_verify` / `POST /api/v1/verify`.
- Not a general JSON Schema validator; not published or packaged.
- Not part of the deployed function (tools/ is not served).

## Done when

1. A bundle from `build_bundle` passes with exit 0 against the openapi
   document `build_openapi()` produces.
2. A tampered fact (raw JSON number where a string is required; unknown
   `type`; bad `operation`) exits 1 and names the fact key.
3. Unreadable bundle or schema exits 2; a schema with an unsupported
   keyword exits 2 rather than passing.
4. The Python test runs it with `node` and is skipped, not failed, when
   `node` is absent.
5. Full suite OK; `tools/refresh.py --check` clean.
