"""Slice 108 - the role catalog. Every role the owner listed is in it, every one
is honestly 'planned', and the status ladder (planned -> built -> evaluated ->
available) is enforced: nothing is for hire without a passed evaluation and an
integer rate."""

import copy
import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

from analystos.catalog import FORMAT, load_catalog, summary, validate_catalog
from analystos.catalog.validate import MAX_RATE_CENTS

ROOT = Path(__file__).resolve().parents[1]

# The owner's list, 2026-11-23, verbatim and in the owner's order.
OWNER_ROLES = """\
Financial / Equity Research Analyst
Credit Analyst
Investment Banking Analyst
Market Research Analyst
Data / BI Analyst
Compliance / AML / KYC Analyst
Regulatory Reporting Analyst
Tax Associate
Staff Accountant / Bookkeeper
Accounts Payable / Receivable Clerk
Payroll Specialist
Paralegal / Contracts Administrator
Policy Analyst / Research Assistant
Content Writer / Copywriter
SEO / SEM Specialist
Social Media Coordinator
Recruiting Coordinator
Procurement Assistant
Claims Adjuster
Underwriting Assistant
Junior Software Developer
QA / Test Analyst
IT Help Desk / Technical Support Specialist
Sales Operations Analyst
Sales Development Representative (SDR)
Grants Administrator
Management Consulting Analyst
Business Analyst
Risk Advisory Associate
Technology Consulting Analyst
Regulatory / Compliance Advisory Associate
Financial Advisory / Transaction Services Analyst
Forensic / Investigations Analyst
Process Improvement / Operations Consulting Analyst
Data & Analytics Consulting Analyst
Digital Assets / Blockchain Advisory Associate
Audit Associate (External Audit)
Internal Audit Associate
Financial Planning & Analysis (FP&A) Analyst
Corporate Finance Analyst
Treasury Analyst
Fund Accountant
Trade Support / Middle Office Analyst
Operations Analyst (Banking / Capital Markets)
Model Validation Analyst
Market Risk Analyst
Operational Risk Analyst
Fraud Analyst
Sanctions Screening Analyst
Financial Crime Investigator (junior)
Regulatory Change Analyst
Third-Party / Vendor Risk Analyst
Cybersecurity Analyst (junior)
Information Security / GRC Analyst
Privacy / Data Protection Analyst
ESG / Sustainability Reporting Analyst
Pricing Analyst
Revenue Operations Analyst
Supply Chain / Logistics Analyst
Demand Planning Analyst
Contract / Procurement Analyst
Legal Operations Analyst
Corporate Communications Coordinator
Technical Writer
Product Analyst / Associate Product Manager
Project / Program Coordinator
Talent Acquisition Associate
Compensation & Benefits Analyst
Learning & Development Coordinator
HR Analyst (People Analytics)
Actuarial Analyst
Real Estate Analyst
Customer Success Associate""".splitlines()

CATALOG = load_catalog()


def _role(doc, role_id):
    return next(r for r in doc["roles"] if r["id"] == role_id)


