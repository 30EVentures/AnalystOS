"""Slice 60 - the report seal and its standalone verifier. See
specs/slice-60/spec.md and docs/seal.md."""

import ast
import copy
import hashlib
import io
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from analystos.l2 import analyze
from analystos.l4 import seal, seal_verify
from analystos.l4.seal import build_bundle, generate_key, load_signing_key
from analystos.l4.seal_verify import (
    canonical_bytes, citation_in_text, match_key, normalize, recompute, verify_bundle,
)
from analystos.pipeline import build_report

REPO = Path(__file__).resolve().parents[1]
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
          "executive_summary": [{"text": "Revenue was {{0}}, and income moved {{1}}."}],
          "sections": [{"heading": "H", "paragraphs": [{"text": "See {{0}}."}],
                        "chart": {"series": [{"label": "a", "fact_index": 0}, {"label": "b", "fact_index": 1}]}}]}
SRC = "a" * 64


def trace(**over):
    base = {"tier": "written", "segments": copy.deepcopy(SEGMENTS), "report": copy.deepcopy(REPORT),
            "document_text": TEXT, "source_hash": SRC}
    base.update(over)
    return base


def statuses(outcome):
    return {c["name"]: c["status"] for c in outcome["checks"]}


# --- an independent re-implementation, written from docs/seal.md only -----------------
def _canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _h(b):
    return hashlib.sha256(b).hexdigest()


def independent_root(facts):
    leaves = sorted((f["key"], _h(b"\x00" + (f["key"] + "\0" + _h(_canon(f["record"]))).encode())) for f in facts)
    level = [h for _, h in leaves]
    while len(level) > 1:
        level = [(_h(b"\x01" + bytes.fromhex(level[i]) + bytes.fromhex(level[i + 1])) if i + 1 < len(level) else level[i])
                 for i in range(0, len(level), 2)]
    return level[0]


class ConstructionTest(unittest.TestCase):
    def test_an_independent_implementation_reproduces_the_root(self):
        bundle = build_bundle(trace(), created="2026-09-25T00:00:00Z")
        self.assertEqual(independent_root(bundle["facts"]), bundle["payload"]["root"])

    def test_known_answer_pins_the_format(self):
        bundle = build_bundle(trace(), created="2026-09-25T00:00:00Z")
        self.assertEqual(bundle["payload"]["root"], "73e4fb808ea0e48852a26d08369679ef385ffe405471031c8e18eb3244d2472d")

    def test_odd_and_single_leaf_counts(self):
        for n in (1, 2, 3, 5, 8):
            segs = [{"type": "prose", "text": f"t{i}"} for i in range(n)]
            b = build_bundle(trace(segments=segs, report=None, tier="plain"))
            self.assertEqual(independent_root(b["facts"]), b["payload"]["root"], n)
            self.assertTrue(verify_bundle(b)["ok"])

    def test_the_payload_binds_source_text_report_and_tier(self):
        p = build_bundle(trace())["payload"]
        self.assertEqual(p["source_sha256"], SRC)
        self.assertEqual(p["text_sha256"], hashlib.sha256(TEXT.encode()).hexdigest())
        self.assertEqual(p["tier"], "written")
        self.assertEqual(p["entries"], 3)
        self.assertEqual(p["report_sha256"], _h(_canon(normalize(REPORT))))

    def test_numbers_are_sealed_as_strings(self):
        record = build_bundle(trace())["facts"][0]["record"]
        self.assertEqual(record["value"], "498000000.0")
        self.assertIsInstance(record["value"], str)

    def test_normalize_refuses_what_it_cannot_seal(self):
        for bad in (float("nan"), float("inf"), object()):
            with self.assertRaises(ValueError):
                normalize({"x": bad})
        self.assertEqual(normalize({"a": (1, True, None, 2.5)}), {"a": ["1", True, None, "2.5"]})

    def test_the_same_run_seals_identically(self):
        a = build_bundle(trace(), created="2026-09-25T00:00:00Z", nonce="0123456789abcdef")
        b = build_bundle(trace(), created="2026-09-25T00:00:00Z", nonce="0123456789abcdef")
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_every_seal_gets_a_fresh_nonce_so_ids_never_collide(self):
        a, b = build_bundle(trace()), build_bundle(trace())
        self.assertNotEqual(a["payload"]["nonce"], b["payload"]["nonce"])
        self.assertEqual(a["payload"]["root"], b["payload"]["root"])
        self.assertNotEqual(canonical_bytes(a["payload"]), canonical_bytes(b["payload"]))


