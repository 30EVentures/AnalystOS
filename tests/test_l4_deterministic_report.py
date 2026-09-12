"""Tests for L4's mandatory deterministic floor - specs/slice-52/spec.md.
No model client anywhere in this file - every function under test is
zero-model-dependency by construction.
"""

import unittest

from analystos.l4.deterministic_report import (
    _benchmark_sentences,
    _disclosure_gap_sentences,
    _relationship_sentences,
    _select_bar_fallback,
    _select_bridge,
    _select_chart,
    _select_kpis,
    _select_time_series,
    _trend_sentences,
    build_deterministic_report,
)
from analystos.l4.rich_export import render_rich_report

SRC = "f8d19a56" * 8


def _quote(label, value, fmt, citation, horizon="reported"):
    return {"type": "quote", "horizon": horizon, "label": label, "value": value,
            "format": fmt, "citation": citation}


def _growth(label, value, from_citation, to_citation):
    return {"type": "computed", "operation": "growth_percent", "horizon": "reported",
            "label": label, "value": value, "format": "percent",
            "citation": [from_citation, to_citation]}


def _remainder(label, value, end_citation, start_citation, *component_citations):
    return {"type": "computed", "operation": "remainder", "horizon": "reported",
            "label": label, "value": value, "format": "usd",
            "citation": [end_citation, start_citation, *component_citations]}


REVENUE_SERIES = [
    _quote("Q3 2025 Revenue", 402_000_000.0, "usd", "cite-q3-25"),
    _quote("Q4 2025 Revenue", 410_000_000.0, "usd", "cite-q4-25"),
    _quote("Q1 2026 Revenue", 432_000_000.0, "usd", "cite-q1-26"),
    _quote("Q2 2026 Revenue", 455_000_000.0, "usd", "cite-q2-26"),
    _quote("Q3 2026 Revenue", 498_000_000.0, "usd", "cite-q3-26"),
]


class KpiSelectionTest(unittest.TestCase):
    def test_only_one_kpi_per_distinct_metric_not_one_per_period(self):
        kpis = _select_kpis(REVENUE_SERIES)
        self.assertEqual(len(kpis), 1)
        self.assertEqual(kpis[0]["value_fact"], 4)  # the latest (Q3 2026) quote

    def test_a_matching_growth_percent_fact_is_paired_as_the_delta(self):
        segments = REVENUE_SERIES + [
            _growth("Revenue growth QoQ", 9.5, "cite-q2-26", "cite-q3-26"),
        ]
        kpis = _select_kpis(segments)
        self.assertEqual(kpis[0]["delta_fact"], 5)

    def test_a_difference_or_remainder_never_becomes_a_kpi_delta(self):
        segments = [
            _quote("Q3 2026 Revenue", 498_000_000.0, "usd", "cite-q3-26"),
            _quote("Q2 2026 Revenue", 455_000_000.0, "usd", "cite-q2-26"),
            _remainder("Some remainder", 43_000_000.0, "cite-q3-26", "cite-q2-26"),
        ]
        kpis = _select_kpis(segments)
        headline = next(k for k in kpis if k["value_fact"] == 0)
        self.assertEqual(headline["delta_fact"], -1)

    def test_diverse_metrics_each_get_their_own_kpi(self):
        segments = REVENUE_SERIES + [
            _quote("Q3 2026 Net Income", 19_600_000.0, "usd", "cite-ni-26"),
            _quote("Gross margin Q3 2026", 58.7, "percent", "cite-gm-26"),
        ]
        kpis = _select_kpis(segments)
        self.assertEqual(len(kpis), 3)

    def test_capped_at_five(self):
        segments = [
            _quote(f"Metric {i}", float(i), "number", f"cite-{i}")
            for i in range(10)
        ]
        self.assertEqual(len(_select_kpis(segments)), 5)


