"""Slice 107 - the Flashy fence. The FlashyOS integration is frozen while the rest
of AnalystOS is rebuilt around it; these tests prove the fence is real.

Each drift test works on a copy of the repository: it first confirms the copy's
fence holds (so a pass is never vacuous), makes one change, and requires the
check to name it. Changes the rebuild legitimately needs (a new vercel.json
route, a new devlog entry, a Flashy mention inside tests/) must still pass."""

import copy
import json
import shutil
import subprocess
import sys
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
        self.assertDrift("vercel.json: a block serving a fenced path or /api/v1")

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

    def test_a_wildcard_vercel_block_over_fenced_paths_is_drift(self):
        for kind, block in (
            ("redirects", {"source": "/.well-known/:path*", "destination": "https://elsewhere.example/:path*"}),
            ("headers", {"source": "/.well-known/(.*)", "headers": [{"key": "Content-Type", "value": "text/html"}]}),
            ("headers", {"source": "/(.*)", "headers": [{"key": "X-Frame-Options", "value": "DENY"}]}),
        ):
            with self.subTest(source=block["source"]):
                original = (self.repo / "vercel.json").read_text()
                self.edit_json("vercel.json", lambda doc: doc.setdefault(kind, []).append(block))
                self.assertDrift("vercel.json: a block serving a fenced path or /api/v1")
                (self.repo / "vercel.json").write_text(original)

    def test_removing_a_v1_rewrite_is_drift(self):
        self.edit_json("vercel.json", lambda doc: doc.update(
            rewrites=[r for r in doc["rewrites"] if r["source"] != "/api/v1/jobs/:job/escalate"]))
        self.assertDrift("vercel.json: a block serving a fenced path or /api/v1")

    def test_a_new_well_known_document_is_drift(self):
        (self.repo / "site/.well-known/agent.json").write_text("{}\n")
        self.assertDrift("file added to site/.well-known/")

    def test_a_second_flashy_section_in_llms_is_drift(self):
        path = self.repo / fence.LLMS_FILE
        path.write_text(path.read_text() + "\n" + fence.LLMS_HEADING + "\n\n- [Charter](x): something else\n")
        self.assertDrift("expected exactly one")

    def test_editing_code_the_fenced_files_import_is_drift(self):
        path = self.repo / "analystos/api_v1/audit_chain.py"
        path.write_text(path.read_text() + "\n# changed\n")
        self.assertDrift("file changed: analystos/api_v1/audit_chain.py")

    def test_openapi_is_built_from_the_checked_tree(self):
        path = self.repo / "analystos/api_v1/openapi.py"
        text = path.read_text()
        self.assertIn("def build_openapi():", text)
        path.write_text(text + "\n_orig = build_openapi\n"
                        "def build_openapi():\n    doc = _orig()\n    doc['info']['title'] += '!'\n    return doc\n")
        problems = fence.check(self.repo)  # no openapi argument: built from the copy's code
        self.assertTrue(any("OpenAPI" in p for p in problems), problems)

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

    def test_reordering_past_entries_is_drift(self):
        self.edit_json("devlog.fragment.json", lambda doc: doc["entries"].reverse())
        self.assertDrift("devlog.fragment.json: past entries were reordered")

    def test_a_duplicate_entry_id_is_drift(self):
        def change(doc):
            doc["entries"].insert(0, dict(doc["entries"][-1], summary="an edited copy"))
        self.edit_json("devlog.fragment.json", change)
        self.assertDrift("devlog.fragment.json: duplicate entry ids")

    def test_changing_an_append_only_header_is_drift(self):
        self.edit_json("site/.well-known/devlog.fragment.json", lambda doc: doc.update(org="someone-else"))
        self.assertDrift("site/.well-known/devlog.fragment.json: unreadable, or a top-level field")

    # --- coverage ------------------------------------------------------------

    def test_a_derived_output_inside_a_fenced_directory_may_change(self):
        # drafts/measures.json is rebuilt by its (fenced) generator, and the suite rewrites it.
        path = self.repo / "drafts/measures.json"
        path.write_text(path.read_text().replace('"computed"', '"computed" ', 1))
        self.assertEqual(self.check(), [])

    def test_a_new_unfenced_flashy_file_is_drift(self):
        (self.repo / "analystos/l3").mkdir(parents=True, exist_ok=True)
        (self.repo / "analystos/l3/mesh_offer.py").write_text("# declare the deck offer on FlashyOS\n")
        self.assertDrift("neither fenced nor watched: analystos/l3/mesh_offer.py")

    def test_flashy_mentions_inside_tests_and_specs_are_allowed(self):
        (self.repo / "tests/test_new.py").write_text("# FlashyOS\n")
        (self.repo / "specs/new-slice").mkdir(parents=True)
        (self.repo / "specs/new-slice/spec.md").write_text("FlashyOS\n")
        self.assertEqual(self.check(), [])

    def test_a_watched_file_that_stops_mentioning_flashy_is_a_warning_not_drift(self):
        (self.repo / "README.md").write_text("A consulting product.\n")
        self.assertEqual(self.check(), [])
        self.assertIn("README.md", fence.stale_watched(self.repo))

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
        manifest = self.repo / fence.MANIFEST_NAME
        before = manifest.read_bytes()
        code, _ = fence.update(self.repo, "   ", "2026-12-01")
        self.assertEqual(code, 2)
        self.assertEqual(manifest.read_bytes(), before)

    def test_update_refuses_over_an_unreadable_manifest(self):
        manifest = self.repo / fence.MANIFEST_NAME
        manifest.write_text("{not json")
        code, message = fence.update(self.repo, "a real reason", "2026-12-01")
        self.assertEqual(code, 1)
        self.assertIn("unreadable", message)
        self.assertEqual(manifest.read_text(), "{not json")

    def test_update_moves_the_fence_and_logs_what_moved(self):
        path = self.repo / "site/.well-known/flashyos-charter.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.assertDrift("file changed: site/.well-known/flashyos-charter.json")
        code, _ = fence.update(self.repo, "Gate F: owner approved a new offer", "2026-12-01")
        self.assertEqual(code, 0)
        self.assertEqual(self.check(), [])
        log = fence.load_manifest(self.repo)["log"]
        self.assertEqual(len(log), 2)
        self.assertEqual(log[-1]["reason"], "Gate F: owner approved a new offer")
        self.assertIn("file changed: site/.well-known/flashyos-charter.json", log[-1]["moved"])

    def test_cli_exit_codes(self):
        script = self.repo / "tools/flashy_freeze.py"
        run = lambda: subprocess.run([sys.executable, str(script), "--check"], cwd=self.repo,
                                     capture_output=True, text=True)
        held = run()
        self.assertEqual(held.returncode, 0, held.stdout + held.stderr)
        self.assertIn("holds", held.stdout)
        path = self.repo / "site/flashyos.roles.json"
        path.write_bytes(path.read_bytes() + b" ")
        drifted = run()
        self.assertEqual(drifted.returncode, 1)
        self.assertIn("file changed: site/flashyos.roles.json", drifted.stdout)

    # --- the decision log ----------------------------------------------------

    def test_an_emptied_or_rewritten_log_is_drift(self):
        self.edit_json(fence.MANIFEST_NAME, lambda doc: doc.update(log=[]))
        self.assertDrift("manifest log is missing or empty")
        self.edit_json(fence.MANIFEST_NAME, lambda doc: doc.update(log=[{"date": "x", "reason": "something else"}]))
        self.assertDrift("no longer starts with the Slice 107 first pin")

    # --- reported, not crashed -----------------------------------------------

    def test_unreadable_inputs_are_reported_not_raised(self):
        (self.repo / "vercel.json").write_text("{broken")
        (self.repo / fence.LLMS_FILE).unlink()
        (self.repo / "devlog.fragment.json").write_text("[]")
        problems = self.check()
        self.assertTrue(any("vercel.json" in p for p in problems), problems)
        self.assertTrue(any(fence.LLMS_FILE in p for p in problems), problems)
        self.assertTrue(any(p.startswith("devlog.fragment.json: unreadable") for p in problems), problems)

    # --- untracked files in a real checkout ----------------------------------

    def test_untracked_files_count_before_git_add(self):
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
        subprocess.run(git + ["init", "-q"], cwd=self.repo, check=True)
        subprocess.run(git + ["add", "-A"], cwd=self.repo, check=True)
        subprocess.run(git + ["commit", "-qm", "base"], cwd=self.repo, check=True)
        self.assertEqual(self.check(), [])
        (self.repo / "mcp-server/extra.mjs").write_text("export {};\n")
        (self.repo / "analystos/mesh_offer.py").write_text("# FlashyOS offer\n")
        problems = self.check()
        self.assertIn("file added inside a fenced directory: mcp-server/extra.mjs", problems)
        self.assertIn("mentions FlashyOS/AAO but is neither fenced nor watched: analystos/mesh_offer.py", problems)


if __name__ == "__main__":
    unittest.main()