class RefusalsTest(unittest.TestCase):
    def test_the_table_path_and_empty_runs_are_not_sealed(self):
        with self.assertRaises(ValueError):
            build_bundle(trace(tier="table"))
        with self.assertRaises(ValueError):
            build_bundle(trace(segments=[]))


class TamperTest(unittest.TestCase):
    def setUp(self):
        self.priv, self.pub = generate_key()
        self.bundle = build_bundle(trace(), signing_key=self.priv)

    def test_the_untouched_bundle_verifies_at_every_level(self):
        out = verify_bundle(self.bundle, public_key=self.pub, source_text=TEXT)
        self.assertEqual((out["ok"], out["authentic"], out["content_checked"]), (True, True, True))

    def test_editing_a_fact_is_caught_by_its_hash(self):
        b = copy.deepcopy(self.bundle)
        b["facts"][0]["record"]["value"] = "999000000.0"
        out = verify_bundle(b)
        self.assertFalse(out["ok"])
        self.assertEqual(statuses(out)["fact_hashes"], "fail")

    def test_editing_a_fact_and_its_hash_is_caught_by_the_root(self):
        b = copy.deepcopy(self.bundle)
        b["facts"][0]["record"]["value"] = "999000000.0"
        b["facts"][0]["hash"] = hashlib.sha256(canonical_bytes(b["facts"][0]["record"])).hexdigest()
        self.assertEqual(statuses(verify_bundle(b))["merkle_root"], "fail")

    def test_dropping_a_fact_is_caught(self):
        b = copy.deepcopy(self.bundle)
        del b["facts"][2]
        self.assertEqual(statuses(verify_bundle(b))["merkle_root"], "fail")

    def test_editing_the_report_is_caught(self):
        b = copy.deepcopy(self.bundle)
        b["report"]["executive_summary"][0]["text"] = "Revenue was {{1}}."
        self.assertEqual(statuses(verify_bundle(b))["report_hash"], "fail")

    def test_a_report_cannot_be_smuggled_into_a_plain_seal(self):
        b = build_bundle(trace(tier="plain", report=None))
        b["report"] = {"title": "x"}
        self.assertEqual(statuses(verify_bundle(b))["report_hash"], "fail")

    def test_changing_the_tier_breaks_the_signature(self):
        b = copy.deepcopy(self.bundle)
        b["payload"]["tier"] = "plain"
        out = verify_bundle(b, public_key=self.pub)
        self.assertEqual(statuses(out)["signature"], "fail")
        self.assertFalse(out["authentic"])

    def test_a_signature_under_the_wrong_pinned_key_fails(self):
        _, other = generate_key()
        out = verify_bundle(self.bundle, public_key=other)
        self.assertEqual(statuses(out)["signature"], "fail")

    def test_a_dangling_reference_in_the_report_is_flagged(self):
        b = build_bundle(trace(report={"executive_summary": [{"text": "See {{9}}."}]}))
        self.assertEqual(statuses(verify_bundle(b))["report_refs"], "fail")

    def test_garbage_is_a_failed_structure_not_a_crash(self):
        for junk in (None, [], {}, {"format": "analystos-seal/1"}, {"format": "x", "payload": {}, "facts": []}):
            with self.subTest(junk=junk):
                self.assertEqual(statuses(verify_bundle(junk))["structure"], "fail")


