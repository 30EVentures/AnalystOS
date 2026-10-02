"""Slice 86 - the public seal-verification key file, its validator, the key-file verifier
path, the tool that writes it, and the smoke checks. See specs/slice-86/spec.md.

Every keypair here is a throwaway generated in-process; no real key exists or is used, and
nothing is written under site/ (copies live in temp directories)."""

import base64
import contextlib
import copy
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analystos.l4 import seal_verify
from analystos.l4.seal import SEAL_KEY_ENV, build_bundle, generate_key
from analystos.l4.seal_verify import (
    KEY_FILE_FORMAT, KEY_FILE_MAX_BYTES, pinned_public_key, validate_key_file, verify_bundle,
    verify_bundle_with_key_file,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_site_machine  # noqa: E402
import seal_key_file as tool  # noqa: E402
import smoke  # noqa: E402

from api import analyze as api_analyze  # noqa: E402
from tests.test_smoke import Deployment, failing  # noqa: E402

TEXT = "Revenue was $498.0 million. Net income fell from $22.4 million to $19.6 million."
SEGMENTS = [
    {"type": "quote", "label": "Revenue", "value": 498000000.0, "format": "usd", "citation": "$498.0 million",
     "horizon": "reported", "gaap_status": "n/a"},
    {"type": "computed", "label": "NI change", "operation": "growth_percent", "value": -12.5, "format": "percent",
     "operands": [22400000.0, 19600000.0], "total": None, "citation": ["$22.4 million", "$19.6 million"],
     "horizon": "reported"},
]
REPORT = {"title": "T", "executive_summary": [{"text": "Revenue was {{0}}, income moved {{1}}."}]}
DATE = "2026-10-02"


def trace():
    return {"tier": "written", "segments": copy.deepcopy(SEGMENTS), "report": copy.deepcopy(REPORT),
            "document_text": TEXT, "source_hash": "a" * 64, "model": "claude-sonnet-5"}


def new_pair():
    priv, pub = generate_key()
    return priv, pub


def key_file(*pubs, active_last=True):
    entries = [tool.key_entry(p, DATE, "retired" if (active_last and i < len(pubs) - 1) else "active")
               for i, p in enumerate(pubs)]
    return tool.build_key_file(entries)


def signed(priv):
    return build_bundle(trace(), signing_key=priv)


def status(outcome, name):
    return {c["name"]: c["status"] for c in outcome["checks"]}[name]


class PublishedKeyRoundTripTest(unittest.TestCase):
    """Done when #1-#3."""

    def setUp(self):
        self.priv, self.pub = new_pair()
        self.kf = key_file(self.pub)

    def test_a_seal_signed_by_a_test_keypair_is_authentic_against_a_key_file_in_the_published_format(self):
        out = verify_bundle_with_key_file(signed(self.priv), self.kf, source_text=TEXT)
        self.assertEqual((out["ok"], out["authentic"], out["content_checked"]), (True, True, True))
        self.assertEqual(out["checks"][0]["name"], "key_file")
        self.assertEqual(out["checks"][0]["status"], "pass")
        self.assertEqual(status(out, "signature"), "pass")

    def test_the_tool_and_the_signer_agree_on_the_key_id(self):
        bundle = signed(self.priv)
        self.assertEqual(bundle["signature"]["key_id"], self.kf["keys"][0]["key_id"])
        self.assertEqual(self.kf["keys"][0]["key_id"], hashlib.sha256(base64.urlsafe_b64decode(self.pub + "=")).hexdigest()[:16])

    def test_the_embedded_key_is_not_what_is_trusted(self):
        # An attacker signs with their own key and names a listed key_id: the listed key must reject it.
        evil_priv, _ = new_pair()
        forged = signed(evil_priv)
        forged["signature"]["key_id"] = self.kf["keys"][0]["key_id"]
        out = verify_bundle_with_key_file(forged, self.kf)
        self.assertFalse(out["authentic"])
        self.assertEqual(status(out, "signature"), "fail")

    def test_a_key_the_file_does_not_list_is_a_failure_not_a_silent_unpinned_check(self):
        other_priv, _ = new_pair()
        out = verify_bundle_with_key_file(signed(other_priv), self.kf)
        self.assertEqual((out["ok"], out["authentic"], out["content_checked"]), (False, False, False))
        self.assertEqual(status(out, "key_file"), "fail")
        self.assertIn("not in the published key file", out["checks"][0]["detail"])

    def test_a_removed_key_stops_being_trusted(self):  # revocation by removal
        _, other_pub = new_pair()
        bundle = signed(self.priv)
        self.assertTrue(verify_bundle_with_key_file(bundle, self.kf)["authentic"])
        self.assertFalse(verify_bundle_with_key_file(bundle, key_file(other_pub))["authentic"])

    def test_a_seal_from_another_org_is_refused(self):
        bundle = build_bundle(trace(), org="someone-else", signing_key=self.priv)
        out = verify_bundle_with_key_file(bundle, self.kf)
        self.assertFalse(out["authentic"])
        self.assertIn("org", out["checks"][0]["detail"])

    def test_a_tampered_seal_is_not_authentic(self):
        bundle = signed(self.priv)
        bundle["payload"]["tier"] = "plain"
        out = verify_bundle_with_key_file(bundle, self.kf)
        self.assertFalse(out["authentic"])
        self.assertFalse(out["ok"])

    def test_an_unsigned_seal_cannot_be_authentic_but_is_not_called_a_key_failure(self):
        out = verify_bundle_with_key_file(build_bundle(trace()), self.kf, source_text=TEXT)
        self.assertTrue(out["ok"])
        self.assertFalse(out["authentic"])
        self.assertEqual(status(out, "key_file"), "skipped")
        self.assertEqual(status(out, "signature"), "skipped")

    def test_an_invalid_key_file_fails_closed(self):
        bad = copy.deepcopy(self.kf)
        bad["keys"][0]["key_id"] = "0" * 16
        out = verify_bundle_with_key_file(signed(self.priv), bad)
        self.assertEqual((out["ok"], out["authentic"]), (False, False))
        self.assertIn("key file is not valid", out["checks"][0]["detail"])

    def test_garbage_in_place_of_a_bundle_is_a_failure_not_a_crash(self):
        for junk in (None, [], {}, {"format": "x"}):
            with self.subTest(junk=junk):
                self.assertFalse(verify_bundle_with_key_file(junk, self.kf)["authentic"])

    def test_a_rotated_file_authenticates_seals_from_both_keys_and_swapped_ids_fail(self):
        priv_old, pub_old = self.priv, self.pub
        priv_new, pub_new = new_pair()
        both = key_file(pub_old, pub_new)
        self.assertEqual([k["status"] for k in both["keys"]], ["retired", "active"])
        old_seal, new_seal = signed(priv_old), signed(priv_new)
        self.assertTrue(verify_bundle_with_key_file(old_seal, both)["authentic"])
        self.assertTrue(verify_bundle_with_key_file(new_seal, both)["authentic"])
        swapped = copy.deepcopy(old_seal)
        swapped["signature"]["key_id"] = both["keys"][1]["key_id"]
        self.assertFalse(verify_bundle_with_key_file(swapped, both)["authentic"])

    def test_pinned_public_key_reasons(self):
        self.assertEqual(pinned_public_key(signed(self.priv), self.kf), (self.pub, None))
        self.assertIn("unsigned", pinned_public_key(build_bundle(trace()), self.kf)[1])
        no_id = signed(self.priv)
        del no_id["signature"]["key_id"]
        self.assertIn("no key_id", pinned_public_key(no_id, self.kf)[1])


class KeyFileValidatorTest(unittest.TestCase):
    """Done when #4."""

    def setUp(self):
        _, self.pub = new_pair()
        self.good = key_file(self.pub)

    def mutated(self, fn):
        doc = copy.deepcopy(self.good)
        fn(doc)
        return doc

    def test_a_good_file_has_no_problems_and_unknown_fields_are_tolerated(self):
        self.assertEqual(validate_key_file(self.good), [])
        extra = self.mutated(lambda d: (d.update({"future": 1}), d["keys"][0].update({"note": "x"})))
        self.assertEqual(validate_key_file(extra), [])

    def test_each_malformed_case_is_rejected(self):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        last = self.pub[-1]
        flipped = alphabet[(alphabet.index(last) & ~3) | (((alphabet.index(last) & 3) + 1) & 3)]
        self.assertEqual(base64.urlsafe_b64decode(self.pub[:-1] + flipped + "="), base64.urlsafe_b64decode(self.pub + "="))
        cases = {
            "not an object": lambda d: None,
            "wrong format": lambda d: d.update(format="analystos-seal-key/2"),
            "no org": lambda d: d.pop("org"),
            "empty org": lambda d: d.update(org=""),
            "keys missing": lambda d: d.pop("keys"),
            "keys empty": lambda d: d.update(keys=[]),
            "keys not a list": lambda d: d.update(keys={}),
            "too many keys": lambda d: d.update(keys=[d["keys"][0]] * 17),
            "key not an object": lambda d: d.update(keys=["x"]),
            "wrong algorithm": lambda d: d["keys"][0].update(algorithm="rsa"),
            "upper-case key id": lambda d: d["keys"][0].update(key_id=d["keys"][0]["key_id"].upper()),
            "short key id": lambda d: d["keys"][0].update(key_id="abcd"),
            "key id not hex": lambda d: d["keys"][0].update(key_id="z" * 16),
            "key id mismatch": lambda d: d["keys"][0].update(key_id="0" * 16),
            "padded public key": lambda d: d["keys"][0].update(public_key=self.pub + "="),
            "short public key": lambda d: d["keys"][0].update(public_key=self.pub[:-4]),
            "long public key": lambda d: d["keys"][0].update(public_key=self.pub + "AAAA"),
            "not base64url": lambda d: d["keys"][0].update(public_key="!" * 43),
            "non-canonical encoding": lambda d: d["keys"][0].update(public_key=self.pub[:-1] + flipped),
            "public key not a string": lambda d: d["keys"][0].update(public_key=123),
            "bad status": lambda d: d["keys"][0].update(status="revoked"),
            "no active key": lambda d: d["keys"][0].update(status="retired"),
            "bad added format": lambda d: d["keys"][0].update(added="02/10/2026"),
            "added not a real date": lambda d: d["keys"][0].update(added="2026-02-30"),
            "added missing": lambda d: d["keys"][0].pop("added"),
            "duplicate key ids": lambda d: d.update(keys=[d["keys"][0], dict(d["keys"][0], status="retired")]),
            "private key at top level": lambda d: d.update(private_key="x"),
            "seed inside a key": lambda d: d["keys"][0].update(seed="x"),
            "secret nested deeper": lambda d: d.update(meta={"Secret": "x"}),
        }
        for label, fn in cases.items():
            with self.subTest(case=label):
                doc = copy.deepcopy(self.good)
                if label == "not an object":
                    doc = ["not", "an", "object"]
                else:
                    fn(doc)
                self.assertTrue(validate_key_file(doc), f"{label} was accepted")

    def test_non_objects_are_rejected(self):
        for junk in (None, [], "x", 3):
            self.assertEqual(len(validate_key_file(junk)), 1)


class VerifierCliKeyFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.priv, self.pub = new_pair()

    def write(self, name, doc):
        path = self.tmp / name
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc))
        return str(path)

    def run_cli(self, *args):
        out = io.StringIO()
        return seal_verify.main(list(args), stdout=out), json.loads(out.getvalue())

    def test_exit_codes_and_results(self):
        bundle, kf = self.write("b.json", signed(self.priv)), self.write("k.json", key_file(self.pub))
        text = self.write("t.txt", TEXT)
        code, result = self.run_cli(bundle, "--key-file", kf, "--text", text)
        self.assertEqual(code, 0)
        self.assertTrue(result["authentic"] and result["content_checked"])
        other_priv, _ = new_pair()
        code, result = self.run_cli(self.write("o.json", signed(other_priv)), "--key-file", kf)
        self.assertEqual((code, result["authentic"]), (1, False))

    def test_a_pinned_public_key_still_works_as_before(self):
        code, result = self.run_cli(self.write("b.json", signed(self.priv)), "--public-key", self.pub)
        self.assertEqual((code, result["authentic"]), (0, True))

    def test_bad_usage_is_exit_2(self):
        bundle, kf = self.write("b.json", signed(self.priv)), self.write("k.json", key_file(self.pub))
        for args in ([bundle, "--key-file", kf, "--public-key", self.pub],
                     [bundle, "--key-file", self.write("bad.json", "{nope")],
                     [bundle, "--key-file", str(self.tmp / "missing.json")],
                     [bundle, "--key-file"],
                     ["--key-file", kf]):
            with self.subTest(args=args):
                code, result = self.run_cli(*args)
                self.assertEqual(code, 2)
                self.assertIn("error", result)

    def test_an_oversized_key_file_is_refused(self):
        big = self.write("big.json", json.dumps({"x": "a" * (KEY_FILE_MAX_BYTES + 10)}))
        code, result = self.run_cli(self.write("b.json", signed(self.priv)), "--key-file", big)
        self.assertEqual(code, 2)
        self.assertIn("larger", result["error"])

    def test_it_runs_as_its_own_command(self):
        bundle, kf = self.write("b.json", signed(self.priv)), self.write("k.json", key_file(self.pub))
        done = subprocess.run([sys.executable, "-m", "analystos.l4.seal_verify", bundle, "--key-file", kf],
                              capture_output=True, text=True, cwd=ROOT, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(json.loads(done.stdout)["authentic"])


class ToolTest(unittest.TestCase):
    """Done when #5."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name) / "site" / ".well-known" / "analystos-seal-key.json"
        self.priv, self.pub = new_pair()

    def run_tool(self, *args, env=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = tool.main(list(args), stdout=out, environ=env if env is not None else {})
        return code, out.getvalue(), err.getvalue()

    def test_from_env_writes_only_the_public_half_and_never_shows_the_seed(self):
        code, out, err = self.run_tool("--from-env", "--out", str(self.out), "--added", DATE, env={SEAL_KEY_ENV: self.priv})
        self.assertEqual(code, 0, err)
        written = self.out.read_text()
        for stream in (written, out, err):
            self.assertNotIn(self.priv, stream)
        doc = json.loads(written)
        self.assertEqual(doc["keys"][0]["public_key"], self.pub)
        self.assertEqual(doc["keys"][0]["status"], "active")
        self.assertEqual(validate_key_file(doc), [])
        self.assertEqual(json.loads(out)["key_id"], doc["keys"][0]["key_id"])
        self.assertTrue(written.endswith("\n"))
        self.assertTrue(verify_bundle_with_key_file(signed(self.priv), doc)["authentic"])

    def test_public_key_mode_writes_the_same_file(self):
        self.run_tool("--from-env", "--out", str(self.out), "--added", DATE, env={SEAL_KEY_ENV: self.priv})
        from_env = self.out.read_text()
        self.out.unlink()
        code, _, _ = self.run_tool("--public-key", self.pub, "--out", str(self.out), "--added", DATE)
        self.assertEqual(code, 0)
        self.assertEqual(self.out.read_text(), from_env)

    def test_pasting_the_private_seed_as_the_public_key_is_refused_and_writes_nothing(self):
        code, out, err = self.run_tool("--public-key", self.priv, "--out", str(self.out), env={SEAL_KEY_ENV: self.priv})
        self.assertEqual(code, 2)
        self.assertIn("PRIVATE", err)
        self.assertNotIn(self.priv, err + out)
        self.assertFalse(self.out.exists())

    def test_it_will_not_overwrite_and_rotation_retires_the_old_key(self):
        self.run_tool("--public-key", self.pub, "--out", str(self.out), "--added", DATE)
        before = self.out.read_text()
        code, _, err = self.run_tool("--public-key", new_pair()[1], "--out", str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("--add", err)
        self.assertEqual(self.out.read_text(), before)

        priv2, pub2 = new_pair()
        code, out, err = self.run_tool("--from-env", "--add", "--out", str(self.out), "--added", "2026-11-01", env={SEAL_KEY_ENV: priv2})
        self.assertEqual(code, 0, err)
        doc = json.loads(self.out.read_text())
        self.assertEqual([k["status"] for k in doc["keys"]], ["retired", "active"])
        self.assertEqual(doc["keys"][1]["public_key"], pub2)
        self.assertEqual(validate_key_file(doc), [])
        self.assertTrue(verify_bundle_with_key_file(signed(self.priv), doc)["authentic"])   # old seals still verify
        self.assertTrue(verify_bundle_with_key_file(signed(priv2), doc)["authentic"])
        self.assertEqual(json.loads(out)["active"], [doc["keys"][1]["key_id"]])

    def test_add_edge_cases_leave_the_file_alone(self):
        code, _, _ = self.run_tool("--public-key", self.pub, "--add", "--out", str(self.out))
        self.assertEqual(code, 2)  # nothing to add to
        self.assertFalse(self.out.exists())
        self.run_tool("--public-key", self.pub, "--out", str(self.out), "--added", DATE)
        before = self.out.read_text()
        code, _, err = self.run_tool("--public-key", self.pub, "--add", "--out", str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("already listed", err)
        self.out.write_text(json.dumps({"format": "nope"}))
        broken = self.out.read_text()
        code, _, err = self.run_tool("--public-key", new_pair()[1], "--add", "--out", str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("not valid", err)
        self.assertEqual(self.out.read_text(), broken)
        self.assertNotEqual(before, broken)

    def test_bad_input_is_refused_with_exit_2(self):
        cases = [
            (["--from-env", "--out", str(self.out)], {}),                                    # env var missing
            (["--from-env", "--out", str(self.out)], {SEAL_KEY_ENV: "not-a-seed"}),          # malformed seed
            (["--from-env", "--public-key", self.pub, "--out", str(self.out)], {SEAL_KEY_ENV: self.priv}),
            (["--out", str(self.out)], {}),                                                  # neither
            (["--public-key", "short", "--out", str(self.out)], {}),                         # not a public key
            (["--public-key", self.pub[:-1] + "=", "--out", str(self.out)], {}),
            (["--bogus"], {}), (["--public-key"], {}), (["--check"], {}),
        ]
        for args, env in cases:
            with self.subTest(args=args):
                code, _, _ = self.run_tool(*args, env=env)
                self.assertEqual(code, 2)
                self.assertFalse(self.out.exists())

    def test_check_mode(self):
        self.run_tool("--public-key", self.pub, "--out", str(self.out), "--added", DATE)
        code, out, _ = self.run_tool("--check", str(self.out))
        self.assertEqual((code, json.loads(out)["valid"]), (0, True))
        bad = self.out.with_name("bad.json")
        bad.write_text(json.dumps({"format": "x"}))
        code, out, _ = self.run_tool("--check", str(bad))
        self.assertEqual((code, json.loads(out)["valid"]), (1, False))
        self.assertTrue(json.loads(out)["problems"])
        self.assertEqual(self.run_tool("--check", str(self.out) + ".missing")[0], 2)
        self.assertEqual(self.run_tool("--check", str(self.out), "--add")[0], 2)

    def test_it_runs_as_a_real_command_and_the_seed_never_reaches_its_output(self):
        env = dict(os.environ, **{SEAL_KEY_ENV: self.priv})
        done = subprocess.run([sys.executable, "tools/seal_key_file.py", "--from-env", "--out", str(self.out)],
                              capture_output=True, text=True, cwd=ROOT, env=env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn(self.priv, done.stdout + done.stderr + self.out.read_text())
        self.assertEqual(json.loads(self.out.read_text())["keys"][0]["public_key"], self.pub)

    def test_the_default_output_is_the_well_known_path_and_the_tool_has_no_network_or_secret_store(self):
        self.assertEqual(tool.DEFAULT_OUT, ROOT / "site" / ".well-known" / "analystos-seal-key.json")
        source = (ROOT / "tools" / "seal_key_file.py").read_text()
        for forbidden in ("urllib", "requests", "socket", "subprocess", "print(seed", "print(env"):
            self.assertNotIn(forbidden, source)


class SmokeSealKeyTest(unittest.TestCase):
    """Done when #6, against an emulated deployment (no external network)."""

    def setUp(self):
        # The per-IP rate limiter's buckets are process-global: a test that drives the app hard from
        # 127.0.0.1 must not leave a full bucket for whichever test runs next.
        self.addCleanup(api_analyze._rate_limit_buckets.clear)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.site = self.tmp / "site"
        shutil.copytree(ROOT / "site", self.site)
        self.priv, self.pub = new_pair()
        self.key_path = self.site / ".well-known" / "analystos-seal-key.json"

    def publish(self, doc=None):
        self.key_path.write_text(json.dumps(doc if doc is not None else key_file(self.pub)))

    def seal_file(self, bundle, name="live.seal.json"):
        path = self.tmp / name
        path.write_text(json.dumps(bundle))
        return str(path)

    def test_no_key_file_is_reported_as_not_published_and_does_not_fail(self):
        with Deployment(self.site) as base:
            code, failed = failing(base)
            _, js = smoke.main, None
            out = io.StringIO()
            smoke.main([base, "--json"], stdout=out)
        self.assertEqual((code, failed), (0, []))
        names = [r["check"] for r in json.loads(out.getvalue())["results"]]
        self.assertIn("seal key file: not published yet (skipped; --expect-seal-key requires it)", names)

    def test_expecting_a_key_file_that_is_missing_fails(self):
        with Deployment(self.site) as base:
            code, failed = failing(base, "--expect-seal-key")
        self.assertEqual(code, 1)
        self.assertEqual(failed, ["GET /.well-known/analystos-seal-key.json -> published"])

    def test_a_valid_published_file_passes_and_is_checked(self):
        self.publish()
        with Deployment(self.site) as base:
            code, failed = failing(base, "--expect-seal-key")
            out = io.StringIO()
            smoke.main([base, "--json", "--expect-seal-key"], stdout=out)
        self.assertEqual((code, failed), (0, []))
        names = [r["check"] for r in json.loads(out.getvalue())["results"]]
        self.assertIn("published seal key file is valid", names)

    def test_an_invalid_published_file_fails(self):
        bad = key_file(self.pub)
        bad["keys"][0]["key_id"] = "0" * 16
        self.publish(bad)
        with Deployment(self.site) as base:
            code, failed = failing(base)
        self.assertEqual(code, 1)
        self.assertEqual(failed, ["published seal key file is valid"])

    def test_a_file_served_with_the_wrong_content_type_fails(self):
        self.publish()
        config = json.loads((ROOT / "vercel.json").read_text())
        config["headers"] = [h for h in config["headers"] if h["source"] != "/.well-known/analystos-seal-key.json"]
        with Deployment(self.site, config=config) as base:
            _, failed = failing(base)
        self.assertIn("GET /.well-known/analystos-seal-key.json -> 200 application/json", failed)

    def test_a_seal_from_the_matching_key_passes(self):
        self.publish()
        good = self.seal_file(signed(self.priv))
        wrapped = self.seal_file({"id": "x", "seal": signed(self.priv)}, "response.json")  # an /api/v1/analyses response
        with Deployment(self.site) as base:
            for path in (good, wrapped):
                with self.subTest(path=path):
                    code, failed = failing(base, "--seal", path)
                    self.assertEqual((code, failed), (0, []))

    def test_a_seal_from_a_different_key_is_the_key_mismatch_this_exists_to_catch(self):
        self.publish()
        other_priv, _ = new_pair()
        with Deployment(self.site) as base:
            code, failed = failing(base, "--seal", self.seal_file(signed(other_priv)))
            out = io.StringIO()
            smoke.main([base, "--json", "--seal", self.seal_file(signed(other_priv))], stdout=out)
        self.assertEqual((code, failed), (1, ["a seal from this deployment verifies under the published key"]))
        detail = [r["detail"] for r in json.loads(out.getvalue())["results"] if not r["ok"]][0]
        self.assertIn("does not match the published key", detail)

    def test_an_unsigned_seal_says_the_host_probably_has_no_key(self):
        self.publish()
        with Deployment(self.site) as base:
            out = io.StringIO()
            code = smoke.main([base, "--json", "--seal", self.seal_file(build_bundle(trace()))], stdout=out)
        self.assertEqual(code, 1)
        detail = [r["detail"] for r in json.loads(out.getvalue())["results"] if not r["ok"]][0]
        self.assertIn("ANALYSTOS_SEAL_KEY", detail)

    def test_a_tampered_seal_fails(self):
        self.publish()
        bundle = signed(self.priv)
        bundle["payload"]["tier"] = "plain"
        with Deployment(self.site) as base:
            code, failed = failing(base, "--seal", self.seal_file(bundle))
        self.assertEqual((code, failed), (1, ["a seal from this deployment verifies under the published key"]))

    def test_an_unreadable_seal_and_a_seal_with_no_published_key_fail(self):
        with Deployment(self.site) as base:
            code, failed = failing(base, "--seal", str(self.tmp / "missing.json"))
            self.assertEqual(code, 1)  # no key file published: --seal implies it is expected
            self.assertEqual(failed, ["GET /.well-known/analystos-seal-key.json -> published"])
        self.publish()
        with Deployment(self.site) as base:
            code, failed = failing(base, "--seal", str(self.tmp / "missing.json"))
        self.assertEqual((code, failed), (1, ["a seal from this deployment verifies under the published key"]))

    def test_usage(self):
        out = io.StringIO()
        for argv in (["--seal"], ["--seal", "--json"], ["a", "b"], ["--bogus"]):
            with self.subTest(argv=argv):
                self.assertEqual(smoke.main(argv, stdout=out), 2)
        self.assertIn("--expect-seal-key", out.getvalue())

    def test_the_smoke_check_sends_nothing_but_gets_for_the_key(self):
        self.publish()
        methods = []
        real = smoke.fetch

        def spy(base, path, method="GET", **kw):
            methods.append((method, path))
            return real(base, path, method=method, **kw)

        with Deployment(self.site) as base, patch.object(smoke, "fetch", spy):
            failing(base, "--no-post", "--seal", self.seal_file(signed(self.priv)))
        self.assertEqual({m for m, _ in methods}, {"GET"})
        self.assertIn(("GET", "/.well-known/analystos-seal-key.json"), methods)


class ProductionPathTest(unittest.TestCase):
    """The operator's two halves must match: the API signs with ANALYSTOS_SEAL_KEY, and the public
    file is derived (--from-env) from the same variable. Uses the real /api/v1/analyses route."""

    def setUp(self):
        from tests.test_api_v1 import ApiTestCase

        class Inner(ApiTestCase):
            def runTest(self):  # pragma: no cover - driven by hand below
                pass

        self.addCleanup(api_analyze._rate_limit_buckets.clear)
        self.case = Inner()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name) / "analystos-seal-key.json"

    def test_a_seal_the_api_returns_authenticates_against_the_file_derived_from_the_same_environment(self):
        seal = self.case.created()["seal"]
        self.assertIsNotNone(seal["signature"], "the harness sets ANALYSTOS_SEAL_KEY, so the API must sign")
        with contextlib.redirect_stderr(io.StringIO()):
            code = tool.main(["--from-env", "--out", str(self.out), "--added", DATE], stdout=io.StringIO(),
                             environ={SEAL_KEY_ENV: self.case.seal_priv})
        self.assertEqual(code, 0)
        out = verify_bundle_with_key_file(seal, json.loads(self.out.read_text()))
        self.assertEqual((out["ok"], out["authentic"]), (True, True))
        self.assertEqual(seal["signature"]["key_id"], json.loads(self.out.read_text())["keys"][0]["key_id"])

    def test_the_dangerous_mistake_a_published_key_that_is_not_the_signing_key_is_caught(self):
        seal = self.case.created()["seal"]
        _, someone_elses_pub = new_pair()
        tool.write_key_file(someone_elses_pub, self.out, added=DATE)
        out = verify_bundle_with_key_file(seal, json.loads(self.out.read_text()))
        self.assertEqual((out["ok"], out["authentic"]), (False, False))
        self.assertEqual(status(out, "key_file"), "fail")

    def test_with_no_signing_key_configured_the_seal_is_unsigned_and_cannot_authenticate(self):
        with patch.dict(os.environ, {SEAL_KEY_ENV: ""}):
            seal = self.case.created()["seal"]
        self.assertIsNone(seal["signature"])
        tool.write_key_file(self.case.seal_pub, self.out, added=DATE)
        out = verify_bundle_with_key_file(seal, json.loads(self.out.read_text()))
        self.assertTrue(out["ok"])
        self.assertFalse(out["authentic"])


