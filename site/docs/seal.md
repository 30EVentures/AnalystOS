# The AnalystOS seal

A seal lets someone who did not run AnalystOS check a delivered report without
trusting AnalystOS. It is a JSON bundle; checking it needs only
`analystos/l4/seal_verify.py` (Python standard library, plus `cryptography`
for the signature) or your own port of the ten rules below.

```
python3 -m analystos.l4.seal_verify bundle.json \
    [--public-key <base64url ed25519 key you trust>] \
    [--text extracted.txt]
```

Exit `0` if no check failed, `1` if one did, `2` for unreadable input. Output
is JSON: `{"ok", "authentic", "content_checked", "checks": [{"name","status","detail"}]}`,
each status `pass`, `fail` or `skipped`.

## What each level means

| Flag | True when | It does **not** mean |
|---|---|---|
| `ok` | No check failed: the bundle is internally consistent. | The report is right, or that AnalystOS made it. |
| `authentic` | `ok`, and the Ed25519 signature verifies under a public key **you supplied**. | A key that came inside the bundle proves nothing: anyone can sign with their own key and include it. |
| `content_checked` | `ok`, and with the extracted text: it is the sealed text, every citation is in it, every number equals a number its citation spells, every calculation recomputes. | That the *choice* of figures is good. |

The `checks` list, in order (each `pass`, `fail` or `skipped`):

| Check | Needs the text? | What it proves |
|---|---|---|
| `structure` | no | it is an `analystos-seal/1` bundle with every required payload field (and any accountability field present is a string or null) |
| `fact_hashes` | no | every fact hashes to its recorded hash; no duplicate keys |
| `merkle_root` | no | the facts make the signed root; `entries` is right |
| `report_hash` | no | the report is the one that was sealed (or there is none) |
| `report_refs` | no | every fact the report cites was sealed |
| `signature` | no | Ed25519 over the payload; `pass` only under a key you pinned |
| `source_text_hash` | yes | the supplied text is the sealed text |
| `citations_in_text` | yes | every citation is in the text |
| `values_match_citations` | yes | every quote value and calculation operand equals a number its citation spells |
| `calculations` | yes | every calculation recomputes from its operands |

An unsigned bundle (no `ANALYSTOS_SEAL_KEY` when it was made) is `ok` but never
`authentic`. AnalystOS never signs with a built-in default key.

## Bundle format (`analystos-seal/1`)

```json
{
  "format": "analystos-seal/1",
  "payload": {
    "version": 1, "org": "analystos", "entries": 2,
    "created": "2026-09-25T00:00:00Z",
    "nonce": "<16 hex chars, random per seal>",
    "root": "<hex sha256 Merkle root>",
    "source_sha256": "<sha256 of the uploaded file's bytes>",
    "text_sha256": "<sha256 of the UTF-8 extracted text the facts were verified against>",
    "report_sha256": "<sha256 of canonical(report)> or null",
    "tier": "written | deterministic | plain",
    "model_id": "<the model the run asked, e.g. claude-sonnet-5> or null",
    "caller_id": "<the API-key name, \"(cli)\", \"(legacy-access-code)\"> or null",
    "code_version": "<deployed commit id or version label> or null"
  },
  "facts":  [ { "key": "fact/000000", "record": { ... }, "hash": "<hex>" } ],
  "report": { ... } or null,
  "signature": { "alg": "ed25519", "sig": "<base64url>", "public_key": "<base64url>", "key_id": "<16 hex>" } or null
}
```

`nonce` makes every seal's payload (and therefore the report id, `sha256(canonical(payload))`) unique even for identical content in the same second. `tier` is inside the signed payload so a fallback report cannot be relabelled
as a written one. `source_sha256` is the same SHA-256 the evidence store names
files by.

`model_id`, `caller_id` and `code_version` (Slice 83) say who and what produced the
report, inside the signed payload so a signed seal cannot be relabelled after the fact:

- `model_id` is the model id the run asked for (`ANALYSTOS_MODEL`, read when the run
  finished; the same value the audit log records). It is the *requested* id, not a
  statement from the model provider.