class TrustLevelsTest(unittest.TestCase):
    def test_unsigned_is_ok_but_never_authentic(self):
        out = verify_bundle(build_bundle(trace()), source_text=TEXT)
        self.assertTrue(out["ok"])
        self.assertFalse(out["authentic"])
        self.assertEqual(statuses(out)["signature"], "skipped")

    def test_signed_without_a_pinned_key_is_not_authentic(self):
        priv, _ = generate_key()
        out = verify_bundle(build_bundle(trace(), signing_key=priv))
        self.assertTrue(out["ok"])
        self.assertFalse(out["authentic"])
        self.assertIn("no pinned key", [c for c in out["checks"] if c["name"] == "signature"][0]["detail"])

    def test_no_text_means_content_is_not_checked(self):
        out = verify_bundle(build_bundle(trace()))
        self.assertFalse(out["content_checked"])
        self.assertEqual(statuses(out)["citations_in_text"], "skipped")


class ContentTest(unittest.TestCase):
    def test_a_different_text_fails_the_hash_but_still_runs_the_checks(self):
        out = verify_bundle(build_bundle(trace()), source_text=TEXT + " Extra.")
        self.assertEqual(statuses(out)["source_text_hash"], "fail")
        self.assertEqual(statuses(out)["citations_in_text"], "pass")

    def test_a_citation_absent_from_the_text_is_caught(self):
        out = verify_bundle(build_bundle(trace()), source_text="Revenue was something else entirely.")
        self.assertEqual(statuses(out)["citations_in_text"], "fail")

    def test_a_bundle_rebuilt_around_a_wrong_calculation_fails_only_content(self):
        segs = copy.deepcopy(SEGMENTS)
        segs[1]["value"] = -20.0
        out = verify_bundle(build_bundle(trace(segments=segs)), source_text=TEXT)
        self.assertEqual(statuses(out)["merkle_root"], "pass")
        self.assertEqual(statuses(out)["calculations"], "fail")
        self.assertFalse(out["content_checked"])

    def test_growth_percent_in_either_operand_order_recomputes(self):
        segs = copy.deepcopy(SEGMENTS)
        segs[1]["operands"] = list(reversed(segs[1]["operands"]))
        segs[1]["value"] = (22400000.0 - 19600000.0) / 19600000.0 * 100
        out = verify_bundle(build_bundle(trace(segments=segs)), source_text=TEXT)
        self.assertEqual(statuses(out)["calculations"], "pass")


class DifferentialAgainstTheAnalyzerTest(unittest.TestCase):
    """The verifier is a second implementation; it must agree with the code
    that accepted the facts in the first place."""

    SAMPLES = ["$1,842.0 Million", "Revenue | 1,842.0 | 1,788.0", "  Net  income— fell ", "−4.7%",
               "12,345,678", "1,23", "Q3 FY2026", "$5.0M", "a,b", "1,000,000 and 2,000"]

    def test_match_key_agrees(self):
        for s in self.SAMPLES:
            with self.subTest(s=s):
                self.assertEqual(match_key(s), analyze._match_key(s))

    def test_citation_matching_agrees(self):
        doc = "Revenue | 1,842.0 | 1,788.0 net income fell to $19.6 million in the quarter"
        folded = analyze._match_key(doc)
        for cite in ("1,842.0", "$1,842.0 million", "1,788.0", "Revenue 1,842.0", "$19.6 million", "19.6", "$20.1 million", "", "  "):
            with self.subTest(cite=cite):
                self.assertEqual(citation_in_text(cite, match_key(doc)), analyze._really_in_document(cite, folded))
        self.assertEqual(match_key(doc), folded)

    def test_recompute_agrees_for_every_operation(self):
        rng = random.Random(7)
        for op in analyze._OPERATIONS:
            for _ in range(50):
                n = 1 if op == "percent_of_total" else (2 if op in ("ratio", "growth_percent") else rng.randint(2, 4))
                vals = [round(rng.uniform(-1e6, 1e6), 2) for _ in range(n)]
                total = round(rng.uniform(1, 1e6), 2) if op == "percent_of_total" else None
                self.assertEqual(recompute(op, vals, total), analyze._recompute(op, vals, total), (op, vals, total))
        for op, vals in (("ratio", [1.0, 0.0]), ("growth_percent", [0.0, 5.0]), ("difference", [1.0]), ("average", [])):
            self.assertEqual(recompute(op, vals), None if op != "average" else None)


