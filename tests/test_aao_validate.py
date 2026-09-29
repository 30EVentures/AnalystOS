"""Tests for the AAO manifest check - one per "Done when" in specs/slice-7/spec.md."""

import copy
import unittest
from pathlib import Path

from analystos.aao import kit
from analystos.aao.__main__ import main as cli_main
from analystos.aao.validate import (
    SCHEMA_SHA256, SCHEMA_PATH, SUPPORTED_KEYWORDS, load_manifest, load_schema, schema_keywords,
    validate_charter, validate_manifest,
)
import hashlib
import io
import json

REPO = Path(__file__).resolve().parents[1]


class ValidateManifestTest(unittest.TestCase):
    def setUp(self):
        self.good = {
            "aao": "0.1",
            "name": "Solwayholdings",
            "slug": "solwayholdings",
            "description": "Solwayholdings on the FlashyOS mesh.",
            "accountableTo": "30eventures@gmail.com",
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


def _good():
    return {
        "aao": "0.1", "name": "X", "slug": "example", "description": "d",
        "accountableTo": "a@b.co",
        "roles": [{"name": "release", "purpose": "p", "capabilities": ["deploy"],
                   "family": "engineering", "humanApprovalAtOrAbove": "LOW"}],
    }


def _with(**kw):
    d = _good()
    d.update(kw)
    return d


def _role(**kw):
    d = _good()
    d["roles"][0].update(kw)
    return d


_REPO = {"name": "r1", "url": "github.com/x/r1", "holds": ["a"]}


class PublishedSchemaProbesTest(unittest.TestCase):
    """Slice 58 Done-when #1: the 21 probe documents from
    docs/flashyos-alignment-2026-09-25.md, each with the verdict the published
    schema and its documented cross-field rules give. (The two role-name
    codename/word-count probes are decided by the naming rules.)"""

    PROBES = [
        ("baseline", _good(), True),
        ("role omits family and tier (both optional)", (lambda d: (d["roles"][0].pop("family"), d["roles"][0].pop("humanApprovalAtOrAbove"), d)[-1])(_good()), True),
        ("tier CRITICAL is a real value", _role(humanApprovalAtOrAbove="CRITICAL"), True),
        ("tier NONE is not in the spec", _role(humanApprovalAtOrAbove="NONE"), False),
        ("family banana is not in the closed list", _role(family="banana"), False),
        ("family finance is real", _role(family="finance"), True),
        ("accountableTo must be an email", _with(accountableTo="30E Ventures"), False),
        ("accountableTo template placeholder", _with(accountableTo="you@example.com"), False),
        ("unknown top-level key", _with(**{"_comment": "hi"}), False),
        ("x- extension key is allowed", _with(**{"x-comment": "hi"}), True),
        ("aao version 0.2 is not 0.1", _with(aao="0.2"), False),
        ("slug with a double hyphen", _with(slug="a--b"), False),
        ("two-character slug (no minimum in the spec)", _with(slug="ab"), True),
        ("slug starting with a digit is allowed", _with(slug="2fast"), True),
        ("blank description", _with(description="   "), False),
        ("network block", _with(network={"offers": ["a"], "wants": ["b"]}), True),
        ("escalation naming an existing role", _with(escalation="release"), True),
        ("escalation naming a missing role", _with(escalation="ghost"), False),
        ("duplicate role names", _with(roles=[_good()["roles"][0], _good()["roles"][0]]), False),
        ("role with an unknown key", _role(title="x"), False),
        ("role with measure and worksIn plus a declared repo",
         _with(repositories=[_REPO], roles=[{"name": "release", "purpose": "p", "capabilities": ["deploy"],
                                              "family": "engineering", "humanApprovalAtOrAbove": "LOW",
                                              "measure": "m", "worksIn": ["r1"]}]), True),
        ("role name with four words", _role(name="release-abc-def-ghi"), False),
    ]

    def test_every_probe_gets_the_published_verdict(self):
        for label, doc, expected in self.PROBES:
            with self.subTest(label=label):
                self.assertEqual(not validate_manifest(doc), expected, validate_manifest(doc))


class CrossFieldRulesTest(unittest.TestCase):
    def codes(self, doc):
        return {p.code for p in validate_charter(doc) if p.level == "error"}

    def test_worksin_must_name_a_declared_repository(self):
        doc = _role(worksIn=["nope"])
        self.assertIn("aao.role.worksin_undeclared", self.codes(doc))

    def test_at_most_one_default_repository(self):
        doc = _with(repositories=[dict(_REPO, default=True), dict(_REPO, name="r2", default=True)])
        self.assertIn("aao.repository.multiple_default", self.codes(doc))

    def test_every_repository_needs_an_owning_role(self):
        doc = _with(repositories=[_REPO])
        self.assertIn("aao.repository.no_owner", self.codes(doc))

    def test_vendor_and_placeholder_role_names(self):
        self.assertIn("aao.role.name.vendor", self.codes(_role(name="claude-reviewer")))
        self.assertIn("aao.role.name.placeholder", self.codes(_role(name="todo")))


class ProblemsAreMachineReadableTest(unittest.TestCase):
    def test_codes_levels_and_paths_are_stable(self):
        problems = validate_charter(_role(humanApprovalAtOrAbove="whenever"))
        (p,) = [q for q in problems if q.level == "error"]
        self.assertEqual((p.code, p.path), ("aao.schema.enum", "/roles/0/humanApprovalAtOrAbove"))
        self.assertEqual(set(p.to_dict()), {"code", "level", "path", "message"})

    def test_a_charter_with_only_warnings_is_valid(self):
        doc = _good()
        problems = validate_charter(doc)
        self.assertEqual([p.code for p in problems], ["aao.role.no_measure"])
        self.assertEqual(problems[0].level, "warning")
        self.assertEqual(validate_manifest(doc), [])

    def test_a_non_object_is_refused_not_crashed(self):
        for bad in (None, [], "x", 3):
            with self.subTest(bad=bad):
                self.assertEqual(validate_charter(bad)[0].code, "aao.schema.type")


class PinnedSchemaTest(unittest.TestCase):
    """Slice 58 Done-when #2."""

    def test_hash_matches_the_pin(self):
        self.assertEqual(hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(), SCHEMA_SHA256)
        self.assertEqual(load_schema()["$id"], "https://flashyos.com/aao.schema.json")

    def test_the_checker_supports_every_keyword_the_schema_uses(self):
        unsupported = schema_keywords(load_schema()) - SUPPORTED_KEYWORDS
        self.assertEqual(unsupported, set())

    def test_a_modified_schema_is_refused(self):
        import analystos.aao.validate as v
        original = v.SCHEMA_SHA256
        v.SCHEMA_SHA256 = "0" * 64
        try:
            with self.assertRaises(RuntimeError):
                v.load_schema()
        finally:
            v.SCHEMA_SHA256 = original


class CliAndKitTest(unittest.TestCase):
    """Slice 58 Done-when #4."""

    def test_cli_valid_file(self):
        out = io.StringIO()
        code = cli_main([str(REPO / "solwayholdings.aao.json")], stdout=out)
        result = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(result["valid"])
        self.assertEqual(result["schema"]["sha256"], SCHEMA_SHA256)

    def test_cli_invalid_stdin(self):
        out = io.StringIO()
        code = cli_main(["-"], stdin=io.StringIO(json.dumps(_role(humanApprovalAtOrAbove="NONE"))), stdout=out)
        result = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result["errors"][0]["code"], "aao.schema.enum")

    def test_cli_unreadable_input(self):
        out = io.StringIO()
        self.assertEqual(cli_main(["-"], stdin=io.StringIO("{nope"), stdout=out), 2)
        self.assertEqual(cli_main([], stdout=io.StringIO()), 2)
        self.assertEqual(cli_main(["/no/such/file.json"], stdout=io.StringIO()), 2)

    def test_kit_adapter_over_the_line_protocol(self):
        lines = [
            json.dumps({"id": "ok", "set": "s", "input": _good()}),
            json.dumps({"id": "bad", "set": "s", "input": _role(family="banana")}),
            "",
            "a banner, not a case",
            json.dumps({"no": "id"}),
        ]
        out = io.StringIO()
        kit.serve(lines, out)
        answers = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(answers, [
            {"id": "ok", "valid": True, "codes": []},
            {"id": "bad", "valid": False, "codes": ["aao.schema.enum"]},
        ])

    def test_kit_adapter_runs_as_a_real_subprocess(self):
        import subprocess, sys
        case = json.dumps({"id": "one", "set": "s", "input": _good()}) + "\n"
        done = subprocess.run([sys.executable, "-m", "analystos.aao.kit"], input=case, text=True,
                              capture_output=True, cwd=REPO, timeout=30)
        self.assertEqual(json.loads(done.stdout), {"id": "one", "valid": True, "codes": []})


if __name__ == "__main__":
    unittest.main()
