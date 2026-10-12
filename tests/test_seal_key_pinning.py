"""Slice 90 - `--from-prompt` (the seed is never on a command line), `--require-authentic`
(exit 0 is not "authentic"), and `--expect-key-id` (pin the key out of band). See
specs/slice-90/spec.md.

Every keypair is a throwaway generated in-process and never printed; nothing is written under
site/ (files live in temp directories)."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from analystos.l4 import seal_verify
from analystos.l4.seal import SEAL_KEY_ENV, build_bundle
from analystos.l4.seal_verify import pinned_public_key, verify_bundle_with_key_file

from tests.test_seal_key_file import DATE, TEXT, key_file, new_pair, signed, trace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import seal_key_file as tool  # noqa: E402

SEED_MARK = "SEED-MUST-NOT-APPEAR"


class FromPromptTest(unittest.TestCase):
    """Done when #1."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name) / "site" / ".well-known" / "analystos-seal-key.json"
        self.priv, self.pub = new_pair()

    def run_tool(self, *args, getpass_fn=None, env=None, isatty_fn=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = tool.main(list(args), stdout=out, environ=env if env is not None else {},
                             getpass_fn=getpass_fn, isatty_fn=isatty_fn)
        return code, out.getvalue(), err.getvalue()

    def answer(self, value):
        prompts = []

        def fake(prompt):
            prompts.append(prompt)
            if isinstance(value, BaseException):
                raise value
            return value

        fake.prompts = prompts
        return fake

    def test_it_writes_the_same_file_as_from_env_and_the_seed_appears_nowhere(self):
        fake = self.answer(self.priv)
        code, out, err = self.run_tool("--from-prompt", "--out", str(self.out), "--added", DATE, getpass_fn=fake)
        self.assertEqual(code, 0, err)
        from_prompt = self.out.read_text()
        for stream in (from_prompt, out, err, "".join(fake.prompts)):
            self.assertNotIn(self.priv, stream)
        self.out.unlink()
        self.run_tool("--from-env", "--out", str(self.out), "--added", DATE, env={SEAL_KEY_ENV: self.priv})
        self.assertEqual(self.out.read_text(), from_prompt)
        doc = json.loads(from_prompt)
        self.assertEqual(doc["keys"][0]["public_key"], self.pub)  # what keygen printed as the public key
        self.assertEqual(json.loads(out)["public_key"], self.pub)
        self.assertEqual(len(fake.prompts), 1)
        self.assertIn("nothing will be shown", fake.prompts[0])

    def test_it_needs_no_environment_variable_and_ignores_one(self):
        other_priv, _ = new_pair()
        fake = self.answer(f"  {self.priv}  \n")
        code, _, _ = self.run_tool("--from-prompt", "--out", str(self.out), "--added", DATE, getpass_fn=fake,
                                   env={SEAL_KEY_ENV: other_priv})
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.out.read_text())["keys"][0]["public_key"], self.pub)

    def test_rotation_works_through_the_prompt(self):
        self.run_tool("--public-key", self.pub, "--out", str(self.out), "--added", DATE)
        priv2, pub2 = new_pair()
        code, _, err = self.run_tool("--from-prompt", "--add", "--out", str(self.out), "--added", "2026-11-01",
                                     getpass_fn=self.answer(priv2))
        self.assertEqual(code, 0, err)
        doc = json.loads(self.out.read_text())
        self.assertEqual([k["status"] for k in doc["keys"]], ["retired", "active"])
        self.assertEqual(doc["keys"][1]["public_key"], pub2)

    def test_every_refusal_exits_2_writes_nothing_and_never_echoes_the_entry(self):
        cases = {
            "empty entry": ("", []),
            "whitespace only": ("   \n", []),
            "not base64url": (SEED_MARK + "!!!", []),
            "too short": ("abcd", []),
            "too long": (self.priv + self.priv, []),
            "interrupted (Ctrl-C)": (KeyboardInterrupt(), []),
            "end of input (Ctrl-D)": (EOFError(), []),
            "together with --from-env": (self.priv, ["--from-env"]),
            "together with --public-key": (self.priv, ["--public-key", self.pub]),
        }
        for label, (entry, extra) in cases.items():
            with self.subTest(case=label):
                code, out, err = self.run_tool("--from-prompt", *extra, "--out", str(self.out), getpass_fn=self.answer(entry),
                                               env={SEAL_KEY_ENV: self.priv})
                self.assertEqual(code, 2, err)
                self.assertFalse(self.out.exists())
                if isinstance(entry, str) and entry.strip():
                    self.assertNotIn(entry.strip(), out + err)
                self.assertNotIn(self.priv, out + err)

    def test_without_a_terminal_it_refuses_and_does_not_read_a_pipe(self):
        code, _, err = self.run_tool("--from-prompt", "--out", str(self.out), isatty_fn=lambda: False)
        self.assertEqual(code, 2)
        self.assertIn("interactive terminal", err)
        self.assertFalse(self.out.exists())

    def test_as_a_real_command_a_piped_seed_is_refused_and_not_used(self):
        done = subprocess.run([sys.executable, "tools/seal_key_file.py", "--from-prompt", "--out", str(self.out)],
                              input=self.priv + "\n", capture_output=True, text=True, cwd=ROOT, timeout=60,
                              env={k: v for k, v in os.environ.items() if k != SEAL_KEY_ENV})
        self.assertEqual(done.returncode, 2)
        self.assertNotIn(self.priv, done.stdout + done.stderr)
        self.assertFalse(self.out.exists())

    def test_pasting_the_public_key_by_mistake_is_visible_in_what_the_tool_prints(self):
        # Both halves are 32 bytes, so the tool cannot tell them apart; the printed public_key is the check.
        code, out, _ = self.run_tool("--from-prompt", "--out", str(self.out), getpass_fn=self.answer(self.pub))
        self.assertEqual(code, 0)
        self.assertNotEqual(json.loads(out)["public_key"], self.pub)

    def test_the_prompt_mode_has_no_network_or_secret_store(self):
        source = (ROOT / "tools" / "seal_key_file.py").read_text()
        for forbidden in ("urllib", "requests", "socket", "subprocess", "print(entered", "print(seed"):
            self.assertNotIn(forbidden, source)