class KeyHandlingTest(unittest.TestCase):
    def test_generated_keys_round_trip_into_a_signing_key(self):
        priv, pub = generate_key()
        self.assertEqual(load_signing_key({seal.SEAL_KEY_ENV: priv}), priv)
        self.assertNotEqual(priv, pub)

    def test_no_key_means_no_signing_and_a_bad_key_is_an_error(self):  # there is no built-in default key
        self.assertIsNone(load_signing_key({}))
        self.assertIsNone(load_signing_key({seal.SEAL_KEY_ENV: "  "}))
        with self.assertRaises(ValueError):
            load_signing_key({seal.SEAL_KEY_ENV: "not-a-key"})


class StandaloneTest(unittest.TestCase):
    def test_the_verifier_imports_only_the_standard_library(self):
        tree = ast.parse((REPO / "analystos" / "l4" / "seal_verify.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertLessEqual(imported, set(sys.stdlib_module_names) | {"cryptography"})
        self.assertNotIn("analystos", imported)

    def test_cli_exit_codes_and_flags(self):
        priv, pub = generate_key()
        bundle = build_bundle(trace(), signing_key=priv)
        with tempfile.TemporaryDirectory() as tmp:
            good, bad, text = Path(tmp, "b.json"), Path(tmp, "bad.json"), Path(tmp, "t.txt")
            good.write_text(json.dumps(bundle))
            tampered = copy.deepcopy(bundle)
            tampered["facts"][0]["record"]["value"] = "1.0"
            bad.write_text(json.dumps(tampered))
            text.write_text(TEXT)
            out = io.StringIO()
            self.assertEqual(seal_verify.main([str(good), "--public-key", pub, "--text", str(text)], stdout=out), 0)
            self.assertTrue(json.loads(out.getvalue())["content_checked"])
            self.assertEqual(seal_verify.main([str(bad)], stdout=io.StringIO()), 1)
            self.assertEqual(seal_verify.main([str(Path(tmp, "missing.json"))], stdout=io.StringIO()), 2)
            self.assertEqual(seal_verify.main([], stdout=io.StringIO()), 2)

    def test_it_runs_as_its_own_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "b.json")
            path.write_text(json.dumps(build_bundle(trace())))
            done = subprocess.run([sys.executable, "-m", "analystos.l4.seal_verify", str(path)],
                                  capture_output=True, text=True, cwd=REPO, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(json.loads(done.stdout)["ok"])


class PipelineSealTest(unittest.TestCase):
    """A real (mocked-model) run: trace -> seal -> full verification."""

    def _run(self, narrative_ok):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        job = Path(tmp.name)
        (job / "data.csv").write_text(
            "metric,value\nq3_2025_revenue,402000000\nq4_2025_revenue,410000000\n"
            "q1_2026_revenue,432000000\nq2_2026_revenue,455000000\nq3_2026_revenue,498000000\n", encoding="utf-8")

        def quote(label, text, value):
            return {"type": "quote", "display": "stat", "label": label, "exact_text": text, "has_value": True,
                    "value": value, "sentence": "{value} was reported.", "format": "usd"}

        raw = [quote("Q3 2025 Revenue", "402000000", 402e6), quote("Q4 2025 Revenue", "410000000", 410e6),
               quote("Q1 2026 Revenue", "432000000", 432e6), quote("Q2 2026 Revenue", "455000000", 455e6),
               quote("Q3 2026 Revenue", "498000000", 498e6),
               {"type": "quote", "display": "stat", "label": "Made up", "exact_text": "999999999",
                "has_value": True, "value": 999999999.0, "sentence": "{value}.", "format": "usd"}]
        report_resp = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"segments": raw})])
        bad_narrative = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"segments": []})])

        def create(**kwargs):
            return bad_narrative if kwargs["tool_choice"]["name"] == "write_narrative" else report_resp

        client = SimpleNamespace(messages=SimpleNamespace(create=create))
        t = {}
        build_report(job / "data.csv", title="Seal test", evidence_dir=job / "ev", llm_client=client, trace=t)
        return t

    def test_the_trace_records_the_tier_and_the_verification_counts(self):
        t = self._run(False)
        self.assertEqual(t["tier"], "deterministic")
        self.assertEqual(t["analysis"], {"proposed": 6, "verified": 5, "dropped": 1})
        self.assertTrue(t["fallback_reason"])
        self.assertEqual(len(t["segments"]), 5)
        self.assertRegex(t["source_hash"], r"^[0-9a-f]{64}$")

    def test_the_run_seals_and_fully_verifies(self):
        t = self._run(False)
        priv, pub = generate_key()
        bundle = build_bundle(t, signing_key=priv)
        out = verify_bundle(bundle, public_key=pub, source_text=t["document_text"])
        self.assertEqual((out["ok"], out["authentic"], out["content_checked"]), (True, True, True), out)
        self.assertEqual(bundle["payload"]["tier"], "deterministic")
        self.assertEqual(bundle["payload"]["source_sha256"], t["source_hash"])

    def test_the_dropped_fact_is_not_in_the_seal(self):
        t = self._run(False)
        sealed = json.dumps(build_bundle(t))
        self.assertNotIn("999999999", sealed)


