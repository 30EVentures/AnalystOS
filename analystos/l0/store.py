"""L0 - the evidence store.

Every source is saved once, in the ``evidence/`` folder, named by the SHA-256
hash of its bytes. That hash is the source's permanent address: the same bytes
always produce the same name, and changing any byte changes the name - so a
tampered file no longer matches where it was filed.
"""

import hashlib
import shutil
from pathlib import Path

# Where stored sources land by default. Git-ignored - see .gitignore.
# parents[2] == the repo root (this file is analystos/l0/store.py).
DEFAULT_EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "evidence"


def hash_of(path) -> str:
    """Return the SHA-256 hex digest of the file's contents (64 hex chars)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def store(path, evidence_dir=None) -> str:
    """Copy the file at ``path`` into the evidence store; return its hash.

    Storing the same bytes again is a no-op: the address is already taken.

    ``evidence_dir`` overrides where copies land (tests use a temp folder).
    """
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"no file at {src}")

    digest = hash_of(src)

    dest_dir = Path(evidence_dir) if evidence_dir is not None else DEFAULT_EVIDENCE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / digest

    if not dest.exists():
        shutil.copyfile(src, dest)

    return digest
