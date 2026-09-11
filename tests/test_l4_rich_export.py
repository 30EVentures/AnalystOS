"""Tests for L4 render_rich_report - one per "Done when" in
specs/slice-28/spec.md that concerns analystos.l4.rich_export.
"""

import unittest
from unittest.mock import patch

from analystos.l4.rich_export import render_rich_report

SRC = "a1b9f2c8" * 8

SEGMENTS = [
    {"type": "quote", "value": 32_600_000.0, "format": "usd", "citation": "$32,600,000"},   # 0
    {"type": "quote", "value": 27_800_000.0, "format": "usd", "citation": "$27,800,000"},   # 1
    {"type": "quote", "value": 21_000_000.0, "format": "usd", "citation": "$21,000,000"},   # 2
    {"type": "quote", "value": 11_600_000.0, "format": "usd", "citation": "$11,600,000"},   # 3
    {"type": "quote", "text": "40 people", "citation": "40 people"},                        # 4: no "value"
    {"type": "prose", "text": "Momentum continued."},                                       # 5: not citable
]


def _report(**overrides):
    base = {
        "title": "Draft Co — Q3 2026",
        "executive_summary": [{"text": "Revenue reached {{0}}, up from {{1}}."}],
        "sections": [{
            "heading": "Revenue",
            "paragraphs": [{"text": "Enterprise contributed {{2}} against SMB's {{3}}."}],
            "chart": {
                "type": "bar", "title": "Revenue by segment", "format": "usd",
                "series": [{"label": "Enterprise", "fact_index": 2}, {"label": "SMB", "fact_index": 3}],
            },
        }],
        "outlook": [{"text": "Momentum should continue into Q4 2026."}],
    }
    base.update(overrides)
    return base


