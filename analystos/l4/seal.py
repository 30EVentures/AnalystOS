"""Seal a delivered report so a stranger can re-verify it. Slice 60.

``build_bundle(trace)`` turns what ``build_report(..., trace=...)`` recorded
into a self-contained bundle (see ``docs/seal.md``): every fact, hashed and
committed to a Merkle root; the report structure that cites them; the source
and extracted-text hashes; and, if a signing key is configured, an Ed25519
signature over the root payload. Checking it needs only
``analystos.l4.seal_verify``.

Signing key: ``ANALYSTOS_SEAL_KEY`` (base64url of a 32-byte Ed25519 seed;
``python3 -m analystos.l4.seal keygen`` makes one). With no key the bundle is
**unsigned** - integrity only, and it says so - never signed with a
built-in default (the evidence store's public fallback key taught why).
"""

import base64
import hashlib
import os
import sys
from datetime import datetime, timezone

from analystos.l4.seal_verify import (
    PAYLOAD_VERSION, SEAL_FORMAT, canonical_bytes, fact_hash, leaf_hash, merkle_root, normalize,
    payload_bytes, sha256_hex,
)

SEAL_KEY_ENV = "ANALYSTOS_SEAL_KEY"
ORG = "analystos"
_SEALABLE_TIERS = ("written", "deterministic", "plain")


def _b64u(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def generate_key():
    """``(private_seed_b64url, public_key_b64url)`` for a new signing key."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return _b64u(seed), _b64u(public)


def load_signing_key(environ=None):
    """The configured seed (b64url) or ``None``. A malformed value is an
    error, not a silent downgrade to unsigned."""
    raw = (environ if environ is not None else os.environ).get(SEAL_KEY_ENV, "").strip()
    if not raw:
        return None
    if len(_b64u_decode(raw)) != 32:
        raise ValueError(f"{SEAL_KEY_ENV} must be the base64url of a 32-byte Ed25519 seed")
    return raw


def _sign(payload, seed_b64):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(_b64u_decode(seed_b64))
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "alg": "ed25519",
        "sig": _b64u(key.sign(payload_bytes(payload))),
        "public_key": _b64u(public),
        "key_id": hashlib.sha256(public).hexdigest()[:16],
    }


def build_bundle(trace, *, org=ORG, created=None, signing_key=None):
    """Seal one run. ``trace`` is the dict ``build_report`` fills. Raises
    ``ValueError`` for a run that cannot be sealed (the table path, or no
    facts)."""
    tier = trace.get("tier")
    if tier not in _SEALABLE_TIERS:
        raise ValueError(f"a {tier!r} run is not sealed - only narrated runs have verified facts to seal")
    segments = trace.get("segments") or []
    if not segments:
        raise ValueError("nothing to seal: the run has no verified facts")
    created = created or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    facts, leaves = [], []
    for i, segment in enumerate(segments):
        key = f"fact/{i:06d}"
        record = normalize(segment)
        digest = fact_hash(record)
        facts.append({"key": key, "record": record, "hash": digest})
        leaves.append((key, leaf_hash(key, digest)))
    report = trace.get("report")
    report = normalize(report) if report is not None else None
    text = trace.get("document_text") or ""
    payload = {
        "version": PAYLOAD_VERSION,
        "org": org,
        "entries": len(facts),
        "created": created,
        "root": merkle_root(leaves),
        "source_sha256": trace.get("source_hash"),
        "text_sha256": sha256_hex(text.encode("utf-8")),
        "report_sha256": sha256_hex(canonical_bytes(report)) if report is not None else None,
        "tier": tier,
    }
    return {
        "format": SEAL_FORMAT,
        "payload": payload,
        "facts": facts,
        "report": report,
        "signature": _sign(payload, signing_key) if signing_key else None,
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv != ["keygen"]:
        print("usage: python3 -m analystos.l4.seal keygen", file=sys.stderr)
        return 2
    private, public = generate_key()
    print(f"{SEAL_KEY_ENV}={private}")
    print(f"public key (publish this so others can pin it): {public}")
    print("Keep the first line secret. It is printed once and stored nowhere.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
