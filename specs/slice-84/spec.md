# Slice 84 - the audit log is a hash chain, signed with the seal key

## Goal

`audit.jsonl` (the `/api/v1` audit log) was "append-only by convention": plain JSON lines, nothing
to show that one was edited, dropped or reordered. The charter's three measures are computed from
it, so a quiet edit changes a published number. Make it tamper-evident by copying the pattern
DiligenceOS already uses for its receipt log (a linear hash chain with a per-entry signature), not
Merkle-over-sorted-ids, which cannot represent honest growth.

## Included

- `analystos/api_v1/audit_chain.py` - the entry format (`seq`, `prev_hash`, `log_signing`,
  `key_id`, `entry_hash`, `signature`), `verify_audit_log(path, public_key=None, expected_head=None)`.
  `entry_hash` is sha256 of the canonical entry without `entry_hash`/`signature`; the signature is
  Ed25519 over `{"domain": "analystos.audit-entry/1", "entry_hash": ...}`, using the seal's own
  helpers and key (`ANALYSTOS_SEAL_KEY`). No new cryptography.
- `analystos/api_v1/store.py` - `append_audit` chains and signs under a file lock; with no key,
  entries are chained and marked `"log_signing": "none"`; a malformed key never loses a line. The
  no-store stderr fallback is untouched.
- `python3 -m analystos.api_v1 verify-audit <path> [--public-key B64URL] [--expect-head HASH]`;
  exit 0 / 1 / 2 like `seal_verify`.
- `docs/api.md`, `docs/decisions.md`, tests.

## Done when

- [ ] Editing, deleting, reordering or inserting a line makes verification fail.
- [ ] Appending keeps earlier verification valid (and an earlier head is still a line of the log).
- [ ] Signed entries verify under the pinned key and fail under another; stripping a signature or
      relabelling an entry "unsigned" fails; unsigned entries are chained and marked.
- [ ] Lines written before this slice are tolerated before the chain starts; an unchained line
      after it is a failure; readers and the `measures` CLI still work.
- [ ] An empty or legacy-only log fails closed (nothing was verified).
- [ ] Concurrent appends keep one unbroken chain.

## Not in this slice

- Anchoring the head outside the file (a truncated chain is only caught with a pinned head).
- Chaining the stderr fallback (no store means no file to chain).
- Rotating keys, or publishing a key.
