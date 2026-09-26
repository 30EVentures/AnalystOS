# AAO charter checking

`analystos/aao/` checks a FlashyOS AAO 0.1 charter without Node, npm or the
network. It exists so AnalystOS can prove its own charter is well-formed before
asking anyone else to read it, and so a second implementation exists to
compare with FlashyOS's own.

## Use

```
python3 -m analystos.aao path/to/charter.json     # or "-" to read stdin
```

Prints one JSON object; exit code `0` valid (warnings allowed), `1` invalid,
`2` unreadable input.

```json
{ "valid": false,
  "errors":   [{ "code": "aao.schema.enum", "level": "error",
                 "path": "/roles/0/humanApprovalAtOrAbove",
                 "message": "must be one of ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']; got 'NONE'" }],
  "warnings": [],
  "schema":   { "source": "https://flashyos.com/aao.schema.json",
                "retrieved": "2026-09-25", "sha256": "99f520bb..." } }
```

From Python:

```python
from analystos.aao.validate import validate_charter, errors, is_valid
problems = validate_charter(doc)      # list of Problem(code, level, path, message)
is_valid(doc)                         # True when there is no *error*
```

`validate_manifest(doc)` is the older string-list form (errors only).

## With FlashyOS's conformance-kit

```
npx @flashyos/conformance-kit <corpus.json> -- python3 -m analystos.aao.kit
```

The adapter follows the kit's line protocol (`{id,set,input}` in,
`{id,valid,codes}` out). A document with only warnings is valid. **No AAO
corpus is public**: the kit ships one bundled corpus, for `frontdoor/1`, which
this adapter would (correctly) disagree with everywhere - it checks charters.

## What is checked

| Layer | What | Source |
|---|---|---|
| Schema | types, `aao` = `"0.1"`, slug/role-name patterns, role-name length 3-24, the ten closed families, impact tiers LOW/MEDIUM/HIGH/CRITICAL, email shape of `accountableTo`, `x-` extensions allowed, any other unknown key refused | `analystos/aao/aao.schema.json`, a pinned byte copy (sha256 in `validate.py`) of the published schema |
| Cross-field | duplicate role names; `worksIn` naming an undeclared repository; `escalation` naming a missing role; more than one default repository; a repository no role owns | the schema's own description text |
| Naming | at most three words; a **partial** vendor list; placeholder names; `you@example.com` | FlashyOS's documented role-naming rules and the `accountableTo` description |
| Advice | a role with no `measure` (warning) | schema: "strongly encouraged" |

Not checked: FlashyOS's codename denylist (we do not have it - a role called
`nova` passes here and may not pass theirs), and whether an org's handshake,
front door or live behaviour conform (that is what `npx @flashyos/conformance`
grades; see `docs/flashyos-alignment-2026-09-25.md`).

## Rule codes

These are AnalystOS's, not FlashyOS's (their corpus is not public, so their
codes are unknown to us).

| Code | Level | Meaning |
|---|---|---|
| `aao.schema.type` | error | wrong JSON type (or the document is not an object) |
| `aao.schema.const` | error | `aao` is not `"0.1"` |
| `aao.schema.enum` | error | not one of the allowed values (family, tier) |
| `aao.schema.pattern` | error | string does not match its pattern (slug, role name, email, blank text) |
| `aao.schema.length` | error | role name shorter than 3 or longer than 24 |
| `aao.schema.min_items` | error | an array that must not be empty is empty |
| `aao.schema.required` | error | a required key is missing |
| `aao.schema.unknown_key` | error | a key that is neither defined nor `x-` prefixed |
| `aao.role.duplicate_name` | error | two roles share a name |
| `aao.role.worksin_undeclared` | error | `worksIn` names an undeclared repository |
| `aao.role.name.too_many_words` | error | more than three hyphen-separated words |
| `aao.role.name.vendor` | error | a role name uses a model-vendor word |
| `aao.role.name.placeholder` | error | a role name is a placeholder |
| `aao.escalation.unknown_role` | error | `escalation` names no role |
| `aao.repository.multiple_default` | error | more than one default repository |
| `aao.repository.no_owner` | error | a repository no role lists in `worksIn` |
| `aao.accountable.placeholder` | error | `accountableTo` is `you@example.com` |
| `aao.role.no_measure` | warning | a role declares no `measure` |

## Updating the pinned schema

`aao.schema.json` must stay byte-identical to the published file. To update it,
fetch the new one, replace the file, then change `SCHEMA_SHA256` and
`SCHEMA_RETRIEVED` in `validate.py` in the same commit. `tests/test_aao_validate.py`
fails if the hash drifts, and if the new schema uses a keyword the checker does
not implement.
