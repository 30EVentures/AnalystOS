"""AnalystOS's public record: shipped/1, devlog/1 and checkpoint/1.

Slice 99 adopted the published @flashyos/shiplog@0.2.0; Slice 106 made the
record public. Slice 131 corrected it once, before Flashy registers it:

- privacy happens before sealing (tools/emit_record.mjs), so every served seal
  recomputes - Slice 106 redacted after sealing and broke one;
- the author is a real id, `person/30e-founder`, never a placeholder;
- each format is served at its own path, so Flashy's fan-in folds what the URL
  says it is;
- the full, unredacted record is no longer committed to this public repository.
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WELL_KNOWN = ROOT / "site" / ".well-known"
CONFIG_PATH = ROOT / ".shiplog" / "config.json"
SHIPLOG_PATH = WELL_KNOWN / "shiplog.json"
DEVLOG_PATH = WELL_KNOWN / "devlog.fragment.json"
CHECKPOINT_PATH = WELL_KNOWN / "checkpoint.json"
DEVLOG_MD_PATH = ROOT / "DEVLOG.md"
NODE = shutil.which("node")

CONFIG = json.loads(CONFIG_PATH.read_text())
SHIPLOG = json.loads(SHIPLOG_PATH.read_text())
DEVLOG = json.loads(DEVLOG_PATH.read_text())
CHECKPOINT = json.loads(CHECKPOINT_PATH.read_text())

PERSON_ID = re.compile(r"^(person|agent|org)/[a-z0-9][a-z0-9._-]*$")
PERSONAL = re.compile(r"(?i)caleb|solway")


class ConfigTest(unittest.TestCase):
    def test_no_raw_personal_email_in_the_committed_config(self):
        # Unmapped commit addresses fall back to defaultAuthor. Mapping them
        # explicitly would only type an email into a tracked, public file.
        self.assertNotRegex(CONFIG_PATH.read_text(), r"[\w.+-]+@gmail\.com")

    def test_the_author_is_a_real_id_not_a_placeholder(self):
        self.assertEqual(CONFIG["defaultAuthor"], "person/30e-founder")
        self.assertNotIn("accountable-human", CONFIG_PATH.read_text())

    def test_each_format_is_served_at_its_own_path(self):
        self.assertEqual(CONFIG["serve"], "site/.well-known/shiplog.json")
        self.assertEqual(CONFIG["serveDevlog"], "site/.well-known/devlog.fragment.json")


class ServedRecordTest(unittest.TestCase):
    def test_shiplog_is_shipped_1(self):
        self.assertEqual(SHIPLOG["shipped"], "1")
        self.assertTrue(SHIPLOG["entries"])

    def test_devlog_is_a_real_devlog_1_not_a_shiplog(self):
        self.assertEqual(DEVLOG["devlog"], "1")
        self.assertNotIn("shipped", DEVLOG)
        self.assertTrue(DEVLOG["entries"])
        for entry in DEVLOG["entries"]:
            self.assertEqual(set(entry), {"id", "at", "summary", "commitSha", "ref"}, entry["id"])
            self.assertTrue(entry["ref"].startswith("https://"), entry["id"])

    def test_every_shiplog_entry_is_public_and_names_a_real_id(self):
        for entry in SHIPLOG["entries"]:
            self.assertEqual(entry["visibility"], "public", entry["id"])
            for by in entry["by"]:
                self.assertRegex(by, PERSON_ID)
                self.assertNotEqual(by, "person/accountable-human", entry["id"])

    def test_nothing_served_names_the_owner_or_carries_a_commit_trailer(self):
        for path in (SHIPLOG_PATH, DEVLOG_PATH, DEVLOG_MD_PATH):
            text = path.read_text()
            self.assertNotRegex(text, PERSONAL, path.name)
            self.assertNotRegex(text, r"(?i)co-authored-by|claude-session", path.name)

    def test_the_checkpoint_covers_every_shiplog_entry(self):
        self.assertEqual(CHECKPOINT["checkpoint"], "1")
        self.assertEqual(CHECKPOINT["origin"], "repo/analystos")
        self.assertEqual(CHECKPOINT["size"], len(SHIPLOG["entries"]))
        # Flashy's fan-in folds a Python-style "+00:00" head time as 1970.
        self.assertTrue(CHECKPOINT["at"].endswith("Z"))

    def test_devlog_md_cites_a_merged_pr(self):
        self.assertRegex(DEVLOG_MD_PATH.read_text(), r"pull request #\d+")


class NoPrivateCopyTest(unittest.TestCase):
    def test_the_full_unredacted_record_is_not_committed(self):
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        for name in ("shiplog.fragment.json", "devlog.fragment.json", "checkpoint.json"):
            self.assertNotIn(name, tracked)


@unittest.skipUnless(NODE, "node is not installed")
class SealTest(unittest.TestCase):
    def run_node(self, *args):
        return subprocess.run([NODE, *args], cwd=ROOT, capture_output=True, text=True, timeout=60)

    def test_every_served_seal_recomputes(self):
        result = self.run_node("vendor-shiplog.mjs", "verify", str(SHIPLOG_PATH))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"ok — {len(SHIPLOG['entries'])} seals recomputed", result.stdout)

    def test_a_tampered_entry_is_refused(self):
        tampered = json.loads(SHIPLOG_PATH.read_text())
        tampered["entries"][0]["title"] = "tampered after sealing"
        tmp = ROOT / "tests" / "_tmp_tampered_shiplog.json"
        try:
            tmp.write_text(json.dumps(tampered))
            result = self.run_node("vendor-shiplog.mjs", "verify", str(tmp))
            self.assertNotEqual(result.returncode, 0)
        finally:
            tmp.unlink(missing_ok=True)

    def test_the_checkpoint_head_recomputes_and_every_leaf_proves(self):
        result = self.run_node("vendor-checkpoint.mjs", "verify", str(CHECKPOINT_PATH))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_privacy_rules_run_before_sealing(self):
        # The cleaning function itself, on commits shaped like parseGitLog's output.
        script = """
import { cleanCommits, stripTrailers } from './tools/emit_record.mjs'
const { commits, dropped } = cleanCommits([
  { sha: 'a', subject: 'Merge pull request #1 from SomeOwnerCaleb/x', body: 'x' },
  { sha: 'b', subject: 'Slice 9: thing', body: 'Real text.\\n\\nCo-Authored-By: Claude <noreply@anthropic.com>\\nClaude-Session: https://x', coAuthorEmails: ['noreply@anthropic.com'] },
  { sha: 'c', subject: 'Only trailers', body: 'Claude-Session: https://x' },
])
console.log(JSON.stringify({ dropped, commits, inline: stripTrailers('a\\nCo-Authored-By: z') }))
"""
        result = self.run_node("--input-type=module", "-e", script)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["dropped"], 1)
        b, c = out["commits"]
        self.assertEqual(b["body"], "Real text.")
        self.assertEqual(b["coAuthorEmails"], ["noreply@anthropic.com"])  # still credited
        self.assertNotIn("body", c)
        self.assertEqual(out["inline"], "a")


if __name__ == "__main__":
    unittest.main()