class TheRealCatalogTest(unittest.TestCase):
    def test_it_is_valid(self):
        self.assertEqual(validate_catalog(CATALOG), [])

    def test_it_lists_exactly_the_owners_roles(self):
        self.assertEqual(len(OWNER_ROLES), 73)
        self.assertEqual(sorted(r["title"] for r in CATALOG["roles"]), sorted(OWNER_ROLES))

    def test_every_role_is_available_on_a_worked_example_and_none_claims_a_live_test(self):
        # Owner's decision 2026-11-23: every role live today, proven by worked examples in the
        # session; only one paid live test, which has not been run. "mock" only for a role
        # a worked example was written for; every other role says "mock-family" (Slice 119).
        own = set()
        for client in ROOT.glob("fixtures/*/*/client.json"):
            own.update(json.loads(client.read_text())["roles"])
        self.assertEqual(len(own), 13)
        for role in CATALOG["roles"]:
            with self.subTest(role=role["id"]):
                self.assertEqual(role["status"], "available")
                self.assertEqual(role["eval"]["method"], "mock" if role["id"] in own else "mock-family")
                self.assertTrue((ROOT / role["eval"]["set"]).is_dir(), role["eval"]["set"])
                self.assertEqual(role["rate_cents_per_engagement_hour"], "tbd")
                self.assertEqual(role["delivers_today"], "verified-deck")

    def test_thirteen_families_and_the_wave_split(self):
        self.assertEqual(len(CATALOG["families"]), 13)
        self.assertEqual(summary(CATALOG)["by_wave"], {"1": 24, "2": 23, "3": 13, "4": 13})
        self.assertEqual(summary(CATALOG)["by_boundary"],
                         {"deliverable-only": 41, "approval-gated": 13, "human-decides": 19})

    def test_approving_a_payment_stays_human(self):
        gated = _role(CATALOG, "accounts-payable-receivable-clerk")["gated_actions"]
        self.assertTrue(any("approving it stays human" in a for a in gated), gated)

    def test_regulated_decisions_stay_human(self):
        # Spot checks of roles whose decision must stay with a qualified human.
        for role_id in ("claims-adjuster", "tax-associate", "sanctions-screening-analyst",
                        "financial-equity-research-analyst", "compliance-aml-kyc-analyst",
                        "audit-associate-external-audit", "talent-acquisition-associate",
                        "credit-analyst", "paralegal-contracts-administrator"):
            with self.subTest(role=role_id):
                self.assertEqual(_role(CATALOG, role_id)["boundary"], "human-decides")

    def test_outward_actions_are_gated(self):
        for role_id in ("sales-development-representative-sdr", "social-media-coordinator",
                        "accounts-payable-receivable-clerk"):
            with self.subTest(role=role_id):
                role = _role(CATALOG, role_id)
                self.assertEqual(role["boundary"], "approval-gated")
                self.assertTrue(role["gated_actions"])

    def test_the_cli(self):
        done = subprocess.run([sys.executable, "-m", "analystos.catalog"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["roles"], 73)


class ValidatorRefusesTest(unittest.TestCase):
    """Each case changes one thing in a copy of the real catalog and requires a problem naming it."""

    def assertProblem(self, doc, needle):
        problems = validate_catalog(doc)
        self.assertTrue(any(needle in p for p in problems), f"expected a problem with {needle!r}, got {problems}")

    def mutated(self, change, role_id="management-consulting-analyst"):
        """A copy of the catalog with the role reset to planned, then changed."""
        doc = copy.deepcopy(CATALOG)
        role = _role(doc, role_id)
        role.update(status="planned", eval=None, rate_cents_per_engagement_hour=None)
        change(role, doc)
        return doc

    def test_not_a_catalog_at_all(self):
        for bad in (None, [], "x", 3):
            with self.subTest(bad=bad):
                self.assertTrue(validate_catalog(bad))

    def test_wrong_format(self):
        doc = copy.deepcopy(CATALOG)
        doc["format"] = "something/2"
        self.assertProblem(doc, f"format must be {FORMAT!r}")

    def test_an_empty_catalog_never_passes(self):
        doc = copy.deepcopy(CATALOG)
        doc["roles"] = []
        self.assertProblem(doc, "an empty catalog is never valid")

    def test_duplicate_and_malformed_ids(self):
        doc = copy.deepcopy(CATALOG)
        doc["roles"].append(copy.deepcopy(doc["roles"][0]))
        self.assertProblem(doc, "duplicate id")
        self.assertProblem(self.mutated(lambda r, d: r.update(id="Not A Slug")), "id must be a lowercase slug")

    def test_unknown_values(self):
        cases = (
            ("family", "astrology", "unknown family"),
            ("status", "live", "unknown status"),
            ("boundary", "anything-goes", "unknown boundary"),
            ("wave", 5, "wave must be one of"),
            ("wave", True, "wave must be one of"),
            ("deliverables", ["hologram"], "unknown deliverable"),
            ("deliverables", [], "deliverables must be a non-empty list"),
        )
        for key, value, needle in cases:
            with self.subTest(key=key, value=value):
                self.assertProblem(self.mutated(lambda r, d: r.update({key: value})), needle)

    def test_unknown_field(self):
        self.assertProblem(self.mutated(lambda r, d: r.update(price=100)), "unknown field 'price'")

    def test_human_decides_must_say_what_stays_human(self):
        for value in (None, [], [""]):
            with self.subTest(value=value):
                self.assertProblem(
                    self.mutated(lambda r, d: r.update(human_decides=value), role_id="claims-adjuster"),
                    "must list the decisions that stay human")

    def test_approval_gated_must_say_what_is_gated(self):
        self.assertProblem(
            self.mutated(lambda r, d: r.update(gated_actions=[]), role_id="social-media-coordinator"),
            "must list the actions that need approval")

    def test_planned_or_built_roles_carry_no_rate(self):
        for status in ("planned", "built"):
            with self.subTest(status=status):
                self.assertProblem(
                    self.mutated(lambda r, d: r.update(status=status, rate_cents_per_engagement_hour=5000)),
                    f"a {status} role cannot carry a rate")

    def test_evaluated_needs_an_eval_record(self):
        self.assertProblem(self.mutated(lambda r, d: r.update(status="evaluated")), "eval must be an object")

    def test_available_needs_a_passed_eval(self):
        def change(r, d):
            r.update(status="available", eval={"set": "evals/consulting-v1", "passed": False, "method": "mock"},
                     rate_cents_per_engagement_hour=5000)
        self.assertProblem(self.mutated(change), "its evaluation did not pass")

    def test_available_needs_a_positive_integer_rate(self):
        for rate in (None, 0, -100, 49.99, "5000", True):
            with self.subTest(rate=rate):
                def change(r, d, rate=rate):
                    r.update(status="available", eval={"set": "evals/consulting-v1", "passed": True, "method": "mock"},
                             rate_cents_per_engagement_hour=rate)
                self.assertProblem(self.mutated(change), "needs a positive integer rate")

    def test_tbd_pricing_and_an_unknown_eval_method(self):
        ok = {"set": "fixtures/consulting", "passed": True, "method": "mock"}
        self.assertEqual(validate_catalog(self.mutated(lambda r, d: r.update(
            status="available", eval=ok, rate_cents_per_engagement_hour="tbd"))), [])
        self.assertProblem(self.mutated(lambda r, d: r.update(
            status="available", eval=dict(ok, method="vibes"), rate_cents_per_engagement_hour="tbd")),
            "eval.method must be one of")
        self.assertProblem(self.mutated(lambda r, d: r.update(
            status="available", eval=dict(ok, method=None), rate_cents_per_engagement_hour="tbd")),
            "eval.method must be one of")
        self.assertProblem(self.mutated(lambda r, d: r.update(
            status="available", eval=ok, rate_cents_per_engagement_hour="free")), "needs a positive integer rate")
        self.assertProblem(self.mutated(lambda r, d: r.update(
            status="planned", rate_cents_per_engagement_hour="tbd")), "cannot carry a rate")
        self.assertProblem(self.mutated(lambda r, d: r.update(delivers_today="code")), "delivers_today must be one of")

    def test_a_correctly_available_role_passes(self):
        def change(r, d):
            r.update(status="available", eval={"set": "evals/consulting-v1", "passed": True, "method": "mock"},
                     rate_cents_per_engagement_hour=5000)
        self.assertEqual(validate_catalog(self.mutated(change)), [])

    def test_family_counts_must_match(self):
        doc = copy.deepcopy(CATALOG)
        doc["families"][0]["roles"] += 1
        self.assertProblem(doc, "declares")

    def test_each_remaining_rule_refuses(self):
        """One case per rule the first review found untested (it disabled each rule and no test broke)."""
        ok_eval = {"set": "evals/consulting-v1", "passed": True, "method": "mock"}
        cases = (
            ("eval.passed as the string 'true'", "management-consulting-analyst",
             lambda r, d: r.update(status="evaluated", eval={"set": "x", "passed": "true"}), "eval.passed must be true or false"),
            ("eval.passed as 1", "management-consulting-analyst",
             lambda r, d: r.update(status="available", eval={"set": "x", "passed": 1}, rate_cents_per_engagement_hour=5000),
             "eval.passed must be true or false"),
            ("eval without set", "management-consulting-analyst",
             lambda r, d: r.update(status="evaluated", eval={"passed": True, "method": "mock"}), "eval.set must name"),
            ("unknown eval field", "management-consulting-analyst",
             lambda r, d: r.update(status="evaluated", eval=dict(ok_eval, verified_by="me")), "unknown eval field"),
            ("evaluated with a rate", "management-consulting-analyst",
             lambda r, d: r.update(status="evaluated", eval=ok_eval, rate_cents_per_engagement_hour=5000),
             "an evaluated role is not for hire yet"),
            ("planned with an eval", "management-consulting-analyst",
             lambda r, d: r.update(eval=ok_eval), "a planned role cannot carry an eval record"),
            ("built with an eval", "management-consulting-analyst",
             lambda r, d: r.update(status="built", eval=ok_eval), "a built role cannot carry an eval record"),
            ("rate beyond what JSON readers keep exactly", "management-consulting-analyst",
             lambda r, d: r.update(status="available", eval=ok_eval, rate_cents_per_engagement_hour=MAX_RATE_CENTS + 1),
             "needs a positive integer rate"),
            ("human_decides on another boundary", "management-consulting-analyst",
             lambda r, d: r.update(human_decides=["x"]), "human_decides is only for human-decides roles"),
            ("gated_actions on another boundary", "management-consulting-analyst",
             lambda r, d: r.update(gated_actions=["x"]), "gated_actions is only for approval-gated roles"),
            ("missing required field", "management-consulting-analyst",
             lambda r, d: r.pop("status"), "missing 'status'"),
            ("empty title", "management-consulting-analyst", lambda r, d: r.update(title=" "), "title must be a non-empty string"),
            ("id with a trailing newline", "management-consulting-analyst",
             lambda r, d: r.update(id="business-analyst-two\n"), "id must be a lowercase slug"),
            ("family as a list", "management-consulting-analyst", lambda r, d: r.update(family=["consulting"]), "unknown family"),
            ("family as an object", "management-consulting-analyst", lambda r, d: r.update(family={"id": 1}), "unknown family"),
            ("duplicate title", "management-consulting-analyst",
             lambda r, d: r.update(title="Business Analyst"), "duplicate title"),
            ("gated role outside wave 3", "social-media-coordinator", lambda r, d: r.update(wave=2), "wave 3 is exactly"),
            ("ungated role in wave 3", "management-consulting-analyst", lambda r, d: r.update(wave=3), "wave 3 is exactly"),
            ("wave-4 role that is not human-decides", "claims-adjuster",
             lambda r, d: (r.update(boundary="deliverable-only"), r.pop("human_decides")), "a wave-4 role must be human-decides"),
            ("duplicate family id", "management-consulting-analyst",
             lambda r, d: d["families"].append(dict(d["families"][0])), "duplicate id"),
            ("family wave not its earliest", "management-consulting-analyst",
             lambda r, d: d["families"][1].update(wave=2), "wave must be the earliest wave of its roles"),
            ("family wave out of range", "management-consulting-analyst",
             lambda r, d: d["families"][0].update(wave=9), "family 'research-reporting': wave must be one of"),
            ("family with an empty skill", "management-consulting-analyst",
             lambda r, d: d["families"][0].update(skill=""), "title and skill must be non-empty"),
            ("family count as a string", "management-consulting-analyst",
             lambda r, d: d["families"][0].update(roles="5"), "roles must be a positive integer count"),
            ("unknown top-level field", "management-consulting-analyst",
             lambda r, d: d.update(available_roles=["all"]), "unknown top-level field"),
            ("statuses list out of step with the code", "management-consulting-analyst",
             lambda r, d: d.update(statuses=["planned", "available"]), "statuses must be exactly"),
            ("boundaries map out of step with the code", "management-consulting-analyst",
             lambda r, d: d["boundaries"].pop("human-decides"), "boundaries must describe exactly"),
            ("waves map out of step with the code", "management-consulting-analyst",
             lambda r, d: d["waves"].update({"5": "x"}), "waves must describe exactly"),
        )
        for name, role_id, change, needle in cases:
            with self.subTest(case=name):
                self.assertProblem(self.mutated(change, role_id=role_id), needle)

    def test_no_json_value_makes_it_raise(self):
        junk = (None, True, 0, 1.5, "", "x", [], [1], {}, {"a": 1}, [[]], {"set": []})
        fields = sorted({k for r in CATALOG["roles"] for k in r})
        for field in fields:
            for value in junk:
                doc = copy.deepcopy(CATALOG)
                doc["roles"][0][field] = value
                validate_catalog(doc)  # must not raise
        for field in ("id", "title", "skill", "wave", "roles"):
            for value in junk:
                doc = copy.deepcopy(CATALOG)
                doc["families"][0][field] = value
                validate_catalog(doc)
        for key in ("format", "statuses", "boundaries", "waves", "families", "roles"):
            for value in junk:
                doc = copy.deepcopy(CATALOG)
                doc[key] = value
                validate_catalog(doc)

    def test_duplicate_json_keys_are_refused_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roles.json"
            path.write_text('{"format": "x", "format": "y"}')
            with self.assertRaises(ValueError):
                load_catalog(path)

    def test_malformed_entries_are_reported_not_raised(self):
        doc = copy.deepcopy(CATALOG)
        doc["roles"][0] = "a string, not a role"
        doc["families"][0] = None
        problems = validate_catalog(doc)
        self.assertTrue(any("must be an object" in p for p in problems), problems)
        self.assertTrue(any("must have exactly the fields" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
