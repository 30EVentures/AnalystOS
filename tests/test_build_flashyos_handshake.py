"""Slice 94 - the handshake's capabilities are derived from the charter, never
hand-typed, and the result passes the real, published FlashyOS validators
(not a local re-implementation of their rules).

Setup (once per checkout, like the Python venv):

    cd tools/flashyos-check && npm install --ignore-scripts

The two tests that call Node skip themselves with a clear reason when that
has not been done, rather than failing the whole suite - this mirrors
live_tests/, which needs a real key, except this needs no key and no
network at test time, only the packages already on disk.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from tools.build_flashyos_handshake import build_handshake, derive_capabilities

ROOT = Path(__file__).resolve().parents[1]
CHARTER_PATH = ROOT / "site" / ".well-known" / "flashyos-charter.json"
HANDSHAKE_PATH = ROOT / "site" / ".well-known" / "flashyos.json"
NODE_MODULES = ROOT / "tools" / "flashyos-check" / "node_modules"

CHARTER = json.loads(CHARTER_PATH.read_text())


class DerivationTest(unittest.TestCase):
    """Pure logic, no subprocess - these always run."""

    def test_capabilities_are_role_names_sorted(self):
        charter = {"roles": [{"name": "verification"}, {"name": "analysis"}, {"name": "evidence"}]}
        self.assertEqual(derive_capabilities(charter), ["analysis", "evidence", "verification"])

    def test_duplicate_role_names_are_not_duplicated(self):
        charter = {"roles": [{"name": "analysis"}, {"name": "analysis"}]}
        self.assertEqual(derive_capabilities(charter), ["analysis"])

    def test_x_capability_slugs_are_advertised_beside_role_names(self):
        # Owner's decision 2026-11-26 (Slice 132): one vocabulary across handshake,
        # charter and mesh. A string or a list are both read.
        charter = {"roles": [{"name": "analysis", "x-capability": ["document-analysis", "analytics"]},
                             {"name": "evidence", "x-capability": "sealed-report"}]}
        self.assertEqual(derive_capabilities(charter),
                         ["analysis", "analytics", "document-analysis", "evidence", "sealed-report"])

    def test_no_roles_means_no_capabilities(self):
        self.assertEqual(derive_capabilities({"roles": []}), [])

    def test_the_served_handshake_matches_what_the_builder_computes_now(self):
        # Guards against a hand-edit drifting from the charter between refresh.py runs.
        computed = build_handshake()
        served = json.loads(HANDSHAKE_PATH.read_text())
        self.assertEqual(computed, served)

    def test_build_flashyos_handshake_check_mode_is_clean(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_flashyos_handshake.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(NODE_MODULES.is_dir(), "run: cd tools/flashyos-check && npm install --ignore-scripts")
class RealValidatorTest(unittest.TestCase):
    """Runs the actual @flashyos/aao and @flashyos/conformance packages - the
    same ones the Flashy estate itself ran against this repo on 2026-11-21 -
    against the files this repo serves. Not a reimplementation of their rules."""

    def _run_node(self, script: str) -> dict:
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_charter_has_zero_validator_errors(self):
        out = self._run_node(
            """
            const aao = require('./tools/flashyos-check/node_modules/@flashyos/aao');
            const fs = require('fs');
            const charter = JSON.parse(fs.readFileSync('site/.well-known/flashyos-charter.json'));
            console.log(JSON.stringify({errors: aao.validateCharterDocument(charter)}));
            """
        )
        self.assertEqual(out["errors"], [])

    def test_audit_property_reaches_level_2_with_no_issues(self):
        out = self._run_node(
            """
            const conf = require('./tools/flashyos-check/node_modules/@flashyos/conformance');
            const fs = require('fs');
            const charter = JSON.parse(fs.readFileSync('site/.well-known/flashyos-charter.json'));
            const handshake = JSON.parse(fs.readFileSync('site/.well-known/flashyos.json'));
            console.log(JSON.stringify(conf.auditProperty({charter, handshake, manifest: charter})));
            """
        )
        self.assertEqual(out, {"ok": True, "issues": [], "level": 2})

    def test_removing_capabilities_drops_it_back_to_level_1(self):
        # Proves the test above is not vacuous: without the handshake's
        # capabilities array, Flashy's own validator reads "declares nothing
        # it can do" and the level drops - this is the exact finding their
        # 21 Nov reply described, reproduced here against the real package.
        out = self._run_node(
            """
            const conf = require('./tools/flashyos-check/node_modules/@flashyos/conformance');
            const fs = require('fs');
            const charter = JSON.parse(fs.readFileSync('site/.well-known/flashyos-charter.json'));
            const handshake = JSON.parse(fs.readFileSync('site/.well-known/flashyos.json'));
            delete handshake.capabilities;
            console.log(JSON.stringify(conf.auditProperty({charter, handshake, manifest: charter})));
            """
        )
        self.assertEqual(out["level"], 1)
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
