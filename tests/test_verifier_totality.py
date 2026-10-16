"""Overnight round 2 - the seal verifier always returns a verdict.

A verifier that raises on hostile input is not failing closed for a caller that is a
library, a web handler or a script reading the exit status of a crash. Fuzzing every
position of a real bundle with values of the wrong type found three ways to make
``verify_bundle`` raise instead of answering:

  * ``signature.public_key`` or ``signature.sig`` that is not a string -> TypeError,
    which ``POST /api/v1/verify`` (no authentication) turned into an HTTP 500;
  * a report reference made of more than 4300 digits -> ValueError from ``int()``;
  * deeply nested JSON in a record, the report or the payload -> RecursionError.

Each must be a ``fail`` verdict: ``ok`` and ``authentic`` false, never an exception.
"""

import copy
import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from analystos.l4 import seal_verify
from analystos.l4.seal import build_bundle, generate_key
from analystos.l4.seal_verify import verify_bundle
from api.analyze import app
from tests.test_l4_seal import TEXT, trace


def nested_list(depth):
    value = "1"
    for _ in range(depth):
        value = [value]
    return value


def nested_dict(depth):
    value = "1"
    for _ in range(depth):
        value = {"a": value}
    return value


class VerifierTotalityTest(unittest.TestCase):
    def setUp(self):
        self.private, self.public = generate_key()
        self.bundle = build_bundle(trace(), signing_key=self.private, caller_id="agent-a")

    def mutated(self, mutate):
        bundle = copy.deepcopy(self.bundle)
        mutate(bundle)
        return bundle

    def hostile(self):
        """name -> a bundle that is wrong in one way."""
        cases = {}
        for field in ("public_key", "sig"):
            for label, value in (("null", None), ("number", 5), ("list", ["x"]), ("object", {"a": 1}), ("bool", True)):
                cases[f"signature.{field} is {label}"] = self.mutated(
                    lambda b, f=field, v=value: b["signature"].__setitem__(f, v))
        cases["signature.sig missing"] = self.mutated(lambda b: b["signature"].pop("sig"))
        cases["signature.public_key missing"] = self.mutated(lambda b: b["signature"].pop("public_key"))
        cases["record nested 3000 lists"] = self.mutated(lambda b: b["facts"][0].__setitem__("record", {"x": nested_list(3000)}))
        cases["record nested 3000 objects"] = self.mutated(lambda b: b["facts"][0].__setitem__("record", {"x": nested_dict(3000)}))
        cases["report nested 3000"] = self.mutated(lambda b: b.__setitem__("report", nested_list(3000)))
        cases["payload field nested 3000"] = self.mutated(lambda b: b["payload"].__setitem__("model_id", nested_list(3000)))
        return cases

    def test_a_hostile_bundle_gets_a_failing_verdict_not_an_exception(self):
        for name, bundle in self.hostile().items():
            for kwargs in ({}, {"public_key": self.public}, {"public_key": self.public, "source_text": TEXT}):
                with self.subTest(case=name, supplied=sorted(kwargs)):
                    outcome = verify_bundle(bundle, **kwargs)
                    self.assertFalse(outcome["ok"], name)
                    self.assertFalse(outcome["authentic"], name)
                    self.assertFalse(outcome["content_checked"], name)

    def test_a_report_reference_of_thousands_of_digits_is_a_dangling_citation(self):
        run = trace()
        run["report"] = {"title": "T", "kpis": [{"label": "R", "value_fact": "9" * 5000}]}
        bundle = build_bundle(run, signing_key=self.private)
        outcome = verify_bundle(bundle, public_key=self.public, source_text=TEXT)  # must not raise
        self.assertFalse(outcome["ok"])
        self.assertIn("not sealed", " ".join(c["detail"] for c in outcome["checks"] if c["name"] == "report_refs"))

    def test_an_ordinary_bundle_still_verifies(self):
        outcome = verify_bundle(self.bundle, public_key=self.public, source_text=TEXT)
        self.assertTrue(outcome["ok"] and outcome["authentic"], outcome)

    def test_the_unauthenticated_verify_route_answers_200_with_a_failing_verdict(self):
        with patch.dict(os.environ, {"ANALYSTOS_RATE_LIMIT_MAX": "100000"}):
            client = app.test_client()
            for name, bundle in self.hostile().items():
                if "nested 3000" in name:
                    continue  # the web layer's own JSON parser refuses these before verification
                with self.subTest(case=name):
                    response = client.post("/api/v1/verify", data=json.dumps({"bundle": bundle, "public_key": self.public}),
                                           content_type="application/json")
                    self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:120])
                    self.assertFalse(response.get_json()["ok"])

    def test_a_key_file_nested_too_deeply_is_invalid_not_a_crash(self):
        from tools.seal_key_file import build_key_file, key_entry
        key_file = build_key_file([key_entry(self.public, "2026-10-01")])
        self.assertEqual(seal_verify.validate_key_file(key_file), [])
        key_file["note"] = nested_list(3000)
        problems = seal_verify.validate_key_file(key_file)
        self.assertTrue(problems and "deeply" in problems[0], problems)
        outcome = seal_verify.verify_bundle_with_key_file(self.bundle, key_file)
        self.assertFalse(outcome["ok"] or outcome["authentic"])

    def test_the_command_line_reports_a_too_deeply_nested_file_as_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep.json"
            path.write_text('{"format": ' + "[" * 200000 + "]" * 200000 + "}", encoding="utf-8")
            out = StringIO()
            code = seal_verify.main([str(path)], stdout=out)
        self.assertEqual(code, 2, out.getvalue()[:200])
        self.assertIn("error", json.loads(out.getvalue()))


if __name__ == "__main__":
    unittest.main()