- `caller_id` is the `/api/v1` API-key **name** that made the run (an operator-chosen
  label, never the key). Runs outside `/api/v1` carry `"(cli)"` or
  `"(legacy-access-code)"`; those contain parentheses, which no key name can, so they
  never collide with a real caller. `null` means the sealer did not say.
- `code_version` is the deployed code's commit id or label, taken from the deployment's
  environment (`ANALYSTOS_CODE_VERSION`, else Vercel's `VERCEL_GIT_COMMIT_SHA`), never
  looked up at request time. `null` means the deployment does not say.

**Compatibility.** These three fields are an additive change to `analystos-seal/1`, with
no version bump. They are optional: a seal made before Slice 83 lacks them and still
verifies, and a verifier that ignores unknown payload fields (as `seal_verify.py` always
did) verifies a new seal unchanged, because the signature covers the whole payload
including them. A *strict* port that rejected unknown payload keys would reject new
seals; ports should ignore unknown payload fields, and may check that each of these
three, when present, is a non-empty string (at most 128 characters) or `null`. As with
every field here, a field is only as trustworthy as the key that signed it: unsigned
seals carry them unauthenticated.

## Fact records

`facts[].record` is one of four shapes, discriminated by `type`. Numbers are
already strings (rule 1). The machine-readable definition is the `SealFact`
schema in `https://analystos.dev/api/v1/openapi.json`
(`components.schemas.SealFact`, JSON Schema 2020-12 keywords); validate a
bundle's facts against it before running the ten rules. It checks **shape
only**: a record can fit it and still fail every content check.

| `type` | Required | Also present |
|---|---|---|
| `quote` | `citation` | `value` (numeric string, must equal a number `citation` spells), `sentence` with one `{value}`, `text` when there is no value, `label`, `format`, `display` |
| `computed` | `operation`, `value`, `operands`, `total`, `citation` (array) | `sentence`, `label`, `format`, `display`. `operation` is one of `sum average ratio growth_percent percent_of_total difference remainder`; `citation[i]` is operand `i`; `total` is null except for `percent_of_total` |
| `event` | `what`, `citation` (equals `what`) | `date`, `status`, `next_step`, `milestones` (`{date, detail}` list); each part is a substring of the document |
| `prose` | `text` | none of its own; it carries no figure |

Every type may also carry `horizon` (`reported`, `guidance`, `projected`) and
`gaap_status` (`gaap`, `non_gaap`, `n/a`). "Required" is what a verifier
reads; unknown extra properties are allowed and ignored.

## The ten rules

1. **Normalize.** In every `record` and in `report`, each JSON number is
   written as a string (`repr` of a float, `str` of an int). Booleans, null,
   strings, arrays and objects stay. This is why no verifier has to agree with
   another about how to print a float. **A verifier rejects a bundle** (a
   `structure` failure) in which any `record`, the `report`, or any `payload`
   field other than `version` and `entries` contains a JSON number. Those two
   are the only numbers in a bundle and must be integers: `1`, not `1.0`.
2. **Canonical JSON.** Keys sorted at every level, separators `,` and `:` with
   no whitespace, UTF-8, non-ASCII characters not escaped.
3. **Fact hash.** `sha256(canonical(record))`, lowercase hex.
4. **Leaf.** `sha256(0x00 || utf8(key + "\0" + fact_hash))`.
5. **Node.** `sha256(0x01 || left_bytes || right_bytes)` over the 32 raw bytes.
6. **Root.** Sort leaves by `key`; pair neighbours left to right; an odd node
   at the end of a level is promoted unchanged; repeat until one is left.
   `entries` is the number of facts. (This is the construction in Flashy's own
   published provenance code, `flashyos-wdk` `provenance.ts`.)
7. **Report hash.** `sha256(canonical(report))`, or `null` with no report
   (the plain tier). A report that cites `{{N}}`, or `fact_index` /
   `value_fact` / `delta_fact` N, must cite a sealed fact (`N < entries`).
8. **Signature.** Ed25519 over `canonical(payload)`, base64url without padding.
9. **Text.** `text_sha256` must equal `sha256(utf8(extracted_text))`.
10. **Content.** With the text, fold both text and each citation
    (lowercase; `–`, `—`, `−` to `-`; drop `$` and `|`; remove a thousands
    comma between digits; collapse whitespace). A citation passes if the folded
    citation, or the folded citation with one trailing scale word
    (`thousand million billion bn mm k m b`) removed, occurs in the folded text
    **as a whole number**: if it starts with a digit, no ASCII digit, and no `.`
    or `,` that follows a digit, may come immediately before it; if it ends with
    a digit, no digit, and no `.` or `,` that is followed by a digit, may come
    immediately after it. A full stop or comma that merely ends a sentence or
    separates a list does not count. If one occurrence fails this test, later
    occurrences are tried. **Values:** read every
    number a citation spells (optional `(` or `-` makes it negative; optional `$`;
    digits with commas and a decimal point; an optional scale word `k thousand m mm
    million b bn billion` multiplies it). The document's *declared scale* is the
    largest of "in thousands/millions/billions" or "thousands/millions/billions of
    [U.S.] dollars" found in the text, else 1. A quote's `value`, and each
    calculation operand's value (`citation[i]` is operand `i`; a `percent_of_total`
    total is the citation after the operands), must equal one of those numbers as
    printed or times the declared scale. A `computed` fact then passes if its
    operation recomputes from its `operands`: `sum`; `difference` and `remainder` =
    first minus the rest; `average`; `ratio` = first / second; `growth_percent` =
    (second - first) / first x 100 (either operand order); `percent_of_total` =
    operand / total x 100 - within relative 1e-9.

