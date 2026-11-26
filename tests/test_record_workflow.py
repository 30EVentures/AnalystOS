"""Slice 134 - the workflow that refreshes the public record after each merge."""

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "record.yml").read_text(encoding="utf-8")
SUBJECT = "shipped/1: refresh the log"


class RecordWorkflowTest(unittest.TestCase):
    def test_runs_after_every_merge_to_main_with_full_history(self):
        self.assertIn("branches: [main]", WORKFLOW)
        self.assertIn("fetch-depth: 0", WORKFLOW)
        self.assertIn("contents: write", WORKFLOW)

    def test_emits_append_only_then_verifies_before_committing(self):
        order = ["node tools/emit_record.mjs", "vendor-checkpoint.mjs emit",
                 "vendor-shiplog.mjs verify", "vendor-checkpoint.mjs verify",
                 "redact_served_devlog.py --check", "git commit"]
        positions = [WORKFLOW.index(step) for step in order]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("--rederive", WORKFLOW)

    def test_commits_only_the_record_and_deploys(self):
        self.assertIn(f'git commit -m "{SUBJECT}"', WORKFLOW)
        self.assertNotRegex(WORKFLOW, r"\[(skip ci|vercel skip|ci skip)\]")
        add = next(line for line in WORKFLOW.splitlines() if "git add" in line)
        self.assertEqual(sorted(add.split()[2:]), sorted([
            "site/.well-known/shiplog.json", "site/.well-known/devlog.fragment.json",
            "site/.well-known/checkpoint.json", "DEVLOG.md"]))

    def test_only_main_can_run_it(self):
        self.assertIn("if: github.ref == 'refs/heads/main'", WORKFLOW)

    def test_an_unchanged_record_is_neither_rebuilt_nor_committed(self):
        # The checkpoint head carries its build time, so rebuilding it over an
        # unchanged record would commit and deploy for nothing (review, Slice 134).
        for step in ("Rebuild the checkpoint head", "Commit the refreshed record"):
            block = WORKFLOW[WORKFLOW.index(step):]
            self.assertIn("if: steps.emit.outputs.changed == 'true'", block.split("run:")[0], step)

    def test_stands_down_only_when_main_moved_on(self):
        self.assertIn('"$(git rev-parse origin/main)" != "$GITHUB_SHA"', WORKFLOW)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_refresh_commit_never_enters_the_record(self):
        script = ("import { isOwnBookkeeping } from './vendor-shiplog.mjs'\n"
                  f"console.log(isOwnBookkeeping('{SUBJECT}'))")
        done = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT,
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.stdout.strip(), "true", done.stderr)


if __name__ == "__main__":
    unittest.main()
