"""Tests for the Slice 9 scaffolder - one per "Done when" in specs/slice-9/spec.md."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from analystos.scaffold import main, scaffold


class ScaffoldTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.csv = self.tmp / "data.csv"
        self.csv.write_text(
            "period,revenue,headcount\nQ1,120000,8\nQ2,145000,9\n", encoding="utf-8"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _job(self, dest):
        return json.loads((dest / "job.json").read_text(encoding="utf-8"))

    def test_creates_folder_with_csv_copy_and_job_json(self):  # Done when #1
        dest = self.tmp / "job"
        scaffold(self.csv, dest)
        self.assertTrue((dest / "data.csv").is_file())
        self.assertTrue((dest / "job.json").is_file())

    def test_schema_guesses_number_and_text(self):  # Done when #2
        dest = self.tmp / "job"
        scaffold(self.csv, dest)
        self.assertEqual(
            self._job(dest)["schema"],
            {"period": "text", "revenue": "number", "headcount": "number"},
        )

    def test_generated_job_runs_through_the_pipeline(self):  # Done when #3
        from analystos.pipeline import run_job

        dest = self.tmp / "job"
        scaffold(self.csv, dest)
        out = run_job(dest, evidence_dir=self.tmp / "ev")
        self.assertIn("[1]", out)  # at least one footnoted finding

    def test_refuses_to_overwrite_an_existing_folder(self):  # Done when #4
        dest = self.tmp / "job"
        scaffold(self.csv, dest)
        with self.assertRaises(FileExistsError):
            scaffold(self.csv, dest)

    def test_cli_main_reports_the_next_command(self):  # Done when #5
        dest = self.tmp / "job"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main([str(self.csv), str(dest)])
        self.assertEqual(code, 0)
        self.assertIn("python3 -m analystos", buf.getvalue())
        self.assertTrue((dest / "job.json").is_file())

    def test_missing_csv_raises(self):  # guard rail
        with self.assertRaises(FileNotFoundError):
            scaffold(self.tmp / "nope.csv", self.tmp / "x")


if __name__ == "__main__":
    unittest.main()
