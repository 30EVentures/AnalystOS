"""Verify an AnalystOS seal with the standard library only. Slice 60.

This file is the whole specification of the seal in executable form, kept
small on purpose so a stranger can port it (see ``docs/seal.md``). It imports
nothing from the rest of AnalystOS - not the analyzer, not the model client -
so checking a report does not require trusting, or even installing, the
thing that wrote it. Ed25519 checking needs the ``cryptography`` package; if
it is missing the signature check says so instead of passing.

    python3 -m analystos.l4.seal_verify bundle.json [--public-key B64URL] [--text extracted.txt]

Exit code: 0 no check failed, 1 a check failed, 2 unreadable input.

What a pass means, level by level (reported separately, never merged):

* ``ok``            - the bundle is internally consistent: every fact hashes
                      to what it claims, the facts make the signed Merkle
                      root, the report is the one that was sealed, and every
                      figure the report cites is one of the sealed facts.
* ``authentic``     - additionally, the signature verifies under a public key
                      *you supplied* (a key inside the bundle proves nothing).
* ``content_checked`` - additionally, with the extracted text: it is the text
                      that was sealed, every citation is in it, and every
                      calculation recomputes from its operands.

Not checked here: that a quote's numeric ``value`` agrees with the number its
citation spells out (AnalystOS checks that when it accepts the fact, and the
seal records the outcome). See ``docs/seal.md``.
"""

import base64
import hashlib
import json
import math
import re
import sys

SEAL_FORMAT = "analystos-seal/1"
PAYLOAD_VERSION = 1
LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"

_REF_KEYS = ("fact_index", "value_fact", "delta_fact")
_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")
_THOUSANDS_SEP_RE = re.compile(r"(?<=\d),(?=\d{3}(?:\D|$))")
_TRAILING_SCALE_RE = re.compile(r"\s*(?:thousand|million|billion|bn|mm|k|m|b)\s*$", re.IGNORECASE)
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def normalize(value):
    """Make a value canonical-JSON-safe: every number becomes a string
    (``repr`` for a float, ``str`` for an int), so no verifier has to agree
    with another about how to print a float. Booleans and null stay."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("cannot seal a NaN or infinite number")
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    raise ValueError(f"cannot seal a value of type {type(value).__name__}")


def canonical_bytes(value):
    """Keys sorted at every level, no whitespace, UTF-8, non-ASCII unescaped."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def fact_hash(record):
    return sha256_hex(canonical_bytes(record))


def leaf_hash(key, content_hash):
    return sha256_hex(LEAF_PREFIX + f"{key}\0{content_hash}".encode("utf-8"))


def node_hash(left_hex, right_hex):
    return sha256_hex(NODE_PREFIX + bytes.fromhex(left_hex) + bytes.fromhex(right_hex))


def merkle_root(leaves):
    """``leaves``: (key, leaf_hex) pairs. Sorted by key; an odd node is
    promoted unchanged. ``None`` for no leaves."""
    level = [h for _, h in sorted(leaves, key=lambda kv: kv[0])]
    if not level:
        return None
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            nxt.append(node_hash(level[i], level[i + 1]) if i + 1 < len(level) else level[i])
        level = nxt
    return level[0]


def match_key(text):
    """The folding used to compare a citation with the source: lowercase,
    unify dashes, drop ``$`` and ``|``, strip thousands separators, collapse
    whitespace."""
    t = text.lower().replace("–", "-").replace("—", "-").replace("−", "-")
    t = t.replace("$", " ").replace("|", " ")
    t = _THOUSANDS_SEP_RE.sub("", t)
    return " ".join(t.split())


def citation_in_text(citation, folded_text):
    key = match_key(citation)
    if not key:
        return False
    if key in folded_text:
        return True
    stripped = _TRAILING_SCALE_RE.sub("", key).strip()
    return bool(stripped) and stripped != key and stripped in folded_text


def recompute(operation, values, total=None):
    if operation in ("sum",):
        return sum(values)
    if operation in ("difference", "remainder"):
        return values[0] - sum(values[1:]) if len(values) >= 2 else None
    if operation == "average":
        return sum(values) / len(values) if values else None
    if operation == "ratio":
        return values[0] / values[1] if len(values) == 2 and values[1] != 0 else None
    if operation == "growth_percent":
        return (values[1] - values[0]) / values[0] * 100 if len(values) == 2 and values[0] != 0 else None
    if operation == "percent_of_total":
        return values[0] / total * 100 if len(values) == 1 and total else None
    return None


