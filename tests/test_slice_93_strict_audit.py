"""Slice 93 - audit lines are strict JSON. See specs/slice-93/spec.md."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analystos.api_v1 import store as store_mod
from analystos.api_v1.audit_chain import StrictJSONError, strict_loads, verify_audit_log, verify_entries
from analystos.l4.seal import generate_key
from tests.test_api_v1_audit_chain import event


class StrictLoadsTest(unittest.TestCase):
    def test_refuses_what_other_parsers_read_differently(self):
        bad = [
            '{"a": 1, "a": 2}', '{"a": 1, "a": 1}', '{"x": {"a": 1, "a": 1}}', '[{"a": 1, "a": 1}]',
            '{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}', '[NaN]', '{"a": 1e999}', '{"a": -1e999}',
        ]
        for raw in bad:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    strict_loads(raw)

    def test_the_portability_failures_are_a_named_error(self):
        for raw in ('{"a": 1, "a": 1}', '{"a": NaN}', '{"a": 1e999}'):
            with self.subTest(raw=raw), self.assertRaises(StrictJSONError):
                strict_loads(raw)

    def test_ordinary_json_loads_exactly_as_before(self):
        raw = '{"a": [1, 2.5, -3e2, "é", null, true], "b": {"c": 0.1}, "d": 12345678901234567890}'
        self.assertEqual(strict_loads(raw), json.loads(raw))

    def test_plain_syntax_errors_are_still_value_errors(self):
        with self.assertRaises(ValueError):
            strict_loads("{not json")


class VerifierTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = store_mod.FileStore(Path(self._tmp.name) / "s")
        patcher = patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def chain(self, n=3, **over):
        for i in range(n):
            self.store.append_audit(event(i, **(over if i == 0 else {})))
        return (self.store.root / "audit.jsonl").read_text().splitlines()

    def test_a_line_with_a_duplicate_key_of_equal_value_is_refused_with_the_reason(self):
        lines = self.chain()
        lines[0] = lines[0].replace('"seq": 0', '"seq": 0, "seq": 0', 1)
        out = verify_entries(lines)
        self.assertFalse(out["ok"])
        self.assertIn("not strict JSON", out["checks"][0]["detail"])
        self.assertIn("twice", out["checks"][0]["detail"])

    def test_an_infinity_literal_is_refused(self):
        lines = self.chain()
        lines[1] = lines[1].replace('"proposed": 5', '"proposed": Infinity', 1)
        self.assertFalse(verify_entries(lines)["ok"])

    def test_a_clean_log_still_verifies(self):
        self.assertTrue(verify_entries(self.chain())["ok"])


class WriterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.priv, self.pub = generate_key()
        patcher = patch.dict(os.environ, {"ANALYSTOS_SEAL_KEY": self.priv})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.store = store_mod.FileStore(Path(self._tmp.name) / "s")
        self.path = self.store.root / "audit.jsonl"

    def append(self, ev):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.store.append_audit(ev)
        return err.getvalue()

    def test_an_event_with_a_non_finite_number_never_reaches_the_file_as_a_literal(self):
        self.append(event(0))
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad):
                self.append(event(1, proposed=bad))
        text = self.path.read_text()
        for literal in ("NaN", "Infinity"):
            self.assertNotIn(literal, text)

    def test_the_refusal_is_a_marker_line_and_the_log_still_verifies_authentic(self):
        self.append(event(0))
        err = self.append(event(1, type="analysis", proposed=float("nan")))
        self.append(event(2))
        lines = self.path.read_text().splitlines()
        self.assertEqual(len(lines), 3)
        marker = strict_loads(lines[1])
        self.assertEqual(marker["type"], "audit_event_refused")
        self.assertEqual(marker["original_type"], "analysis")
        self.assertIn("non-finite", err)
        out = verify_audit_log(self.path, public_key=self.pub)
        self.assertTrue(out["ok"] and out["authentic"], out)
        self.assertEqual(out["chained"], 3)

    def test_a_normal_event_is_written_unchanged(self):
        self.append(event(0))
        entry = strict_loads(self.path.read_text().splitlines()[0])
        self.assertEqual(entry["type"], "analysis")
        self.assertEqual(entry["proposed"], 5)


if __name__ == "__main__":
    unittest.main()
