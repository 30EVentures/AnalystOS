"""Slice 77: the Node checker, run for real against bundles this repo seals."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from analystos.api_v1.openapi import build_openapi
from analystos.l4.seal import build_bundle

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "seal_facts_check.mjs"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class NodeCheckerTest(unittest.TestCase):
    def setUp(self):
        from tests.test_l4_seal import trace
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.bundle = build_bundle(trace())
        self.spec = self.write("openapi.json", build_openapi())

    def write(self, name, data):
        path = self.dir / name
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return path

    def run_tool(self, bundle, spec=None):
        path = bundle if isinstance(bundle, Path) else self.write("bundle.json", bundle)
        done = subprocess.run(["node", str(TOOL), str(path), str(spec or self.spec)], capture_output=True, text=True)
        return done.returncode, done.stdout, done.stderr

    def test_a_sealed_bundle_fits(self):
        code, out, err = self.run_tool(self.bundle)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(json.loads(out), {"ok": True, "checked": 3, "problems": []})

    def test_tampered_facts_are_named(self):
        for mutate in (lambda r: r.update(value=5),
                       lambda r: r.update(type="chart"),
                       lambda r: r.update(operation="median")):
            bundle = copy.deepcopy(self.bundle)
            target = bundle["facts"][1]  # the computed fact
            mutate(target["record"])
            code, out, _ = self.run_tool(bundle)
            self.assertEqual(code, 1, out)
            self.assertEqual({p["key"] for p in json.loads(out)["problems"]}, {target["key"]})

    def test_unreadable_input_is_exit_2(self):
        self.assertEqual(self.run_tool(self.write("junk.json", "not json"))[0], 2)
        self.assertEqual(self.run_tool(self.bundle, self.dir / "missing.json")[0], 2)

    def test_a_schema_with_an_unsupported_keyword_is_refused_not_passed(self):
        spec = copy.deepcopy(build_openapi())  # it shares the module-level schema dict
        spec["components"]["schemas"]["SealFact"]["oneOf"][3]["properties"]["text"]["minLength"] = 1
        code, _, err = self.run_tool(self.bundle, self.write("strict.json", spec))
        self.assertEqual(code, 2)
        self.assertIn("minLength", err)


if __name__ == "__main__":
    unittest.main()
