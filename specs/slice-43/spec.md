# Slice 43 — L0 encryption at rest + a retention/expiry policy

## Goal

`evidence/` has held plain, unencrypted copies of every uploaded source
since Slice 2, indefinitely - no retention policy, and anyone with disk
access reads them directly. This slice adds both: files are now encrypted
at rest, and a configurable retention window actually removes files past
it. The content-addressed hash naming and round-trip guarantee (Slice 2/3)
are unchanged from the caller's point of view - `store`/`retrieve` keep
their exact signatures and behavior; what changes is what's actually
sitting on disk under that hash.

## Included

- `analystos/l0/store.py`:
  - `hash_of` keeps hashing the **original (plaintext)** bytes - the
    content-addressed name must stay based on real content, not on
    ciphertext that changes every time the same bytes are encrypted (a
    fresh random nonce each time) - or the same source would file under a
    different hash on every store, breaking the "same bytes -> same name"
    guarantee this store exists for.
  - `store` now writes `Fernet(key).encrypt(original_bytes)` to disk
    instead of the original bytes verbatim. `retrieve` decrypts before
    returning - the round trip (`retrieve(store(x)) == x`) is unchanged
    from a caller's perspective.
  - The key: `ANALYSTOS_EVIDENCE_KEY` if set (a real Fernet key - set this
    in any real deployment). If unset, a **stable, repo-known development
    fallback** derived from a fixed local constant - evidence is still
    genuinely encrypted at rest even with zero configuration (never
    plaintext), but this fallback is not a secret and must not be treated
    as one; it exists so the store isn't silently insecure-by-default in a
    dev environment, not to be relied on anywhere real data matters.
  - `purge_expired_evidence(evidence_dir=None, max_age_days=None)` - a
    standalone, independently callable cleanup pass: any stored file whose
    on-disk mtime is older than the retention window is deleted. Returns
    the digests it removed. Configurable via
    `ANALYSTOS_EVIDENCE_RETENTION_DAYS`; **unset means no expiry** - the
    same "second layer, opt-in" pattern Slices 41/42 already use, not a
    surprise deletion policy forced on by default. `store()` also calls
    this itself (best-effort, never lets a cleanup problem break the store
    it's riding along with) so retention is actually enforced over time
    without needing an external cron job, while remaining directly
    callable on its own (from a script, a scheduled task, or a test).
  - Deletion, not archiving, for "past the retention window" - the simpler
    of the two options the task explicitly allowed ("delete or archive").
- `requirements.txt` / `docs/decisions.md` - `cryptography` added as a
  direct, pinned dependency (already present transitively; this makes it
  explicit) with the reasoning above recorded.
- `tests/test_l0_store.py` - `test_stored_bytes_match_the_original`
  (Slice 2's original assertion, written when the store was plaintext by
  design) is replaced: it asserted exactly the property this slice
  removes, so keeping it unchanged would mean asserting the store is
  *not* encrypted. The existing round-trip test
  (`test_retrieve_returns_the_original_bytes`) already covers `Done when`
  #2 below unchanged - `retrieve()`'s contract never moved.
- `tests/test_l0_retention.py` - the expiry cleanup pass, its own file.

## Done when

1. A stored file is **not** readable as plaintext directly from disk - a
   test reads the raw bytes under `evidence/<hash>` and confirms the
   original content is not literally present in them.
2. A round trip (`retrieve(store(path)) == path's original bytes`) passes -
   the existing Slice 3 test already proves this holds through the new
   encryption layer unchanged.
3. An expiry test proves a file past its retention window is actually
   removed on the next cleanup run: store a file, backdate its on-disk
   mtime past a configured retention window, run the cleanup pass, and
   confirm the file is gone from disk and `retrieve()` now raises
   `FileNotFoundError` for that hash.
4. Every existing L0 test (`tests/test_l0_store.py`, apart from the one
   assertion this slice necessarily inverts) keeps passing unchanged -
   the hash algorithm, idempotency, and the "one byte changes the hash"
   guarantee are all unaffected by encryption.
5. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Migrating evidence files already on disk from before this slice (plain
  bytes stored under Slice 2's original behavior) - `evidence/` is
  git-ignored, dev/test data at this stage, not production data needing a
  migration path. A pre-existing plaintext file under a hash simply fails
  to decrypt if `retrieve()` is ever called on it (a clean `ValueError`,
  not a crash) - retrieve() is not currently called anywhere in the live
  pipeline (confirmed by inspection: only `store()` is used, for the hash
  itself), so this has no live-behavior impact today.
- Key rotation, multiple active keys, or per-file keys - one key from one
  env var, same category of scope Slice 22 already accepted for the
  access code.
- Archiving (moving to cold storage) as an alternative to deletion - the
  task's own "e.g." allowed either; deletion is simpler and sufficient
  here.
- A real cron/scheduled trigger for cleanup - `purge_expired_evidence` is
  called opportunistically from `store()` and is independently callable,
  but nothing in this repo runs it on a fixed external schedule.
