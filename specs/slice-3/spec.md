# Slice 3 — L0: retrieve a source by its hash

## Goal

Given a hash, return the exact bytes stored under it. If nothing is stored
under that hash, fail clearly. The other half of L0 — `store` puts evidence
in, `retrieve` gets it back out unchanged.

## Included

- `analystos/l0/store.py` — add a `retrieve(hash, evidence_dir=None)` function
- `tests/test_l0_store.py` — add tests for `retrieve`
- no new files, no new folders

## Done when

1. Store a file, then `retrieve` with the hash it returned → you get bytes
   identical to the original file.
2. `retrieve` of a hash that was never stored → a clear error (not empty
   bytes, not a wrong file).
3. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Returning anything but raw bytes (no "open as PDF", no text decoding).
- Listing or searching what's in the store.
- Re-checking the stored file's hash on the way out — its own slice later.
- Streaming huge files — reads it all into memory, like `store` does.