class BenchmarkSentenceTest(unittest.TestCase):
    def test_the_current_value_gets_the_benchmark_sentence_not_the_baseline(self):
        # Found while building this slice: attaching a growth_percent
        # fact to *either* cited quote produced "Q2 revenue was $455.0M,
        # which grew 9.5%" - Q2 didn't grow, Q3 did. Only the
        # destination/current value may carry the sentence.
        segments = [
            _quote("Q3 2026 Revenue", 498_000_000.0, "usd", "cite-q3-26"),
            _quote("Q2 2026 Revenue", 455_000_000.0, "usd", "cite-q2-26"),
            _growth("Revenue growth QoQ", 9.5, "cite-q2-26", "cite-q3-26"),
        ]
        sentences = _benchmark_sentences(segments)
        texts = [s["text"] for s in sentences]
        self.assertTrue(any("{{0}}" in t and "grew" in t for t in texts))
        self.assertFalse(any("{{1}}" in t and "grew" in t for t in texts))

    def test_a_decline_uses_declined_not_grew(self):
        segments = [
            _quote("Q3 2026 Net Income", 19_600_000.0, "usd", "cite-ni-26"),
            _quote("Q3 2025 Net Income", 22_400_000.0, "usd", "cite-ni-25"),
            _growth("Net income growth YoY", -12.5, "cite-ni-25", "cite-ni-26"),
        ]
        sentences = _benchmark_sentences(segments)
        text = sentences[0]["text"]
        self.assertIn("declined", text)
        self.assertNotIn("grew", text)

    def test_a_difference_or_remainder_comparison_gets_no_direction_verb(self):
        # Gate 1's own rule: a difference/remainder's sign isn't a
        # reliable direction - this generator must never claim one.
        segments = [
            _quote("End", 142_000_000.0, "usd", "cite-end"),
            _quote("Start", 88_000_000.0, "usd", "cite-start"),
            _remainder("Organic growth", 20_000_000.0, "cite-end", "cite-start"),
        ]
        sentences = _benchmark_sentences(segments)
        text = sentences[0]["text"]
        self.assertNotIn("grew", text)
        self.assertNotIn("declined", text)
        self.assertIn("a change of", text)

    def test_two_comparisons_are_stacked_in_one_sentence(self):
        segments = [
            _quote("Q3 2026 Revenue", 498_000_000.0, "usd", "cite-q3-26"),
            _quote("Q2 2026 Revenue", 455_000_000.0, "usd", "cite-q2-26"),
            _quote("Q3 2025 Revenue", 402_000_000.0, "usd", "cite-q3-25"),
            _growth("QoQ", 9.5, "cite-q2-26", "cite-q3-26"),
            _growth("YoY", 23.9, "cite-q3-25", "cite-q3-26"),
        ]
        sentences = _benchmark_sentences(segments)
        text = next(s["text"] for s in sentences if "{{0}}" in s["text"])
        self.assertIn("{{3}}", text)
        self.assertIn("{{4}}", text)

    def test_a_quote_with_no_comparison_produces_no_sentence(self):
        segments = [_quote("Lonely fact", 1.0, "number", "cite-only")]
        self.assertEqual(_benchmark_sentences(segments), [])


class TrendSentenceTest(unittest.TestCase):
    def test_a_consistent_uptrend_is_described_as_grown(self):
        sentences = _trend_sentences(REVENUE_SERIES)
        self.assertEqual(len(sentences), 1)
        text = sentences[0]["text"]
        self.assertIn("grown", text)
        self.assertIn("4 consecutive periods", text)
        self.assertIn("{{0}}", text)
        self.assertIn("{{4}}", text)

    def test_a_consistent_downtrend_is_described_as_declined(self):
        segments = [
            _quote("Q3 2025 Margin", 61.5, "percent", "cite-m1"),
            _quote("Q4 2025 Margin", 61.2, "percent", "cite-m2"),
            _quote("Q1 2026 Margin", 60.8, "percent", "cite-m3"),
        ]
        text = _trend_sentences(segments)[0]["text"]
        self.assertIn("declined", text)

    def test_a_non_monotonic_series_gets_no_trend_claim(self):
        # up, then down - never claim "N consecutive" for a series that
        # doesn't actually move the same direction throughout.
        segments = [
            _quote("Q3 2025 X", 100.0, "usd", "cite-a"),
            _quote("Q4 2025 X", 110.0, "usd", "cite-b"),
            _quote("Q1 2026 X", 90.0, "usd", "cite-c"),
        ]
        text = _trend_sentences(segments)[0]["text"]
        self.assertNotIn("consecutive", text)
        self.assertNotIn("grown", text)
        self.assertNotIn("declined", text)

    def test_fewer_than_three_periods_produces_no_trend_sentence(self):
        segments = REVENUE_SERIES[:2]
        self.assertEqual(_trend_sentences(segments), [])

    def test_an_adversarial_flipped_sign_never_produces_a_wrong_claim(self):
        # A trend generator that (hypothetically, via a bug) computed
        # direction from something other than the segments' own values
        # could claim "grown" for a series that actually declined - this
        # proves the real generator can't: it derives the word directly
        # from the data's own diffs, so a declining series is described
        # as declined, never as grown, however the labels are named.
        segments = [
            _quote("Q3 2025 Revenue", 500_000_000.0, "usd", "cite-a"),
            _quote("Q4 2025 Revenue", 480_000_000.0, "usd", "cite-b"),
            _quote("Q1 2026 Revenue", 460_000_000.0, "usd", "cite-c"),
        ]
        text = _trend_sentences(segments)[0]["text"]
        self.assertIn("declined", text)
        self.assertNotIn("grown", text)