### Worked vector

Two facts, keys `fact/000000` and `fact/000001`:

| key | canonical record | fact hash |
|---|---|---|
| `fact/000000` | `{"text":"Momentum continued.","type":"prose"}` | `86c4578bbaddfca5459cf5c8f86be65c3eb6aa12153a57749b74f8c5180a7c0b` |
| `fact/000001` | `{"citation":"$498.0 million","label":"Revenue","type":"quote","value":"498000000.0"}` | `94e5d1320d014c7eaf7e500190415425449d075fd49b37b7e367543685b23d3a` |

Leaves: `788741d444405b11399adb37f76b01291428567136aec8909efac24a210dfe3a` and
`289899dacf126d005f2d43c47230b956fc51549a4910d369fbe01853c89f5970`.
Root: `7093b80cc076808b59c1500f0cc425003408f757add4afad1963e40c8e044747`.
If your port does not reproduce that root, it is not the same seal.

## Making one

- The CLI (`python3 -m analystos <job-dir>`) writes `section.seal.json` next to
  `section.html` for every narrated run.
- From Python: `build_report(path, ..., trace=t)` then
  `analystos.l4.seal.build_bundle(t, signing_key=...)`.
- Signing: `python3 -m analystos.l4.seal keygen` prints a new key pair once and
  stores nothing. Put the secret line in `ANALYSTOS_SEAL_KEY` and publish the public
  half as described in "The published public key" below. A malformed key is an
  error, not a silent downgrade to unsigned.

## The published public key

A signature only counts under a key you obtained **independently of the seal**
(a key inside the bundle proves nothing). When signing is on, AnalystOS publishes
its public key at

    https://analystos.dev/.well-known/analystos-seal-key.json

and **until that file exists, seals are unsigned and cannot be authenticated by
anyone**. (The file is added by an operator, not by the code; see "Turning it on".)

```json
{
  "format": "analystos-seal-key/1",
  "keys": [
    {"added": "2026-10-02", "algorithm": "ed25519", "key_id": "<16 hex>",
     "public_key": "<base64url, 43 chars>", "status": "active"}
  ],
  "org": "analystos",
  "seal_spec": "https://analystos.dev/docs/seal.md"
}
```

Rules a reader (or a port) should enforce: `format` is exactly `analystos-seal-key/1`;
`public_key` is the canonical unpadded base64url of 32 bytes; `key_id` is the first
16 hex characters of `sha256(those 32 bytes)` and equals the `key_id` in a seal's
`signature` block; ids are unique; at least one key is `active`; the file never
contains a private key (`validate_key_file` rejects fields named `private_key`,
`seed`, `secret` and similar). Unknown extra fields are ignored.

Verify a seal against it:

