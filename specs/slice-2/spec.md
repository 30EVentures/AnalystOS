# Slice 2 — L0: store one source, return its hash

## Goal

Store one file in an evidence folder, addressed by the hash of its contents,
and return that hash. The bottom of L0 — the thing every future citation
points at.

## Included

- `analystos/l0/store.py` — a `store(path)` function
- `analystos/__init__.py`, `analystos/l0/__init__.py` — mark the code folders
- `tests/test_l0_store.py` — one test per "Done when" check
- an `evidence/` folder at the repo root, git-ignored, where copies land

## Done when

1. `store("some/file.pdf")` returns a 64-character hex string (a SHA-256 hash).
2. A copy of the file now sits in `evidence/`, named by that hash.
3. Storing the **same file again** returns the **same hash** and makes no
   second copy.
4. A file with **one byte changed** returns a **different hash**.
5. The stored copy's bytes are identical to the original.
6. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Getting the file back out by hash → Slice 3.
- Any awareness of file *type* (PDF vs CSV) — bytes are bytes here.
- Metadata, timestamps, who stored it, storing many files at once.
- Any database — the folder *is* the store.
- How files are arranged *inside* `evidence/` (flat for now; could shard later
  without changing the hash-is-the-address contract).
- Robustness for very large files or crashes mid-copy — later.
