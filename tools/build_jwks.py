#!/usr/bin/env python3
"""Serve AnalystOS's public signing keys as a JWKS (Slice 132, Flashy plan C-ID-6).

    python3 tools/build_jwks.py           # write site/.well-known/jwks.json
    python3 tools/build_jwks.py --check   # exit 1 if it is stale

Derived from site/.well-known/analystos-seal-key.json, never typed by hand, so the
two files cannot disagree: each key's `kid` is that file's `key_id`, and `x` is its
`public_key`. The shape is a standard OKP JWK ({kty, crv, x, kid, use, alg}), which
Flashy's key reader and any JOSE library accept.

One key today, the report-seal key. Flashy's plan asks for one key per purpose
(seals, agent assertions, organisation signatures, invoices) so that a compromised
seal key cannot mint identity or ask for payment. The other keys are added here
when the slices that use them exist; publishing a key nothing signs with would
claim a capability AnalystOS does not have.
"""

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEAL_KEY_PATH = ROOT / "site" / ".well-known" / "analystos-seal-key.json"
JWKS_PATH = ROOT / "site" / ".well-known" / "jwks.json"


def jwk_for(key: dict) -> dict:
    if key.get("algorithm") != "ed25519":
        raise ValueError(f"key {key.get('key_id')}: only ed25519 is published")
    x = key["public_key"]
    if len(base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))) != 32:
        raise ValueError(f"key {key['key_id']}: an Ed25519 public key is 32 bytes")
    return {"kty": "OKP", "crv": "Ed25519", "x": x, "kid": key["key_id"], "use": "sig", "alg": "EdDSA"}


def build() -> str:
    seal = json.loads(SEAL_KEY_PATH.read_text(encoding="utf-8"))
    keys = [jwk_for(k) for k in seal["keys"] if k.get("status") == "active"]
    return json.dumps({"keys": keys}, indent=2) + "\n"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    text = build()
    current = JWKS_PATH.read_text(encoding="utf-8") if JWKS_PATH.exists() else None
    if "--check" in argv:
        if current != text:
            print("site/.well-known/jwks.json is stale")
            return 1
        print("jwks.json matches the seal-key file")
        return 0
    if current == text:
        print("jwks.json: nothing to do")
        return 0
    JWKS_PATH.write_text(text, encoding="utf-8")
    print("wrote site/.well-known/jwks.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