class RepositoryInvariantsTest(unittest.TestCase):
    """Done when #7."""

    KEY_PATH = ROOT / "site" / ".well-known" / "analystos-seal-key.json"
    SEED_ASSIGNMENT = re.compile(r"ANALYSTOS_SEAL_KEY\s*=\s*[\"']?[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])")

    def test_if_the_key_file_is_ever_added_it_is_valid_and_advertised_exactly_then(self):
        text = (ROOT / "site" / "llms.txt").read_text()
        link = "/.well-known/analystos-seal-key.json"
        if self.KEY_PATH.exists():
            self.assertEqual(validate_key_file(json.loads(self.KEY_PATH.read_text())), [])
            self.assertEqual(tool.main(["--check", str(self.KEY_PATH)], stdout=io.StringIO()), 0)
            self.assertIn(link, text)
        else:
            self.assertNotIn(link, text)  # never advertise a 404

    def test_no_file_in_the_repository_contains_a_pasted_signing_seed(self):
        offenders = []
        for base in ("site", "docs", "tools", "analystos", "api", "specs", "README.md", "ROADMAP.md", "vercel.json"):
            path = ROOT / base
            files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file() and p.suffix in (".md", ".txt", ".json", ".py", ".html", ".xml")]
            for f in files:
                if "__pycache__" in f.parts:
                    continue
                if self.SEED_ASSIGNMENT.search(f.read_text(encoding="utf-8", errors="replace")):
                    offenders.append(str(f.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_the_leak_guard_would_catch_a_pasted_keygen_line(self):
        priv, _ = new_pair()
        self.assertTrue(self.SEED_ASSIGNMENT.search(f"{SEAL_KEY_ENV}={priv}"))
        self.assertFalse(self.SEED_ASSIGNMENT.search("ANALYSTOS_SEAL_KEY=<the seed>"))

    def test_vercel_serves_the_key_file_as_json_with_cors(self):
        config = json.loads((ROOT / "vercel.json").read_text())
        rules = {h["source"]: {x["key"]: x["value"] for x in h["headers"]} for h in config["headers"]}
        headers = rules["/.well-known/analystos-seal-key.json"]
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("max-age", headers["Cache-Control"])

    def test_the_llms_txt_generator_adds_the_link_only_when_the_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            shutil.copytree(ROOT / "docs", fake / "docs")
            (fake / "site" / ".well-known").mkdir(parents=True)
            with patch.object(build_site_machine, "ROOT", fake):
                without = build_site_machine.generated_files()["llms.txt"]
                (fake / "site" / ".well-known" / "analystos-seal-key.json").write_text("{}")
                with_file = build_site_machine.generated_files()["llms.txt"]
        self.assertNotIn("analystos-seal-key", without)
        self.assertIn("analystos-seal-key.json", with_file)
        self.assertIn("Seal verification key", with_file)

    def test_the_standalone_verifier_still_imports_only_the_standard_library(self):
        import ast
        tree = ast.parse((ROOT / "analystos" / "l4" / "seal_verify.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertLessEqual(imported, set(sys.stdlib_module_names) | {"cryptography"})

    def test_the_docs_name_the_path_the_format_and_the_operator_steps(self):
        doc = (ROOT / "docs" / "seal.md").read_text()
        for needle in ("/.well-known/analystos-seal-key.json", KEY_FILE_FORMAT, "--key-file", "Turning it on",
                       "tools/seal_key_file.py --from-env", "--expect-seal-key --seal", "Revocation is removal"):
            self.assertIn(needle, doc)


if __name__ == "__main__":
    unittest.main()
