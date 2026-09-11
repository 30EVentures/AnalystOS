"""L0 - the evidence store.

Every source is saved once, in the ``evidence/`` folder, named by the SHA-256
hash of its ORIGINAL (plaintext) bytes. That hash is the source's permanent
address: the same real content always produces the same name, and changing
any byte changes the name - so a tampered file no longer matches where it
was filed. The hash is computed from the plaintext on purpose, before
encryption (below) ever touches it - encryption uses a fresh random nonce
every time, so hashing the ciphertext would make the same source file a
different address on every store, breaking that guarantee.

What's actually written to disk under that name is encrypted (Slice 43),
not the plaintext bytes verbatim - ``store``/``retrieve``'s signatures and
round-trip contract are unchanged; only what's sitting on disk changed.
See specs/slice-43/spec.md.
"""

import hashlib
import os
import time
from base64 import urlsafe_b64encode
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

# Where stored sources land by default. Git-ignored - see .gitignore.
# parents[2] == the repo root (this file is analystos/l0/store.py).
DEFAULT_EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "evidence"

_EVIDENCE_KEY_ENV_VAR = "ANALYSTOS_EVIDENCE_KEY"
_RETENTION_DAYS_ENV_VAR = "ANALYSTOS_EVIDENCE_RETENTION_DAYS"
# A stable, repo-known fallback so the store is never plaintext-by-default,
# even with zero configuration - but this is a development fallback, not a
# secret: anyone with this source can derive it. Set ANALYSTOS_EVIDENCE_KEY
# in any real deployment for genuine protection.
_DEV_FALLBACK_KEY_MATERIAL = b"AnalystOS evidence store dev fallback - set ANALYSTOS_EVIDENCE_KEY in prod"


def _fernet() -> Fernet:
    """The Fernet cipher for this process: ``ANALYSTOS_EVIDENCE_KEY`` if
    set, else a stable local fallback (never a fresh random key per call -
    that would make every file undecryptable the moment it's generated
    again)."""
    raw = os.environ.get(_EVIDENCE_KEY_ENV_VAR)
    if raw:
        return Fernet(raw.encode("utf-8"))
    key = urlsafe_b64encode(hashlib.sha256(_DEV_FALLBACK_KEY_MATERIAL).digest())
    return Fernet(key)


def _retention_days():
    """The configured retention window in days, or ``None`` if unset/
    unparseable - unset means no expiry enforced, the same opt-in default
    Slices 41/42 already use for their own ceilings."""
    raw = os.environ.get(_RETENTION_DAYS_ENV_VAR)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def hash_of(path) -> str:
    """Return the SHA-256 hex digest of the file's original contents (64
    hex chars) - computed before encryption; see the module docstring."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def store(path, evidence_dir=None) -> str:
    """Encrypt and copy the file at ``path`` into the evidence store;
    return the hash of its original (plaintext) bytes.

    Storing the same bytes again is a no-op: the address is already taken.
    Also runs the retention cleanup pass (best-effort - a cleanup problem
    never breaks the store it's riding along with), so old evidence is
    actually purged over time without needing an external scheduler.

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
        ciphertext = _fernet().encrypt(src.read_bytes())
        dest.write_bytes(ciphertext)

    try:
        purge_expired_evidence(dest_dir)
    except OSError:
        pass

    return digest


def retrieve(digest, evidence_dir=None) -> bytes:
    """Return the original (decrypted) bytes stored under ``digest``.

    Raises ``FileNotFoundError`` if nothing is stored under that hash - the
    caller gets a clear failure, never the wrong file or empty bytes.
    Raises ``ValueError`` if what's on disk can't be decrypted with the
    configured key (wrong/missing ``ANALYSTOS_EVIDENCE_KEY``, or a file
    stored before Slice 43 under the old plaintext format).

    ``evidence_dir`` overrides where to look (tests use a temp folder).
    """
    dest_dir = Path(evidence_dir) if evidence_dir is not None else DEFAULT_EVIDENCE_DIR
    blob = dest_dir / digest

    if not blob.is_file():
        raise FileNotFoundError(f"nothing stored under {digest}")

    try:
        return _fernet().decrypt(blob.read_bytes())
    except InvalidToken as exc:
        raise ValueError(
            f"stored evidence under {digest} could not be decrypted - "
            "wrong or missing ANALYSTOS_EVIDENCE_KEY, or a pre-encryption file"
        ) from exc


def purge_expired_evidence(evidence_dir=None, max_age_days=None):
    """Delete any stored evidence file whose on-disk mtime is older than
    the retention window. Returns the list of digests (filenames) removed.

    ``max_age_days`` overrides ``ANALYSTOS_EVIDENCE_RETENTION_DAYS`` for
    this call; if neither is given, nothing is removed - opt-in, not a
    surprise deletion policy. Independently callable (a script, a
    scheduled task, a test), and also called from ``store`` itself so
    retention is enforced over time without needing an external cron job.
    """
    dest_dir = Path(evidence_dir) if evidence_dir is not None else DEFAULT_EVIDENCE_DIR
    days = max_age_days if max_age_days is not None else _retention_days()
    if days is None or not dest_dir.is_dir():
        return []

    cutoff = time.time() - (days * 86400)
    removed = []
    for entry in dest_dir.iterdir():
        if entry.is_file() and entry.stat().st_mtime < cutoff:
            entry.unlink()
            removed.append(entry.name)
    return removed
