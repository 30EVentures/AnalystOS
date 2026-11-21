"""Slice 99 - the real shipped/1 + devlog/1 emission, run for real with the
published @flashyos/shiplog@0.2.0 (not a local reimplementation). See
docs/decisions.md and ROADMAP.md for what this is and is not yet.

Unlike every other draft in this session, these are committed as the tool's
own real output (`.shiplog/config.json`, `vendor-shiplog.mjs`,
`shiplog.fragment.json`, `DEVLOG.md`, `drafts/devlog.fragment.json`) - the
point of this format is a committed, private record; the decision left open
is whether and when to flip `visibility` to public and hand the URL to
Flashy's fan-in, not whether to commit the record at all.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".shiplog" / "config.json"
FRAGMENT_PATH = ROOT / "shiplog.fragment.json"
DEVLOG_SERVED_PATH = ROOT / "drafts" / "devlog.fragment.json"
DEVLOG_MD_PATH = ROOT / "DEVLOG.md"
SHIPLOG_BIN = ROOT / "tools" / "flashyos-check" / "node_modules" / ".bin" / "flashy-shiplog"

CONFIG = json.loads(CONFIG_PATH.read_text())
FRAGMENT = json.loads(FRAGMENT_PATH.read_text())


class ConfigTest(unittest.TestCase):
    def test_visibility_is_private_the_intended_first_state(self):
        # "Everything lands private, so the served fragment publishes
        # nothing until somebody decides otherwise" - the tool's own words
        # when it adopted. Flipping this is an owner decision, recorded
        # open in ROADMAP.md, not something this test should expect yet.
        self.assertEqual(CONFIG["visibility"], "private")

    def test_served_path_is_a_draft_not_the_live_site(self):
        # Same safety boundary as every other draft this session built:
        # a path under site/ would be live on the next deploy.
        self.assertFalse(CONFIG["serve"].startswith("site/"))

    def test_pr_base_was_auto_detected_as_a_real_https_url_not_left_opaque(self):
        # The documented silent-failure trap: with no GitHub-shaped prBase
        # and no explicit commitBase, entries emit validly but fold onto
        # no transparency log, with nothing red anywhere. Confirms the
        # real tool avoided it by reading the actual git remote.
        self.assertTrue(CONFIG.get("prBase", "").startswith("https://github.com/"))

    def test_no_raw_personal_email_in_the_committed_config(self):
        # Two commit authors came back unmapped when this was first run
        # (one of them the repo owner's personal address). Both already
        # fall back to defaultAuthor correctly - mapping them explicitly
        # would add nothing except typing a personal email into a tracked
        # file, so this test pins the deliberate choice not to.
        text = CONFIG_PATH.read_text()
        self.assertNotRegex(text, r"[\w.+-]+@gmail\.com")
        self.assertIn("person/", CONFIG["defaultAuthor"])


class FragmentTest(unittest.TestCase):
    def test_every_entry_is_private(self):
        self.assertTrue(FRAGMENT["entries"])
        for entry in FRAGMENT["entries"]:
            self.assertEqual(entry.get("visibility"), "private", entry["id"])

    def test_no_entry_carries_a_raw_email_in_its_by_field(self):
        # The real finding from running this for real: unmapped git commit
        # authors fall back to a safe node id, never leaking the address
        # itself into the record. Proven here, not just asserted.
        for entry in FRAGMENT["entries"]:
            for by in entry.get("by", []):
                self.assertNotIn("@", by, entry["id"])

    def test_the_served_public_projection_has_zero_entries(self):
        # Matches "everything lands private": the public projection is
        # genuinely empty today, not merely unpublished.
        served = json.loads(DEVLOG_SERVED_PATH.read_text())
        self.assertEqual(served["entries"], [])

    def test_devlog_md_exists_and_is_not_empty(self):
        self.assertTrue(DEVLOG_MD_PATH.exists())
        self.assertGreater(len(DEVLOG_MD_PATH.read_text()), 100)

    def test_devlog_md_cites_the_most_recently_merged_pr(self):
        # The thing this whole format is for: a dated, derived record of
        # real work, not hand-maintained prose that can drift from git.
        # Correctly stops at #89 (publish-seal-key, 2026-11-20) - this
        # session's own commits are unmerged, feature-branch work and are
        # right to be absent from a "what shipped" changelog.
        text = DEVLOG_MD_PATH.read_text()
        self.assertIn("publish-seal-key", text.lower())
        self.assertIn("2026-11-20", text)


@unittest.skipUnless(SHIPLOG_BIN.exists(), "run: cd tools/flashyos-check && npm install --ignore-scripts")
class RealShiplogCheckTest(unittest.TestCase):
    def test_every_seal_recomputes_offline(self):
        result = subprocess.run(
            [str(SHIPLOG_BIN), "check", str(FRAGMENT_PATH)], cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ok", result.stdout.lower())

    def test_a_tampered_fragment_is_refused(self):
        tampered = json.loads(FRAGMENT_PATH.read_text())
        tampered["entries"][0]["title"] = "tampered after sealing"
        tmp = ROOT / "tests" / "_tmp_tampered_shiplog.json"
        try:
            tmp.write_text(json.dumps(tampered))
            result = subprocess.run(
                [str(SHIPLOG_BIN), "check", str(tmp)], cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
        finally:
            tmp.unlink(missing_ok=True)

    def test_summary_reports_the_real_entry_count(self):
        result = subprocess.run(
            [str(SHIPLOG_BIN), "summary", str(FRAGMENT_PATH)], cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r"(\d+) entries across", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        self.assertEqual(int(match.group(1)), len(FRAGMENT["entries"]))


if __name__ == "__main__":
    unittest.main()
