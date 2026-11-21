"""Slice 96 - measures/1 is computed correctly from real audit events, states
its window instead of trusting the clock, and never turns an empty
denominator into a fake 0% or 100%."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from analystos.api_v1.measures import compute_measures
from analystos.api_v1.store import FileStore

ROOT = Path(__file__).resolve().parents[1]
CHARTER = json.loads((ROOT / "site" / ".well-known" / "flashyos-charter.json").read_text())

FAKE_CHARTER = {
    "slug": "analystos",
    "roles": [
        {"name": "analysis", "measure": "Reports delivered at the written tier, as a share of reports delivered"},
        {"name": "verification", "measure": "Facts refused, as a share of facts proposed"},
        {"name": "evidence", "measure": "Delivered reports whose seal re-verifies offline, as a share of reports delivered"},
        {"name": "some-future-role", "measure": "Not yet instrumented"},
    ]
}


def _event(tier, proposed, verified, dropped, seal_ok, ts="2026-11-01T00:00:00Z"):
    return {
        "type": "analysis", "ts": ts, "tier": tier,
        "proposed": proposed, "verified": verified, "dropped": dropped, "seal_ok": seal_ok,
    }


class ComputeMeasuresTest(unittest.TestCase):
    def test_empty_denominator_is_null_never_a_fake_percentage(self):
        out = compute_measures(FAKE_CHARTER, [], ("2026-11-01T00:00:00Z", "2026-11-21T00:00:00Z"), "2026-11-21T00:00:00Z")
        for role in out["roles"]:
            with self.subTest(role=role["role"]):
                self.assertEqual(role["denominator"], 0 if role["role"] != "some-future-role" else None)
                self.assertIsNone(role["value"])

    def test_the_measure_sentence_is_copied_from_the_charter_byte_for_byte(self):
        out = compute_measures(FAKE_CHARTER, [], ("x", "y"), "z")
        by_role = {r["role"]: r for r in out["roles"]}
        for role in FAKE_CHARTER["roles"]:
            self.assertEqual(by_role[role["name"]]["measure"], role["measure"])

    def test_window_is_stated_verbatim_not_derived_from_a_clock(self):
        out = compute_measures(FAKE_CHARTER, [], ("2020-01-01T00:00:00Z", "2099-01-01T00:00:00Z"), "irrelevant")
        self.assertEqual(out["window"], "2020-01-01T00:00:00Z/2099-01-01T00:00:00Z")
        for role in out["roles"]:
            self.assertEqual(role["window"], out["window"])

    def test_analysis_measure_counts_written_tier_against_all_delivered(self):
        events = [
            _event("written", 5, 5, 0, True),
            _event("written", 3, 3, 0, True),
            _event("plain", 2, 1, 1, False),  # delivered, but not at the written tier
        ]
        out = compute_measures(FAKE_CHARTER, events, ("a", "b"), "c")
        analysis = next(r for r in out["roles"] if r["role"] == "analysis")
        self.assertEqual(analysis["numerator"], 2)  # two events at tier == "written"
        self.assertEqual(analysis["denominator"], 3)  # three delivered in total
        self.assertEqual(analysis["value"], round(2 / 3, 4))

    def test_verification_measure_sums_dropped_over_proposed_across_all_events(self):
        events = [
            _event("written", 10, 9, 1, True),
            _event("plain", 4, 2, 2, False),
        ]
        out = compute_measures(FAKE_CHARTER, events, ("a", "b"), "c")
        verification = next(r for r in out["roles"] if r["role"] == "verification")
        self.assertEqual(verification["numerator"], 3)  # 1 + 2 dropped
        self.assertEqual(verification["denominator"], 14)  # 10 + 4 proposed
        self.assertEqual(verification["value"], round(3 / 14, 4))

    def test_evidence_measure_counts_seals_that_actually_reverified(self):
        events = [
            _event("written", 1, 1, 0, True),
            _event("written", 1, 1, 0, True),
            _event("plain", 1, 0, 1, False),  # delivered, but its own seal check failed
        ]
        out = compute_measures(FAKE_CHARTER, events, ("a", "b"), "c")
        evidence = next(r for r in out["roles"] if r["role"] == "evidence")
        self.assertEqual(evidence["numerator"], 2)
        self.assertEqual(evidence["denominator"], 3)

    def test_a_role_with_no_known_formula_is_null_not_guessed_at(self):
        out = compute_measures(FAKE_CHARTER, [_event("written", 1, 1, 0, True)], ("a", "b"), "c")
        future = next(r for r in out["roles"] if r["role"] == "some-future-role")
        self.assertFalse(future["instrumented"])
        self.assertIsNone(future["value"])

    def test_non_analysis_events_are_ignored(self):
        events = [
            {"type": "view", "ts": "2026-11-01T00:00:00Z", "id": "x"},
            {"type": "job_created", "ts": "2026-11-01T00:00:00Z", "id": "y"},
        ]
        out = compute_measures(FAKE_CHARTER, events, ("a", "b"), "c")
        for role in out["roles"]:
            if role["role"] != "some-future-role":
                self.assertEqual(role["denominator"], 0)


class RealStoreIntegrationTest(unittest.TestCase):
    """Writes real events through FileStore.append_audit (the exact method
    analystos/api_v1/blueprint.py calls in production) and checks the live,
    three-role charter's measures compute correctly from the real chained
    log - not a mock of the store."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = FileStore(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_real_chained_audit_log_produces_correct_measures(self):
        self.store.append_audit({"type": "analysis", "tier": "written", "proposed": 4, "verified": 4, "dropped": 0, "seal_ok": True})
        self.store.append_audit({"type": "analysis", "tier": "plain", "proposed": 2, "verified": 1, "dropped": 1, "seal_ok": False})
        self.store.append_audit({"type": "view", "id": "irrelevant"})  # must be ignored

        events = self.store.read_audit()
        out = compute_measures(CHARTER, events, ("2026-11-01T00:00:00Z", "2026-11-21T00:00:00Z"), "2026-11-21T00:00:00Z")

        by_role = {r["role"]: r for r in out["roles"]}
        self.assertEqual(by_role["analysis"]["numerator"], 1)
        self.assertEqual(by_role["analysis"]["denominator"], 2)
        self.assertEqual(by_role["verification"]["numerator"], 1)  # dropped: 0 + 1
        self.assertEqual(by_role["verification"]["denominator"], 6)  # proposed: 4 + 2
        self.assertEqual(by_role["evidence"]["numerator"], 1)
        self.assertEqual(by_role["evidence"]["denominator"], 2)
        # Every live role is instrumented - no silent gaps on the three that exist today.
        self.assertTrue(all(r["instrumented"] for r in out["roles"]))