```
curl -sO https://analystos.dev/.well-known/analystos-seal-key.json
python3 -m analystos.l4.seal_verify section.seal.json --key-file analystos-seal-key.json [--text extracted.txt]
```

The key is selected by the seal's `key_id`. A seal whose key is **not in the file**,
a seal from another `org`, and an invalid file are all **failures** (`key_file` check),
never a silent check without a pinned key. An unsigned seal cannot be authentic.

**What this does and does not give you.** The file is trusted exactly as far as a TLS
connection to analystos.dev is: whoever controls the site can publish a different key.
For more than that, record the `key_id` out of band when you first adopt AnalystOS
(a contract, a config in your own repository) and compare it before trusting a file.
**Rotation** adds a new `active` key and marks the old one `retired` (old seals keep
verifying). **Revocation is removal**: delete a compromised key from the file and its
seals stop being authentic.

### Turning it on (an operator's steps)

Nothing in the repository does this for you, and nothing here ever needs a private key
in a file, a chat or git.

1. In your own terminal: `python3 -m analystos.l4.seal keygen`. It prints the **private**
   seed (`ANALYSTOS_SEAL_KEY=...`) once and stores nothing. Put it straight into your
   host's secret store (Vercel: Project Settings, Environment Variables, Production,
   `ANALYSTOS_SEAL_KEY`, sensitive) and a password manager. Never commit it.
2. In the same terminal, with the seed in the environment, write the **public** file
   (the seed is never printed or written):
   `ANALYSTOS_SEAL_KEY=<the seed> python3 tools/seal_key_file.py --from-env`
   (or `--public-key <the line keygen labels "public key">`; the tool refuses a value
   equal to the seed in your environment). It creates
   `site/.well-known/analystos-seal-key.json`. Then close the terminal.
3. `python3 tools/refresh.py`, run the tests, commit the file (public data only), open
   the pull request and merge. Redeploy so the new environment variable is live.
4. Prove the two halves match: run one analysis in production, download its seal, and run
   `python3 tools/smoke.py --expect-seal-key --seal ~/Downloads/<name>.seal.json`. It
   must report `a seal from this deployment verifies under the published key`. This is
   the check for the one dangerous mistake, a signing key in the host that is not the
   key on the site.
5. To rotate later: generate a new key, run `tools/seal_key_file.py --from-env --add`
   (new key active, old one retired), deploy the file, then switch
   `ANALYSTOS_SEAL_KEY`. `tools/seal_key_file.py --check <file>` validates a file.

Either half alone is safe: the key in the environment without the file means signed
seals nobody can yet authenticate; the file without the key means unsigned seals.

## A conformance corpus for porting the verifier

If you write your own verifier, `conformance/seal-1.json` in the repository is a data file of inputs
and the verdict each must get, most of them things that must be **refused**: tampered facts, roots
and signatures, a signature under a key you did not pin, duplicate keys, raw JSON numbers, and for the
audit log edited, deleted, reordered, inserted and signature-stripped lines. It is generated, runs
over one JSON object per line (`python3 -m analystos.conformance` is our adapter), and is the quickest
way to find where a port is more lenient than this one. A few cases are marked `known_gap`: places
where this verifier is itself known to be lenient, kept strict so the gap stays visible.

## Limits, stated plainly

- The extracted text is **not** in the bundle (it may be confidential). To
  check content you must supply text whose hash matches; otherwise the hash
  check fails and the content checks still run on what you supplied.
- Event facts (dates, milestones) and prose carry no numeric value; the checks
  above do not cover them beyond the citation being in the text.
- The seal proves the report was built from these facts. It does not prove the
  facts are the important ones, that a relationship between two figures is right
  (Slice 55 checks some), or that the model's GAAP/guidance labels are correct.
- There is no chain between reports and no transparency log yet.
- A citation with its scale word stripped (rule 10) matches any standalone
  occurrence of the bare number, even one the scale was never meant to apply
  to - `$5 million` is satisfied by a document that only ever says "5" on its
  own. Rule 10 proves the number is genuinely present as a whole number, not
  that it is the right one; that is still `values_match_citations`'s job where
  it applies, and a human's job otherwise.
