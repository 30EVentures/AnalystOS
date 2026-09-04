"""Tests for analystos.templates - one per "Done when" in specs/slice-19/spec.md."""

import unittest

from analystos.templates import build_asks, income_statement_asks, recognize_columns


class RecognizeColumnsTest(unittest.TestCase):
    def test_recognizes_common_aliases_case_and_underscore_insensitively(self):  # Done when #1
        found = recognize_columns(["Period", "Total Revenue", "cost_of_revenue", "NET INCOME"])
        self.assertEqual(
            found,
            {
                "period": "Period",
                "revenue": "Total Revenue",
                "cost_of_revenue": "cost_of_revenue",
                "net_income": "NET INCOME",
            },
        )

    def test_unrecognized_columns_are_absent_not_guessed(self):  # Done when #2
        found = recognize_columns(["period", "widgets_sold", "warehouse_zone"])
        self.assertEqual(found, {"period": "period"})


class IncomeStatementAsksTest(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"period": "FY2023", "revenue": 26974.0, "gross_profit": 15356.0,
             "operating_income": 4224.0, "net_income": 4368.0},
            {"period": "FY2024", "revenue": 60922.0, "gross_profit": 44301.0,
             "operating_income": 32972.0, "net_income": 29760.0},
        ]

    def test_generates_a_lookup_for_each_recognized_line_item_at_the_latest_period(self):  # Done when #3
        asks = income_statement_asks(self.rows)
        lookups = [a for a in asks if a.get("kind", "lookup") == "lookup"]
        self.assertEqual(len(lookups), 4)  # revenue, gross_profit, operating_income, net_income
        for a in lookups:
            self.assertEqual(a["where"], ["period", "FY2024"])  # the latest period
            self.assertEqual(a["format"], "usd")

    def test_generates_growth_for_revenue_and_net_income_when_two_periods_exist(self):  # Done when #4
        asks = income_statement_asks(self.rows)
        growth = [a for a in asks if a.get("kind") == "growth"]
        self.assertEqual({a["value_column"] for a in growth}, {"revenue", "net_income"})
        for a in growth:
            self.assertEqual(a["from"], "FY2023")
            self.assertEqual(a["to"], "FY2024")
            self.assertEqual(a["format"], "percent")

    def test_no_growth_asks_with_only_one_period(self):  # Done when #5
        asks = income_statement_asks(self.rows[:1])
        self.assertEqual([a for a in asks if a.get("kind") == "growth"], [])

    def test_generates_margins_when_the_inputs_are_recognized(self):  # Done when #6
        asks = income_statement_asks(self.rows)
        ratios = {a["text"]: a for a in asks if a.get("kind") == "ratio"}
        self.assertIn("Gross margin was {answer} in FY2024.", ratios)
        self.assertIn("Operating margin was {answer} in FY2024.", ratios)

    def test_operating_expenses_uses_the_plural_verb(self):  # caught in live demo
        rows = [{"period": "FY2024", "operating_expenses": 100.0}]
        asks = income_statement_asks(rows)
        self.assertEqual(asks[0]["text"], "FY2024 operating expenses were {answer}.")

    def test_missing_line_item_is_skipped_not_invented(self):  # Done when #7
        rows = [{"period": "FY2024", "revenue": 100.0}]  # no gross_profit etc.
        asks = income_statement_asks(rows)
        self.assertEqual(len(asks), 1)  # only the revenue lookup
        self.assertEqual(asks[0]["select"], "revenue")

    def test_no_period_column_raises(self):  # Done when #8
        with self.assertRaises(ValueError) as cm:
            income_statement_asks([{"revenue": 100.0}])
        self.assertIn("period", str(cm.exception))

    def test_empty_rows_raises(self):  # guard rail
        with self.assertRaises(ValueError):
            income_statement_asks([])


class BuildAsksTest(unittest.TestCase):
    def test_dispatches_by_name(self):
        rows = [{"period": "FY2024", "revenue": 100.0}]
        self.assertEqual(build_asks("income_statement", rows), income_statement_asks(rows))

    def test_unknown_template_raises(self):
        with self.assertRaises(ValueError):
            build_asks("cash_flow_statement", [{"period": "FY2024"}])


if __name__ == "__main__":
    unittest.main()
