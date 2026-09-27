"""Slice 71 - no unused imports or dead module-level functions creep back in,
the one-command regeneration works, and a documented helper is exercised."""

import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("analystos", "api", "tools", "live_tests")
FILES = [p for d in SOURCE_DIRS for p in (ROOT / d).rglob("*.py") if "__pycache__" not in p.parts]
ALL_TEXT = {p: p.read_text(encoding="utf-8") for p in FILES + list((ROOT / "tests").rglob("*.py"))}


def is_decorated_route(node):
    return any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ("get", "post", "route", "add_url_rule")
               for d in node.decorator_list)


class NoDeadCodeTest(unittest.TestCase):
    def test_no_unused_imports(self):
        offenders = []
        for path in FILES:
            if path.name == "__init__.py":
                continue
            src = ALL_TEXT[path]
            tree = ast.parse(src)
            imported = {}
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    for a in n.names:
                        imported[(a.asname or a.name).split(".")[0]] = n.lineno
                elif isinstance(n, ast.ImportFrom):
                    for a in n.names:
                        imported[a.asname or a.name] = n.lineno
            used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            lines = src.splitlines()
            for name, line in imported.items():
                if name not in used and name != "*" and "noqa" not in lines[line - 1]:
                    offenders.append(f"{path.relative_to(ROOT)}:{line} imports {name} but never uses it")
        self.assertEqual(offenders, [])

    def test_no_module_level_function_or_class_is_referenced_nowhere(self):
        offenders = []
        for path in FILES:
            for node in ast.parse(ALL_TEXT[path]).body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith("__") and node.name != "main":
                    if is_decorated_route(node):
                        continue
                    uses = sum(len(re.findall(r"\b" + re.escape(node.name) + r"\b", text)) for text in ALL_TEXT.values())
                    if uses <= 1:
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name} is defined and never used")
        self.assertEqual(offenders, [])


class IsValidTest(unittest.TestCase):
    def test_documented_helper_is_exercised(self):
        from analystos.aao.validate import is_valid
        good = {"aao": "0.1", "name": "X", "slug": "example", "description": "d", "accountableTo": "a@b.co",
                "roles": [{"name": "release", "purpose": "p", "capabilities": ["deploy"]}]}
        self.assertTrue(is_valid(good))
        self.assertFalse(is_valid(dict(good, aao="0.2")))
        self.assertFalse(is_valid(None))
        self.assertIn("is_valid", (ROOT / "docs" / "aao.md").read_text())


class RefreshTest(unittest.TestCase):
    def run_refresh(self, *args):
        return subprocess.run([sys.executable, "tools/refresh.py", *args], cwd=ROOT, capture_output=True, text=True, timeout=120)

    def test_check_passes_on_a_clean_tree_and_names_all_three_generators(self):
        done = self.run_refresh("--check")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        for step in ("build_site_machine.py", "build_specs_index.py", "site_counts.py"):
            self.assertIn(step, done.stdout)

    def test_check_detects_a_stale_generated_file_without_changing_it(self):
        target = ROOT / "site" / "robots.txt"
        original = target.read_text()
        try:
            target.write_text(original + "# stale\n")
            done = self.run_refresh("--check")
            self.assertEqual(done.returncode, 1)
            self.assertIn("robots.txt", done.stdout)
            self.assertEqual(target.read_text(), original + "# stale\n")  # --check never writes
        finally:
            target.write_text(original)


if __name__ == "__main__":
    unittest.main()
