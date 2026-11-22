"""Slice 99 - the real shipped/1 + devlog/1 emission, run for real with the
published @flashyos/shiplog@0.2.0 (not a local reimplementation). See
docs/decisions.md and ROADMAP.md for what this is and is not yet.

Unlike every other draft in this session, these are committed as the tool's
own real output (`.shiplog/config.json`, `vendor-shiplog.mjs`,
`shiplog.fragment.json`, `DEVLOG.md`, `site/.well-known/devlog.fragment.json`).
`visibility` was flipped to `public` 2026-11-22 (owner's decision) and every
entry re-derived against it; the served projection moved from `drafts/` to a
real `site/.well-known/` path the same day. Handing the URL to Flashy's
fan-in is a separate, still-open step.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".shiplog" / "config.json"
FRAGMENT_PATH = ROOT / "shiplog.fragment.json"
DEVLOG_SERVED_PATH = ROOT / "site" / ".well-known" / "devlog.fragment.json"
DEVLOG_MD_PATH = ROOT / "DEVLOG.md"
SHIPLOG_BIN = ROOT / "tools" / "flashyos-check" / "node_modules" / ".bin" / "flashy-shiplog"

CONFIG = json.loads(CONFIG_PATH.read_text())
FRAGMENT = json.loads(FRAGMENT_PATH.read_text())


class ConfigTest(unittest.TestCase):
    def test_visibility_is_public_the_owners_decision(self):
        # "Everything lands private, so the served fragment publishes
        # nothing until somebody decides otherwise" - the tool's own words
        # when it adopted. Flipped 2026-11-22 (owner's decision, recorded
        # in docs/decisions.md and ROADMAP.md): the record is real work,
        # already shipped, not something that needed to wait.
        self.assertEqual(CONFIG["visibility"], "public")

    def test_served_path_is_live_under_well_known(self):
        # Flipped 2026-11-22 (owner's decision): unlike every other draft
        # this session built, this record is real, already-shipped work -
        # it is meant to be live, not parked under drafts/ forever.
        self.assertEqual(CONFIG["serve"], "site/.well-known/devlog.fragment.json")

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
    def test_every_entry_is_public(self):
        # Re-derived 2026-11-22 after the owner's decision to flip visibility -
        # every entry, not just new ones, since --rederive discards the stale
        # private-stamped history rather than leaving it half-flipped.
        self.assertTrue(FRAGMENT["entries"])
        for entry in FRAGMENT["entries"]:
            self.assertEqual(entry.get("visibility"), "public", entry["id"])

    def test_no_entry_carries_a_raw_email_in_its_by_field(self):
        # The real finding from running this for real: unmapped git commit
        # authors fall back to a safe node id, never leaking the address
        # itself into the record. Proven here, not just asserted.
        for entry in FRAGMENT["entries"]:
            for by in entry.get("by", []):
                self.assertNotIn("@", by, entry["id"])

    def test_the_served_public_projection_is_a_filtered_subset_of_the_fragment(self):
        # Now that visibility is public, every entry in the full fragment is
        # tagged public - but the served copy is smaller (tools/redact_served_devlog.py
        # drops anything naming the owner personally, found live 2026-11-22
        # in old merge-commit titles from this repo's personal-fork era).
        served = json.loads(DEVLOG_SERVED_PATH.read_text())
        self.assertTrue(served["entries"])
        served_ids = {e["id"] for e in served["entries"]}
        fragment_ids = {e["id"] for e in FRAGMENT["entries"]}
        self.assertTrue(served_ids <= fragment_ids)
        self.assertLess(len(served_ids), len(fragment_ids))
        for entry in served["entries"]:
            self.assertEqual(entry.get("visibility"), "public", entry["id"])

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
