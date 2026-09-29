"""Slice 76: the published SealFact schema matches what the pipeline seals.

No jsonschema dependency: `valid` implements only the keywords the schema uses.
"""
import re
import unittest

from analystos.api_v1.openapi import build_openapi
from analystos.l2 import analyze
from analystos.l4.seal import build_bundle
from analystos.l4.seal_schema import OPERATIONS, SEAL_FACT_SCHEMA
from analystos.l4.seal_verify import normalize

_TYPES = {"string": str, "array": list, "object": dict, "null": type(None)}


def valid(value, schema):
    if "oneOf" in schema:
        return sum(valid(value, s) for s in schema["oneOf"]) == 1
    if "anyOf" in schema:
        return any(valid(value, s) for s in schema["anyOf"])
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(isinstance(value, _TYPES[k]) for k in kinds):
            return False
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        return False
    if isinstance(value, dict):
        if any(k not in value for k in schema.get("required", [])):
            return False
        if not all(valid(value[k], s) for k, s in schema.get("properties", {}).items() if k in value):
            return False
    if isinstance(value, list) and "items" in schema:
        return all(valid(v, schema["items"]) for v in value)
    return True


DOC = analyze._match_key(
    "Revenue was $498.0 million. Net income fell from $22.4 million to $19.6 million. Launch on March 3.")
SCALE = 1


def sealed(record):
    return normalize(record)


class ProducedRecordsFitTest(unittest.TestCase):
    def check(self, record):
        self.assertTrue(valid(sealed(record), SEAL_FACT_SCHEMA), record)

    def test_quote_without_a_value(self):
        rec, err = analyze._verify_quote({"exact_text": "Revenue was $498.0 million"}, DOC, SCALE)
        self.assertIsNone(err)
        self.check(rec)

    def test_quote_with_a_value(self):
        rec, err = analyze._verify_quote({"exact_text": "$498.0 million", "has_value": True, "value": 498000000.0,
                                          "sentence": "Revenue was {value}.", "label": "Revenue", "format": "usd"}, DOC, SCALE)
        self.assertIsNone(err, err)
        self.check(rec)

    def test_computed_growth_and_percent_of_total(self):
        ops = [{"exact_text": "$22.4 million", "value": 22400000.0}, {"exact_text": "$19.6 million", "value": 19600000.0}]
        rec, err = analyze._verify_computed({"operation": "growth_percent", "operands": ops, "result": -12.5,
                                             "sentence": "Income moved {value}.", "format": "percent"}, DOC, SCALE)
        self.assertIsNone(err, err)
        self.check(rec)
        rec, err = analyze._verify_computed({"operation": "percent_of_total", "operands": ops[:1], "result": 22400000.0 / 498000000.0 * 100,
                                             "has_total": True, "total_value": 498000000.0, "total_exact_text": "$498.0 million",
                                             "sentence": "That is {value}.", "format": "percent"}, DOC, SCALE)
        self.assertIsNone(err, err)
        self.check(rec)

    def test_prose_and_event(self):
        self.check(analyze._verify_prose({"text": "Momentum continued."})[0])
        rec, err = analyze._verify_event({"event": {"what": "Launch", "date": "March 3", "milestones": []}}, DOC)
        self.assertIsNone(err, err)
        self.check(rec)

    def test_the_seal_test_fixture_facts_fit_too(self):
        from tests.test_l4_seal import trace
        for fact in build_bundle(trace())["facts"]:
            self.assertTrue(valid(fact["record"], SEAL_FACT_SCHEMA), fact["record"])


class MalformedRecordsFailTest(unittest.TestCase):
    def test_rejections(self):
        good = {"type": "prose", "text": "x"}
        self.assertTrue(valid(good, SEAL_FACT_SCHEMA))
        for bad in (
            {"type": "chart", "text": "x"},
            {"type": "quote", "citation": "x", "value": 5},           # raw JSON number, rule 1
            {"type": "quote", "citation": "x", "value": "five"},
            {"type": "computed", "operation": "median", "value": "1", "operands": ["1"], "total": None, "citation": ["a"]},
            {"type": "computed", "operation": "sum", "value": "1", "total": None, "citation": ["a"]},
            {"type": "prose"},
            {"type": "event", "citation": "x"},
        ):
            self.assertFalse(valid(bad, SEAL_FACT_SCHEMA), bad)


class PublishedTest(unittest.TestCase):
    def test_openapi_publishes_it_and_the_bundle_points_at_it(self):
        spec = build_openapi()
        self.assertEqual(spec["components"]["schemas"]["SealFact"], SEAL_FACT_SCHEMA)
        self.assertEqual(spec["components"]["schemas"]["SealBundle"]["properties"]["facts"]["items"],
                         {"$ref": "#/components/schemas/SealFact"})

    def test_operations_match_the_pipeline(self):
        self.assertEqual(tuple(OPERATIONS), analyze._OPERATIONS)

    def test_seal_md_documents_every_type_and_names_the_schema(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parents[1] / "docs" / "seal.md").read_text(encoding="utf-8")
        self.assertIn("SealFact", text)
        for kind in ("quote", "computed", "event", "prose"):
            self.assertIn(f"`{kind}`", text)


if __name__ == "__main__":
    unittest.main()