class WrittenTierSealTest(unittest.TestCase):
    def test_a_successful_narrative_run_seals_at_the_written_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            (job / "data.csv").write_text("period,revenue\nFY2024,18400000\n", encoding="utf-8")
            report_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"segments": [{
                "type": "quote", "display": "inline", "label": "Revenue", "exact_text": "18400000",
                "has_value": True, "value": 18400000.0, "sentence": "Revenue was {value}.", "format": "usd"}]})])
            narrative = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
                "executive_summary": [{"text": "The headline figure this quarter was {{0}}."}],
                "sections": [{"heading": "Revenue", "paragraphs": [{"text": "That figure, {{0}}, set the tone."}],
                              "has_chart": False, "chart": {"type": "bar", "title": "", "format": "number", "series": []}}],
                "outlook": []})])
            proof = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"passed": True, "issues": []})])

            def create(**kwargs):
                return {"write_narrative": narrative, "report_issues": proof}.get(kwargs["tool_choice"]["name"], report_response)

            t = {}
            build_report(job / "data.csv", title="X", evidence_dir=job / "ev",
                         llm_client=SimpleNamespace(messages=SimpleNamespace(create=create)), trace=t)
            self.assertEqual(t["tier"], "written")
            self.assertIsNone(t["fallback_reason"])
            self.assertEqual(t["analysis"], {"proposed": 1, "verified": 1, "dropped": 0})
            bundle = build_bundle(t)
            out = verify_bundle(bundle, source_text=t["document_text"])
            self.assertTrue(out["ok"] and out["content_checked"], out)
            self.assertIn("headline figure", json.dumps(bundle["report"]))


class CliWritesTheSealTest(unittest.TestCase):
    def test_main_writes_section_seal_json_for_a_narrated_run(self):
        from analystos import pipeline

        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            (job / "job.json").write_text(json.dumps({"source": "doc.csv"}))
            (job / "doc.csv").write_text("a,b\n1,2\n")

            def fake_run_job(job_dir, evidence_dir=None, want_pdf=False, trace=None):
                trace.update(tier="written", segments=copy.deepcopy(SEGMENTS), report=copy.deepcopy(REPORT),
                             document_text=TEXT, source_hash=SRC)
                return "<!doctype html><html></html>", b"%PDF"

            saved = pipeline.run_job
            pipeline.run_job = fake_run_job
            try:
                os.environ.pop(seal.SEAL_KEY_ENV, None)
                self.assertEqual(pipeline.main([str(job)]), 0)
            finally:
                pipeline.run_job = saved
            bundle = json.loads((job / "section.seal.json").read_text())
            self.assertTrue(verify_bundle(bundle, source_text=TEXT)["ok"])
            self.assertIsNone(bundle["signature"])


if __name__ == "__main__":
    unittest.main()