class ChronologyNotPositionTest(unittest.TestCase):  # Slice 52, found live 2026-09-12
    """A real live run against a real document produced "Net Income Q3
    2025 was $22.4M, a change of $-2.8M" - attached to the *older*
    quarter, because a plain two-operand "difference" fact has no
    operand-order convention at all (unlike growth_percent, there's no
    swap-and-retry at the verification layer for difference/remainder,
    but that doesn't mean the model reliably puts one specific operand
    first for an ordinary two-point comparison - it just means whichever
    order it used happened to pass). Fixed by determining "current" from
    each candidate's own period token, never from citation position."""

    def test_a_plain_two_point_difference_attaches_to_the_later_quarter_regardless_of_operand_order(self):
        # operands/citations deliberately given [older, newer] - the
        # *opposite* of what the old, buggy position-based rule assumed.
        segments = [
            _quote("Net Income Q3 2025", 22_400_000.0, "usd", "cite-2025"),
            _quote("Net Income Q3 2026", 19_600_000.0, "usd", "cite-2026"),
            {"type": "computed", "operation": "difference", "horizon": "reported",
             "label": "Net Income Change YoY", "value": -2_800_000.0, "format": "usd",
             "citation": ["cite-2025", "cite-2026"]},  # older first, on purpose
        ]
        sentences = _benchmark_sentences(segments)
        text = next(s["text"] for s in sentences if "{{2}}" in s["text"])
        self.assertIn("{{1}}", text)     # Q3 2026 (the later quarter) gets the sentence
        self.assertNotIn("{{0}}", text)  # Q3 2025 (the baseline) does not

    def test_an_ordinary_two_point_difference_is_never_treated_as_a_bridge(self):
        # No named component at all - this must never produce a
        # "moved from X to Y" relationship sentence; that's reserved for
        # a genuine start -> components -> end bridge (3+ citations).
        segments = [
            _quote("Net Income Q3 2025", 22_400_000.0, "usd", "cite-2025"),
            _quote("Net Income Q3 2026", 19_600_000.0, "usd", "cite-2026"),
            {"type": "computed", "operation": "difference", "horizon": "reported",
             "label": "Net Income Change YoY", "value": -2_800_000.0, "format": "usd",
             "citation": ["cite-2025", "cite-2026"]},
        ]
        self.assertIsNone(_select_bridge(segments))
        self.assertEqual(_relationship_sentences(segments), [])

    def test_kpi_delta_pairing_is_also_order_independent(self):
        segments = [
            _quote("Net Income Q3 2025", 22_400_000.0, "usd", "cite-2025"),
            _quote("Net Income Q3 2026", 19_600_000.0, "usd", "cite-2026"),
            _growth("Net income growth YoY", -12.5, "cite-2025", "cite-2026"),
        ]
        kpis = _select_kpis(segments)
        headline = next(k for k in kpis if k["value_fact"] == 1)  # Q3 2026, the later one
        self.assertEqual(headline["delta_fact"], 2)


class RelationshipSentenceTest(unittest.TestCase):
    def test_a_genuine_bridge_produces_a_relationship_sentence(self):
        segments = [
            _quote("Data Services end", 142_000_000.0, "usd", "cite-end"),
            _quote("Data Services start", 88_000_000.0, "usd", "cite-start"),
            _quote("Halyard contribution", 34_000_000.0, "usd", "cite-halyard"),
            _remainder("Data Services organic growth", 20_000_000.0,
                       "cite-end", "cite-start", "cite-halyard"),
        ]
        sentences = _relationship_sentences(segments)
        self.assertEqual(len(sentences), 1)
        text = sentences[0]["text"]
        self.assertIn("{{1}}", text)  # start
        self.assertIn("{{0}}", text)  # end
        self.assertIn("{{2}}", text)  # named component
        self.assertIn("{{3}}", text)  # the remainder itself
        self.assertIn("Halyard", text)

    def test_no_bridge_shape_produces_no_relationship_sentence(self):
        self.assertEqual(_relationship_sentences(REVENUE_SERIES), [])


