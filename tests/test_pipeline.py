"""Tests for the Slice 8 glue pipeline - one per "Done when" in specs/slice-8/spec.md."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from analystos.l0.store import hash_of
from analystos.pipeline import run_job

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "fixtures" / "golden"


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_run_job_matches_the_golden_answer_key(self):  # Done when #1
        out = run_job(GOLDEN, evidence_dir=self.tmp / "ev")
        expected = (GOLDEN / "expected_section.md").read_text(encoding="utf-8")
        self.assertEqual(out, expected)

    def test_footnotes_carry_the_real_source_hash(self):  # Done when #2 (non-circular)
        out = run_job(GOLDEN, evidence_dir=self.tmp / "ev")
        real_hash = hash_of(GOLDEN / "income_statement.csv")
        self.assertEqual(out.count(real_hash), 3)  # all three footnotes cite it
        self.assertIn("FY2024 revenue was 4200000.0. [1]", out)
        self.assertIn("FY2023 revenue was 3560000.0. [3]", out)
        self.assertIn(f'[1] source {real_hash} - row 4, column "revenue"', out)

    def test_editing_the_source_changes_the_output(self):  # Done when #3
        job = self.tmp / "job"
        shutil.copytree(GOLDEN, job)
        csv = job / "income_statement.csv"
        csv.write_text(csv.read_text().replace("4200000", "9900000"), encoding="utf-8")
        out = run_job(job, evidence_dir=self.tmp / "ev2")
        self.assertIn("FY2024 revenue was 9900000.0.", out)
        self.assertNotEqual(
            out, (GOLDEN / "expected_section.md").read_text(encoding="utf-8")
        )

    def test_module_entrypoint_prints_the_section(self):  # Done when #4
        result = subprocess.run(
            [sys.executable, "-m", "analystos", str(GOLDEN)],
            capture_output=True,
            text=True,
            cwd=REPO,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Revenue and cost review", result.stdout)


if __name__ == "__main__":
    unittest.main()
