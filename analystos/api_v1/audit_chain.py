"""A hash-chained, signed audit log (Slice 84).

Each line of ``audit.jsonl`` is the event plus, added when it is written:

    seq          0, 1, 2 ... counted from the first chained line
    prev_hash    ``entry_hash`` of the line before it (``GENESIS`` for seq 0)
    log_signing  "ed25519" or "none"  - inside the hash, so a signature cannot
                 be stripped and the line relabelled "unsigned"
    key_id       the signing key's id (only when signed); also inside the hash
    entry_hash   ``sha256:`` + sha256 of canonical(the line minus entry_hash/signature)
    signature    (only when signed) Ed25519 over canonical({"domain":
                 "analystos.audit-entry/1", "entry_hash": entry_hash})

An insertion-order linear chain, not a Merkle tree over sorted ids: honest
growth only ever appends, and editing, deleting, reordering or inserting a
line breaks the next line's ``prev_hash``. Signing uses the seal's key
(``ANALYSTOS_SEAL_KEY``) and the seal's Ed25519 helpers; with no key a line is
still chained and says ``"log_signing": "none"``.

What it does not do: a chain that ends early looks like a shorter honest
chain (pin the head you saw: ``expected_head``), and whoever holds the signing
key, or the whole file when lines are unsigned, can rewrite history from some
point on. Tamper-evident, not tamper-proof. Lines written before this slice
(no ``entry_hash``) are tolerated as a legacy prefix; one after the chain has
begun is a failure.
"""

import hashlib
import json

from analystos.l4 import seal as seal_mod
from analystos.l4.seal_verify import _b64u_decode, _ed25519_verify, canonical_bytes, sha256_hex

GENESIS = "sha256:" + "0" * 64
ENTRY_DOMAIN = "analystos.audit-entry/1"
_UNHASHED = ("entry_hash", "signature")


def entry_hash(entry):
    return "sha256:" + sha256_hex(canonical_bytes({k: v for k, v in entry.items() if k not in _UNHASHED}))


def _signed_message(digest):
    return {"domain": ENTRY_DOMAIN, "entry_hash": digest}


def key_id(signing_key):
    """The 16-hex id of the signing key (the seal's own ``key_id``)."""
    return seal_mod._sign(_signed_message(GENESIS), signing_key)["key_id"]


def seal_entry(event, seq, prev_hash, signing_key=None):
    """The event as a chained line. ``signing_key`` is a b64url Ed25519 seed or ``None``."""
    entry = {**event, "seq": seq, "prev_hash": prev_hash, "log_signing": "ed25519" if signing_key else "none"}
    if signing_key:
        entry["key_id"] = key_id(signing_key)  # inside the hashed body
    entry["entry_hash"] = entry_hash(entry)
    if signing_key:
        entry["signature"] = seal_mod._sign(_signed_message(entry["entry_hash"]), signing_key)["sig"]
    return entry


def last_chained(lines):
    """``(seq, entry_hash)`` of the last chained line among decoded ``lines``
    (raw text), or ``None`` when no line is chained yet (empty or legacy-only)."""
    for raw in reversed(lines):
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if isinstance(entry, dict) and isinstance(entry.get("entry_hash"), str) and isinstance(entry.get("seq"), int):
            return entry["seq"], entry["entry_hash"]
    return None