class DisclosureGapSentenceTest(unittest.TestCase):
    def test_a_missing_checklist_item_is_flagged(self):
        sentences = _disclosure_gap_sentences(REVENUE_SERIES)
        texts = [s["text"] for s in sentences]
        self.assertTrue(any("Earnings per share" in t for t in texts))

    def test_a_mentioned_metric_is_not_flagged(self):
        segments = REVENUE_SERIES + [
            _quote("Gross margin", 58.7, "percent", "Consolidated gross margin was 58.7%"),
        ]
        texts = [s["text"] for s in _disclosure_gap_sentences(segments)]
        self.assertFalse(any("Gross margin" in t for t in texts))

    def test_capped_at_five(self):
        # every checklist item present today is 5 or fewer; this proves
        # the cap itself, not today's exact list length
        segments = [_quote("x", 1.0, "number", "x")]
        self.assertLessEqual(len(_disclosure_gap_sentences(segments)), 5)


class ChartSelectionTest(unittest.TestCase):
    def test_a_bridge_is_preferred_when_one_exists(self):
        segments = [
            _quote("End", 142_000_000.0, "usd", "cite-end"),
            _quote("Start", 88_000_000.0, "usd", "cite-start"),
            _quote("Component", 34_000_000.0, "usd", "cite-comp"),
            _remainder("Remainder", 20_000_000.0, "cite-end", "cite-start", "cite-comp"),
            *REVENUE_SERIES,  # also has a time series available - bridge still wins
        ]
        self.assertIsNotNone(_select_bridge(segments))
        chart = _select_chart(segments)
        indices = [p["fact_index"] for p in chart["series"]]
        self.assertEqual(indices, [1, 3, 2, 0])

    def test_a_time_series_is_used_when_no_bridge_exists(self):
        chart = _select_chart(REVENUE_SERIES)
        labels = [p["label"] for p in chart["series"]]
        self.assertEqual(labels, ["Q3 2025", "Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026"])

    def test_same_format_bar_fallback_when_neither_bridge_nor_series_exists(self):
        segments = [
            _quote("Revenue", 100.0, "usd", "cite-a"),
            _quote("Opex", 60.0, "usd", "cite-b"),
        ]
        self.assertIsNone(_select_bridge(segments))
        self.assertIsNone(_select_time_series(segments))
        chart = _select_chart(segments)
        self.assertEqual(len(chart["series"]), 2)

    def test_mixed_formats_never_get_paired_in_a_bar_chart(self):
        segments = [_quote("Revenue", 100.0, "usd", "a"), _quote("Margin", 50.0, "percent", "b")]
        self.assertIsNone(_select_bar_fallback(segments))
        self.assertIsNone(_select_chart(segments))

    def test_fewer_than_two_numeric_facts_produces_no_chart(self):
        self.assertIsNone(_select_chart([_quote("Solo", 1.0, "number", "a")]))


