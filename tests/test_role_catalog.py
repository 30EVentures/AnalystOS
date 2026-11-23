"""Slice 108 - the role catalog. Every role the owner listed is in it, every one
is honestly 'planned', and the status ladder (planned -> built -> evaluated ->
available) is enforced: nothing is for hire without a passed evaluation and an
integer rate."""

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from analystos.catalog import FORMAT, load_catalog, summary, validate_catalog

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

    def test_every_role_is_honestly_planned(self):
        for role in CATALOG["roles"]:
            with self.subTest(role=role["id"]):
                self.assertEqual(role["status"], "planned")
                self.assertIsNone(role["eval"])
                self.assertIsNone(role["rate_cents_per_engagement_hour"])

    def test_thirteen_families_and_the_wave_split(self):
        self.assertEqual(len(CATALOG["families"]), 13)
        self.assertEqual(summary(CATALOG)["by_wave"], {"1": 24, "2": 23, "3": 13, "4": 13})

    def test_regulated_decisions_stay_human(self):
        # Spot checks of roles whose decision must stay with a qualified human.
        for role_id in ("claims-adjuster", "tax-associate", "sanctions-screening-analyst",
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
        doc = copy.deepcopy(CATALOG)
        change(_role(doc, role_id), doc)
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
            r.update(status="available", eval={"set": "evals/consulting-v1", "passed": False},
                     rate_cents_per_engagement_hour=5000)
        self.assertProblem(self.mutated(change), "its evaluation did not pass")

    def test_available_needs_a_positive_integer_rate(self):
        for rate in (None, 0, -100, 49.99, "5000", True):
            with self.subTest(rate=rate):
                def change(r, d, rate=rate):
                    r.update(status="available", eval={"set": "evals/consulting-v1", "passed": True},
                             rate_cents_per_engagement_hour=rate)
                self.assertProblem(self.mutated(change), "needs a positive integer rate")

    def test_a_correctly_available_role_passes(self):
        def change(r, d):
            r.update(status="available", eval={"set": "evals/consulting-v1", "passed": True},
                     rate_cents_per_engagement_hour=5000)
        self.assertEqual(validate_catalog(self.mutated(change)), [])

    def test_family_counts_must_match(self):
        doc = copy.deepcopy(CATALOG)
        doc["families"][0]["roles"] += 1
        self.assertProblem(doc, "declares")

    def test_malformed_entries_are_reported_not_raised(self):
        doc = copy.deepcopy(CATALOG)
        doc["roles"][0] = "a string, not a role"
        doc["families"][0] = None
        problems = validate_catalog(doc)
        self.assertTrue(any("must be an object" in p for p in problems), problems)
        self.assertTrue(any("must have exactly the fields" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
