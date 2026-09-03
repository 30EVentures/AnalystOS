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

from analystos.l0.store import hash_of
from analystos.pipeline import main, run_job

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
