"""Tests for the AAO manifest check - one per "Done when" in specs/slice-7/spec.md."""

import copy
import unittest
from pathlib import Path

from analystos.aao.validate import load_manifest, validate_manifest

REPO = Path(__file__).resolve().parents[1]


class ValidateManifestTest(unittest.TestCase):
    def setUp(self):
        self.good = {
            "aao": "0.1",
            "name": "Solwayholdings",
            "slug": "solwayholdings",
            "description": "Solwayholdings on the FlashyOS mesh.",
            "accountableTo": "calebsolway@gmail.com",
            "roles": [
                {
                    "name": "integration",
                    "family": "engineering",
                    "purpose": "Builds things.",
                    "capabilities": ["build"],
                    "humanApprovalAtOrAbove": "LOW",
                }
            ],
        }

    def test_the_real_manifest_file_passes(self):  # Done when #1
        manifest = load_manifest(REPO / "solwayholdings.aao.json")
        self.assertEqual(validate_manifest(manifest), [])

    def test_a_well_formed_manifest_passes(self):  # Done when #2
        self.assertEqual(validate_manifest(self.good), [])

    def test_missing_accountable_to_is_flagged(self):  # Done when #3
        bad = copy.deepcopy(self.good)
        del bad["accountableTo"]
        self.assertTrue(any("accountableTo" in p for p in validate_manifest(bad)))

    def test_placeholder_accountable_to_is_flagged(self):  # Done when #4
        bad = copy.deepcopy(self.good)
        bad["accountableTo"] = "TODO"
        self.assertTrue(any("accountableTo" in p for p in validate_manifest(bad)))

    def test_bad_slug_is_flagged(self):  # Done when #5
        bad = copy.deepcopy(self.good)
        bad["slug"] = "Solway Holdings!"
        self.assertTrue(any("slug" in p for p in validate_manifest(bad)))

    def test_vendor_role_name_is_flagged(self):  # Done when #6
        bad = copy.deepcopy(self.good)
        bad["roles"][0]["name"] = "claude-agent"
        self.assertTrue(any("vendor" in p for p in validate_manifest(bad)))

    def test_bad_approval_tier_is_flagged(self):  # Done when #7
        bad = copy.deepcopy(self.good)
        bad["roles"][0]["humanApprovalAtOrAbove"] = "whenever"
        self.assertTrue(
            any("humanApprovalAtOrAbove" in p for p in validate_manifest(bad))
        )

    def test_empty_roles_is_flagged(self):  # guard rail
        bad = copy.deepcopy(self.good)
        bad["roles"] = []
        self.assertTrue(any("roles" in p for p in validate_manifest(bad)))


if __name__ == "__main__":
    unittest.main()