def _check(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def verify_entries(raw_lines, public_key=None, expected_head=None):
    """Verify decoded text lines of an audit log. Pure and offline.

    Returns ``{"ok", "authentic", "chained", "legacy_unchained", "signed",
    "unsigned", "head", "checks"}``. ``ok``: nothing failed and at least one
    chained line was checked (an empty or legacy-only log verifies nothing and
    fails closed). ``authentic``: ``ok``, every line is signed, and every
    signature verified under the ``public_key`` you supplied.
    """
    errors, legacy, chained, signed, unsigned, bad_sigs = [], 0, 0, 0, 0, []
    prev = GENESIS
    sig_status = None
    started = False
    for number, raw in enumerate(raw_lines, start=1):
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except ValueError:
            errors.append(f"line {number} is not valid JSON")
            break
        if not isinstance(entry, dict):
            errors.append(f"line {number} is not an object")
            break
        if "entry_hash" not in entry:
            if started:
                errors.append(f"line {number} is unchained but comes after the chain began")
            else:
                legacy += 1
            continue
        started = True
        if entry.get("seq") != chained or isinstance(entry.get("seq"), bool):
            errors.append(f"line {number} has seq {entry.get('seq')!r}, expected {chained}")
        if entry.get("prev_hash") != prev:
            errors.append(f"line {number} does not link to the line before it")
        try:
            recomputed = entry_hash(entry)
        except (TypeError, ValueError):
            errors.append(f"line {number} cannot be hashed")
            break
        if entry.get("entry_hash") != recomputed:
            errors.append(f"line {number} does not match its own hash")
        mode = entry.get("log_signing")
        if mode == "ed25519":
            signed += 1
            sig = entry.get("signature")
            if not isinstance(sig, str) or not isinstance(entry.get("key_id"), str):
                errors.append(f"line {number} says it is signed but has no signature or key_id")
            elif public_key is not None:
                try:
                    key_id_ok = hashlib.sha256(_b64u_decode(public_key)).hexdigest()[:16] == entry["key_id"]
                    verdict = _ed25519_verify(public_key, sig, canonical_bytes(_signed_message(entry["entry_hash"])))
                except (ValueError, TypeError):
                    key_id_ok, verdict = False, False
                if verdict is None:
                    sig_status = "unavailable"
                elif not (key_id_ok and verdict):
                    bad_sigs.append(number)
        elif mode == "none":
            unsigned += 1
            if "signature" in entry:
                errors.append(f"line {number} says it is unsigned but carries a signature")
        else:
            errors.append(f"line {number} has log_signing {mode!r}")
        chained += 1
        prev = entry.get("entry_hash")  # follow the stored hash so one edit reports once
    head = prev if chained else None
    if expected_head is not None and head != expected_head:
        errors.append("head does not match the expected head (lines dropped or replaced)")

    checks = []
    if errors:
        checks.append(_check("chain", "fail", "; ".join(errors[:5])))
    elif chained == 0:
        checks.append(_check("chain", "fail", f"no chained lines to verify ({legacy} legacy line(s)); an empty or unchained log proves nothing"))
    else:
        checks.append(_check("chain", "pass", f"{chained} chained line(s) link from genesis and match their hashes"
                             + (f"; {legacy} legacy unchained line(s) before them" if legacy else "")))
    if signed == 0:
        checks.append(_check("signatures", "skipped", f"no line is signed ({unsigned} unsigned): integrity only, no claim about who wrote it"))
    elif bad_sigs:
        checks.append(_check("signatures", "fail", f"signature or key_id does not verify under the supplied key at line(s) {bad_sigs[:5]}"))
    elif public_key is None:
        checks.append(_check("signatures", "skipped", f"{signed} signed line(s), but no public key was supplied, so authenticity is not established"))
    elif sig_status == "unavailable":
        checks.append(_check("signatures", "skipped", "install `cryptography` to check the ed25519 signatures"))
    elif unsigned:
        checks.append(_check("signatures", "pass", f"{signed} signed line(s) verify under the supplied key; {unsigned} line(s) are unsigned"))
    else:
        checks.append(_check("signatures", "pass", f"all {signed} line(s) verify under the supplied key"))
    failed = any(c["status"] == "fail" for c in checks)
    return {
        "ok": not failed,
        "authentic": not failed and signed > 0 and unsigned == 0 and checks[-1]["status"] == "pass",
        "chained": chained, "legacy_unchained": legacy, "signed": signed, "unsigned": unsigned,
        "head": head, "checks": checks,
    }


def verify_audit_log(path, public_key=None, expected_head=None):
    """Verify the audit log file at ``path``. Raises ``OSError`` if it cannot be read."""
    with open(path, encoding="utf-8") as handle:
        return verify_entries(handle.read().splitlines(), public_key=public_key, expected_head=expected_head)
