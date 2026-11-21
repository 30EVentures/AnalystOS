"""Slice 96 - the measures/1 envelope around the existing, already-tested
`analystos.api_v1.audit.measures()` (Slice 61; see tests/test_api_v1.py::MeasuresTest
for the arithmetic itself - numerator/denominator/share, null on an empty
denominator). This file tests only what Slice 96 actually added: the window,
the charter's own measure sentence copied in rather than retyped, honest
handling of a role audit.measures() does not know about, and the
drafts/measures.json CLI (tools/build_measures.py)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from analystos.api_v1.audit import measures as compute_role_measures
from analystos.api_v1.store import FileStore
from tools.build_measures import build_measures_document

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


class EnvelopeTest(unittest.TestCase):
    def test_the_measure_sentence_is_copied_from_the_charter_byte_for_byte(self):
        out = build_measures_document(FAKE_CHARTER, [], ("x", "y"), "z")
        by_role = {r["role"]: r for r in out["roles"]}
        for role in FAKE_CHARTER["roles"]:
            self.assertEqual(by_role[role["name"]]["measure"], role["measure"])

    def test_window_is_stated_verbatim_not_derived_from_a_clock(self):
        out = build_measures_document(FAKE_CHARTER, [], ("2020-01-01T00:00:00Z", "2099-01-01T00:00:00Z"), "irrelevant")
        self.assertEqual(out["window"], "2020-01-01T00:00:00Z/2099-01-01T00:00:00Z")
        for role in out["roles"]:
            self.assertEqual(role["window"], out["window"])

    def test_a_role_audit_measures_does_not_know_about_is_null_not_guessed_at(self):
        out = build_measures_document(FAKE_CHARTER, [], ("a", "b"), "c")
        future = next(r for r in out["roles"] if r["role"] == "some-future-role")
        self.assertFalse(future["instrumented"])
        self.assertIsNone(future["numerator"])
        self.assertIsNone(future["value"])

    def test_the_three_known_roles_are_marked_instrumented(self):
        out = build_measures_document(FAKE_CHARTER, [], ("a", "b"), "c")
        for role in out["roles"]:
            if role["role"] != "some-future-role":
                self.assertTrue(role["instrumented"], role["role"])

    def test_agrees_with_audit_measures_directly_on_a_real_log(self):
        # Belt-and-braces: the envelope's numbers must be exactly what the
        # existing, separately-tested function returns - never a second,
        # possibly-drifted computation.
        events = [
            {"type": "analysis", "tier": "written", "proposed": 4, "verified": 4, "dropped": 0, "seal_ok": True},
            {"type": "analysis", "tier": "plain", "proposed": 2, "verified": 1, "dropped": 1, "seal_ok": False},
        ]
        direct = compute_role_measures(events)
        out = build_measures_document(CHARTER, events, ("a", "b"), "c")
        by_role = {r["role"]: r for r in out["roles"]}
        for name in ("analysis", "verification", "evidence"):
            self.assertEqual(by_role[name]["numerator"], direct[name]["numerator"], name)
            self.assertEqual(by_role[name]["denominator"], direct[name]["denominator"], name)
            self.assertEqual(by_role[name]["value"], direct[name]["share"], name)


class RealStoreIntegrationTest(unittest.TestCase):
    """Writes real events through FileStore.append_audit (the exact method
    analystos/api_v1/blueprint.py calls in production), the same fixture
    shape tests/test_api_v1.py::MeasuresTest already uses directly."""

    def test_real_chained_audit_log_feeds_the_envelope_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FileStore(tmp)
            store.append_audit({"type": "analysis", "tier": "written", "proposed": 4, "verified": 4, "dropped": 0, "seal_ok": True})
            store.append_audit({"type": "analysis", "tier": "plain", "proposed": 2, "verified": 1, "dropped": 1, "seal_ok": False})
            store.append_audit({"type": "view", "id": "irrelevant"})  # must be ignored, same as audit.measures()

            events = store.read_audit()
            out = build_measures_document(CHARTER, events, ("2026-11-01T00:00:00Z", "2026-11-21T00:00:00Z"), "2026-11-21T00:00:00Z")
            by_role = {r["role"]: r for r in out["roles"]}
            self.assertEqual(by_role["analysis"]["numerator"], 1)
            self.assertEqual(by_role["analysis"]["denominator"], 2)
            self.assertEqual(by_role["verification"]["numerator"], 1)
            self.assertEqual(by_role["verification"]["denominator"], 6)
            self.assertEqual(by_role["evidence"]["numerator"], 1)
            self.assertEqual(by_role["evidence"]["denominator"], 2)


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
            self.assertIsNone(role["value"])

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
