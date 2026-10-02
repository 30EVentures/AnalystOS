"""Slice 84 - the audit log is a hash chain, signed when a key is set."""

import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from analystos.api_v1 import store as store_mod
from analystos.api_v1.__main__ import main as cli_main
from analystos.api_v1.audit import measures
from analystos.api_v1.audit_chain import GENESIS, verify_audit_log
from analystos.l4.seal import generate_key


def event(i, **over):
    return {"ts": f"2026-10-02T00:00:{i:02d}Z", "type": "analysis", "caller": "agent-a", "id": f"{i:064x}",
            "tier": "written", "proposed": 5, "verified": 4, "dropped": 1, "seal_ok": True, **over}


class ChainTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.priv, self.pub = generate_key()
        self.store = store_mod.FileStore(Path(self._tmp.name) / "store")
        self.path = self.store.root / "audit.jsonl"
        env = patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": self.priv})
        env.start()
        self.addCleanup(env.stop)

    def fill(self, n=4):
        for i in range(n):
            self.store.append_audit(event(i))

    def lines(self):
        return self.path.read_text().splitlines()

    def rewrite(self, lines):
        self.path.write_text("\n".join(lines) + "\n")

    def edit_line(self, index, **changes):
        lines = self.lines()
        entry = json.loads(lines[index])
        entry.update(changes)
        lines[index] = json.dumps(entry, sort_keys=True)
        self.rewrite(lines)

    def check(self, **kw):
        return verify_audit_log(self.path, public_key=self.pub, **kw)

    def names(self, outcome):
        return {c["name"]: c["status"] for c in outcome["checks"]}