class FiscalYearPeriodFormatTest(unittest.TestCase):  # Slice 54, found live 2026-09-12
    """A real document ("Test #10") labelled quarters "Q2 FY2027"
    (quarter + "FY" + year combined) - a real, common fiscal-quarter
    convention. Reproduces the exact real data behind that failure:
    before Slice 54, this label format broke KPI dedup (5 "Revenue" KPIs
    across 5 quarters instead of 1), benchmark attachment (attached to
    the wrong quarter), the trend sentence (never fired - no 3+ group
    ever formed), and the chart (a jumbled bar mixing unrelated facts
    instead of a clean revenue line)."""

    SEGMENTS = [
        _quote("Q2 FY2027 Revenue", 486_000_000.0, "usd", "cite-q2fy27"),
        _quote("Q1 FY2027 Revenue", 461_000_000.0, "usd", "cite-q1fy27"),
        _quote("Q4 FY2026 Revenue", 438_000_000.0, "usd", "cite-q4fy26"),
        _quote("Q3 FY2026 Revenue", 419_000_000.0, "usd", "cite-q3fy26"),
        _quote("Q2 FY2026 Revenue", 402_000_000.0, "usd", "cite-q2fy26"),
        _growth("Revenue growth QoQ", 5.4, "cite-q1fy27", "cite-q2fy27"),
        _growth("Revenue growth YoY", 20.9, "cite-q2fy26", "cite-q2fy27"),
        _quote("Industrial Systems Segment Revenue", 302_000_000.0, "usd", "cite-seg"),
    ]

    def test_kpis_deduplicate_to_one_per_distinct_metric(self):
        kpis = _select_kpis(self.SEGMENTS)
        self.assertEqual(len(kpis), 2)  # Revenue (once) + Industrial Systems
        self.assertEqual(kpis[0]["value_fact"], 0)  # Q2 FY2027, the current quarter
        self.assertEqual(kpis[0]["delta_fact"], 5)

    def test_both_growth_facts_attach_to_the_current_quarter(self):
        text = _benchmark_sentences(self.SEGMENTS)[0]["text"]
        self.assertIn("{{0}}", text)
        self.assertIn("{{5}}", text)
        self.assertIn("{{6}}", text)
        self.assertNotIn("{{1}}", text)
        self.assertNotIn("{{4}}", text)

    def test_a_genuine_trend_sentence_fires(self):
        text = _trend_sentences(self.SEGMENTS)[0]["text"]
        self.assertIn("grown", text)
        self.assertIn("4 consecutive periods", text)

    def test_the_chart_is_a_clean_same_metric_revenue_series_not_a_jumbled_mix(self):
        chart = _select_chart(self.SEGMENTS)
        labels = [p["label"] for p in chart["series"]]
        self.assertEqual(labels, ["Q2 FY2026", "Q3 FY2026", "Q4 FY2026", "Q1 FY2027", "Q2 FY2027"])
        # the unrelated segment figure never gets mixed into the revenue trend
        self.assertNotIn(7, [p["fact_index"] for p in chart["series"]])


class BuildDeterministicReportTest(unittest.TestCase):  # Done when #1, #2
    def _report(self):
        segments = REVENUE_SERIES + [
            _growth("Revenue growth QoQ", 9.5, "cite-q2-26", "cite-q3-26"),
            _growth("Revenue growth YoY", 23.9, "cite-q3-25", "cite-q3-26"),
            _quote("Q3 2026 Net Income", 19_600_000.0, "usd", "cite-ni-26"),
            _quote("Q3 2025 Net Income", 22_400_000.0, "usd", "cite-ni-25"),
            _growth("Net income growth YoY", -12.5, "cite-ni-25", "cite-ni-26"),
            _quote("Data Services end", 142_000_000.0, "usd", "cite-ds-end"),
            _quote("Data Services start", 88_000_000.0, "usd", "cite-ds-start"),
            _quote("Halyard contribution", 34_000_000.0, "usd", "cite-halyard"),
            _remainder("Data Services organic growth", 20_000_000.0,
                       "cite-ds-end", "cite-ds-start", "cite-halyard"),
        ]
        return segments, build_deterministic_report(segments, "Meridian Q3 2026")

    def test_fewer_than_two_numeric_facts_returns_none(self):
        self.assertIsNone(build_deterministic_report([_quote("Solo", 1.0, "number", "a")], "X"))

    def test_returns_the_same_report_shape_write_narrative_produces(self):
        _segments, report = self._report()
        for key in ("title", "kpis", "executive_summary", "executive_insight",
                    "sections", "disclosure_gaps", "outlook", "outlook_interpretation"):
            self.assertIn(key, report)
        self.assertIsInstance(report["sections"], list)
        self.assertIn("heading", report["sections"][0])
        self.assertIn("paragraphs", report["sections"][0])
        self.assertIn("chart", report["sections"][0])

    def test_renders_through_the_real_unmodified_renderer_with_all_four_sentence_types(self):
        segments, report = self._report()
        html = render_rich_report(report, segments, SRC, "actual")
        self.assertIn("<!doctype html", html.lower())
        self.assertIn('class="kpi-strip"', html)
        self.assertIn("<svg", html)  # a real chart drew
        body = html[html.index("<body"):]
        # benchmarking
        self.assertTrue(any(w in body for w in ("grew", "declined")))
        # trend
        self.assertIn("consecutive periods", body)
        # relationship
        self.assertIn("Halyard", body)
        # disclosure gap
        self.assertIn("Earnings per share is not disclosed", body)

    def test_no_field_marks_this_output_as_degraded(self):
        _segments, report = self._report()
        # the exact keys _assemble_report's own output has - nothing
        # extra bolted on to signal "this one is different"
        self.assertEqual(
            set(report.keys()),
            {"title", "kpis", "executive_summary", "executive_insight",
             "sections", "disclosure_gaps", "outlook", "outlook_interpretation"},
        )


if __name__ == "__main__":
    unittest.main()
