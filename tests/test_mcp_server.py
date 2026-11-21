"""Slice 100 - wires mcp-server/'s own real, end-to-end Node test suite into
`python3 -m unittest discover`, so `tools/refresh.py`-style discovery and CI
see it without a human needing to know a second test runner exists. The real
assertions live in mcp-server/test.mjs, run over actual stdio with the
official @modelcontextprotocol/sdk client and server - this file only skips
gracefully (never fails the whole suite) when the npm step has not been run."""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = ROOT / "mcp-server"
NODE_MODULES = MCP_DIR / "node_modules"


@unittest.skipUnless(NODE_MODULES.is_dir(), "run: cd mcp-server && npm install --ignore-scripts")
class McpServerTest(unittest.TestCase):
    def test_the_real_stdio_server_suite_passes(self):
        result = subprocess.run(
            ["node", "--test", "test.mjs"],
            cwd=MCP_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("# fail 0", result.stdout)
        self.assertIn("# pass 9", result.stdout)


if __name__ == "__main__":
    unittest.main()
