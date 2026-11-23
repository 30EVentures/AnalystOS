"""Slice 107 - the Flashy fence. The FlashyOS integration is frozen while the rest
of AnalystOS is rebuilt around it; these tests prove the fence is real.

Each drift test works on a copy of the repository: it first confirms the copy's
fence holds (so a pass is never vacuous), makes one change, and requires the
check to name it. Changes the rebuild legitimately needs (a new vercel.json
route, a new devlog entry, a Flashy mention inside tests/) must still pass."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import flashy_freeze as fence

ROOT = Path(__file__).resolve().parents[1]
OPENAPI = fence._openapi_v1()


def _repo_files():
    return sorted(set(fence.tracked_files(ROOT)) | {fence.MANIFEST_NAME, "tools/flashy_freeze.py"})


class FlashyFenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_dir = tempfile.TemporaryDirectory()
        cls.base = Path(cls._base_dir.name) / "repo"
        for rel in _repo_files():
            dest = cls.base / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dest)

    @classmethod
    def tearDownClass(cls):
        cls._base_dir.cleanup()

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.repo = Path(self._dir.name) / "repo"
        shutil.copytree(self.base, self.repo)
        self.assertEqual(self.check(), [], "the unmodified copy must hold, or every test below is vacuous")

    def tearDown(self):
        self._dir.cleanup()

    def check(self, openapi=None):
        return fence.check(self.repo, openapi=openapi if openapi is not None else OPENAPI)

    def assertDrift(self, needle):
        problems = self.check()
        self.assertTrue(any(needle in p for p in problems), f"expected drift naming {needle!r}, got {problems}")

    def edit_json(self, rel, change):
        path = self.repo / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc)
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    # --- the real repository -------------------------------------------------

    def test_the_repository_fence_holds(self):
        self.assertEqual(fence.check(ROOT), [])

    def test_manifest_log_records_the_decision(self):
        log = fence.load_manifest(ROOT)["log"]
        self.assertIn("Slice 107", log[0]["reason"])
        self.assertTrue(all(entry.get("reason", "").strip() for entry in log))

    # --- exact files and directories ----------------------------------------

    def test_one_byte_charter_edit_is_drift(self):
        path = self.repo / "site/.well-known/flashyos-charter.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.assertDrift("file changed: site/.well-known/flashyos-charter.json")

    def test_deleted_fenced_file_is_drift(self):
        (self.repo / "analystos/l4/seal_verify.py").unlink()
        self.assertDrift("file changed: analystos/l4/seal_verify.py")

    def test_new_file_inside_a_fenced_directory_is_drift(self):
        (self.repo / "mcp-server/extra.mjs").write_text("export {};\n")
        self.assertDrift("file added inside a fenced directory: mcp-server/extra.mjs")

    def test_editing_the_fence_itself_is_drift(self):
        path = self.repo / "tools/flashy_freeze.py"
        path.write_text(path.read_text() + "\n# weakened\n")
        self.assertDrift("file changed: tools/flashy_freeze.py")

    # --- the /api/v1 contract -----------------------------------------------

    def test_changed_v1_openapi_is_drift(self):
        changed = copy.deepcopy(OPENAPI)
        changed.setdefault("paths", {})["/api/v1/new-thing"] = {"get": {"responses": {"200": {"description": "x"}}}}
        problems = self.check(openapi=changed)
        self.assertTrue(any("OpenAPI" in p for p in problems), problems)

    # --- shared files: only their Flashy parts are frozen ---------------------

    def test_editing_a_flashy_vercel_block_is_drift(self):
        def change(doc):
            for block in doc["headers"]:
                if block["source"] == "/.well-known/flashyos.json":
                    block["headers"][0]["value"] = "text/plain"
        self.edit_json("vercel.json", change)
        self.assertDrift("vercel.json block changed or removed for /.well-known/flashyos.json")

    def test_a_new_unrelated_vercel_block_is_allowed(self):
        self.edit_json("vercel.json", lambda doc: doc["rewrites"].append(
            {"source": "/api/v2/engagements", "destination": "/api/v2/engagements.py"}))
        self.assertEqual(self.check(), [])

    def test_editing_the_llms_flashy_section_is_drift(self):
        path = self.repo / fence.LLMS_FILE
        path.write_text(path.read_text().replace("flashyos/1", "flashyos/2", 1))
        self.assertDrift("Identity and the FlashyOS mesh")

    def test_editing_llms_outside_the_flashy_section_is_allowed(self):
        path = self.repo / fence.LLMS_FILE
        path.write_text(path.read_text() + "\n## Consulting engagements\n\n- something new\n")
        self.assertEqual(self.check(), [])

    # --- append-only records -------------------------------------------------

    def test_a_new_devlog_entry_is_allowed(self):
        def change(doc):
            entry = dict(doc["entries"][0], id="new-entry", summary="Slice 108: something new")
            doc["entries"].insert(0, entry)
            doc["generated"] = "2026-12-01T00:00:00Z"
        self.edit_json("devlog.fragment.json", change)
        self.assertEqual(self.check(), [])

    def test_rewriting_a_past_devlog_entry_is_drift(self):
        def change(doc):
            doc["entries"][-1]["summary"] = "rewritten history"
        self.edit_json("devlog.fragment.json", change)
        self.assertDrift("devlog.fragment.json: 1 past entry changed or removed")

    def test_removing_a_past_shiplog_entry_is_drift(self):
        self.edit_json("shiplog.fragment.json", lambda doc: doc["entries"].pop())
        self.assertDrift("shiplog.fragment.json: 1 past entry changed or removed")

    def test_changing_an_append_only_header_is_drift(self):
        self.edit_json("site/.well-known/devlog.fragment.json", lambda doc: doc.update(org="someone-else"))
        self.assertDrift("site/.well-known/devlog.fragment.json: a top-level field")

    # --- coverage ------------------------------------------------------------

    def test_a_derived_output_inside_a_fenced_directory_may_change(self):
        # drafts/measures.json is rebuilt by its (fenced) generator, and the suite rewrites it.
        path = self.repo / "drafts/measures.json"
        path.write_text(path.read_text().replace('"computed"', '"computed" ', 1))
        self.assertEqual(self.check(), [])

    def test_a_new_unfenced_flashy_file_is_drift(self):
        (self.repo / "analystos/l3").mkdir(parents=True)
        (self.repo / "analystos/l3/mesh_offer.py").write_text("# declare the deck offer on FlashyOS\n")
        self.assertDrift("neither fenced nor watched: analystos/l3/mesh_offer.py")

    def test_flashy_mentions_inside_tests_and_specs_are_allowed(self):
        (self.repo / "tests/test_new.py").write_text("# FlashyOS\n")
        (self.repo / "specs/new-slice").mkdir(parents=True)
        (self.repo / "specs/new-slice/spec.md").write_text("FlashyOS\n")
        self.assertEqual(self.check(), [])

    def test_a_watched_file_that_stops_mentioning_flashy_is_reported(self):
        (self.repo / "README.md").write_text("A consulting product.\n")
        self.assertDrift("drop it from WATCHED): README.md")

    # --- failing closed ------------------------------------------------------

    def test_missing_or_malformed_manifest_fails_closed(self):
        manifest = self.repo / fence.MANIFEST_NAME
        manifest.write_text("{not json")
        self.assertDrift("the fence cannot be checked")
        manifest.write_text(json.dumps({"format": fence.FORMAT}))
        self.assertDrift("the fence cannot be checked")
        manifest.unlink()
        self.assertDrift("the fence cannot be checked")

    def test_update_refuses_without_a_reason(self):
        before = (ROOT / fence.MANIFEST_NAME).read_bytes()
        self.assertEqual(fence.main(["--update", "--reason", "   "]), 2)
        self.assertEqual((ROOT / fence.MANIFEST_NAME).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
