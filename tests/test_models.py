"""Slice 70 - the model is one setting, used by every call site and recorded.
See specs/slice-70/spec.md."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from analystos.models import DEFAULT_MODEL, MODEL_ENV, model_name
from analystos.pipeline import build_report

ROOT = Path(__file__).resolve().parents[1]


class ModelNameTest(unittest.TestCase):
    def test_default_and_override(self):
        self.assertEqual(DEFAULT_MODEL, "claude-sonnet-5")
        self.assertEqual(model_name({}), "claude-sonnet-5")
        self.assertEqual(model_name({MODEL_ENV: "  "}), "claude-sonnet-5")
        self.assertEqual(model_name({MODEL_ENV: "claude-haiku-4-5-20251001"}), "claude-haiku-4-5-20251001")
        self.assertEqual(model_name({MODEL_ENV: "claude-opus-5-5"}), "claude-opus-5-5")

    def test_it_is_read_at_call_time(self):
        with patch.dict(os.environ, {MODEL_ENV: "model-a"}):
            self.assertEqual(model_name(), "model-a")
        with patch.dict(os.environ, {MODEL_ENV: "model-b"}):
            self.assertEqual(model_name(), "model-b")

    def test_a_value_that_is_not_a_model_id_is_refused(self):
        for bad in ("has space", "semi;colon", "../x", "x" * 81, "-leading", "quo\"te"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    model_name({MODEL_ENV: bad})

    def test_no_model_name_is_hard_coded_at_a_call_site(self):
        for path in ("analystos/l2/analyze.py", "analystos/l2/narrate.py", "analystos/l2/proofread.py", "analystos/l1/image_facts.py"):
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertNotIn('"claude-', text)
                self.assertNotIn("_MODEL", text)
                self.assertIn("model=model_name()", text)


def recording_client(seen):
    """A fake Anthropic client that records every requested model."""
    def quote(label, text, value):
        return {"type": "quote", "display": "stat", "label": label, "exact_text": text, "has_value": True,
                "value": value, "sentence": "{value} was reported.", "format": "usd"}
    facts = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"segments": [quote("Revenue", "4200000", 4.2e6)]})])
    narrative = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
        "executive_summary": [{"text": "The headline figure this quarter was {{0}}."}],
        "sections": [{"heading": "Revenue", "paragraphs": [{"text": "That figure, {{0}}, set the tone."}],
                      "has_chart": False, "chart": {"type": "bar", "title": "", "format": "number", "series": []}}],
        "outlook": []})])
    proof = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"passed": True, "issues": []})])

    def create(**kwargs):
        seen.append((kwargs["tool_choice"]["name"], kwargs["model"]))
        return {"write_narrative": narrative, "report_issues": proof}.get(kwargs["tool_choice"]["name"], facts)
    return SimpleNamespace(messages=SimpleNamespace(create=create))


class EveryCallSiteUsesItTest(unittest.TestCase):
    def run_pipeline(self):
        seen, trace = [], {}
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            path = Path(tmp) / "data.csv"
            path.write_text("period,revenue\nFY2024,4200000\n")
            build_report(path, title="T", evidence_dir=Path(tmp) / "ev", llm_client=recording_client(seen), trace=trace)
        return seen, trace

    def test_unset_every_stage_requests_the_default(self):
        with patch.dict(os.environ, {MODEL_ENV: ""}):
            seen, trace = self.run_pipeline()
        self.assertEqual({name for name, _ in seen}, {"write_report", "write_narrative", "report_issues"})
        self.assertEqual({model for _, model in seen}, {"claude-sonnet-5"})
        self.assertEqual(trace["model"], "claude-sonnet-5")

    def test_set_every_stage_requests_the_override(self):
        with patch.dict(os.environ, {MODEL_ENV: "claude-opus-5-5"}):
            seen, trace = self.run_pipeline()
        self.assertEqual({name for name, _ in seen}, {"write_report", "write_narrative", "report_issues"})
        self.assertEqual({model for _, model in seen}, {"claude-opus-5-5"})
        self.assertEqual(trace["model"], "claude-opus-5-5")

    def test_the_image_transcription_call_site_uses_it_too(self):
        from analystos.l1 import image_facts
        seen = []
        client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: seen.append(kw["model"]) or SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", input={"transcript": "x", "has_data": False})])))
        with patch.dict(os.environ, {MODEL_ENV: "claude-opus-5-5"}), contextlib.suppress(Exception):
            image_facts._transcribe(client, b"\x89PNG")
        self.assertEqual(seen, ["claude-opus-5-5"])

    def test_a_bad_setting_fails_the_run_with_a_clear_message(self):
        with patch.dict(os.environ, {MODEL_ENV: "not a model"}):
            with self.assertRaises(ValueError) as cm:
                self.run_pipeline()
        self.assertIn(MODEL_ENV, str(cm.exception))


class RecordedTest(unittest.TestCase):
    def test_the_api_audit_event_records_the_model(self):
        from tests.test_api_v1 import ApiTestCase

        class Inner(ApiTestCase):
            def runTest(self):  # pragma: no cover
                pass

        case = Inner()
        case.setUp()
        try:
            with patch.dict(os.environ, {MODEL_ENV: "claude-opus-5-5"}):
                case.created()
            events = [e for e in case.store.read_audit() if e["type"] == "analysis"]
            self.assertEqual(events[-1]["model"], "claude-opus-5-5")
        finally:
            case.doCleanups()

    def test_the_table_path_records_no_model(self):
        trace = {}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.csv"
            path.write_text("period,revenue\nFY2023,26974\nFY2024,60922\n")
            build_report(path, None, "T", template="income_statement", evidence_dir=Path(tmp) / "ev", trace=trace)
        self.assertIsNone(trace["model"])


class UnpricedModelTest(unittest.TestCase):
    def test_the_live_suite_refuses_a_model_it_has_no_price_for(self):
        from live_tests.run_live_tests import _price
        with self.assertRaises(ValueError):
            _price("claude-opus-5-5", 1000, 1000)


if __name__ == "__main__":
    unittest.main()
