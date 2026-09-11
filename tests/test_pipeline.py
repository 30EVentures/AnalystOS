"""Tests for the glue pipeline.

One per "Done when" in specs/slice-8/spec.md (run_job) and
specs/slice-10/spec.md (main writes section.md).
"""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pdfplumber
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from analystos.l0.store import hash_of
from analystos.pipeline import build_report, main, run_job

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "fixtures" / "golden"


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _golden_copy(self):
        dest = self.tmp / "job"
        shutil.copytree(GOLDEN, dest)
        return dest

    # --- run_job (slice 8) ---

    def test_run_job_matches_the_golden_answer_key(self):  # Done when #1
        out = run_job(GOLDEN, evidence_dir=self.tmp / "ev")
        expected = (GOLDEN / "expected_section.md").read_text(encoding="utf-8")
        self.assertEqual(out, expected)

    def test_footnotes_carry_the_real_source_hash(self):  # Done when #2 (non-circular)
        out = run_job(GOLDEN, evidence_dir=self.tmp / "ev")
        real_hash = hash_of(GOLDEN / "income_statement.csv")
        self.assertEqual(out.count(real_hash), 3)
        self.assertIn("FY2024 revenue was 4200000.0. [1]", out)
        self.assertIn("FY2023 revenue was 3560000.0. [3]", out)
        self.assertIn(f'[1] source {real_hash} - row 4, column "revenue"', out)

    def test_editing_the_source_changes_the_output(self):  # Done when #3
        job = self._golden_copy()
        csv = job / "income_statement.csv"
        csv.write_text(csv.read_text().replace("4200000", "9900000"), encoding="utf-8")
        out = run_job(job, evidence_dir=self.tmp / "ev2")
        self.assertIn("FY2024 revenue was 9900000.0.", out)
        self.assertNotEqual(
            out, (GOLDEN / "expected_section.md").read_text(encoding="utf-8")
        )

    # --- main writes section.md (slice 10) ---

    def test_entrypoint_prints_and_writes_the_section(self):  # slice 8 #4 + slice 10 #1, #4
        job = self._golden_copy()
        result = subprocess.run(
            [sys.executable, "-m", "analystos", str(job)],
            capture_output=True,
            text=True,
            cwd=REPO,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Revenue and cost review", result.stdout)
        written = (job / "section.md").read_text(encoding="utf-8")
        self.assertEqual(written, run_job(GOLDEN, evidence_dir=self.tmp / "ev"))

    def test_rerun_overwrites_section_md(self):  # slice 10 #2
        job = self._golden_copy()
        (job / "section.md").write_text("stale", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main([str(job)])
        self.assertEqual(code, 0)
        text = (job / "section.md").read_text(encoding="utf-8")
        self.assertNotEqual(text, "stale")
        self.assertIn("# Revenue and cost review", text)

    def test_run_job_alone_writes_no_file(self):  # slice 10 #3
        job = self._golden_copy()
        run_job(job, evidence_dir=self.tmp / "ev")
        self.assertFalse((job / "section.md").exists())

    def test_entrypoint_also_writes_section_html(self):  # slice 13 #1
        job = self._golden_copy()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main([str(job)])
        self.assertEqual(code, 0)
        page = (job / "section.html").read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", page)
        self.assertIn("<h1>", page)

    def test_entrypoint_also_writes_a_real_section_pdf(self):  # slice 24 #4
        job = self._golden_copy()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main([str(job)])
        self.assertEqual(code, 0)
        pdf_bytes = (job / "section.pdf").read_bytes()
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        self.assertIn("Revenue and cost review", text)

    # --- ask dispatch: growth / ratio (slice 12) ---

    # --- source format dispatch by extension + templates + currency_unit (slice 19) ---

    def test_run_job_reads_an_xlsx_source(self):
        job = self.tmp / "xlsx-job"
        job.mkdir()
        wb = Workbook()
        ws = wb.active
        ws.append(["period", "revenue"])
        ws.append(["FY2024", 4200000])
        wb.save(job / "data.xlsx")
        (job / "job.json").write_text(
            json.dumps(
                {
                    "title": "From Excel",
                    "source": "data.xlsx",
                    "schema": {"period": "text", "revenue": "number"},
                    "asks": [
                        {"text": "Revenue was {answer}.", "format": "usd",
                         "where": ["period", "FY2024"], "select": "revenue"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        out = run_job(job, evidence_dir=self.tmp / "ev")
        self.assertIn("Revenue was $4.2M.", out)

    # --- .pdf source + confirm-before-cite gate (slice 23) ---

    def _make_pdf(self, path, rows):
        data = [[str(v) for v in row] for row in rows]
        t = Table(data)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
        SimpleDocTemplate(str(path), pagesize=letter).build([t])

    def test_pdf_source_without_confirmation_raises(self):
        job = self.tmp / "pdf-job"
        job.mkdir()
        self._make_pdf(job / "data.pdf", [["period", "revenue"], ["FY2024", "4200000"]])
        with self.assertRaises(ValueError) as cm:
            build_report(
                job / "data.pdf", {"period": "text", "revenue": "number"}, "From PDF",
                asks=[{"text": "Revenue was {answer}.", "format": "usd",
                       "where": ["period", "FY2024"], "select": "revenue"}],
                evidence_dir=self.tmp / "ev",
            )
        message = str(cm.exception)
        self.assertIn("pdf_confirmed", message)
        self.assertIn("FY2024", message)  # the actual extracted value is shown, not hidden
        self.assertIn("4200000", message)

    def test_pdf_source_with_confirmation_proceeds(self):
        job = self.tmp / "pdf-job-confirmed"
        job.mkdir()
        pdf_path = job / "data.pdf"
        self._make_pdf(pdf_path, [["period", "revenue"], ["FY2024", "4200000"]])
        out = build_report(
            pdf_path, {"period": "text", "revenue": "number"}, "From PDF",
            asks=[{"text": "Revenue was {answer}.", "format": "usd",
                   "where": ["period", "FY2024"], "select": "revenue"}],
            evidence_dir=self.tmp / "ev",
            extract_options={"pdf_confirmed": True},
        )
        self.assertIn("Revenue was $4.2M.", out)
        self.assertIn(hash_of(pdf_path), out)  # cites the real PDF, same as any other format

    def test_run_job_reads_a_confirmed_pdf_source(self):
        job = self.tmp / "pdf-run-job"
        job.mkdir()
        self._make_pdf(job / "data.pdf", [["period", "revenue"], ["FY2024", "4200000"]])
        (job / "job.json").write_text(
            json.dumps(
                {
                    "title": "From PDF",
                    "source": "data.pdf",
                    "schema": {"period": "text", "revenue": "number"},
                    "pdf_confirmed": True,
                    "asks": [
                        {"text": "Revenue was {answer}.", "format": "usd",
                         "where": ["period", "FY2024"], "select": "revenue"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        out = run_job(job, evidence_dir=self.tmp / "ev")
        self.assertIn("Revenue was $4.2M.", out)

    # --- schema auto-detection + no-title default (slice 25) ---

    def test_build_report_with_no_schema_auto_detects(self):
        job = self.tmp / "no-schema-job"
        job.mkdir()
        (job / "data.csv").write_text(
            "period,revenue\nFY2023,1000000\nFY2024,1250000\n", encoding="utf-8"
        )
        out = build_report(
            job / "data.csv",
            title="Auto-detected",
            asks=[{"text": "Revenue was {answer}.", "format": "usd",
                   "where": ["period", "FY2024"], "select": "revenue"}],
            evidence_dir=self.tmp / "ev",
        )
        self.assertIn("Revenue was $1.2M.", out)  # "revenue" guessed as a number

    def test_run_job_with_no_schema_or_title_in_job_json(self):
        job = self.tmp / "bare-job"
        job.mkdir()
        (job / "data.csv").write_text(
            "period,revenue\nFY2023,1000000\nFY2024,1250000\n", encoding="utf-8"
        )
        (job / "job.json").write_text(
            json.dumps({"source": "data.csv", "template": "income_statement"}),
            encoding="utf-8",
        )
        out = run_job(job, evidence_dir=self.tmp / "ev")
        self.assertIn("# Review of data.csv", out)  # default title
        self.assertIn("Revenue grew 25.0% from FY2023 to FY2024.", out)

    def test_run_job_uses_a_template_when_no_asks_are_given(self):
        job = self.tmp / "template-job"
        job.mkdir()
        (job / "data.csv").write_text(
            "period,revenue,net_income\nFY2023,26974,4368\nFY2024,60922,29760\n",
            encoding="utf-8",
        )
        (job / "job.json").write_text(
            json.dumps(
                {
                    "title": "Auto-generated",
                    "source": "data.csv",
                    "schema": {"period": "text", "revenue": "number", "net_income": "number"},
                    "template": "income_statement",
                    "currency_unit": "actual",
                }
            ),
            encoding="utf-8",
        )
        out = run_job(job, evidence_dir=self.tmp / "ev")
        self.assertIn("FY2024 revenue was $60.9K.", out)
        self.assertIn("Revenue grew 125.9% from FY2023 to FY2024.", out)

    def test_neither_asks_nor_template_runs_the_narrated_default(self):  # slice 26
        job = self.tmp / "bare-narrated-job"
        job.mkdir()
        (job / "data.csv").write_text("period,revenue\nFY2024,100\n", encoding="utf-8")

        # A qualitative quote (no "value" key at all) just needs a real exact_text.
        tool_use = SimpleNamespace(type="tool_use", input={"segments": [{
            "type": "quote", "display": "inline", "label": "Revenue", "exact_text": "revenue",
        }]})
        response = SimpleNamespace(content=[tool_use])
        fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response))

        out = build_report(
            job / "data.csv", title="X", evidence_dir=self.tmp / "ev", llm_client=fake_client,
        )
        self.assertIn("# X", out)
        self.assertIn("revenue", out)

    def test_narrated_default_always_uses_actual_currency_scale(self):  # slice 26 follow-up
        # The narrated path's quoted values are always literal, already-real
        # numbers copied verbatim from the source text - never data
        # pre-scaled by a "figures in thousands" header convention, unlike
        # the old template path. A currency_unit other than "actual" must
        # never apply here, no matter what the caller passes in.
        job = self.tmp / "narrated-currency-job"
        job.mkdir()
        (job / "data.csv").write_text("period,revenue\nFY2024,18400000\n", encoding="utf-8")

        tool_use = SimpleNamespace(type="tool_use", input={"segments": [{
            "type": "quote", "display": "inline", "label": "Revenue",
            "exact_text": "18400000", "has_value": True, "value": 18400000.0,
            "sentence": "Revenue was {value}.", "format": "usd",
        }]})
        response = SimpleNamespace(content=[tool_use])
        fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response))

        out = build_report(
            job / "data.csv", title="X", evidence_dir=self.tmp / "ev",
            llm_client=fake_client, currency_unit="thousands",
        )
        self.assertIn("Revenue was $18.4M.", out)

    def test_the_narrative_pass_actually_runs_when_it_succeeds(self):  # slice 27 + 30
        # test_neither_asks_nor_template_runs_the_narrated_default and
        # test_narrated_default_always_uses_actual_currency_scale both use a
        # client that always returns the write_report response, so
        # write_narrative gets a "segments" reply instead of the structured
        # report and correctly falls back - proving the fallback works, not
        # that the narrative pass itself ever runs. This client tells the
        # two calls apart by which tool was requested, so both stages fire,
        # and the output is the rich HTML document (Slice 30), not the
        # flat per-segment fallback.
        job = self.tmp / "narrative-success-job"
        job.mkdir()
        (job / "data.csv").write_text("period,revenue\nFY2024,18400000\n", encoding="utf-8")

        report_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "segments": [{
                "type": "quote", "display": "inline", "label": "Revenue",
                "exact_text": "18400000", "has_value": True, "value": 18400000.0,
                "sentence": "Revenue was {value}.", "format": "usd",
            }],
        })])
        narrative_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "executive_summary": [{"text": "The headline figure this quarter was {{0}}."}],
            "sections": [{
                "heading": "Revenue",
                "paragraphs": [{"text": "That figure, {{0}}, set the tone for the quarter."}],
                "has_chart": False,
                "chart": {"type": "bar", "title": "", "format": "number", "series": []},
            }],
            "outlook": [],
        })])
        proofread_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "passed": True, "issues": [],
        })])

        def _create(**kwargs):
            name = kwargs["tool_choice"]["name"]
            if name == "write_narrative":
                return narrative_response
            if name == "report_issues":
                return proofread_response
            return report_response

        fake_client = SimpleNamespace(messages=SimpleNamespace(create=_create))

        out = build_report(
            job / "data.csv", title="X", evidence_dir=self.tmp / "ev", llm_client=fake_client,
        )
        self.assertTrue(out.lstrip().lower().startswith("<!doctype html"))  # rich path
        self.assertIn("<h2>Revenue</h2>", out)
        self.assertIn("The headline figure this quarter was $18.4M", out)
        # the plain per-segment sentence - proof this is the narrative
        # pass's own wording, not a silent fallback to Slice 26's rendering
        self.assertNotIn("Revenue was $18.4M", out)

    def test_a_gate2_failure_is_repaired_not_immediately_fallen_back(self):  # slice 40
        # Found live 2026-09-11: a report can pass Gate 1 (every number
        # correctly cited) and still fail Gate 2 on pure wording - before
        # this, that meant an instant fallback to the flat renderer with
        # no attempt to fix the actual flagged sentence.
        job = self.tmp / "gate2-repair-job"
        job.mkdir()
        (job / "data.csv").write_text("period,revenue\nFY2024,18400000\n", encoding="utf-8")

        report_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "segments": [{
                "type": "quote", "display": "inline", "label": "Revenue",
                "exact_text": "18400000", "has_value": True, "value": 18400000.0,
                "sentence": "Revenue was {value}.", "format": "usd",
            }],
        })])
        narrative_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "executive_summary": [{"text": "The headline figure this quarter was {{0}}."}],
            "sections": [{
                "heading": "Revenue",
                "paragraphs": [{"text": "That figure {{0}}, that figure, set the tone."}],
                "has_chart": False,
                "chart": {"type": "bar", "title": "", "format": "number", "series": []},
            }],
            "outlook": [],
        })])
        failed_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "passed": False,
            "issues": [{"location": "That figure {{0}}, that figure, set the tone.",
                        "problem": "repeats 'that figure' awkwardly"}],
        })])
        passed_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "passed": True, "issues": [],
        })])
        fixed_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "text": "That figure, {{0}}, set the tone for the quarter.",
        })])
        proofread_calls = {"n": 0}

        def _create(**kwargs):
            name = kwargs["tool_choice"]["name"]
            if name == "write_narrative":
                return narrative_response
            if name == "report_issues":
                proofread_calls["n"] += 1
                return failed_response if proofread_calls["n"] == 1 else passed_response
            if name == "fixed_paragraph":
                return fixed_response
            return report_response

        fake_client = SimpleNamespace(messages=SimpleNamespace(create=_create))

        out = build_report(
            job / "data.csv", title="X", evidence_dir=self.tmp / "ev", llm_client=fake_client,
        )
        self.assertTrue(out.lstrip().lower().startswith("<!doctype html"))  # rich path, not fallback
        self.assertIn("That figure, $18.4M", out)  # the repaired wording landed
        self.assertIn("set the tone for the quarter.", out)
        self.assertNotIn("that figure, set the tone", out.lower())  # the awkward repeat is gone
        self.assertEqual(proofread_calls["n"], 2)  # failed once, repaired, passed on recheck

    def test_an_event_flows_through_to_the_rendered_report(self):  # slice 32
        job = self.tmp / "event-job"
        job.mkdir()
        sentence = (
            "Acme completed its acquisition of Halyard on May 14 2026; "
            "integration is underway; the deal is expected to be accretive in 2027"
        )
        (job / "memo.csv").write_text(f"note\n{sentence}\n", encoding="utf-8")

        report_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "segments": [{
                "type": "event", "horizon": "reported",
                "event": {
                    "what": "completed its acquisition of Halyard",
                    "date": "May 14 2026",
                    "status": "integration is underway",
                    "next_step": "expected to be accretive in 2027",
                },
            }],
        })])
        narrative_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "executive_summary": [{"text": "The quarter's headline was the deal: Acme {{0}}."}],
            "sections": [{
                "heading": "The deal",
                "paragraphs": [{"text": "For context, Acme {{0}}."}],
                "has_chart": False,
                "chart": {"type": "bar", "title": "", "format": "number", "series": []},
            }],
            "outlook": [],
        })])
        proofread_response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={
            "passed": True, "issues": [],
        })])

        def _create(**kwargs):
            name = kwargs["tool_choice"]["name"]
            if name == "write_narrative":
                return narrative_response
            if name == "report_issues":
                return proofread_response
            return report_response

        fake_client = SimpleNamespace(messages=SimpleNamespace(create=_create))
        out = build_report(
            job / "memo.csv", title="Acme deal", evidence_dir=self.tmp / "ev",
            llm_client=fake_client,
        )
        # Slice 38: an event's {{N}} substitutes its short name inline, not
        # the full composed timeline - that was leaking into prose verbatim
        self.assertIn("Acme completed its acquisition of Halyard", out)
        self.assertNotIn("(May 14 2026) — integration is underway", out)

    def test_both_asks_and_template_still_raises(self):  # unchanged guard
        job = self.tmp / "both-still-bad-job"
        job.mkdir()
        (job / "data.csv").write_text("period,revenue\nFY2024,100\n", encoding="utf-8")
        with self.assertRaises(ValueError) as cm:
            build_report(
                job / "data.csv", {"period": "text", "revenue": "number"}, "X",
                asks=[], template="income_statement", evidence_dir=self.tmp / "ev",
            )
        self.assertIn("exactly one", str(cm.exception))

    def test_build_report_with_an_empty_asks_list_is_valid_not_missing(self):
        # asks=[] means "given, just empty" - must not be treated the same
        # as "no asks given" (bool([]) is False, which is the trap here)
        job = self.tmp / "empty-asks-job"
        job.mkdir()
        (job / "data.csv").write_text("period,revenue\nFY2024,100\n", encoding="utf-8")
        out = build_report(
            job / "data.csv", {"period": "text", "revenue": "number"}, "X",
            asks=[], evidence_dir=self.tmp / "ev",
        )
        self.assertIn("# X", out)  # ran fine, just produced an empty body

    def test_build_report_with_both_asks_and_template_raises(self):
        job = self.tmp / "both-job"
        job.mkdir()
        (job / "data.csv").write_text("period,revenue\nFY2024,100\n", encoding="utf-8")
        with self.assertRaises(ValueError) as cm:
            build_report(
                job / "data.csv", {"period": "text", "revenue": "number"}, "X",
                asks=[], template="income_statement", evidence_dir=self.tmp / "ev",
            )
        self.assertIn("exactly one", str(cm.exception))

    def test_unsupported_source_extension_raises(self):
        job = self.tmp / "bad-ext-job"
        job.mkdir()
        (job / "data.txt").write_text("not a real source format", encoding="utf-8")
        (job / "job.json").write_text(
            json.dumps(
                {
                    "title": "X",
                    "source": "data.txt",
                    "schema": {"period": "text"},
                    "asks": [],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError) as cm:
            run_job(job, evidence_dir=self.tmp / "ev")
        self.assertIn(".txt", str(cm.exception))

    def test_run_job_dispatches_growth_and_ratio_asks(self):  # slice 12 #5
        job = self.tmp / "job"
        job.mkdir()
        (job / "fin.csv").write_text(
            "period,revenue,cogs\nFY2023,26974,11618\nFY2024,60922,16621\n",
            encoding="utf-8",
        )
        (job / "job.json").write_text(
            json.dumps(
                {
                    "title": "Computed",
                    "source": "fin.csv",
                    "schema": {"period": "text", "revenue": "number", "cogs": "number"},
                    "asks": [
                        {
                            "kind": "growth",
                            "text": "Revenue grew {answer}% YoY.",
                            "key_column": "period",
                            "from": "FY2023",
                            "to": "FY2024",
                            "value_column": "revenue",
                        },
                        {
                            "kind": "ratio",
                            "text": "FY2024 cost ratio was {answer}%.",
                            "key_column": "period",
                            "key": "FY2024",
                            "numerator": "cogs",
                            "denominator": "revenue",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        out = run_job(job, evidence_dir=self.tmp / "ev")
        self.assertIn("Revenue grew 125.9% YoY. [1]", out)  # (60922-26974)/26974*100
        self.assertIn("FY2024 cost ratio was 27.3%. [2]", out)  # 16621/60922*100
        self.assertIn("[1] computed from: ", out)


if __name__ == "__main__":
    unittest.main()
