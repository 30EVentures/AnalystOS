# Slice 86 - a public key a stranger can pin, and the means to publish it safely (hardening plan item A2)

## Goal

`~/flashy-audit/reports/11-hardening-roadmap.md` item A2. Seals can be signed
(`ANALYSTOS_SEAL_KEY`), but the verifier's rule is "authentic only under a public
key **you** supplied" and nothing publishes one. A stranger therefore has no
independent way to obtain the key, and production seals are most likely
unsigned. A key that must be trusted blind is no better than none.

This slice builds everything needed to publish the key **without publishing
one**: no real key is generated, printed, stored or written, and the key file is
not added to `site/`. Turning it on is a human act (see "Turning it on" in
`docs/seal.md`).

- **A file format**, `analystos-seal-key/1`, served at
  `/.well-known/analystos-seal-key.json`: `format`, `org`, and a `keys` list
  (`key_id`, `algorithm: "ed25519"`, `public_key`, `status` active|retired,
  `added`). A list from the start so a key can be rotated without breaking
  anyone who pinned the file's format; a key removed from the list is no longer
  trusted (revocation by removal, fail closed).
- **`validate_key_file`** in the standalone verifier (`analystos/l4/seal_verify.py`,
  stdlib only): strict, canonical encodings, `key_id` must equal
  `sha256(public key)[:16]`, unique ids, at least one active key, and no
  private-key-looking field.
- **`verify_bundle_with_key_file`** and `--key-file` on the verifier CLI: select
  the key by the seal's `key_id`; a seal whose key is not in the file, a seal
  from another org, and an invalid file are all **failures**, never a silent
  fall-back to "no pinned key".
- **`tools/seal_key_file.py`** writes the file from `ANALYSTOS_SEAL_KEY` in the
  operator's own shell (`--from-env`, so no key is ever pasted anywhere), or from
  a public key (`--public-key`, which refuses a value equal to the private seed in
  the environment). It writes only the public half, never prints the seed,
  refuses to overwrite (rotation is `--add`), and has `--check`.
- **`tools/smoke.py`**: validates the published file when present (a missing
  file is reported as "not published yet", and fails only with
  `--expect-seal-key`); `--seal PATH` verifies a seal made by the live service
  against the live key file - the check that catches the one dangerous mistake,
  the key in Vercel not matching the key on the site.
- `vercel.json` headers for the path (JSON, CORS, 5-minute cache), a conditional
  line in `llms.txt` once the file exists, and docs.

## Not in this slice

- Generating or publishing a real key, setting `ANALYSTOS_SEAL_KEY`, touching
  Vercel, or deploying. Nothing here changes what analystos.dev serves today.
- Revocation with a reason or date (removal is the revocation), key transparency,
  or a signed key file (the file is trusted exactly as far as a TLS connection to
  analystos.dev is; the docs say so and show how to pin the `key_id` out of band).
- Verifying the hardening branch's audit log with the key file.

## Done when

1. A seal signed by a throwaway test keypair verifies as `authentic` against a
   key file in the published format, through the library and the CLI.
2. A seal signed by a key not in the file, a seal from another org, a tampered
   seal, an unsigned seal and an invalid key file are each refused or reported
   as not authentic, never passed.
3. A two-key file (rotation) authenticates seals from both keys.
4. The key-file validator rejects each malformed case in a table (wrong format,
   bad encodings, wrong key length, `key_id` mismatch, duplicate ids, no active
   key, private-key fields).
5. The tool writes only a public key, refuses to overwrite, rotates with `--add`,
   refuses a private seed given as `--public-key`, and never puts the seed in its
   output or the file.
6. The smoke check passes against an emulated deployment with no key file (skipped)
   and with one (validated), fails for a missing file under `--expect-seal-key`,
   for an invalid file, and for a seal signed by a different key; passes a real
   seal from the matching key.
7. No file under `site/` contains a key; the suite and `tools/refresh.py --check`
   pass.