class RenderRichReportTest(unittest.TestCase):
    def test_executive_summary_section_and_outlook_all_render(self):  # Done when #4
        out = render_rich_report(_report(), SEGMENTS, SRC)
        self.assertIn("Executive summary", out)
        self.assertIn("<h2>Revenue</h2>", out)
        self.assertIn('class="outlook"', out)
        self.assertIn("$32.6M", out)
        self.assertIn("$27.8M", out)

    def test_chart_is_embedded_in_its_section(self):  # Done when #4
        out = render_rich_report(_report(), SEGMENTS, SRC)
        self.assertIn('class="chart-card"', out)
        self.assertIn("<svg", out)
        self.assertIn("$21.0M", out)  # Enterprise value, drawn into the chart

    def test_outlook_is_visually_distinct_from_verified_sections(self):  # Done when #4
        out = render_rich_report(_report(), SEGMENTS, SRC)
        outlook_start = out.index('class="outlook"')
        section_start = out.index("<section>")
        self.assertNotEqual(outlook_start, section_start)
        self.assertIn("interpretation, not verified fact", out.lower())

    def test_citation_marker_carries_a_hover_title(self):  # Done when #5
        out = render_rich_report(_report(), SEGMENTS, SRC)
        self.assertIn('title="source', out)
        self.assertIn('$32,600,000', out)

    def test_footnote_numbers_are_shared_across_summary_section_and_outlook(self):  # Done when #6
        report = _report(
            executive_summary=[{"text": "Revenue was {{0}}."}],
            sections=[{"heading": "Detail", "paragraphs": [{"text": "Also {{1}}."}], "chart": None}],
            outlook=[{"text": "Watch {{2}} next."}],
        )
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertIn(">1<", out)
        self.assertIn(">2<", out)
        self.assertIn(">3<", out)
        # exactly 3 footnote entries in the Sources panel, not reset per section
        self.assertEqual(out.count('<p id="fn'), 3)

    def test_a_fact_referenced_twice_reuses_one_footnote_number(self):
        report = _report(
            executive_summary=[{"text": "Revenue was {{0}}."}],
            sections=[{"heading": "Detail", "paragraphs": [{"text": "That same {{0}} figure led."}], "chart": None}],
            outlook=None,
        )
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertEqual(out.count('<p id="fn'), 1)

    def test_chart_with_an_out_of_range_reference_drops_that_point(self):  # Done when #2
        report = _report(sections=[{
            "heading": "Revenue",
            "paragraphs": [{"text": "See the chart."}],
            "chart": {
                "type": "bar", "title": "Revenue by segment", "format": "usd",
                "series": [
                    {"label": "Enterprise", "fact_index": 2},
                    {"label": "SMB", "fact_index": 3},
                    {"label": "Bad", "fact_index": 999},
                ],
            },
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertIn("<svg", out)
        self.assertNotIn("Bad", out)  # the dropped point's label never appears

    def test_chart_referencing_a_prose_segment_drops_that_point(self):  # Done when #2
        report = _report(sections=[{
            "heading": "Revenue",
            "paragraphs": [{"text": "See the chart."}],
            "chart": {
                "type": "bar", "title": "Revenue", "format": "usd",
                "series": [
                    {"label": "Enterprise", "fact_index": 2},
                    {"label": "SMB", "fact_index": 3},
                    {"label": "Not citable", "fact_index": 5},  # prose segment
                ],
            },
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertNotIn("Not citable", out)

    def test_chart_referencing_a_qualitative_quote_drops_that_point(self):  # Done when #2
        report = _report(sections=[{
            "heading": "Revenue",
            "paragraphs": [{"text": "See the chart."}],
            "chart": {
                "type": "bar", "title": "Revenue", "format": "usd",
                "series": [
                    {"label": "Enterprise", "fact_index": 2},
                    {"label": "SMB", "fact_index": 3},
                    {"label": "Qualitative", "fact_index": 4},  # no "value"
                ],
            },
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertNotIn("Qualitative", out)

    def test_a_chart_left_with_fewer_than_two_points_is_omitted_entirely(self):  # Done when #3
        report = _report(sections=[{
            "heading": "Revenue",
            "paragraphs": [{"text": "No chart should render here."}],
            "chart": {
                "type": "bar", "title": "Revenue", "format": "usd",
                "series": [
                    {"label": "Enterprise", "fact_index": 2},
                    {"label": "Bad", "fact_index": 999},
                ],
            },
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertNotIn("<svg", out)
        self.assertNotIn('class="chart-card"', out)

    def test_a_section_with_no_chart_at_all_renders_fine(self):
        report = _report(sections=[{
            "heading": "Revenue", "paragraphs": [{"text": "Revenue was {{0}}."}], "chart": None,
        }])
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertIn("<h2>Revenue</h2>", out)
        self.assertNotIn("<svg", out)

    def test_no_outlook_omits_the_outlook_block_entirely(self):
        out = render_rich_report(_report(outlook=None), SEGMENTS, SRC)
        self.assertNotIn('class="outlook"', out)

    def test_bold_markdown_in_prose_is_rendered_not_shown_literally(self):
        report = _report(
            executive_summary=[{"text": "**Revenue** reached {{0}}."}],
        )
        out = render_rich_report(report, SEGMENTS, SRC)
        self.assertIn("<strong>Revenue</strong>", out)
        self.assertNotIn("**", out)


class HorizonMarkerTest(unittest.TestCase):
    """Slice 31: a guidance/projected fact is visibly marked wherever it
    is used - executive summary, section, or outlook - so it can't be
    read as a verified historical result.
    """

    SEGMENTS = [
        {"type": "quote", "horizon": "reported", "value": 3_800_000_000.0,
         "format": "usd", "citation": "$3.80 billion"},                      # 0
        {"type": "quote", "horizon": "guidance", "value": 15_000_000_000.0,
         "format": "usd", "citation": "$15.00 billion"},                     # 1
        {"type": "computed", "horizon": "projected", "value": 4_450_000_000.0,
         "format": "usd", "citation": ["$15.00 billion", "$3.80 billion"]},  # 2
    ]

    def _report(self, **over):
        base = {
            "title": "Acme — revenue review",
            "executive_summary": [{"text": "Q3 revenue was {{0}}; the full-year guide is {{1}}."}],
            "sections": [{
                "heading": "Revenue",
                "paragraphs": [{"text": "Against {{0}} in Q3, the guide of {{1}} is a step up."}],
                "chart": None,
            }],
            "outlook": [{"text": "The guide of {{1}} leaves {{2}} for the rest of the year."}],
        }
        base.update(over)
        return base

    def test_a_guidance_fact_is_marked_in_the_executive_summary(self):  # Done when #1
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        summary = out.split('class="exec-summary"')[1].split("</div>")[0]
        self.assertIn('<span class="horizon-tag">guidance</span>', summary)

    def test_a_guidance_fact_is_marked_inside_a_section(self):  # Done when #1
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        section = out.split('<section>')[1].split('</section>')[0]
        self.assertIn('<span class="horizon-tag">guidance</span>', section)

    def test_guidance_and_projected_are_both_marked_in_the_outlook(self):  # Done when #1
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        outlook = out.split('class="outlook"')[1].split("</div>")[0]
        self.assertIn('<span class="horizon-tag">guidance</span>', outlook)
        self.assertIn('<span class="horizon-tag">projected</span>', outlook)

    def test_a_reported_fact_is_not_marked(self):  # Done when #2
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        # $3.8B (fact 0, reported) goes straight to its footnote link, no tag
        self.assertIn('$3.8B <sup class="cite"', out)
        self.assertNotIn('$3.8B <span class="horizon-tag"', out)

    def test_segments_with_no_horizon_key_are_never_marked(self):  # Done when #2
        out = render_rich_report(_report(), SEGMENTS, SRC)  # module fixtures, no horizon
        # the CSS rule is always present; a rendered span is what must not be
        self.assertNotIn('<span class="horizon-tag">', out)

    def test_the_sentinel_never_leaks_as_literal_text(self):  # Done when #3
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        self.assertNotIn("⟦", out)
        self.assertNotIn("⟧", out)


class GaapStatusMarkerTest(unittest.TestCase):
    """Slice 45: a non-GAAP fact is visibly marked wherever it's cited -
    the same mechanism (and the same guarantee) Slice 31's horizon marker
    already has for a forward-looking fact. The tag is attached by the
    renderer itself from the segment's own gaap_status, not by anything
    the model writes - it can't be silently omitted.
    """

    SEGMENTS = [
        {"type": "quote", "horizon": "reported", "gaap_status": "gaap",
         "value": 19_600_000.0, "format": "usd", "citation": "$19.6 million"},        # 0
        {"type": "quote", "horizon": "reported", "gaap_status": "non_gaap",
         "value": 24_100_000.0, "format": "usd", "citation": "$24.1 million"},        # 1
        {"type": "computed", "horizon": "reported", "gaap_status": "n/a",
         "operation": "difference", "value": 4_500_000.0, "format": "usd",
         "citation": ["$24.1 million", "$19.6 million"]},                             # 2
    ]

    def _report(self, **over):
        base = {
            "title": "Acme — Q3 review",
            "executive_summary": [
                {"text": "GAAP net income was {{0}}; non-GAAP net income was {{1}}."},
            ],
            "sections": [{
                "heading": "Net income",
                "paragraphs": [{"text": "The reconciling gap was {{2}}."}],
                "chart": None,
            }],
            "outlook": None,
        }
        base.update(over)
        return base

    def test_a_non_gaap_fact_is_marked_wherever_it_is_cited(self):
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        self.assertIn('<span class="horizon-tag">non-gaap</span>', out)

    def test_the_gaap_fact_next_to_it_is_not_marked(self):
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        self.assertIn('$19.6M <sup class="cite"', out)
        self.assertNotIn('$19.6M <span class="horizon-tag"', out)

    def test_a_reconciling_difference_with_no_gaap_status_is_not_marked(self):
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        self.assertIn('$4.5M <sup class="cite calc"', out)
        self.assertNotIn('$4.5M <span class="horizon-tag"', out)

    def test_the_sentinel_never_leaks_as_literal_text(self):
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        self.assertNotIn("⟦", out)
        self.assertNotIn("⟧", out)


class EventInRichReportTest(unittest.TestCase):
    """Slice 32/38: an event referenced by {{N}} substitutes its short
    name inline - never the full composed timeline (Slice 38 fixed that
    leaking verbatim into prose, duplicated, wherever the same event was
    cited: found live 2026-09-11, "next:" and all). Still shares one
    footnote across uses, and (when projected) carries the Slice 31 marker.
    """

    SEGMENTS = [
        {"type": "quote", "horizon": "reported", "value": 3_800_000_000.0,
         "format": "usd", "citation": "$3.80 billion"},                      # 0
        {"type": "event", "horizon": "reported",
         "what": "acquired Halyard Analytics", "date": "May 2026",
         "status": "integrating", "next_step": "accretive in 2027",
         "citation": "acquired Halyard Analytics"},                          # 1
        {"type": "event", "horizon": "projected",
         "what": "plans to divest the legacy unit", "date": "", "status": "",
         "next_step": "", "citation": "plans to divest the legacy unit"},    # 2
    ]

    def _report(self):
        return {
            "title": "Deal review",
            "executive_summary": [{"text": "Revenue was {{0}}; the company {{1}}."}],
            "sections": [{
                "heading": "The deal",
                "paragraphs": [{"text": "In context: the company {{1}}, and separately {{2}}."}],
                "chart": None,
            }],
            "outlook": [{"text": "The next milestone is tied to {{1}}."}],
        }

    def test_event_substitutes_its_short_name_inline_not_the_full_timeline(self):  # Slice 38
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        self.assertIn("the company acquired Halyard Analytics", out)
        # the full composed line belongs only in a dedicated .timeline
        # widget (2+ dated rows) - never dumped inline mid-sentence
        self.assertNotIn("(May 2026) — integrating — next:", out)

    def test_an_event_referenced_three_times_shares_one_footnote(self):  # Done when #4
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        self.assertEqual(out.count('<p id="fn2">'), 1)

    def test_a_projected_event_carries_the_horizon_tag(self):  # Done when #4
        out = render_rich_report(self._report(), self.SEGMENTS, SRC)
        self.assertIn('<span class="horizon-tag">projected</span>', out)


class V4StructureTest(unittest.TestCase):  # Slice 36
    SEG = [
        {"type": "quote", "horizon": "reported", "value": 498_000_000.0, "format": "usd",
         "citation": "$498.0 million"},                                                  # 0
        {"type": "computed", "horizon": "reported", "operation": "growth_percent",
         "value": -12.5, "format": "percent", "operands": [22_400_000.0, 19_600_000.0],
         "total": None, "citation": ["$22.4 million", "$19.6 million"]},                 # 1
        {"type": "quote", "horizon": "reported", "value": 88_000_000.0, "format": "usd",
         "citation": "$88.0 million"},                                                   # 2 bridge start
        {"type": "computed", "horizon": "reported", "operation": "difference",
         "value": 20_000_000.0, "format": "usd",
         "operands": [142_000_000.0, 88_000_000.0, 34_000_000.0], "total": None,
         "citation": ["$142.0M", "$88.0M", "$34.0M"]},                                   # 3 component
        {"type": "quote", "horizon": "reported", "value": 34_000_000.0, "format": "usd",
         "citation": "$34.0 million"},                                                   # 4 component
        {"type": "quote", "horizon": "reported", "value": 142_000_000.0, "format": "usd",
         "citation": "$142.0 million"},                                                  # 5 bridge end
        {"type": "event", "horizon": "reported", "what": "acquired Halyard",
         "date": "May 14, 2026", "status": "", "next_step": "",
         "milestones": [{"date": "May 14, 2026", "detail": "closed at $340M"},
                        {"date": "1H 2027", "detail": "expected accretive"}],
         "citation": "acquired Halyard"},                                                # 6 event
    ]

    def _report(self, **over):
        base = {
            "title": "Acme Q3",
            "kpis": [{"label": "Revenue", "value_fact": 0, "delta_fact": 1}],
            "executive_summary": [{"text": "Revenue was {{0}}."}],
            "executive_insight": "Read together, {{0}} and {{1}} tell one story.",
            "sections": [{
                "heading": "Segments",
                "paragraphs": [{"text": "It grew via {{6}} to {{5}}."}],
                "chart": {"type": "waterfall", "title": "Bridge", "format": "usd",
                          "series": [{"label": "start", "fact_index": 2},
                                     {"label": "organic", "fact_index": 3},
                                     {"label": "halyard", "fact_index": 4},
                                     {"label": "end", "fact_index": 5}]},
            }],
            "disclosure_gaps": [{"text": "EPS is not disclosed."}],
            "outlook": [{"text": "Guidance was reiterated."}],
            "outlook_interpretation": "That reiteration is itself a signal.",
        }
        base.update(over)
        return base

    def test_all_eight_v4_elements_render(self):
        out = render_rich_report(self._report(), self.SEG, SRC)
        self.assertIn('class="kpi-strip"', out)                    # 1 KPI strip
        self.assertIn('<sup class="cite">&#10003;', out)           # 1 quote tag
        self.assertIn('<sup class="cite calc">&#8721;', out)       # 1 computed tag
        self.assertIn('class="analysis-block"', out)               # 2 boxed insight
        self.assertIn(">Analysis<", out)
        self.assertIn('<figure class="chart-card"', out)           # 3 chart (waterfall)
        self.assertIn('class="gap-note"', out)                     # 4 disclosure gap
        self.assertIn("Disclosure gap:", out)
        self.assertIn('class="timeline"', out)                     # 5 dated timeline
        self.assertIn('tl-date">May 14, 2026', out)
        self.assertIn('class="outlook"', out)                      # 6 outlook, distinct
        self.assertIn('class="interp">Interpretation:', out)
        self.assertIn("($19.6M − $22.4M) / $22.4M", out)  # 7 footnote shows the actual arithmetic
        self.assertIn("IBM Plex Serif", out)                       # 8 typography system

    def test_data_that_does_not_form_a_real_bridge_renders_as_a_bar_not_a_waterfall(self):
        # Slice 47: chart type is now decided by code from the verified
        # data's own shape, not by whatever the model declared - see
        # specs/slice-47/spec.md. Breaking the bridge no longer means the
        # chart vanishes; it means code correctly stops calling it a
        # bridge and shows the same real numbers as an honest bar
        # comparison instead - no chart lost, no misleading bridge shown.
        bad = self._report()
        bad["sections"][0]["chart"]["series"][1]["fact_index"] = 0  # $498M component breaks the bridge
        out = render_rich_report(bad, self.SEG, SRC)
        self.assertIn("<svg", out)
        self.assertNotIn("&#8721; Computed &amp; verified", out)  # the waterfall-only footer tag
        self.assertIn("&#10003; Direct quote", out)  # the bar/line footer tag instead

    def test_the_post_hoc_waterfall_tie_out_check_is_still_an_independent_safety_layer(self):
        # Proves the existing validation genuinely still runs as its own
        # check, not just inferred from the detector agreeing with
        # itself: force the detector to (wrongly) call broken-bridge data
        # "waterfall" and confirm the separate, untouched tie-out check
        # in _chart_html still refuses to render it.
        with patch("analystos.l4.rich_export._detect_chart_type", return_value="waterfall"):
            bad = self._report()
            bad["sections"][0]["chart"]["series"][1]["fact_index"] = 0  # breaks the bridge
            out = render_rich_report(bad, self.SEG, SRC)
        self.assertNotIn("<svg", out)

    def test_a_bad_kpi_reference_is_skipped_not_fatal(self):
        r = self._report(kpis=[{"label": "Bad", "value_fact": 99, "delta_fact": -1},
                               {"label": "Revenue", "value_fact": 0, "delta_fact": -1}])
        out = render_rich_report(r, self.SEG, SRC)
        self.assertIn('class="kpi-strip"', out)
        self.assertIn(">Revenue<", out)
        self.assertNotIn(">Bad<", out)

    def test_every_report_has_a_download_pdf_button_that_prints_the_page(self):  # Slice 37
        # Real browser print, not a generated file - the page already
        # renders pixel-for-pixel (real fonts, real inline SVG charts), so
        # printing it *is* the PDF, with no second renderer to drift from
        # the HTML. Works identically for a CLI-written section.html and
        # the live site's iframe.
        out = render_rich_report(self._report(), self.SEG, SRC)
        self.assertIn('<button class="pdf-btn" onclick="window.print()"', out)
        self.assertIn("Download PDF</button>", out)

    def test_the_pdf_button_and_only_it_is_hidden_when_printing(self):  # Slice 37
        out = render_rich_report(self._report(), self.SEG, SRC)
        style = out.split("<style>")[1].split("</style>")[0]
        media_print = style.split("@media print{")[1]
        self.assertIn(".pdf-btn{display:none}", media_print)

    def test_colored_boxes_are_forced_to_print_their_background(self):  # Slice 37
        # Chrome/Safari drop background colors on print by default - without
        # this the analysis-block/gap-note/outlook boxes print as plain
        # white, losing the verified-vs-interpretation visual system.
        out = render_rich_report(self._report(), self.SEG, SRC)
        self.assertIn("print-color-adjust:exact", out)


class ChartTypeAutoDetectionTest(unittest.TestCase):  # Slice 47
    """Chart type is decided by code from the verified data's own shape,
    not by whatever the model declared in chart["type"] - each test here
    deliberately declares the *wrong* type to prove the override is real,
    not just a case where the model happened to guess correctly.
    """

    def _quote(self, value):
        return {"type": "quote", "horizon": "reported", "value": value,
                "format": "usd", "citation": f"${value:,.0f}"}

    def _report_with_chart(self, declared_type, series):
        return {
            "title": "Acme Q3",
            "kpis": [],
            "executive_summary": [{"text": "See the chart below."}],
            "executive_insight": None,
            "sections": [{
                "heading": "Chart",
                "paragraphs": [{"text": "The figures are charted below."}],
                "chart": {"type": declared_type, "title": "Chart", "format": "usd",
                          "series": series},
            }],
            "disclosure_gaps": [],
            "outlook": None,
            "outlook_interpretation": None,
        }

    def test_a_start_components_end_bridge_renders_as_a_waterfall(self):
        # 100 -> +20 -> 120: a real, tying bridge - model wrongly declared "bar".
        segments = [self._quote(100_000_000.0), self._quote(20_000_000.0), self._quote(120_000_000.0)]
        report = self._report_with_chart("bar", [
            {"label": "start", "fact_index": 0},
            {"label": "component", "fact_index": 1},
            {"label": "end", "fact_index": 2},
        ])
        out = render_rich_report(report, segments, SRC)
        self.assertIn('stroke-dasharray="3,3"', out)  # the waterfall connector - unique to it
        self.assertNotIn("<polyline", out)

    def test_a_categorical_comparison_renders_as_a_bar_chart(self):
        # Three distinct, non-chronological categories - model wrongly declared "line".
        segments = [self._quote(10_000_000.0), self._quote(25_000_000.0), self._quote(15_000_000.0)]
        report = self._report_with_chart("line", [
            {"label": "Product A", "fact_index": 0},
            {"label": "Product B", "fact_index": 1},
            {"label": "Product C", "fact_index": 2},
        ])
        out = render_rich_report(report, segments, SRC)
        self.assertIn("<rect", out)
        self.assertNotIn("<polyline", out)
        self.assertNotIn('stroke-dasharray="3,3"', out)  # not mistaken for a waterfall

    def test_a_trend_over_three_or_more_periods_renders_as_a_line(self):
        # Model wrongly declared "donut".
        segments = [self._quote(100_000_000.0), self._quote(110_000_000.0), self._quote(120_000_000.0)]
        report = self._report_with_chart("donut", [
            {"label": "Q1 2026", "fact_index": 0},
            {"label": "Q2 2026", "fact_index": 1},
            {"label": "Q3 2026", "fact_index": 2},
        ])
        out = render_rich_report(report, segments, SRC)
        self.assertIn("<polyline", out)


class PrecisionConsistencyGateTest(unittest.TestCase):
    """Slice 38, Gate 1 check #3 - reproduces the live bug exactly:
    footnote 15 showed "$1.9B - $498.0M - $455.0M - $432.0M = $565.0M",
    which only works with the real $1,950,000,000 - "$1.9B" is that
    number's 1-decimal display, and 1.9B - 1.385B = $515M, not $565M.
    """

    SEG = [
        {"type": "quote", "horizon": "guidance", "value": 498_000_000.0, "format": "usd",
         "citation": "Q3"},                                                   # 0 (unused directly)
        {"type": "computed", "horizon": "guidance", "operation": "difference",
         "value": 565_000_000.0, "format": "usd",
         "operands": [1_950_000_000.0, 498_000_000.0, 455_000_000.0, 432_000_000.0],
         "total": None, "citation": ["$1.95 billion", "$498.0M", "$455.0M", "$432.0M"]},  # 1
    ]

    def _report(self):
        return {
            "title": "Precision check",
            "executive_summary": [{"text": "The remaining gap to guidance is {{1}}."}],
            "sections": [], "outlook": None,
        }

    def test_the_footnote_shows_numbers_that_actually_foot(self):
        out = render_rich_report(self._report(), self.SEG, SRC)
        # the operand that needed more precision now shows it ($1.95B, not
        # the lossy $1.9B) - every other number stays at the same precision
        self.assertIn("$1.95B − $498.00M − $455.00M − $432.00M = $565.00M", out)
        self.assertNotIn("$1.9B −", out)

    def test_the_displayed_expression_is_arithmetically_self_consistent(self):
        # don't just trust the fix - parse the numbers exactly as a reader
        # would see them and confirm they really do add up
        out = render_rich_report(self._report(), self.SEG, SRC)
        import re as _re
        expr = _re.search(r"\$[\d.]+B − \$[\d.]+M − \$[\d.]+M − \$[\d.]+M = \$[\d.]+M", out)
        self.assertIsNotNone(expr)
        nums = _re.findall(r"([\d.]+)(B|M)", expr.group(0))
        scale = {"B": 1e9, "M": 1e6}
        a, b, c, d, result = (float(v) * scale[u] for v, u in nums)
        self.assertAlmostEqual(a - b - c - d, result, delta=1.0)


class KpiDeltaSignGateTest(unittest.TestCase):
    """Slice 38 - a KPI delta is only colored pos/neg when it's backed by
    a growth_percent fact (the only operation with a defined sign). A
    difference-based delta renders neutral - found live 2026-09-11: a
    $2.8M net-income *decline* rendered green ("pos") because the
    subtraction behind it happened to come out positive.
    """

    SEG = [
        {"type": "quote", "horizon": "reported", "value": 19_600_000.0, "format": "usd",
         "citation": "$19.6M"},                                                          # 0
        {"type": "computed", "horizon": "reported", "operation": "difference",
         "value": 2_800_000.0, "format": "usd", "operands": [22_400_000.0, 19_600_000.0],
         "total": None, "citation": ["$22.4M", "$19.6M"]},                               # 1
        {"type": "computed", "horizon": "reported", "operation": "growth_percent",
         "value": -12.5, "format": "percent", "operands": [22_400_000.0, 19_600_000.0],
         "total": None, "citation": ["$22.4M", "$19.6M"]},                               # 2
    ]

    def _report(self, delta_fact):
        return {
            "title": "KPI sign check",
            "kpis": [{"label": "Net income", "value_fact": 0, "delta_fact": delta_fact}],
            "executive_summary": [{"text": "Net income was {{0}}."}],
            "sections": [], "outlook": None,
        }

    def test_a_difference_backed_delta_is_neutral_not_colored(self):
        out = render_rich_report(self._report(1), self.SEG, SRC)
        self.assertIn('class="delta neutral"', out)
        self.assertNotIn('class="delta pos"', out)
        self.assertNotIn('class="delta neg"', out)

    def test_a_growth_percent_backed_delta_is_colored_by_its_real_sign(self):
        out = render_rich_report(self._report(2), self.SEG, SRC)
        self.assertIn('class="delta neg"', out)  # -12.5% is a real decline


if __name__ == "__main__":
    unittest.main()
