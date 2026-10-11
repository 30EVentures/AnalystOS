# Slice 90 - pin the key out of band, never see the seed, and never mistake "no check failed" for "authentic"

## Goal

Review of the seal-key rollout (2026-10-11) found three places where the safe path
was easy to get wrong. All three are in code that already exists; none changes what
a seal contains, so the conformance corpus and every existing seal stay valid.

1. **The runbook leaves the signing seed in shell history.** `docs/seal.md` step 2 is
   `ANALYSTOS_SEAL_KEY=<the seed> python3 tools/seal_key_file.py --from-env`: the seed
   is typed on a command line. `tools/seal_key_file.py --from-prompt` reads the seed
   with a hidden prompt (no echo, no history, no environment variable, no argument).
2. **Exit code 0 does not mean "authentic".** `seal_verify` exits 0 when *no check
   failed*. With the `cryptography` package missing, or with no pinned key, a signed
   seal exits 0 with `authentic=false`. A caller that only reads the exit status is
   misled. `--require-authentic` makes the exit status non-zero unless the seal is
   authentic.
3. **`--key-file` trusts whatever the file lists.** The file is only as trustworthy
   as the connection that fetched it. A relying party who recorded the key's `key_id`
   out of band (a message, a signed tag, a second website) has no way to say "and it
   must be *this* key". `--expect-key-id ID` adds that pin: the seal must be signed
   by the key with exactly that id, and the file must list it, or the check fails.

## Included

- `tools/seal_key_file.py --from-prompt`: hidden `getpass` entry of the seed. Refuses to
  run without a terminal, refuses an empty entry, a malformed seed, an interrupted
  prompt, and combination with `--from-env` or `--public-key`. The seed is never printed,
  logged, written, or placed in an error message. Output and file are as `--from-env`.
- `seal_verify --require-authentic`: exit 1 unless `authentic` is true (in addition to
  every existing failure). The JSON output is unchanged; only the exit status differs.
- `seal_verify --key-file F --expect-key-id ID`, and
  `verify_bundle_with_key_file(..., expect_key_id=ID)`: `ID` must be 16 lowercase hex
  characters (anything else is a usage error, exit 2). A seal signed by a different key,
  or a key file that does not list `ID`, is a failure of the `key_file` check, never a
  fall-back to another key. Only valid with `--key-file`.
- `docs/seal.md`: the runbook uses `--from-prompt`; `--from-env` stays documented with
  its history caveat; a warning not to generate a key in a terminal an assistant can read
  or under screen recording; `--require-authentic`, `--expect-key-id`, and the guidance
  to pin the `key_id` through at least two channels that do not share a host.

## Not in this slice

- Generating, printing or publishing any key; setting any environment variable; touching
  the host. Nothing here changes what analystos.dev serves.
- Separate keys for seals and the audit log; a revocation date in the key file;
  `--expect-key-id` on `tools/smoke.py`.
- Changing the default exit status of `seal_verify` (that would break existing callers;
  the flag is opt-in and the docs say which to use).

## Done when

1. `--from-prompt` writes the same file as `--from-env` for the same seed, and the seed
   appears in no stdout, stderr or file; every refusal listed above exits 2 and writes
   nothing.
2. With `--require-authentic`: an authentic seal exits 0; a signed seal with no pinned key,
   an unsigned seal, and a signed seal verified with the `cryptography` package missing
   all exit 1 (and exit 0 without the flag, unchanged); tampered and unreadable input
   still exit 1 and 2.
3. With `--expect-key-id`: the matching id passes; a different id, an id the file does not
   list, a seal that merely *names* the pinned id but is signed by another key, and a
   malformed id are each refused; in a rotated two-key file a seal from the other key is
   refused.
4. The docs name all three flags and no longer present the inline-seed command as the
   recommended one.
5. The conformance corpus and every existing test are unchanged and pass.
