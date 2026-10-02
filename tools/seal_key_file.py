"""Write or check the public seal-verification key file (Slice 86).

    ANALYSTOS_SEAL_KEY=... python3 tools/seal_key_file.py --from-env     # write the file
    python3 tools/seal_key_file.py --public-key B64URL                  # or give the public half
    python3 tools/seal_key_file.py --from-env --add                     # rotate: new key active, old retired
    python3 tools/seal_key_file.py --check site/.well-known/analystos-seal-key.json

The file goes to ``site/.well-known/analystos-seal-key.json`` unless ``--out`` says
otherwise. It holds **only public keys**. ``--from-env`` derives the public key from
``ANALYSTOS_SEAL_KEY`` in your own shell, so no key is ever pasted, printed or stored
by this tool; ``--public-key`` refuses a value equal to the private seed in the
environment (``keygen`` prints both halves next to each other and pasting the wrong
line would publish the secret). It refuses to overwrite an existing file: rotate with
``--add``. Exit code 0 on success, 1 when ``--check`` finds a problem, 2 for bad input.
"""

import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analystos.l4.seal import ORG, SEAL_KEY_ENV  # noqa: E402
from analystos.l4.seal_verify import (  # noqa: E402
    KEY_FILE_FORMAT, KEY_FILE_MAX_BYTES, _B64U_KEY_RE, _b64u_decode, _b64u_encode, validate_key_file,
)

DEFAULT_OUT = ROOT / "site" / ".well-known" / "analystos-seal-key.json"
SEAL_SPEC = "https://analystos.dev/docs/seal.md"
_VALUED = ("--public-key", "--out", "--added", "--check")


class Refusal(Exception):
    """Bad input or an unsafe request; the message is shown, nothing is written."""


def public_key_from_seed(seed_b64url):
    """The base64url public key for a base64url Ed25519 seed (needs ``cryptography``)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    try:
        raw = _b64u_decode(seed_b64url)
        if len(raw) != 32:
            raise ValueError("not 32 bytes")
        key = Ed25519PrivateKey.from_private_bytes(raw)
    except ValueError as exc:
        raise Refusal(f"{SEAL_KEY_ENV} must be the base64url of a 32-byte Ed25519 seed ({exc})") from exc
    return _b64u_encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def check_public_key(public_key):
    """Refuse anything that is not the canonical unpadded base64url of 32 bytes."""
    ok = isinstance(public_key, str) and _B64U_KEY_RE.match(public_key)
    raw = _b64u_decode(public_key) if ok else b""
    if not ok or len(raw) != 32 or _b64u_encode(raw) != public_key:
        raise Refusal("that is not an Ed25519 public key: expected exactly 43 base64url characters "
                      "(the line keygen labels 'public key'). Nothing was written.")
    return public_key


def key_entry(public_key, added, status="active"):
    raw = _b64u_decode(check_public_key(public_key))
    return {
        "added": added,
        "algorithm": "ed25519",
        "key_id": hashlib.sha256(raw).hexdigest()[:16],
        "public_key": public_key,
        "status": status,
    }


def build_key_file(entries):
    return {"format": KEY_FILE_FORMAT, "keys": entries, "org": ORG, "seal_spec": SEAL_SPEC}


def render(doc):
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def _load_existing(path):
    try:
        with open(path, "rb") as handle:
            raw = handle.read(KEY_FILE_MAX_BYTES + 1)
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise Refusal(f"cannot read the existing key file {path}: {exc}") from exc
    problems = validate_key_file(doc)
    if problems:
        raise Refusal(f"the existing key file is not valid, so it will not be extended: {'; '.join(problems[:3])}")
    return doc


def write_key_file(public_key, out, add=False, added=None):
    """Write (or, with ``add``, extend) the key file at ``out``; returns the document."""
    added = added or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    out = Path(out)
    entry = key_entry(public_key, added)
    if out.exists():
        if not add:
            raise Refusal(f"{out} already exists; refusing to overwrite it. To rotate, add the new key with --add")
        doc = _load_existing(out)
        if any(k["key_id"] == entry["key_id"] for k in doc["keys"]):
            raise Refusal(f"key {entry['key_id']} is already listed in {out}")
        doc["keys"] = [dict(k, status="retired") for k in doc["keys"]] + [entry]
    else:
        if add:
            raise Refusal(f"{out} does not exist, so there is nothing to add to; write it first without --add")
        doc = build_key_file([entry])
    problems = validate_key_file(doc)
    if problems:  # a bug or bad input, never a file we should write
        raise Refusal("refusing to write an invalid key file: " + "; ".join(problems[:3]))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(render(doc), encoding="utf-8")
    os.replace(tmp, out)
    return doc


def _parse(argv):
    flags, values, i = set(), {}, 0
    while i < len(argv):
        arg = argv[i]
        if arg in _VALUED:
            if i + 1 >= len(argv):
                raise Refusal(f"{arg} needs a value")
            values[arg] = argv[i + 1]
            i += 2
        elif arg in ("--from-env", "--add"):
            flags.add(arg)
            i += 1
        else:
            raise Refusal(f"unexpected argument {arg!r}")
    return flags, values


def main(argv=None, stdout=None, environ=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    env = os.environ if environ is None else environ
    try:
        flags, values = _parse(argv)
        if "--check" in values:
            if flags or set(values) != {"--check"}:
                raise Refusal("--check takes only a path")
            try:
                with open(values["--check"], "rb") as handle:
                    doc = json.loads(handle.read(KEY_FILE_MAX_BYTES + 1).decode("utf-8"))
            except (OSError, ValueError) as exc:
                raise Refusal(f"cannot read {values['--check']}: {exc}") from exc
            problems = validate_key_file(doc)
            stdout.write(json.dumps({"valid": not problems, "problems": problems}, indent=2) + "\n")
            return 0 if not problems else 1
        from_env, given = "--from-env" in flags, values.get("--public-key")
        if from_env == (given is not None):
            raise Refusal("give exactly one of --from-env or --public-key")
        seed = (env.get(SEAL_KEY_ENV) or "").strip()
        if from_env:
            if not seed:
                raise Refusal(f"{SEAL_KEY_ENV} is not set in this shell")
            public_key = public_key_from_seed(seed)
        else:
            public_key = given.strip()
            if seed and public_key == seed:
                raise Refusal(
                    f"that value is your PRIVATE signing key ({SEAL_KEY_ENV}), not the public key. "
                    "Nothing was written. Use --from-env, or the line keygen labels 'public key'."
                )
        out = Path(values.get("--out", DEFAULT_OUT))
        doc = write_key_file(public_key, out, add="--add" in flags, added=values.get("--added"))
        newest = doc["keys"][-1]
        stdout.write(json.dumps({"wrote": str(out), "key_id": newest["key_id"], "public_key": newest["public_key"],
                                 "keys": len(doc["keys"]), "active": [k["key_id"] for k in doc["keys"] if k["status"] == "active"]},
                                indent=2) + "\n")
        print("Only the public key was written. The private seed is not stored or printed by this tool.", file=sys.stderr)
        return 0
    except Refusal as exc:
        print(f"seal_key_file: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
