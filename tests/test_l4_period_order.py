"""Overnight round 4 - chronological order of period labels.

``_period_sort_key`` understood quarters ("Q3 2026"), fiscal years ("FY2026") and bare years,
and returned (0, 0) for everything else. But the period-token regex also recognises half-years
("H1 2025", "2H 2025") and months ("Mar 2025", "September 2025"), so for those the "sorted"
series stayed in document order. Financial tables list the newest period first about as often
as last, so a series of months written newest-first was read oldest-last: a rising metric came
out as "has declined for N consecutive periods", and the "most recent" KPI was the first one
seen instead of the latest. The wrong direction word is a verified-looking sentence that is false.
"""

import unittest

from analystos.l4.deterministic_report import (
    _period_sort_key, _select_kpis, _select_time_series, _trend_sentences,
)
from tests.test_l4_deterministic_report import _quote


def revenue(labels_and_values):
    return [_quote(f"{label} Revenue", value, "usd", f"cite-{i}") for i, (label, value) in enumerate(labels_and_values)]


class PeriodSortKeyTest(unittest.TestCase):
    def assertAscending(self, *tokens):
        keys = [_period_sort_key(t) for t in tokens]
        self.assertEqual(keys, sorted(keys), tokens)
        self.assertEqual(len(set(keys)), len(keys), f"distinct periods need distinct keys: {tokens}")

    def test_half_years_sort_by_year_then_half(self):
        self.assertAscending("H1 2025", "H2 2025", "H1 2026", "H2 2026")
        self.assertAscending("1H 2025", "2H 2025", "1H 2026")
        self.assertAscending("H1 '25", "H2 '25", "H1 '26")

    def test_months_sort_by_year_then_month(self):
        self.assertAscending("Jan 2025", "Feb 2025", "Mar 2025", "Sep 2025", "Dec 2025", "Jan 2026")
        self.assertAscending("March 2025", "September 2025", "December 2025")
        self.assertAscending("Sept. 2025", "Oct 2025")
        self.assertAscending("Dec '24", "Jan '25")

    def test_the_existing_forms_are_unchanged(self):
        self.assertEqual(_period_sort_key("Q3 2026"), (2026, 3))
        self.assertEqual(_period_sort_key("Q3 FY2026"), (2026, 3))
        self.assertEqual(_period_sort_key("FY2026"), (2026, 0))
        self.assertEqual(_period_sort_key("2025"), (2025, 0))
        self.assertEqual(_period_sort_key("not a period"), (0, 0))


class SeriesOrderTest(unittest.TestCase):
    NEWEST_FIRST = revenue([("Mar 2025", 140.0), ("Feb 2025", 120.0), ("Jan 2025", 100.0)])
    OLDEST_FIRST = revenue([("Jan 2025", 100.0), ("Feb 2025", 120.0), ("Mar 2025", 140.0)])
    HALVES_NEWEST_FIRST = revenue([("H2 2025", 300.0), ("H1 2025", 200.0), ("H2 2024", 100.0)])

    def test_a_series_listed_newest_first_is_still_read_oldest_first(self):
        for segments in (self.NEWEST_FIRST, self.OLDEST_FIRST):
            tokens = [token for token, _ in _select_time_series(segments)]
            self.assertEqual(tokens, ["Jan 2025", "Feb 2025", "Mar 2025"])

    def test_a_rising_series_is_never_described_as_declining(self):
        for segments in (self.NEWEST_FIRST, self.OLDEST_FIRST, self.HALVES_NEWEST_FIRST):
            text = _trend_sentences(segments)[0]["text"]
            self.assertIn("grown", text)
            self.assertNotIn("declined", text)

    def test_the_headline_kpi_is_the_latest_period_not_the_first_listed(self):
        for segments, latest in ((self.NEWEST_FIRST, 0), (self.OLDEST_FIRST, 2), (self.HALVES_NEWEST_FIRST, 0)):
            self.assertEqual(_select_kpis(segments)[0]["value_fact"], latest)


if __name__ == "__main__":
    unittest.main()
