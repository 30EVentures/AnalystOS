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
import re
import secrets
import sys
from datetime import datetime, timezone

from analystos.l4.seal_verify import (
    PAYLOAD_VERSION, SEAL_FORMAT, canonical_bytes, fact_hash, leaf_hash, merkle_root, normalize,
    payload_bytes, sha256_hex,
)

SEAL_KEY_ENV = "ANALYSTOS_SEAL_KEY"
CODE_VERSION_ENV = "ANALYSTOS_CODE_VERSION"
VERCEL_SHA_ENV = "VERCEL_GIT_COMMIT_SHA"  # set by Vercel for a git deployment; nothing here shells out to git
ORG = "analystos"
# caller_id for runs with no API-key name. Parentheses are not allowed in a
# key name (analystos.api_v1.auth), so these can never equal a real caller.
CALLER_CLI = "(cli)"
CALLER_LEGACY = "(legacy-access-code)"
_CODE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
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


def code_version(environ=None):
    """The deployed code's version for the seal payload (Slice 83), or ``None``
    when the deployment does not say. Read from ``ANALYSTOS_CODE_VERSION``,
    else Vercel's ``VERCEL_GIT_COMMIT_SHA``: both are fixed when the code is
    deployed, so the value is derived from the deployment, not looked up at
    request time or claimed by the caller. ``None`` means "not stated", never
    a guess. A malformed explicit value is an error, not a silent downgrade."""
    env = environ if environ is not None else os.environ
    for name in (CODE_VERSION_ENV, VERCEL_SHA_ENV):
        raw = (env.get(name) or "").strip()
        if raw:
            if not _CODE_VERSION_RE.match(raw):
                raise ValueError(f"{name} must be a short version label or commit id (letters, digits, . _ + -), got {raw!r}")
            return raw
    return None


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


def build_bundle(trace, *, org=ORG, created=None, nonce=None, signing_key=None,
                 caller_id=None, code_version_override=None):
    """Seal one run. ``trace`` is the dict ``build_report`` fills. Raises
    ``ValueError`` for a run that cannot be sealed (the table path, or no
    facts).

    Slice 83 adds three accountability fields to the signed payload:
    ``model_id`` (``trace["model"]``, the model the run asked), ``caller_id``
    (the API-key name, or ``CALLER_CLI`` / ``CALLER_LEGACY``; ``None`` when the
    caller does not say) and ``code_version`` (``code_version()``, or
    ``code_version_override``; ``None`` when the deployment does not say)."""
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
        "nonce": nonce or secrets.token_hex(8),
        "root": merkle_root(leaves),
        "source_sha256": trace.get("source_hash"),
        "text_sha256": sha256_hex(text.encode("utf-8")),
        "report_sha256": sha256_hex(canonical_bytes(report)) if report is not None else None,
        "tier": tier,
        "model_id": trace.get("model"),
        "caller_id": caller_id,
        "code_version": code_version_override if code_version_override is not None else code_version(),
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