def _num(text):
    return float(text)


def _same(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def payload_bytes(payload):
    return canonical_bytes(payload)


def _b64u_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _check(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def _ed25519_verify(public_key_b64, signature_b64, message):
    """True/False, or None when the ``cryptography`` package is unavailable."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return None
    try:
        Ed25519PublicKey.from_public_bytes(_b64u_decode(public_key_b64)).verify(_b64u_decode(signature_b64), message)
        return True
    except (InvalidSignature, ValueError):
        return False


def _report_refs(node, out):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _REF_KEYS and isinstance(value, str) and re.fullmatch(r"-?\d+", value):
                if int(value) >= 0:
                    out.add(int(value))
            else:
                _report_refs(value, out)
    elif isinstance(node, list):
        for item in node:
            _report_refs(item, out)
    elif isinstance(node, str):
        out.update(int(m.group(1)) for m in _PLACEHOLDER_RE.finditer(node))


def verify_bundle(bundle, public_key=None, source_text=None):
    """Verify a seal bundle; see the module docstring for what each level means."""
    checks = []

    def result():
        failed = any(c["status"] == "fail" for c in checks)
        by = {c["name"]: c["status"] for c in checks}
        content_names = ("source_text_hash", "citations_in_text", "calculations")
        return {
            "ok": not failed,
            "authentic": not failed and by.get("signature") == "pass",
            "content_checked": not failed and all(by.get(n) == "pass" for n in content_names),
            "checks": checks,
        }

    try:
        ok_shape = (
            isinstance(bundle, dict) and bundle.get("format") == SEAL_FORMAT
            and isinstance(bundle.get("payload"), dict) and isinstance(bundle.get("facts"), list)
        )
    except Exception:
        ok_shape = False
    if not ok_shape:
        checks.append(_check("structure", "fail", f"not an {SEAL_FORMAT} bundle"))
        return result()
    payload, facts = bundle["payload"], bundle["facts"]
    needed = ("version", "org", "entries", "created", "nonce", "root", "source_sha256", "text_sha256", "report_sha256", "tier")
    missing = [k for k in needed if k not in payload]
    if missing or payload.get("version") != PAYLOAD_VERSION:
        checks.append(_check("structure", "fail", f"payload missing {missing} or wrong version"))
        return result()
    checks.append(_check("structure", "pass", f"{len(facts)} facts, tier {payload['tier']}"))

    bad = []
    keys = []
    for i, fact in enumerate(facts):
        try:
            key, record, claimed = fact["key"], fact["record"], fact["hash"]
            if not _HEX64_RE.match(claimed) or fact_hash(record) != claimed:
                bad.append(key)
            keys.append(key)
        except (KeyError, TypeError, ValueError):
            bad.append(f"#{i}")
    if bad or len(set(keys)) != len(keys):
        checks.append(_check("fact_hashes", "fail", f"facts that do not hash to what they claim, or duplicate keys: {bad[:5]}"))
        return result()
    checks.append(_check("fact_hashes", "pass", "every fact hashes to its recorded hash"))

    root = merkle_root([(f["key"], leaf_hash(f["key"], f["hash"])) for f in facts])
    if root != payload["root"] or payload["entries"] != len(facts):
        checks.append(_check("merkle_root", "fail", f"facts give root {root}, payload says {payload['root']} over {payload['entries']} entries"))
        return result()
    checks.append(_check("merkle_root", "pass", f"root {root}"))

    report = bundle.get("report")
    if payload["report_sha256"] is None:
        checks.append(_check("report_hash", "pass" if report is None else "fail",
                             "no report sealed (plain tier)" if report is None else "a report is present but none was sealed"))
    elif report is None or sha256_hex(canonical_bytes(report)) != payload["report_sha256"]:
        checks.append(_check("report_hash", "fail", "the report is missing or is not the one that was sealed"))
        return result()
    else:
        checks.append(_check("report_hash", "pass", "the report is the one that was sealed"))
        refs = set()
        _report_refs(report, refs)
        dangling = sorted(r for r in refs if r >= len(facts))
        checks.append(_check("report_refs", "fail" if dangling else "pass",
                             f"the report cites facts that were not sealed: {dangling}" if dangling
                             else f"all {len(refs)} cited facts are sealed"))

    sig = bundle.get("signature")
    if not sig:
        checks.append(_check("signature", "skipped", "unsigned: integrity only, no claim about who made it"))
    else:
        message = payload_bytes(payload)
        embedded = _ed25519_verify(sig.get("public_key", ""), sig.get("sig", ""), message)
        if embedded is None:
            checks.append(_check("signature", "skipped", "install `cryptography` to check the ed25519 signature"))
        elif embedded is False:
            checks.append(_check("signature", "fail", "the signature does not verify under the key in the bundle"))
        elif public_key is None:
            checks.append(_check("signature", "skipped",
                                 "valid under the key inside the bundle, but no pinned key was supplied, so authenticity is not established"))
        else:
            pinned = _ed25519_verify(public_key, sig["sig"], message)
            checks.append(_check("signature", "pass" if pinned else "fail",
                                 "valid under the pinned public key" if pinned else "does not verify under the pinned public key"))

    if source_text is None:
        for name in ("source_text_hash", "citations_in_text", "calculations"):
            checks.append(_check(name, "skipped", "no extracted text supplied"))
        return result()

    same = sha256_hex(source_text.encode("utf-8")) == payload["text_sha256"]
    checks.append(_check("source_text_hash", "pass" if same else "fail",
                         "the text is the text that was sealed" if same
                         else "the supplied text is not the text that was sealed; the checks below ran on it anyway"))
    folded = match_key(source_text)
    missing_cites, bad_calcs, checked_cites, checked_calcs = [], [], 0, 0
    for fact in facts:
        record = fact["record"]
        cites = record.get("citation")
        cites = [cites] if isinstance(cites, str) else cites if isinstance(cites, list) else []
        for c in cites:
            checked_cites += 1
            if not isinstance(c, str) or not citation_in_text(c, folded):
                missing_cites.append(f"{fact['key']}: {c!r}"[:80])
        if record.get("type") == "computed":
            checked_calcs += 1
            try:
                values = [_num(v) for v in record["operands"]]
                total = _num(record["total"]) if record.get("total") is not None else None
                claimed = _num(record["value"])
                expected = recompute(record["operation"], values, total)
                if record["operation"] == "growth_percent" and (expected is None or not _same(expected, claimed)):
                    expected = recompute("growth_percent", list(reversed(values)), total)
                if expected is None or not _same(expected, claimed):
                    bad_calcs.append(f"{fact['key']}: {record['operation']} gives {expected!r}, sealed {claimed!r}")
            except (KeyError, TypeError, ValueError):
                bad_calcs.append(f"{fact['key']}: malformed calculation")
    checks.append(_check("citations_in_text", "fail" if missing_cites else "pass",
                         f"citations not found in the text: {missing_cites[:5]}" if missing_cites
                         else f"all {checked_cites} citations are in the text"))
    checks.append(_check("calculations", "fail" if bad_calcs else "pass",
                         f"calculations that do not recompute: {bad_calcs[:5]}" if bad_calcs
                         else f"all {checked_calcs} calculations recompute"))
    return result()


def main(argv=None, stdout=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    public_key = source_text = path = None
    try:
        i = 0
        while i < len(argv):
            if argv[i] == "--public-key":
                public_key = argv[i + 1]
                i += 2
            elif argv[i] == "--text":
                with open(argv[i + 1], encoding="utf-8") as handle:
                    source_text = handle.read()
                i += 2
            else:
                path, i = argv[i], i + 1
        if path is None:
            raise ValueError("usage: python3 -m analystos.l4.seal_verify bundle.json [--public-key B64URL] [--text extracted.txt]")
        with open(path, encoding="utf-8") as handle:
            bundle = json.load(handle)
    except (OSError, ValueError, IndexError) as exc:
        stdout.write(json.dumps({"error": str(exc)}) + "\n")
        return 2
    outcome = verify_bundle(bundle, public_key=public_key, source_text=source_text)
    stdout.write(json.dumps(outcome, indent=2) + "\n")
    return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