class WritingTest(ChainTestCase):
    def test_entries_are_chained_from_genesis_in_insertion_order(self):
        self.fill(3)
        entries = [json.loads(l) for l in self.lines()]
        self.assertEqual([e["seq"] for e in entries], [0, 1, 2])
        self.assertEqual(entries[0]["prev_hash"], GENESIS)
        self.assertEqual(entries[1]["prev_hash"], entries[0]["entry_hash"])
        self.assertEqual(entries[2]["prev_hash"], entries[1]["entry_hash"])
        self.assertTrue(all(e["log_signing"] == "ed25519" and e["signature"] and e["key_id"] for e in entries))

    def test_the_event_fields_are_preserved(self):
        self.store.append_audit(event(7))
        entry = self.store.read_audit()[0]
        for key, value in event(7).items():
            self.assertEqual(entry[key], value)

    def test_without_a_key_entries_are_chained_unsigned_and_say_so(self):
        with patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": ""}):
            self.fill(3)
        entries = [json.loads(l) for l in self.lines()]
        self.assertTrue(all(e["log_signing"] == "none" and "signature" not in e and "key_id" not in e for e in entries))
        out = verify_audit_log(self.path)
        self.assertTrue(out["ok"], out)
        self.assertFalse(out["authentic"])
        self.assertEqual(self.names(out)["signatures"], "skipped")

    def test_a_malformed_key_does_not_lose_the_line(self):
        with patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": "garbage"}):
            self.fill(2)
        self.assertEqual(len(self.lines()), 2)
        self.assertTrue(verify_audit_log(self.path)["ok"])

    def test_emit_audit_without_a_store_still_goes_to_stderr_unchanged(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            store_mod.emit_audit(None, {"type": "analysis", "caller": "x"})
        line = json.loads(err.getvalue())
        self.assertEqual(set(line), {"audit"})
        self.assertNotIn("seq", line["audit"])
        self.assertNotIn("entry_hash", line["audit"])

    def test_a_cut_short_last_line_is_not_glued_onto(self):
        self.fill(2)
        with open(self.path, "a") as handle:
            handle.write('{"partial": tr')  # no newline
        self.store.append_audit(event(9))
        self.assertEqual(len(self.lines()), 4)
        json.loads(self.lines()[-1])

    def test_concurrent_appends_keep_one_unbroken_chain(self):
        def work(base):
            for i in range(10):
                self.store.append_audit(event(base + i))

        threads = [threading.Thread(target=work, args=(b,)) for b in (0, 20, 40, 60)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        out = self.check()
        self.assertTrue(out["ok"] and out["authentic"], out)
        self.assertEqual(out["chained"], 40)


class VerificationTest(ChainTestCase):
    def test_an_intact_signed_log_is_ok_and_authentic_under_the_pinned_key(self):
        self.fill()
        out = self.check()
        self.assertTrue(out["ok"] and out["authentic"], out)
        self.assertEqual((out["chained"], out["signed"], out["unsigned"], out["legacy_unchained"]), (4, 4, 0, 0))

    def test_without_a_pinned_key_it_is_ok_but_not_authentic(self):
        self.fill()
        out = verify_audit_log(self.path)
        self.assertTrue(out["ok"])
        self.assertFalse(out["authentic"])
        self.assertEqual(self.names(out)["signatures"], "skipped")

    def test_editing_one_entry_is_detected(self):
        self.fill()
        self.edit_line(1, caller="someone-else")
        out = self.check()
        self.assertFalse(out["ok"], out)
        self.assertEqual(self.names(out)["chain"], "fail")

    def test_editing_an_entry_and_recomputing_its_hash_breaks_the_next_link(self):
        from analystos.api_v1.audit_chain import entry_hash

        self.fill()
        entry = json.loads(self.lines()[1])
        entry["caller"] = "forged"
        entry["entry_hash"] = entry_hash(entry)
        lines = self.lines()
        lines[1] = json.dumps(entry, sort_keys=True)
        self.rewrite(lines)
        self.assertFalse(self.check()["ok"])  # the next line's prev_hash no longer matches

    def test_a_forged_rehash_without_the_key_fails_the_signature(self):
        from analystos.api_v1.audit_chain import entry_hash

        self.fill(1)
        entry = json.loads(self.lines()[0])
        entry["caller"] = "forged"
        entry["entry_hash"] = entry_hash(entry)  # chain is self-consistent now
        self.rewrite([json.dumps(entry, sort_keys=True)])
        out = self.check()
        self.assertEqual(self.names(out)["chain"], "pass")
        self.assertEqual(self.names(out)["signatures"], "fail")
        self.assertFalse(out["ok"])

    def test_a_signature_from_a_different_key_fails(self):
        self.fill(2)
        _, other_pub = generate_key()
        out = verify_audit_log(self.path, public_key=other_pub)
        self.assertEqual(self.names(out)["signatures"], "fail")

    def test_deleting_a_middle_entry_is_detected(self):
        self.fill()
        lines = self.lines()
        del lines[1]
        self.rewrite(lines)
        self.assertFalse(self.check()["ok"])

    def test_reordering_is_detected(self):
        self.fill()
        lines = self.lines()
        lines[1], lines[2] = lines[2], lines[1]
        self.rewrite(lines)
        self.assertFalse(self.check()["ok"])

    def test_inserting_a_line_is_detected(self):
        self.fill()
        lines = self.lines()
        lines.insert(2, lines[1])
        self.rewrite(lines)
        self.assertFalse(self.check()["ok"])

    def test_dropping_the_tail_is_caught_only_with_a_pinned_head(self):
        self.fill()
        head = self.check()["head"]
        self.rewrite(self.lines()[:-1])
        self.assertTrue(self.check()["ok"])  # a shorter honest chain: indistinguishable without the head
        out = self.check(expected_head=head)
        self.assertFalse(out["ok"])

    def test_growth_keeps_old_verification_valid(self):
        self.fill(2)
        head_before = self.check()["head"]
        self.fill(3)
        out = self.check()
        self.assertTrue(out["ok"] and out["authentic"], out)
        self.assertEqual(out["chained"], 5)
        # the earlier head is still a line of the grown log
        self.assertIn(head_before, [json.loads(l)["entry_hash"] for l in self.lines()])
        first_two = self.path.read_text().splitlines()[:2]
        self.rewrite(first_two)
        self.assertEqual(self.check(expected_head=head_before)["head"], head_before)

    def test_stripping_a_signature_cannot_pass_as_unsigned(self):
        self.fill(2)
        lines = self.lines()
        entry = json.loads(lines[1])
        del entry["signature"]
        lines[1] = json.dumps(entry, sort_keys=True)
        self.rewrite(lines)
        self.assertFalse(self.check()["ok"])

    def test_relabelling_a_signed_entry_unsigned_breaks_its_hash(self):
        self.fill(2)
        self.edit_line(1, log_signing="none")
        self.assertFalse(self.check()["ok"])

    def test_a_mixed_log_is_ok_but_not_authentic(self):
        with patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": ""}):
            self.fill(2)
        self.fill(2)
        out = self.check()
        self.assertTrue(out["ok"], out)
        self.assertFalse(out["authentic"])
        self.assertEqual((out["signed"], out["unsigned"]), (2, 2))

    def test_an_empty_log_fails_closed(self):
        self.path.write_text("")
        out = self.check()
        self.assertFalse(out["ok"])

    def test_garbage_is_a_failure_not_a_crash(self):
        self.fill(2)
        self.rewrite(self.lines() + ["not json"])
        self.assertFalse(self.check()["ok"])
        self.rewrite(["[1,2]"])
        self.assertFalse(self.check()["ok"])


class LegacyTest(ChainTestCase):
    LEGACY = [event(i) for i in range(3)]

    def seed_legacy(self):
        self.path.write_text("\n".join(json.dumps(e, sort_keys=True) for e in self.LEGACY) + "\n")

    def test_old_unchained_lines_are_tolerated_before_the_chain_and_still_counted(self):
        self.seed_legacy()
        self.fill(2)
        out = self.check()
        self.assertTrue(out["ok"] and out["authentic"], out)
        self.assertEqual((out["legacy_unchained"], out["chained"]), (3, 2))
        self.assertEqual(json.loads(self.lines()[3])["seq"], 0)

    def test_an_unchained_line_after_the_chain_began_is_a_failure(self):
        self.fill(2)
        self.rewrite(self.lines() + [json.dumps(event(9))])
        self.assertFalse(self.check()["ok"])

    def test_a_legacy_only_log_fails_closed_because_nothing_is_verifiable(self):
        self.seed_legacy()
        self.assertFalse(self.check()["ok"])

    def test_readers_tolerate_the_new_fields_and_legacy_lines(self):
        self.seed_legacy()
        self.fill(2)
        events = self.store.read_audit()
        self.assertEqual(len(events), 5)
        result = measures(events)
        self.assertEqual(result["analysis"]["denominator"], 5)
        self.assertEqual(result["verification"]["numerator"], 5)
        out = io.StringIO()
        self.assertEqual(cli_main(["measures", str(self.path)], stdout=out), 0)
        self.assertEqual(json.loads(out.getvalue())["analysis"]["denominator"], 5)


class CliTest(ChainTestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        code = cli_main(["verify-audit", *args], stdout=out)
        return code, json.loads(out.getvalue())

    def test_exit_codes(self):
        self.fill(3)
        code, body = self.run_cli(str(self.path), "--public-key", self.pub)
        self.assertEqual((code, body["ok"], body["authentic"]), (0, True, True))
        code, _ = self.run_cli(str(self.path))
        self.assertEqual(code, 0)
        code, body = self.run_cli(str(self.path), "--expect-head", "sha256:" + "1" * 64)
        self.assertEqual(code, 1)
        self.edit_line(0, caller="x")
        code, body = self.run_cli(str(self.path))
        self.assertEqual(code, 1)
        self.assertFalse(body["ok"])
        code, body = self.run_cli(str(self.path.with_name("missing.jsonl")))
        self.assertEqual(code, 2)
        self.assertIn("error", body)
        code, _ = self.run_cli()
        self.assertEqual(code, 2)
        code, _ = self.run_cli(str(self.path), "--public-key")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