def cli(*args, stdout=None):
    out = io.StringIO()
    code = seal_verify.main(list(args), stdout=out)
    text = out.getvalue()
    try:
        return code, json.loads(text), text
    except ValueError:
        return code, {}, text


class RequireAuthenticTest(unittest.TestCase):
    """Done when #2."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.priv, self.pub = new_pair()

    def write(self, name, doc):
        path = self.tmp / name
        path.write_text(json.dumps(doc))
        return str(path)

    def test_an_authentic_seal_exits_0_with_or_without_the_flag(self):
        bundle = self.write("b.json", signed(self.priv))
        for flags in ([], ["--require-authentic"]):
            with self.subTest(flags=flags):
                code, result, _ = cli(bundle, "--public-key", self.pub, *flags)
                self.assertEqual((code, result["authentic"]), (0, True))

    def test_not_authentic_but_no_check_failed_exits_0_by_default_and_1_with_the_flag(self):
        cases = {
            "signed seal, no pinned key": (self.write("a.json", signed(self.priv)), []),
            "unsigned seal": (self.write("u.json", build_bundle(trace())), []),
            "unsigned seal even with a pinned key": (self.write("u2.json", build_bundle(trace())), ["--public-key", self.pub]),
        }
        for label, (bundle, extra) in cases.items():
            with self.subTest(case=label):
                code, result, plain = cli(bundle, *extra)
                self.assertEqual((code, result["ok"], result["authentic"]), (0, True, False))   # unchanged default
                code2, result2, strict = cli(bundle, *extra, "--require-authentic")
                self.assertEqual(code2, 1)
                self.assertEqual(plain, strict)   # the flag changes only the exit status, not the output

    def test_with_a_key_file(self):
        bundle = self.write("b.json", signed(self.priv))
        listed = self.write("k.json", key_file(self.pub))
        unlisted = self.write("k2.json", key_file(new_pair()[1]))
        self.assertEqual(cli(bundle, "--key-file", listed, "--require-authentic")[0], 0)
        self.assertEqual(cli(bundle, "--key-file", unlisted, "--require-authentic")[0], 1)
        self.assertEqual(cli(bundle, "--key-file", unlisted)[0], 1)   # a key failure is already a failure

    def test_tampered_and_unreadable_input_are_unchanged_by_the_flag(self):
        bad = signed(self.priv)
        bad["payload"]["tier"] = "plain"
        tampered = self.write("t.json", bad)
        for flags in ([], ["--require-authentic"]):
            with self.subTest(flags=flags):
                self.assertEqual(cli(tampered, "--public-key", self.pub, *flags)[0], 1)
                self.assertEqual(cli(str(self.tmp / "missing.json"), *flags)[0], 2)
                self.assertEqual(cli(*flags)[0], 2)

    def test_the_headline_case_a_missing_cryptography_package(self):
        bundle = self.write("b.json", signed(self.priv))
        code = ("import sys; sys.modules['cryptography'] = None; "
                "from analystos.l4.seal_verify import main; sys.exit(main(sys.argv[1:]))")
        env = {k: v for k, v in os.environ.items() if k != SEAL_KEY_ENV}

        def run(*args):
            done = subprocess.run([sys.executable, "-c", code, bundle, "--public-key", self.pub, *args],
                                  capture_output=True, text=True, cwd=ROOT, env=env, timeout=60)
            return done.returncode, json.loads(done.stdout)

        plain_code, plain = run()
        self.assertEqual((plain_code, plain["ok"], plain["authentic"]), (0, True, False))   # the trap
        strict_code, strict = run("--require-authentic")
        self.assertEqual((strict_code, strict["authentic"]), (1, False))
        sig = {c["name"]: c for c in strict["checks"]}["signature"]
        self.assertEqual(sig["status"], "skipped")
        self.assertIn("cryptography", sig["detail"])


class ExpectKeyIdTest(unittest.TestCase):
    """Done when #3."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.old_priv, self.old_pub = new_pair()
        self.new_priv, self.new_pub = new_pair()
        self.kf = key_file(self.old_pub, self.new_pub)      # a rotated file: old retired, new active
        self.old_id, self.new_id = (k["key_id"] for k in self.kf["keys"])

    def write(self, name, doc):
        path = self.tmp / name
        path.write_text(json.dumps(doc))
        return str(path)

    def test_the_pinned_key_passes(self):
        out = verify_bundle_with_key_file(signed(self.new_priv), self.kf, source_text=TEXT, expect_key_id=self.new_id)
        self.assertEqual((out["ok"], out["authentic"], out["content_checked"]), (True, True, True))
        self.assertEqual(out["checks"][0]["status"], "pass")
        out_old = verify_bundle_with_key_file(signed(self.old_priv), self.kf, expect_key_id=self.old_id)
        self.assertTrue(out_old["authentic"])

    def test_a_seal_signed_by_a_different_listed_key_is_refused(self):
        for seal_priv, pinned in ((self.old_priv, self.new_id), (self.new_priv, self.old_id)):
            out = verify_bundle_with_key_file(signed(seal_priv), self.kf, expect_key_id=pinned)
            self.assertEqual((out["ok"], out["authentic"], out["content_checked"]), (False, False, False))
            self.assertEqual(out["checks"][0]["status"], "fail")
            self.assertIn("you pinned key " + pinned, out["checks"][0]["detail"])

    def test_without_the_pin_the_same_seals_pass_so_the_pin_is_what_refuses_them(self):
        self.assertTrue(verify_bundle_with_key_file(signed(self.old_priv), self.kf)["authentic"])

    def test_a_pinned_id_the_file_does_not_list_is_refused_even_if_the_seal_names_it(self):
        stranger_priv, stranger_pub = new_pair()
        pinned = tool.key_entry(stranger_pub, DATE)["key_id"]
        out = verify_bundle_with_key_file(signed(stranger_priv), self.kf, expect_key_id=pinned)
        self.assertEqual((out["ok"], out["authentic"]), (False, False))
        self.assertIn("not in the published key file", out["checks"][0]["detail"])

    def test_naming_the_pinned_id_in_the_unsigned_key_id_field_is_not_enough(self):
        attacker_priv, _ = new_pair()
        forged = signed(attacker_priv)
        forged["signature"]["key_id"] = self.new_id         # claims the pinned key; signed by someone else
        out = verify_bundle_with_key_file(forged, self.kf, expect_key_id=self.new_id)
        self.assertEqual((out["ok"], out["authentic"]), (False, False))
        self.assertEqual({c["name"]: c["status"] for c in out["checks"]}["signature"], "fail")

    def test_a_file_that_swaps_in_another_public_key_under_the_pinned_id_is_invalid(self):
        evil = key_file(new_pair()[1])
        evil["keys"][0]["key_id"] = self.new_id              # key_id must be sha256(public key)[:16]
        out = verify_bundle_with_key_file(signed(self.new_priv), evil, expect_key_id=self.new_id)
        self.assertEqual((out["ok"], out["authentic"]), (False, False))
        self.assertIn("not valid", out["checks"][0]["detail"])

    def test_malformed_ids_are_a_usage_error_not_a_verdict(self):
        bundle = signed(self.new_priv)
        for bad in (self.new_id.upper(), self.new_id[:-1], self.new_id + "0", "z" * 16, "", 7, ["x"]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    verify_bundle_with_key_file(bundle, self.kf, expect_key_id=bad)

    def test_an_unsigned_seal_stays_not_authentic_and_the_flag_catches_it(self):
        unsigned = self.write("u.json", build_bundle(trace()))
        kf = self.write("k.json", self.kf)
        code, result, _ = cli(unsigned, "--key-file", kf, "--expect-key-id", self.new_id)
        self.assertEqual((code, result["ok"], result["authentic"]), (0, True, False))
        self.assertEqual(cli(unsigned, "--key-file", kf, "--expect-key-id", self.new_id, "--require-authentic")[0], 1)

    def test_pinned_public_key_reports_why(self):
        key, reason = pinned_public_key(signed(self.old_priv), self.kf, expect_key_id=self.new_id)
        self.assertIsNone(key)
        self.assertIn(f"signed by key {self.old_id}", reason)
        self.assertEqual(pinned_public_key(signed(self.new_priv), self.kf, expect_key_id=self.new_id), (self.new_pub, None))

    def test_the_cli_end_to_end(self):
        bundle, kf = self.write("b.json", signed(self.new_priv)), self.write("k.json", self.kf)
        text = self.tmp / "t.txt"
        text.write_text(TEXT)
        code, result, _ = cli(bundle, "--key-file", kf, "--expect-key-id", self.new_id, "--text", str(text), "--require-authentic")
        self.assertEqual((code, result["authentic"], result["content_checked"]), (0, True, True))
        code, result, _ = cli(bundle, "--key-file", kf, "--expect-key-id", self.old_id)
        self.assertEqual((code, result["authentic"]), (1, False))

    def test_cli_usage_errors_exit_2(self):
        bundle, kf = self.write("b.json", signed(self.new_priv)), self.write("k.json", self.kf)
        for args in ([bundle, "--expect-key-id", self.new_id],                                  # no key file
                     [bundle, "--public-key", self.new_pub, "--expect-key-id", self.new_id],      # a full pin already
                     [bundle, "--key-file", kf, "--expect-key-id", "NOPE"],                       # malformed
                     [bundle, "--key-file", kf, "--expect-key-id"]):                              # missing value
            with self.subTest(args=args):
                code, result, _ = cli(*args)
                self.assertEqual(code, 2)
                self.assertIn("error", result)


class DocsTest(unittest.TestCase):
    """Done when #4."""

    DOC = (ROOT / "docs" / "seal.md").read_text()

    def test_all_three_flags_are_documented(self):
        for flag in ("--from-prompt", "--require-authentic", "--expect-key-id"):
            self.assertIn(flag, self.DOC)

    def test_the_recommended_step_does_not_put_the_seed_on_a_command_line(self):
        step = self.DOC[self.DOC.index("### Turning it on"):]
        self.assertLess(step.index("--from-prompt"), step.index("--from-env"))
        self.assertIn("shell history", step)
        recommended = step[:step.index("Alternatives:")]   # everything before the clearly labelled alternatives
        self.assertNotIn("ANALYSTOS_SEAL_KEY=<", recommended)
        self.assertIn("--from-prompt", recommended)

    def test_the_docs_warn_about_where_not_to_generate_a_key_and_say_exit_0_is_not_authentic(self):
        self.assertIn("terminal an AI assistant can read", self.DOC)
        self.assertIn("does not mean authentic", self.DOC)
        self.assertIn("two channels", self.DOC)


if __name__ == "__main__":
    unittest.main()
