"""Generate ``conformance/seal-1.json``, a refusal-first conformance corpus (Slice 87).

    python3 tools/build_conformance_corpus.py            # write
    python3 tools/build_conformance_corpus.py --check    # exit 1 if the file is stale

The corpus is data: every case is ``{id, set, input, expect: {valid, codes?}, note}`` so an
implementation in any language can be run against it (``python3 -m analystos.conformance`` is
this repo's adapter for the one-JSON-object-per-line protocol, see ``analystos/conformance.py``).

Expectations are written **by hand below**, never computed by the verifier under test; that would
make the corpus agree with the code by construction. Only the *inputs* are built with the real
sealing/chaining code, then deliberately broken.

Two published TEST keys are used so the output is byte-for-byte reproducible (Ed25519 signatures
are deterministic). They are not secrets and sign nothing real: the seeds are ``bytes(range(32))``
and ``bytes(range(32, 64))``.
"""

import base64
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analystos.api_v1 import audit_chain  # noqa: E402
from analystos.l4 import seal  # noqa: E402
from analystos.l4.seal_verify import KEY_FILE_FORMAT, canonical_bytes, fact_hash, leaf_hash, merkle_root, sha256_hex  # noqa: E402

OUT = ROOT / "conformance" / "seal-1.json"


def b64u(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


SEED_A, SEED_B = b64u(bytes(range(32))), b64u(bytes(range(32, 64)))
PUB_A = seal._sign({}, SEED_A)["public_key"]
PUB_B = seal._sign({}, SEED_B)["public_key"]
KEY_ID_A = hashlib.sha256(base64.urlsafe_b64decode(PUB_A + "==")).hexdigest()[:16]
KEY_ID_B = hashlib.sha256(base64.urlsafe_b64decode(PUB_B + "==")).hexdigest()[:16]

TEXT = "Revenue was $498.0 million. Net income fell from $22.4 million to $19.6 million."
SEGMENTS = [
    {"type": "quote", "label": "Revenue", "value": 498000000.0, "format": "usd",
     "citation": "$498.0 million", "horizon": "reported", "gaap_status": "n/a"},
    {"type": "computed", "label": "Net income change", "operation": "growth_percent", "value": -12.5,
     "format": "percent", "operands": [22400000.0, 19600000.0], "total": None,
     "citation": ["$22.4 million", "$19.6 million"], "horizon": "reported"},
    {"type": "prose", "text": "Momentum continued.", "horizon": "reported"},
]
REPORT = {"title": "T", "kpis": [{"label": "R", "value_fact": 0, "delta_fact": 1}],
          "executive_summary": [{"text": "Revenue was {{0}}, and income moved {{1}}."}]}
SRC = "a" * 64
CREATED = "2026-10-01T00:00:00Z"
NONCE = "0011223344556677"


def make(segments=None, report=REPORT, text=TEXT, tier="written", key=SEED_A, **kw):
    trace = {"tier": tier, "segments": copy.deepcopy(SEGMENTS if segments is None else segments),
             "report": copy.deepcopy(report), "document_text": text, "source_hash": SRC, "model": "test-model-1"}
    kw.setdefault("caller_id", "agent-a")
    kw.setdefault("code_version_override", "abc1234")
    return seal.build_bundle(trace, created=CREATED, nonce=NONCE, signing_key=key, **kw)


def resign(bundle, key=SEED_A):
    """Re-sign after editing the payload (an attacker who holds the key, or a test of a legacy shape)."""
    bundle["signature"] = seal._sign(bundle["payload"], key)
    return bundle


def rehash_facts(bundle, key=SEED_A):
    """Make the facts, hashes, root and entries internally consistent again (an attacker who rebuilds
    the whole bundle) and sign with ``key``."""
    for fact in bundle["facts"]:
        fact["hash"] = fact_hash(fact["record"])
    bundle["payload"]["root"] = merkle_root([(f["key"], leaf_hash(f["key"], f["hash"])) for f in bundle["facts"]])
    bundle["payload"]["entries"] = len(bundle["facts"])
    return resign(bundle, key) if key else bundle


def edit(bundle, fn):
    out = copy.deepcopy(bundle)
    fn(out)
    return out


BASE = make()
UNSIGNED = make(key=None)
OTHER = make(caller_id="agent-b")  # same key, different payload (nonce equal, caller differs)
KEY_FILE = {"format": KEY_FILE_FORMAT, "org": "analystos",
            "keys": [{"key_id": KEY_ID_A, "algorithm": "ed25519", "public_key": PUB_A, "status": "active", "added": "2026-10-01"}]}

CASES = []

# Cases the current code is known to get wrong: the case stays strict (it is never weakened), and the
# runner requires it to keep failing until the entry is removed here. Each needs a decisions.md note.
KNOWN_GAPS = {
    "seal/no-facts-vacuous": "a bundle with zero facts verifies (vacuous pass)",
    "seal/entry-key-is-a-number": "verify_bundle raises TypeError instead of refusing",
    "seal/entry-key-is-a-list": "verify_bundle raises TypeError instead of refusing",
    "seal/signature-is-a-string": "verify_bundle raises AttributeError instead of refusing",
    "seal/signature-is-a-list": "verify_bundle raises AttributeError instead of refusing",
    "seal-content/fact-record-is-not-an-object": "verify_bundle raises AttributeError instead of refusing",
    "audit/duplicate-key-in-a-line": "verify_entries keeps the last duplicate key silently",
    "audit/non-finite-number-literal": "verify_entries accepts a NaN literal, which is not JSON",
}


def add(set_, id_, input_, valid, codes=None, note=""):
    assert codes is None or isinstance(codes, list), f"{id_}: codes must be a list (did a note land in the codes slot?)"
    expect = {"valid": valid}
    if codes:
        expect["codes"] = sorted(codes)
    CASES.append({"id": f"{set_}/{id_}", "set": set_, "input": input_, "expect": expect, "note": note})


def sealcase(bundle, **extra):
    return {"bundle": bundle, **extra}


# --- seal: valid = ok (internally consistent) ------------------------------------------------------
S = "seal"
add(S, "signed-valid-pinned", sealcase(BASE, public_key=PUB_A), True, note="a signed bundle checked against the pinned key")
add(S, "signed-valid-no-pin", sealcase(BASE), True, note="ok does not claim authenticity; the -authentic set refuses this")
add(S, "unsigned-valid", sealcase(UNSIGNED), True, note="integrity only")
add(S, "legacy-no-accountability-fields",
    sealcase(rehash_facts(edit(BASE, lambda b: [b["payload"].pop(k) for k in ("model_id", "caller_id", "code_version")])), public_key=PUB_A),
    True, note="a seal made before Slice 83 must keep verifying")
add(S, "accountability-fields-null",
    sealcase(resign(edit(BASE, lambda b: b["payload"].update(model_id=None, caller_id=None, code_version=None))), public_key=PUB_A), True,
    note="null is 'not stated'")
add(S, "accountability-field-128-chars",
    sealcase(resign(edit(BASE, lambda b: b["payload"].update(caller_id="c" * 128))), public_key=PUB_A), True, note="boundary: 128 allowed")
add(S, "one-fact", sealcase(make(segments=SEGMENTS[2:], report=None, tier="plain", key=None)), True, note="a single leaf is its own root")
add(S, "five-facts-odd-merkle",
    sealcase(make(segments=[{"type": "prose", "text": f"t{i}"} for i in range(5)], report=None, tier="plain", key=None)), True,
    note="odd levels promote the unpaired node unchanged")
add(S, "plain-tier-no-report", sealcase(make(report=None, tier="plain", key=None)), True, note="no report sealed, none present")
add(S, "numbers-as-strings", sealcase(rehash_facts(edit(BASE, lambda b: b["facts"][2]["record"].update(
    big="123456789012345678901234567890", exp="1e999", nan="NaN", neg_zero="-0")), key=None) | {"signature": None}), True,
    note="every number is a string (rule 1), including ones no float can hold")
add(S, "booleans-and-null-in-record", sealcase(rehash_facts(edit(UNSIGNED, lambda b: b["facts"][2]["record"].update(flag=True, none=None)), key=None)), True,
    note="booleans and null are not numbers")
add(S, "control-characters-in-text", sealcase(rehash_facts(edit(UNSIGNED, lambda b: b["facts"][2]["record"].update(
    text="a\u0000b\u0007c d😀".encode("utf-16", "surrogatepass").decode("utf-16"))), key=None)), True,
    note="control and exotic characters inside a string are hashed, not mangled")
add(S, "empty-signature-object-is-unsigned", sealcase(edit(BASE, lambda b: b.update(signature={})), public_key=PUB_A), True,
    note="a falsy signature means unsigned; the -authentic set refuses it")

add(S, "tampered-fact-value", sealcase(edit(BASE, lambda b: b["facts"][0]["record"].update(value="999000000.0")), public_key=PUB_A),
    False, ["fact_hashes"], "value changed, hash not")
add(S, "tampered-fact-quote", sealcase(edit(BASE, lambda b: b["facts"][0]["record"].update(citation="$999.0 million")), public_key=PUB_A),
    False, ["fact_hashes"], "citation changed, hash not")
add(S, "tampered-entry-key", sealcase(edit(BASE, lambda b: b["facts"][0].update(key="fact/000009")), public_key=PUB_A),
    False, ["merkle_root"], "the key is committed in the leaf")
add(S, "swapped-entry-keys", sealcase(edit(BASE, lambda b: (b["facts"][0].update(key="fact/000001"), b["facts"][1].update(key="fact/000000"))), public_key=PUB_A),
    False, ["merkle_root"], "records exchange positions")
add(S, "tampered-record-and-hash", sealcase(edit(BASE, lambda b: (b["facts"][0]["record"].update(value="1.0"),
    b["facts"][0].update(hash=fact_hash(b["facts"][0]["record"])))), public_key=PUB_A),
    False, ["merkle_root"], "attacker fixes the fact hash but cannot change the root")
add(S, "tampered-root", sealcase(edit(BASE, lambda b: b["payload"].update(root="0" * 64)), public_key=PUB_A), False, ["merkle_root"])
add(S, "tampered-entries-count", sealcase(edit(BASE, lambda b: b["payload"].update(entries=4)), public_key=PUB_A), False, ["merkle_root"])
add(S, "entries-count-as-string", sealcase(edit(BASE, lambda b: b["payload"].update(entries="3")), public_key=PUB_A), False, ["structure"])
add(S, "truncated-facts", sealcase(edit(BASE, lambda b: b["facts"].pop()), public_key=PUB_A), False, ["merkle_root"],
    "a fact removed from the end")
add(S, "extra-fact-appended", sealcase(edit(BASE, lambda b: b["facts"].append(
    {"key": "fact/000003", "record": {"type": "prose", "text": "x"}, "hash": fact_hash({"type": "prose", "text": "x"})})), public_key=PUB_A),
    False, ["merkle_root"])
add(S, "no-facts-vacuous", sealcase(edit(UNSIGNED, lambda b: (b.update(facts=[], report=None),
    b["payload"].update(entries=0, root=None, report_sha256=None, tier="plain")))), False, ["structure"],
    "a bundle that seals nothing must not pass vacuously (build_bundle refuses to make one)")
add(S, "duplicate-entry-keys", sealcase(edit(BASE, lambda b: b["facts"].append(copy.deepcopy(b["facts"][0]))), public_key=PUB_A),
    False, ["fact_hashes"])
add(S, "fact-hash-uppercase", sealcase(edit(BASE, lambda b: b["facts"][0].update(hash=b["facts"][0]["hash"].upper())), public_key=PUB_A),
    False, ["fact_hashes"])
add(S, "fact-hash-with-nul", sealcase(edit(BASE, lambda b: b["facts"][0].update(hash=b["facts"][0]["hash"][:-1] + "\u0000")), public_key=PUB_A),
    False, ["fact_hashes"])
add(S, "fact-missing-hash", sealcase(edit(BASE, lambda b: b["facts"][0].pop("hash")), public_key=PUB_A), False, ["fact_hashes"])
add(S, "fact-is-null", sealcase(edit(BASE, lambda b: b["facts"].__setitem__(1, None)), public_key=PUB_A), False, ["fact_hashes"])
add(S, "entry-key-is-a-number", sealcase(edit(BASE, lambda b: b["facts"][0].update(key=5)), public_key=PUB_A), False,
    note="non-string key: must be refused, not crash")
add(S, "entry-key-is-a-list", sealcase(edit(BASE, lambda b: b["facts"][0].update(key=["fact/000000"])), public_key=PUB_A), False,
    note="unhashable key: must be refused, not crash")
add(S, "facts-is-an-object", sealcase(edit(BASE, lambda b: b.update(facts={"0": b["facts"][0]}))), False, ["structure"])
add(S, "payload-is-a-list", sealcase(edit(BASE, lambda b: b.update(payload=[]))), False, ["structure"])
add(S, "wrong-format-tag", sealcase(edit(BASE, lambda b: b.update(format="analystos-seal/2")), public_key=PUB_A), False, ["structure"])
add(S, "bundle-is-null", sealcase(None), False, ["structure"])
add(S, "bundle-is-a-list", sealcase([BASE]), False, ["structure"])
add(S, "bundle-is-a-string", sealcase("analystos-seal/1"), False, ["structure"])
for key in ("nonce", "root", "report_sha256", "tier"):
    add(S, f"missing-payload-{key}", sealcase(edit(BASE, lambda b, k=key: b["payload"].pop(k)), public_key=PUB_A), False, ["structure"])
add(S, "version-2", sealcase(edit(BASE, lambda b: b["payload"].update(version=2)), public_key=PUB_A), False, ["structure"])
add(S, "version-as-string", sealcase(edit(BASE, lambda b: b["payload"].update(version="1")), public_key=PUB_A), False, ["structure"])
add(S, "version-as-true", sealcase(edit(BASE, lambda b: b["payload"].update(version=True)), public_key=PUB_A), False, ["structure"],
    "True == 1 in Python; a boolean is not the integer 1")
add(S, "accountability-field-129-chars", sealcase(edit(BASE, lambda b: b["payload"].update(caller_id="c" * 129)), public_key=PUB_A), False, ["structure"])
add(S, "accountability-field-empty", sealcase(edit(BASE, lambda b: b["payload"].update(model_id="")), public_key=PUB_A), False, ["structure"])
add(S, "accountability-field-a-list", sealcase(edit(BASE, lambda b: b["payload"].update(code_version=["x"])), public_key=PUB_A), False, ["structure"])
add(S, "raw-float-in-fact", sealcase(edit(BASE, lambda b: b["facts"][0]["record"].update(value=498000000.5)), public_key=PUB_A), False, ["structure"],
    "rule 1: no raw JSON numbers in a sealed record")
add(S, "raw-integer-in-fact", sealcase(edit(BASE, lambda b: b["facts"][0]["record"].update(value=5)), public_key=PUB_A), False, ["structure"])
add(S, "raw-huge-integer-in-fact", sealcase(edit(BASE, lambda b: b["facts"][0]["record"].update(value=10 ** 30)), public_key=PUB_A), False, ["structure"])
add(S, "raw-number-in-payload", sealcase(edit(BASE, lambda b: b["payload"].update(created=20261001)), public_key=PUB_A), False, ["structure"])
add(S, "raw-number-in-report", sealcase(edit(BASE, lambda b: b["report"]["kpis"][0].update(label=7)), public_key=PUB_A), False, ["structure"])
add(S, "report-tampered", sealcase(edit(BASE, lambda b: b["report"].update(title="Other")), public_key=PUB_A), False, ["report_hash"])
add(S, "report-missing-but-sealed", sealcase(edit(BASE, lambda b: b.update(report=None)), public_key=PUB_A), False, ["report_hash"])
add(S, "report-present-but-none-sealed", sealcase(edit(UNSIGNED, lambda b: b["payload"].update(report_sha256=None))), False, ["report_hash"])
add(S, "report-cites-an-unsealed-fact", sealcase(rehash_facts(edit(BASE, lambda b: (b["report"]["executive_summary"].append({"text": "see {{9}}"}),
    b["payload"].update(report_sha256=sha256_hex(canonical_bytes(b["report"]))))), key=SEED_A), public_key=PUB_A),
    False, ["report_refs"], "a dangling citation of a fact that was never sealed")
add(S, "swapped-signature", sealcase(edit(BASE, lambda b: b.update(signature=OTHER["signature"])), public_key=PUB_A), False, ["signature"],
    "a genuine signature, but over a different payload")
add(S, "signature-by-another-key", sealcase(resign(edit(BASE, lambda b: None), SEED_B), public_key=PUB_A), False, ["signature"],
    "valid under the key it carries, which is not the pinned one")
add(S, "wrong-pinned-key", sealcase(BASE, public_key=PUB_B), False, ["signature"])
add(S, "pinned-key-not-base64", sealcase(BASE, public_key="not*base64!!"), False, ["signature"])
add(S, "pinned-key-too-short", sealcase(BASE, public_key=PUB_A[:20]), False, ["signature"])
add(S, "pinned-key-empty-string", sealcase(BASE, public_key=""), False, ["signature"], "an empty pin is not 'no pin'")
add(S, "signature-bit-flipped", sealcase(edit(BASE, lambda b: b["signature"].update(sig=("A" if b["signature"]["sig"][0] != "A" else "B") + b["signature"]["sig"][1:])), public_key=PUB_A),
    False, ["signature"])
add(S, "signature-without-sig", sealcase(edit(BASE, lambda b: b["signature"].pop("sig")), public_key=PUB_A), False, ["signature"])
add(S, "signature-is-a-string", sealcase(edit(BASE, lambda b: b.update(signature="deadbeef")), public_key=PUB_A), False, note="must be refused, not crash")
add(S, "signature-is-a-list", sealcase(edit(BASE, lambda b: b.update(signature=["x"])), public_key=PUB_A), False, note="must be refused, not crash")
add(S, "payload-edited-after-signing", sealcase(edit(BASE, lambda b: b["payload"].update(caller_id="someone-else")), public_key=PUB_A), False, ["signature"],
    "accountability fields are inside the signed bytes")

# --- seal-authentic: valid = authentic ---------------------------------------------------------------
A = "seal-authentic"
add(A, "signed-pinned", sealcase(BASE, public_key=PUB_A), True)
add(A, "legacy-signed-pinned", sealcase(rehash_facts(edit(BASE, lambda b: [b["payload"].pop(k) for k in ("model_id", "caller_id", "code_version")])), public_key=PUB_A), True)
add(A, "key-file-lists-the-key", sealcase(BASE, key_file=KEY_FILE), True)
add(A, "unsigned-is-never-authentic", sealcase(UNSIGNED, public_key=PUB_A), False, ["signature"])
add(A, "empty-signature-object-is-never-authentic", sealcase(edit(BASE, lambda b: b.update(signature={})), public_key=PUB_A), False, ["signature"])
add(A, "signed-but-no-pin", sealcase(BASE), False, ["signature"], "a key inside the bundle proves nothing")
add(A, "attacker-resigned-with-own-key-no-pin", sealcase(resign(edit(BASE, lambda b: b["payload"].update(caller_id="mallory")), SEED_B)), False, ["signature"],
    "valid under its own embedded key, so ok; never authentic without a pin")
add(A, "attacker-resigned-with-own-key-pinned", sealcase(resign(edit(BASE, lambda b: b["payload"].update(caller_id="mallory")), SEED_B), public_key=PUB_A), False, ["signature"])
add(A, "wrong-pin", sealcase(BASE, public_key=PUB_B), False, ["signature"])
add(A, "tampered-fact", sealcase(edit(BASE, lambda b: b["facts"][0]["record"].update(value="9")), public_key=PUB_A), False, ["fact_hashes"])
add(A, "key-file-without-the-key", sealcase(BASE, key_file=edit(KEY_FILE, lambda f: f["keys"][0].update(
    key_id=KEY_ID_B, public_key=PUB_B))), False, ["key_file"], "a key absent from the published file is not trusted (revocation by removal)")
add(A, "key-file-other-org", sealcase(BASE, key_file=edit(KEY_FILE, lambda f: f.update(org="someone-else"))), False, ["key_file"])
add(A, "key-file-invalid", sealcase(BASE, key_file=edit(KEY_FILE, lambda f: f.update(format="nope/1"))), False, ["key_file"])
add(A, "key-file-with-private-field", sealcase(BASE, key_file=edit(KEY_FILE, lambda f: f["keys"][0].update(private_key="x"))), False, ["key_file"],
    "a key file must never carry a private key")
add(A, "key-file-unsigned-bundle", sealcase(UNSIGNED, key_file=KEY_FILE), False, ["key_file"])

# --- seal-content: valid = content_checked -------------------------------------------------------------
C = "seal-content"
SCALE_TEXT = "Revenue 498.0 (in millions)."
add(C, "text-matches", sealcase(UNSIGNED, source_text=TEXT), True)
add(C, "declared-scale-supports-the-value",
    sealcase(make(segments=[dict(SEGMENTS[0], citation="498.0")], report=None, text=SCALE_TEXT, tier="plain", key=None), source_text=SCALE_TEXT), True,
    note="498.0 in a document that declares millions supports 498,000,000")
add(C, "no-text-supplied", sealcase(UNSIGNED), False, ["source_text_hash"], "content was not checked, so it must not be reported as checked")
add(C, "wrong-text", sealcase(UNSIGNED, source_text=TEXT + " "), False, ["source_text_hash"])
add(C, "citation-not-in-text", sealcase(make(text="Revenue was $498.0 million.", key=None), source_text="Revenue was $498.0 million."), False, ["citations_in_text"])
add(C, "citation-only-as-part-of-a-longer-number",
    sealcase(make(segments=[dict(SEGMENTS[0], value=22400000.0, citation="$22.4 million")], report=None, tier="plain", text="Net income was $122.45 million.", key=None),
             source_text="Net income was $122.45 million."), False, ["citations_in_text"], "22.4 is inside 122.45")
add(C, "value-not-supported-by-its-citation",
    sealcase(make(segments=[dict(SEGMENTS[0], value=499000000.0)], report=None, tier="plain", key=None), source_text=TEXT), False, ["values_match_citations"])
add(C, "sign-flipped-value",
    sealcase(make(segments=[dict(SEGMENTS[0], value=-498000000.0)], report=None, tier="plain", key=None), source_text=TEXT), False, ["values_match_citations"])
add(C, "calculation-does-not-recompute",
    sealcase(make(segments=[SEGMENTS[0], dict(SEGMENTS[1], value=-50.0)], report=None, tier="plain", key=None), source_text=TEXT), False, ["calculations"])
add(C, "calculation-with-no-operands",
    sealcase(make(segments=[SEGMENTS[0], dict(SEGMENTS[1], operands=[], citation=[])], report=None, tier="plain", key=None), source_text=TEXT), False, ["calculations"])
add(C, "fact-record-is-not-an-object", sealcase(rehash_facts(edit(UNSIGNED, lambda b: b["facts"][2].update(record="just a string")), key=None) | {"signature": None},
    source_text=TEXT), False, note="must be refused, not crash")


# --- audit chain ------------------------------------------------------------------------------------
def ev(i, **over):
    return {"ts": f"2026-10-02T00:00:{i:02d}Z", "type": "analysis", "caller": "agent-a", "id": f"{i:064x}",
            "tier": "written", "proposed": 5, "verified": 4, "dropped": 1, "seal_ok": True, **over}


def chain(n=4, key=SEED_A, start=0, prev=audit_chain.GENESIS, events=None):
    entries = []
    for i in range(n):
        entry = audit_chain.seal_entry((events or {}).get(i) or ev(start + i), start + i, prev, key)
        entries.append(entry)
        prev = entry["entry_hash"]
    return entries


def dump(entries):
    return [json.dumps(e, sort_keys=True) for e in entries]


def rehash(entry):
    entry = dict(entry)
    entry["entry_hash"] = audit_chain.entry_hash(entry)
    return entry


def lines_edit(lines, i, **changes):
    entry = json.loads(lines[i])
    entry.update(changes)
    return lines[:i] + [json.dumps(entry, sort_keys=True)] + lines[i + 1:]


def acase(lines, **extra):
    return {"lines": lines, **extra}


SIGNED = dump(chain())
UNSIG = dump(chain(key=None))
HEAD = json.loads(SIGNED[-1])["entry_hash"]
LEGACY = [json.dumps({"ts": "2026-09-01T00:00:00Z", "type": "analysis", "caller": "old"}), json.dumps({"ts": "2026-09-02T00:00:00Z", "type": "analysis", "caller": "old"})]

L = "audit"
add(L, "signed-chain-valid", acase(SIGNED, public_key=PUB_A), True)
add(L, "unsigned-chain-valid", acase(UNSIG), True, note="integrity only; the -authentic set refuses it")
add(L, "head-matches", acase(SIGNED, public_key=PUB_A, expected_head=HEAD), True)
add(L, "legacy-prefix-then-chain", acase(LEGACY + dump(chain(n=3, key=None))), True, note="lines written before Slice 84 are a tolerated prefix")
add(L, "blank-lines-tolerated", acase([""] + SIGNED[:2] + ["   "] + SIGNED[2:], public_key=PUB_A), True)
add(L, "control-characters-in-an-event", acase(dump(chain(n=2, key=None, events={0: ev(0, caller="a\u0000b\u0007c ")}))), True,
    note="escaped inside the JSON line and covered by the hash")
add(L, "unicode-event", acase(dump(chain(n=2, key=None, events={0: ev(0, caller="Zoë \U0001f600")}))), True)
add(L, "tail-dropped-without-a-pinned-head", acase(SIGNED[:2], public_key=PUB_A), True,
    note="DOCUMENTED LIMITATION (audit_chain docstring): a log that ends early looks like a shorter honest log; pin expected_head. Recorded so the limit is explicit.")

add(L, "edited-entry", acase(lines_edit(SIGNED, 1, tier="plain"), public_key=PUB_A), False, ["chain"])
add(L, "edited-and-rehashed-entry-in-the-middle",
    acase(dump([json.loads(SIGNED[0]), rehash({**json.loads(SIGNED[1]), "tier": "plain"}), json.loads(SIGNED[2]), json.loads(SIGNED[3])])), False, ["chain"],
    "the next line's prev_hash no longer matches")
add(L, "deleted-middle-entry", acase(SIGNED[:1] + SIGNED[2:], public_key=PUB_A), False, ["chain"])
add(L, "deleted-first-entry", acase(SIGNED[1:], public_key=PUB_A), False, ["chain"])
add(L, "reordered-entries", acase([SIGNED[0], SIGNED[2], SIGNED[1], SIGNED[3]], public_key=PUB_A), False, ["chain"])
add(L, "inserted-forged-entry",
    acase(SIGNED[:2] + [json.dumps(audit_chain.seal_entry(ev(9, caller="mallory"), 2, json.loads(SIGNED[1])["entry_hash"], SEED_B), sort_keys=True)] + SIGNED[2:], public_key=PUB_A),
    False, ["chain"])
add(L, "tail-dropped-with-a-pinned-head", acase(SIGNED[:2], public_key=PUB_A, expected_head=HEAD), False, ["chain"])
add(L, "expected-head-on-an-empty-log", acase([], expected_head=HEAD), False, ["chain"])
add(L, "tail-replaced-with-pinned-head", acase(SIGNED[:3] + dump(chain(n=1, start=3, prev=json.loads(SIGNED[2])["entry_hash"], key=None, events={0: ev(3, caller="mallory")})), expected_head=HEAD), False, ["chain"])
add(L, "signature-stripped", acase(dump([{k: v for k, v in json.loads(SIGNED[0]).items() if k != "signature"}] + [json.loads(x) for x in SIGNED[1:]]), public_key=PUB_A), False, ["chain"],
    "still labelled ed25519, so it claims a signature it does not have")
add(L, "signature-stripped-and-relabelled-none",
    acase(dump([{k: v for k, v in {**json.loads(SIGNED[0]), "log_signing": "none"}.items() if k not in ("signature",)}] + [json.loads(x) for x in SIGNED[1:]])), False, ["chain"],
    "log_signing is inside the hash, so relabelling breaks it")
add(L, "unsigned-line-carrying-a-signature", acase(lines_edit(UNSIG, 1, signature="AAAA")), False, ["chain"])
add(L, "key-id-altered", acase(lines_edit(SIGNED, 1, key_id="0" * 16), public_key=PUB_A), False, ["chain"], "key_id is inside the hash")
add(L, "unknown-log-signing-value", acase(lines_edit(UNSIG, 1, log_signing="rsa")), False, ["chain"])
add(L, "log-signing-missing", acase(dump([json.loads(UNSIG[0]), {k: v for k, v in json.loads(UNSIG[1]).items() if k != "log_signing"}, json.loads(UNSIG[2])])), False, ["chain"])
add(L, "signature-is-a-number", acase(lines_edit(SIGNED, 1, signature=7), public_key=PUB_A), False, ["chain"])
add(L, "legacy-only-log", acase(LEGACY), False, ["chain"], "no chained line: must fail, not pass vacuously")
add(L, "empty-log", acase([]), False, ["chain"])
add(L, "blank-lines-only", acase(["", "  ", ""]), False, ["chain"])
add(L, "legacy-line-after-the-chain-began", acase(SIGNED[:2] + LEGACY[:1] + SIGNED[2:], public_key=PUB_A), False, ["chain"])
add(L, "line-is-not-json", acase(SIGNED[:2] + ["{not json"], public_key=PUB_A), False, ["chain"])
add(L, "line-is-an-array", acase(SIGNED[:2] + ["[1,2,3]"], public_key=PUB_A), False, ["chain"])
add(L, "truncated-last-line", acase(SIGNED[:3] + [SIGNED[3][:-20]], public_key=PUB_A), False, ["chain"])
add(L, "seq-starts-at-one", acase(dump(chain(n=3, start=1, key=None))), False, ["chain"])
add(L, "seq-repeated", acase(dump(chain(n=2, key=None)[:1] + chain(n=2, key=None)[:1])), False, ["chain"])
add(L, "seq-is-a-string", acase(dump([rehash({**json.loads(UNSIG[0]), "seq": "0"})] + [json.loads(x) for x in UNSIG[1:]])), False, ["chain"])
add(L, "seq-is-a-float", acase(dump([rehash({**json.loads(UNSIG[0]), "seq": 0.0})] + [json.loads(x) for x in UNSIG[1:]])), False, ["chain"], "0.0 == 0 in Python; a float is not the integer 0")
add(L, "genesis-prev-hash-wrong", acase(dump([rehash({**json.loads(UNSIG[0]), "prev_hash": "sha256:" + "1" * 64})] + [json.loads(x) for x in UNSIG[1:]])), False, ["chain"])
add(L, "entry-hash-without-prefix", acase(lines_edit(UNSIG, 1, entry_hash=json.loads(UNSIG[1])["entry_hash"][7:])), False, ["chain"])
add(L, "entry-hash-is-a-number", acase(lines_edit(UNSIG, 1, entry_hash=5)), False, ["chain"])
add(L, "duplicate-key-in-a-line",
    acase([UNSIG[0].replace('"seq": 0', '"seq": 7, "seq": 0', 1)] + UNSIG[1:]), False, note="a line whose meaning depends on which duplicate a parser keeps is ambiguous across implementations; refuse")
add(L, "non-finite-number-literal",
    acase([json.dumps(audit_chain.seal_entry(ev(0, proposed=float("nan")), 0, audit_chain.GENESIS, None), sort_keys=True)]), False,
    note="NaN is not valid JSON; a strict parser in another language cannot read the line, so the chain is not portable")

# --- audit-authentic: valid = authentic ------------------------------------------------------------------
LA = "audit-authentic"
add(LA, "all-signed-pinned", acase(SIGNED, public_key=PUB_A), True)
add(LA, "all-signed-pinned-and-head", acase(SIGNED, public_key=PUB_A, expected_head=HEAD), True)
add(LA, "unsigned-chain", acase(UNSIG, public_key=PUB_A), False, ["signatures"])
add(LA, "mixed-signed-and-unsigned", acase(SIGNED[:2] + dump(chain(n=2, start=2, prev=json.loads(SIGNED[1])["entry_hash"], key=None)), public_key=PUB_A), False,
    note="one unsigned line leaves a hole an attacker can rewrite")
add(LA, "signed-but-no-pin", acase(SIGNED), False, ["signatures"])
add(LA, "wrong-pin", acase(SIGNED, public_key=PUB_B), False, ["signatures"])
add(LA, "signed-by-another-key", acase(dump(chain(key=SEED_B)), public_key=PUB_A), False, ["signatures"])
add(LA, "signature-swapped-between-lines", acase(lines_edit(lines_edit(SIGNED, 1, signature=json.loads(SIGNED[2])["signature"]), 2, signature=json.loads(SIGNED[1])["signature"]), public_key=PUB_A), False, ["signatures"])
add(LA, "edited-entry", acase(lines_edit(SIGNED, 2, tier="plain"), public_key=PUB_A), False, ["chain"])
add(LA, "empty-log", acase([], public_key=PUB_A), False, ["chain"])


def build():
    for case in CASES:
        if case["id"] in KNOWN_GAPS:
            case["known_gap"] = KNOWN_GAPS[case["id"]]
    assert set(KNOWN_GAPS) <= {c["id"] for c in CASES}, "a known gap names a case that does not exist"
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    sets = []
    for name in dict.fromkeys(c["set"] for c in CASES):
        members = [c for c in CASES if c["set"] == name]
        sets.append({"name": name, "kind": "validate", "accept": sum(c["expect"]["valid"] for c in members),
                     "refuse": sum(not c["expect"]["valid"] for c in members), "cases": members})
    return {
        "contract": "analystos-conformance/1",
        "profile": "analystos-seal/1 + analystos-audit-chain/1",
        "version": "1.0.0",
        "about": ("Refusal-first corpus for the seal verifier and the audit-log verifier. `valid` means: for set `seal` the bundle is "
                  "internally consistent (ok); `seal-authentic` it is authentic under the pinned key or key file (authentic); `seal-content` "
                  "its content was checked against the supplied text (content_checked); `audit` the log verifies (ok); `audit-authentic` "
                  "every line is signed and verifies under the pinned key (authentic). `codes`, where present, are the names of failed checks "
                  "and are compared as a subset. Generated by tools/build_conformance_corpus.py: regenerated, never hand-edited."),
        "protocol": {"stdin": {"id": "string", "set": "string", "input": "see each set"},
                     "stdout": {"id": "string", "valid": "boolean", "codes": "string[]  (optional)"}},
        "inputs": {
            "seal*": "{bundle, public_key?, key_file?, source_text?}",
            "audit*": "{lines: [string], public_key?, expected_head?}",
        },
        "test_keys": {"note": "published test vectors, not secrets: seeds are bytes(range(32)) and bytes(range(32,64))", "public_key_a": PUB_A, "public_key_b": PUB_B},
        "sets": sets,
    }


def render():
    corpus = build()
    head = {k: v for k, v in corpus.items() if k != "sets"}
    text = json.dumps(head, indent=1, ensure_ascii=True)[:-2] + ',\n "sets": [\n'
    chunks = []
    for s in corpus["sets"]:
        meta = {k: v for k, v in s.items() if k != "cases"}
        body = ",\n".join("   " + json.dumps(c, ensure_ascii=True, separators=(",", ":"), sort_keys=True) for c in s["cases"])
        chunks.append("  " + json.dumps(meta, ensure_ascii=True)[:-1] + ',"cases":[\n' + body + "\n  ]}")
    return text + ",\n".join(chunks) + "\n ]\n}\n"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    text = render()
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
        print("up to date" if current == text else "STALE: run python3 tools/build_conformance_corpus.py")
        return 0 if current == text else 1
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
