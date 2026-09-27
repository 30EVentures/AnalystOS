"""Slice 66 - the standalone verifier checks each quote's value against its
citation. See specs/slice-66/spec.md."""

import copy
import random
import unittest

from analystos.l2 import analyze
from analystos.l4.seal import build_bundle
from analystos.l4.seal_verify import detect_scale, parse_numbers, value_supported, verify_bundle

TEXT = ("All amounts in millions of U.S. dollars.\n"
        "Revenue | 1,842.0 | 1,788.0 | 1,715.0\n"
        "Net additions | (1,050) | 1,240\n"
        "Guidance: revenue of $1.9 billion. Net income was $22.4 million, then $19.6 million.\n"
        "Costs were 88.0 and 34.0 against a total of 142.0.")


def quote(value, citation, **extra):
    return {"type": "quote", "label": "x", "value": value, "format": "usd", "citation": citation, **extra}


def bundle_for(segments, text=TEXT):
    return build_bundle({"tier": "plain", "segments": segments, "report": None, "document_text": text, "source_hash": "b" * 64})


def status(bundle, name="values_match_citations", text=TEXT):
    return {c["name"]: c for c in verify_bundle(bundle, source_text=text)["checks"]}[name]


class LegitimateValuesTest(unittest.TestCase):
    def test_each_way_a_value_can_legitimately_match(self):
        segments = [
            quote(1.9e9, "$1.9 billion"),                    # scale word in the citation
            quote(1_842_000_000.0, "1,842.0"),               # bare, document declares millions
            quote(1_788_000_000.0, "Revenue | 1,842.0 | 1,788.0 | 1,715.0"),  # one cell of a row
            quote(-1_050_000_000.0, "(1,050)"),              # accounting negative, scaled
            quote(22_400_000.0, "$22.4 million"),
            {"type": "prose", "text": "Momentum continued."},   # no value: not covered
            {"type": "quote", "label": "q", "text": "steady", "citation": "steady"},  # qualitative
        ]
        out = status(bundle_for(segments))
        self.assertEqual(out["status"], "pass", out)
        self.assertIn("all 5 values", out["detail"])

    def test_computed_operands_and_total_are_checked_against_their_own_citations(self):
        seg = {"type": "computed", "operation": "percent_of_total", "value": 88 / 142 * 100, "format": "percent",
               "operands": [88_000_000.0], "total": 142_000_000.0, "citation": ["88.0", "142.0"]}
        self.assertEqual(status(bundle_for([seg]))["status"], "pass")


class TamperedValuesTest(unittest.TestCase):
    def assert_caught(self, segments):
        bundle = bundle_for(segments)
        # every hash and the root are valid: a sealer rebuilt the whole thing
        self.assertEqual(status(bundle, "merkle_root")["status"], "pass")
        self.assertEqual(status(bundle)["status"], "fail")
        self.assertFalse(verify_bundle(bundle, source_text=TEXT)["content_checked"])

    def test_a_real_quote_paired_with_a_wrong_value(self):
        self.assert_caught([quote(999_000_000.0, "$22.4 million")])

    def test_a_sign_flip(self):
        self.assert_caught([quote(1_050_000_000.0, "(1,050)")])

    def test_an_unscaled_value_for_a_scaled_table_cell_that_matches_nothing(self):
        self.assert_caught([quote(18_420_000_000.0, "1,842.0")])  # 10x off

    def test_a_wrong_operand(self):
        seg = {"type": "computed", "operation": "sum", "value": 122_400_000.0, "format": "usd",
               "operands": [100_000_000.0, 22_400_000.0], "total": None, "citation": ["$88.0 million", "$22.4 million"]}
        self.assert_caught([seg])

    def test_a_wrong_total(self):
        seg = {"type": "computed", "operation": "percent_of_total", "value": 88 / 999 * 100, "format": "percent",
               "operands": [88_000_000.0], "total": 999_000_000.0, "citation": ["88.0", "142.0"]}
        self.assert_caught([seg])

    def test_a_malformed_value_is_a_failure_not_a_crash(self):
        b = bundle_for([quote("not-a-number", "$22.4 million")])
        self.assertEqual(status(b)["status"], "fail")

    def test_without_the_text_it_is_skipped_and_content_is_unchecked(self):
        b = bundle_for([quote(999_000_000.0, "$22.4 million")])
        out = verify_bundle(b)
        self.assertEqual({c["name"]: c["status"] for c in out["checks"]}["values_match_citations"], "skipped")
        self.assertFalse(out["content_checked"])


class DifferentialAgainstTheAnalyzerTest(unittest.TestCase):
    SAMPLES = [
        "$1.9 billion", "1,842.0", "(1,050)", "-4.7%", "Revenue | 1,842.0 | 1,788.0 | 1,715.0", "$22.4M and $19.6M",
        "12 mm", "3.5bn", ".75", "5 thousand", "1,234,567.89", "no digits here", "Q3 2026 revenue $498.0 million",
        "(2.5) M", "$-3", "7k", "9 b", "10 bn", "100 basis points", "2.0x",
    ]
    TEXTS = ["In thousands", "in millions", "Amounts in Billions of U.S. dollars", "in thousands, and in millions", "plain memo", ""]

    def test_number_parsing_agrees(self):
        for s in self.SAMPLES:
            with self.subTest(s=s):
                self.assertEqual(parse_numbers(s), analyze._parse_numbers(s))

    def test_scale_detection_agrees(self):
        for t in self.TEXTS:
            with self.subTest(t=t):
                self.assertEqual(detect_scale(t), analyze._detect_scale(t))

    def test_the_match_decision_agrees_including_the_analyzers_tolerance_only_when_exact(self):
        rng = random.Random(66)
        for cite in self.SAMPLES:
            for scale in (1, 1_000, 1_000_000):
                candidates = {0.0, 1.0, 1e9}
                for p in parse_numbers(cite):
                    candidates |= {p, p * scale, -p, p * 2, p + 1}
                for value in candidates:
                    ours = value_supported(value, cite, scale)
                    theirs = analyze._value_matches_text(value, cite, scale) is not None
                    # the analyzer accepts within 1%; the verifier is exact on the stored canonical value.
                    # So: whenever the verifier accepts, the analyzer must too.
                    if ours:
                        self.assertTrue(theirs, (cite, scale, value))
        for _ in range(500):
            n = round(rng.uniform(-9999, 9999), rng.randint(0, 3))
            cite = f"${n:,}" if n >= 0 else f"({abs(n):,})"
            scale = rng.choice((1, 1_000, 1_000_000))
            canonical = analyze._value_matches_text(n * scale, cite, scale)
            if canonical is not None:
                self.assertTrue(value_supported(canonical, cite, scale), (cite, scale, canonical))

    def test_what_the_analyzer_stores_always_passes_the_verifier(self):
        for cite in self.SAMPLES:
            for scale in (1, 1_000_000):
                for parsed in parse_numbers(cite):
                    for raw in (parsed, parsed * scale):
                        stored = analyze._value_matches_text(raw, cite, scale)
                        if stored is not None:
                            self.assertTrue(value_supported(stored, cite, scale), (cite, scale, raw))


class DocsTest(unittest.TestCase):
    def test_the_seal_doc_describes_the_check(self):
        from pathlib import Path
        doc = (Path(__file__).resolve().parents[1] / "docs" / "seal.md").read_text()
        self.assertIn("values_match_citations", doc)


if __name__ == "__main__":
    unittest.main()