class BuildMeasuresCliTest(unittest.TestCase):
    """tools/build_measures.py end to end, including against a real store dir."""

    def test_with_no_store_dir_every_value_is_honestly_null(self):
        result = subprocess.run(
            [sys.executable, "tools/build_measures.py", "--since", "a", "--until", "b"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads((ROOT / "drafts" / "measures.json").read_text())
        for role in doc["roles"]:
            self.assertEqual(role["value"], None)

    def test_check_mode_is_clean_right_after_a_build(self):
        subprocess.run([sys.executable, "tools/build_measures.py"], cwd=ROOT, capture_output=True, text=True)
        result = subprocess.run(
            [sys.executable, "tools/build_measures.py", "--check"], cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_with_a_real_store_dir_numbers_are_computed_not_null(self):
        with tempfile.TemporaryDirectory() as store_dir:
            store = FileStore(store_dir)
            store.append_audit({"type": "analysis", "tier": "written", "proposed": 3, "verified": 3, "dropped": 0, "seal_ok": True})
            result = subprocess.run(
                [sys.executable, "tools/build_measures.py", "--store-dir", store_dir],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            doc = json.loads((ROOT / "drafts" / "measures.json").read_text())
            analysis = next(r for r in doc["roles"] if r["role"] == "analysis")
            self.assertEqual(analysis["numerator"], 1)
            self.assertEqual(analysis["denominator"], 1)
            self.assertEqual(analysis["value"], 1.0)

        # Restore the honestly-empty committed version so other tests and the
        # working tree are not left depending on this test's run order.
        subprocess.run([sys.executable, "tools/build_measures.py"], cwd=ROOT, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
