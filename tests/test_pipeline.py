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

    def test_run_job_with_neither_asks_nor_template_raises(self):
        job = self.tmp / "bad-job"
        job.mkdir()
        (job / "data.csv").write_text("period,revenue\nFY2024,100\n", encoding="utf-8")
        (job / "job.json").write_text(
            json.dumps(
                {
                    "title": "X",
                    "source": "data.csv",
                    "schema": {"period": "text", "revenue": "number"},
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError) as cm:
            run_job(job, evidence_dir=self.tmp / "ev")
        self.assertIn("asks", str(cm.exception))

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
