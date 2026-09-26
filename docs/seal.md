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
| `content_checked` | `ok`, and with the extracted text: it is the sealed text, every citation is in it, every calculation recomputes. | That a quote's number equals the number in its citation, or that the *choice* of figures is good. |

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
    "tier": "written | deterministic | plain"
  },
  "facts":  [ { "key": "fact/000000", "record": { ... }, "hash": "<hex>" } ],
  "report": { ... } or null,
  "signature": { "alg": "ed25519", "sig": "<base64url>", "public_key": "<base64url>", "key_id": "<16 hex>" } or null
}
```

`nonce` makes every seal's payload (and therefore the report id, `sha256(canonical(payload))`) unique even for identical content in the same second. `tier` is inside the signed payload so a fallback report cannot be relabelled
as a written one. `source_sha256` is the same SHA-256 the evidence store names
files by.

## The ten rules

1. **Normalize.** In every `record` and in `report`, each JSON number is
   written as a string (`repr` of a float, `str` of an int). Booleans, null,
   strings, arrays and objects stay. This is why no verifier has to agree with
   another about how to print a float.
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
10. **Content.** With the text: fold both text and each citation
    (lowercase; `–`, `—`, `−` to `-`; drop `$` and `|`; remove a thousands
    comma between digits; collapse whitespace). A citation passes if the folded
    citation is a substring of the folded text, or is with one trailing scale
    word (`thousand million billion bn mm k m b`) removed. A `computed` fact
    passes if its operation recomputes from its `operands`: `sum`; `difference`
    and `remainder` = first minus the rest; `average`; `ratio` = first / second;
    `growth_percent` = (second - first) / first x 100 (either operand order);
    `percent_of_total` = operand / total x 100 — within relative 1e-9.

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
  stores nothing. Put the secret line in `ANALYSTOS_SEAL_KEY`; publish the
  public key wherever a verifier can pin it. A malformed key is an error, not a
  silent downgrade to unsigned.

## Limits, stated plainly

- The extracted text is **not** in the bundle (it may be confidential). To
  check content you must supply text whose hash matches; otherwise the hash
  check fails and the content checks still run on what you supplied.
- The verifier does not check that a quote's numeric `value` matches the number
  in its citation (scale words, accounting negatives, table scale). AnalystOS
  checks that when it accepts the fact; the seal records the outcome.
- The seal proves the report was built from these facts. It does not prove the
  facts are the important ones, that a relationship between two figures is right
  (Slice 55 checks some), or that the model's GAAP/guidance labels are correct.
- There is no chain between reports and no transparency log yet.
