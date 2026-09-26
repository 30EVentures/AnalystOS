# Slice 58 - an AAO checker that follows the published schema, with rule codes

## Goal

`docs/flashyos-alignment-2026-09-25.md`: `analystos/aao/validate.py` disagreed
with the published AAO 0.1 JSON Schema on 15 of 21 probe documents. It
invented an approval tier (`NONE`), rejected the real `CRITICAL`, made two
optional fields required, treated the schema's `x-` extension convention as
an error, and imported by nothing but its own test. It also could not talk
to FlashyOS's `conformance-kit`, whose line protocol needs machine-readable
codes for refusals.

Replaced by:

- `analystos/aao/aao.schema.json` - a byte-for-byte copy of
  https://flashyos.com/aao.schema.json as read on 2026-09-25 (sha256 pinned
  in the code and in a test, so it cannot be edited silently).
- `analystos/aao/validate.py` - a small JSON Schema checker limited to the
  exact keywords that schema uses (a test fails if the schema ever uses one
  the checker does not implement), plus the cross-field rules the schema's
  own description documents, plus the naming rules documented for role names
  that can be checked without a denylist we do not have.
- `validate_charter(doc)` returns `Problem(code, level, path, message)`;
  `validate_manifest(doc)` keeps its old shape (list of strings, errors only).
- `python3 -m analystos.aao <file>` prints JSON and exits 0/1;
  `python3 -m analystos.aao.kit` is a `conformance-kit` line-protocol adapter
  (stdin `{id,set,input}` -> stdout `{id,valid,codes}`; a document with only
  warnings is valid).

## Honesty about the codes

FlashyOS's `aao/0.1` conformance corpus is not public (its link 404s), so we
do not know their rule codes. Ours are namespaced `aao.*` and documented in
`docs/aao.md`. Any mismatch with their codes is a finding to report to them,
not something to hide.

## Not in this slice

- The official `@flashyos/aao` codename denylist (we do not have it; a role
  named `nova` is not refused here).
- Running the official npm validator (not authorised yet).
- Serving the charter (Slice 59).

## Done when

1. Every one of the 21 probes from the alignment document gets the verdict
   the published schema gives (`tests/test_aao_validate.py`).
2. The pinned schema hash matches, and the checker refuses to run against a
   schema that uses an unsupported keyword.
3. A charter that is only warned about is valid; errors carry stable codes.
4. The CLI and the kit adapter work end to end over real stdin/stdout.
5. The existing manifest passes (the AnalystOS charter itself is Slice 59).
6. Full suite OK.
