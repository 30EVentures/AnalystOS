"""Slices 113-116 - rendering a verified deck spec as PowerPoint.

The renderer prints every number from a verified figure (the model only writes
tags), derives the client's text and the role from the engagement and the
catalog, and refuses anything it cannot re-verify. The no-new-numbers check here
is independent of the verifier's number detector: on every slide, including the
text inside charts, it removes the exact formatted values of the figures that
slide uses and the few numbers the layout itself draws, and requires that no
numeric character is left."""

import copy
import io
import json
import re
import unicodedata
import unittest

from pptx import Presentation

from analystos.l4 import deck
from analystos.packs import consulting as c
from analystos.packs.replay import ReplayClient
from tests.test_consulting_pack import CATALOG, ENGAGEMENT, RESPONSE, catalog_with_available, engagement

SPEC = c.build_deck_spec(ENGAGEMENT, CATALOG, client=ReplayClient([RESPONSE]))
DATA = deck.render_deck(SPEC, ENGAGEMENT, CATALOG)
PRS = Presentation(io.BytesIO(DATA))
FIGURES = {f["id"]: f for f in SPEC["content"]["figures"]}


def shape_texts(slide):
    for shape in slide.shapes:
        if shape.has_text_frame:
            yield shape.text_frame.text
        if getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    yield cell.text
        if getattr(shape, "has_chart", False) and shape.has_chart:
            chart = shape.chart
            if chart.has_title:
                yield chart.chart_title.text_frame.text
            plot = chart.plots[0]
            yield from (str(category) for category in plot.categories)
            for point in range(len(plot.categories)):
                yield plot.series[0].points[point].data_label.text_frame.text


def slide_text(slide):
    return "\n".join(shape_texts(slide))


def rendered_slides(spec):
    """The spec slide behind each rendered slide (sources slides repeat), with its page."""
    out = []
    for s in spec["slides"]:
        if s["kind"] == "sources":
            figs = spec["content"]["figures"]
            pages = range(0, len(figs), deck.SOURCES_PER_SLIDE)
            for k, start in enumerate(pages):
                out.append((s, figs[start:start + deck.SOURCES_PER_SLIDE], k + 1, len(pages)))
        else:
            out.append((s, None, None, None))
    return out


def unexplained_numbers(prs, spec):
    """Numeric characters on a slide that are not part of: the formatted value or the
    reference of a figure that slide uses, its slide number, and - only where the
    layout draws them - sources pagination, quotes and formulas, and the roadmap's
    column labels."""
    figures = {f["id"]: f for f in spec["content"]["figures"]}
    total = len(prs.slides)
    found = []
    for i, (slide, (spec_slide, chunk, page, pages)) in enumerate(zip(prs.slides, rendered_slides(spec)), start=1):
        text = slide_text(slide)
        removable = [f"{i} / {total}"]
        ids = [f["id"] for f in chunk] if chunk is not None else list(spec_slide["figure_ids"])
        for fid in ids:
            removable += [deck.format_value(figures[fid]), fid]
        if chunk is not None:
            removable += [deck.value_cell(f) for f in chunk]
            for f in chunk:
                for ref in re.findall(r"\[(F[0-9]+)\]", f.get("rationale", "")):
                    removable.append(f"{deck.format_value(figures[ref])} ({ref})")
            if pages > 1:
                removable.append(f"({page} of {pages})")
            for f in chunk:
                if f["basis"] == "client":
                    removable.append(f["quote"])
                if f["basis"] == "computed":
                    removable.append(deck.formula(f["operation"], f["inputs"]))
                    removable += list(f["inputs"])
        if spec_slide["kind"] == "roadmap":
            removable += list(c.HORIZONS)
        for item in sorted(set(removable), key=len, reverse=True):
            text = re.sub(r"(?<![\w$.,])" + re.escape(item) + r"(?![\w%])(?![.,]\d)", " ", text)
        text = re.sub(r"\b(?:Q[1-4]|H[12]|FY ?(?:\d{4}|\d{2})|B2B|B2C)\b", " ", text)  # labels the content may use
        left = "".join(ch for ch in text if unicodedata.numeric(ch, None) is not None)
        if left:
            found.append((i, left))
    return found


class RenderTest(unittest.TestCase):
    def test_slide_count(self):
        self.assertEqual(PRS.slide_width, deck.SLIDE_W)
        self.assertEqual(len(PRS.slides), deck.slide_count(SPEC))

    def test_numbers_are_printed_from_figures(self):
        exec_summary = slide_text(PRS.slides[1])
        self.assertIn("churn rose from 4% F1 to 7% F2", exec_summary)
        self.assertIn("costs $30,600 F14", exec_summary)
        self.assertIn("rose by 3 pts F11", exec_summary)

    def test_the_renderer_adds_no_numbers_of_its_own(self):
        self.assertEqual(unexplained_numbers(PRS, SPEC), [])

    def test_the_check_catches_injected_numbers(self):
        for injected in ("TOP 3 priorities", "ARR10M", "2x faster", "(3 of 12)", "× 100", "F99", "a 10% uplift",
                         "70%", "$1,200"):
            with self.subTest(injected=injected):
                prs = Presentation(io.BytesIO(DATA))
                shape = next(s for s in prs.slides[3].shapes if s.has_text_frame and s.text_frame.text.strip())
                shape.text_frame.paragraphs[0].add_run().text = " " + injected
                self.assertTrue(unexplained_numbers(prs, SPEC), injected)

    def test_the_check_reads_charts(self):
        prs = Presentation(io.BytesIO(DATA))
        chart = next(s.chart for s in prs.slides[4].shapes if getattr(s, "has_chart", False) and s.has_chart)
        chart.chart_title.text_frame.text = "Churn is up 40% on last year."
        self.assertTrue(unexplained_numbers(prs, SPEC))

    def test_every_tile_shows_its_own_figure(self):
        checked = 0
        for slide in PRS.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                paragraphs = [p.text for p in shape.text_frame.paragraphs]
                if len(paragraphs) == 3 and re.match(r"^F\d+ · ", paragraphs[2]):
                    fid = paragraphs[2].split(" ")[0]
                    self.assertEqual(paragraphs[0], deck.format_value(FIGURES[fid]), fid)
                    self.assertEqual(paragraphs[1], FIGURES[fid]["label"])
                    checked += 1
        self.assertGreaterEqual(checked, 5)

    def test_chart_labels_use_the_same_formatter_as_the_text(self):
        charts = [s.chart for slide in PRS.slides for s in slide.shapes if getattr(s, "has_chart", False) and s.has_chart]
        findings = [s for s in SPEC["slides"] if s["kind"] == "finding"]
        self.assertEqual(len(charts), len(findings))
        for chart, spec_slide in zip(charts, findings):
            plot = chart.plots[0]
            expected = [deck.format_value(FIGURES[fid]) for fid in spec_slide["chart"]["figure_ids"]]
            shown = [plot.series[0].points[i].data_label.text_frame.text for i in range(len(expected))]
            self.assertEqual(shown, expected)
            self.assertEqual(list(plot.series[0].values), [FIGURES[f]["value"] for f in spec_slide["chart"]["figure_ids"]])
            self.assertFalse(chart.value_axis.visible)

    def test_assumptions_are_flagged_where_used(self):
        roadmap = next(i for i, (s, *_rest) in enumerate(rendered_slides(SPEC)) if s["kind"] == "roadmap")
        self.assertIn("Includes assumption F15: not from client data.", slide_text(PRS.slides[roadmap]))
        self.assertNotIn("Includes assumption", slide_text(PRS.slides[2]))

    def test_sources_list_every_figure_with_its_basis(self):
        sources = "\n".join(slide_text(s) for s in list(PRS.slides)[-2:])
        for fig in RESPONSE["figures"]:
            self.assertIn(fig["label"], sources)
        self.assertIn("Client's words: “went from 4%”", sources)
        self.assertIn("Calculated: F5 × F2 ÷ 100", sources)
        self.assertIn("3 pts", sources)
        self.assertNotIn("[F", sources)  # an assumption's rationale shows values, not raw tags

    def test_role_title_comes_from_the_catalog(self):
        self.assertIn("Management Consulting Analyst", slide_text(PRS.slides[0]))
        self.assertEqual(PRS.core_properties.subject, "Management Consulting Analyst")
        self.assertIn(f"spec sha256 {deck.spec_digest(SPEC)}", PRS.core_properties.keywords)


class RefusalTest(unittest.TestCase):
    def assertRefused(self, spec, eng=ENGAGEMENT, needle="refusing to render"):
        with self.assertRaisesRegex(ValueError, needle):
            deck.render_deck(spec, eng, CATALOG)

    def test_an_edited_spec(self):
        edited = json.loads(json.dumps(SPEC))
        edited["content"]["answer"] = "Churn will hit [F2] next year, so act now on retention."
        self.assertRefused(edited)

    def test_a_spec_that_forges_its_own_client_text(self):
        forged = json.loads(json.dumps(SPEC))
        forged["client_text"] += "\nWe expect $90 million in new revenue."
        forged["content"]["figures"].append({"id": "F16", "label": "New revenue", "value": 90000000, "unit": "usd",
                                             "basis": "client", "quote": "We expect $90 million in new revenue"})
        forged["content"]["answer"] += " New revenue could reach [F16]."
        forged["slides"] = c.assemble_slides(forged["content"])
        self.assertEqual(c.check_deck_spec(forged), [])  # internally consistent ...
        self.assertRefused(forged, needle="client text is not the engagement's")  # ... but not the engagement's

    def test_a_role_the_engagement_did_not_ask_for(self):
        self.assertRefused(dict(SPEC, role="fpa-analyst"), needle="not one this engagement asked for")

    def test_a_role_name_cannot_be_injected(self):
        self.assertRefused(dict(SPEC, role="Saves 40% Consulting"))

    def test_the_wrong_or_unaccepted_engagement(self):
        self.assertRefused(SPEC, eng=dict(ENGAGEMENT, id="f" * 32), needle="does not belong")
        self.assertRefused(SPEC, eng=engagement(accept=False), needle="does not belong")
        self.assertRefused(SPEC, eng={"not": "an engagement"}, needle="not valid")

    def test_malformed_specs(self):
        weird = copy.deepcopy(SPEC)
        weird["slides"][3]["kind"] = "hologram"
        for bad in (None, {}, {"format": SPEC["format"]}, dict(SPEC, content=None), dict(SPEC, client_text=None), weird):
            with self.subTest(bad=str(bad)[:40]):
                with self.assertRaises(ValueError):
                    deck.render_deck(bad, ENGAGEMENT, CATALOG)

    def test_a_drawing_failure_is_a_value_error(self):
        original = deck.RENDERERS["kpis"]

        def broken(*args):
            raise KeyError("boom")

        deck.RENDERERS["kpis"] = broken
        try:
            with self.assertRaisesRegex(ValueError, "could not draw the deck: KeyError"):
                deck.render_deck(SPEC, ENGAGEMENT, CATALOG)
        finally:
            deck.RENDERERS["kpis"] = original


class FormatTest(unittest.TestCase):
    def test_values(self):
        cases = ((7, "percent", "7%"), (6.5, "percent", "6.5%"), (73.846, "percent", "73.8%"), (0.04, "percent", "0.04%"),
                 (3, "points", "3 pts"), (0.7, "points", "0.7 pts"), (30600, "usd", "$30,600"), (1200, "usd", "$1,200"),
                 (2.5, "usd", "$2.50"), (-18000, "usd", "-$18,000"), (59.5, "count", "60"), (25.5, "count", "26"),
                 (14.1667, "count", "14"), (6.5, "other", "6.5"), (850, "count", "850"), (1.25, "ratio", "1.25x"),
                 (6, "months", "6 months"), (0, "usd", "$0"))
        for value, unit, expected in cases:
            with self.subTest(value=value, unit=unit):
                self.assertEqual(deck.format_value({"value": value, "unit": unit}), expected)

    def test_a_nonzero_value_is_never_written_as_zero(self):
        for value, unit, expected in ((0.004, "percent", "0.004%"), (0.001, "usd", "$0.001"),
                                      (-0.004, "points", "-0.004 pts"), (0.004, "count", "0.004"),
                                      (0.0004, "ratio", "0.0004x"), (-0.002, "usd", "-$0.002")):
            with self.subTest(value=value, unit=unit):
                self.assertEqual(deck.format_value({"value": value, "unit": unit}), expected)

    def test_the_sources_value_is_exact_when_the_deck_rounds(self):
        for value, unit, expected in ((59.5, "count", "60 (exact 59.5)"), (7, "percent", "7%"),
                                      (30600, "usd", "$30,600"), (14.1667, "count", "14 (exact 14.1667)"),
                                      (73.846, "percent", "73.8% (exact 73.846%)"), (2.5, "usd", "$2.50"),
                                      (-18000.25, "usd", "-$18,000 (exact -$18,000.25)")):
            with self.subTest(value=value, unit=unit):
                self.assertEqual(deck.value_cell({"value": value, "unit": unit}), expected)

    def test_a_negative_bar_gets_an_axis_below_zero(self):
        for values, floor in (((-18000, 5000), None), ((18000, 5000), 0.0)):
            figs = [{"id": f"F{i + 1}", "value": v, "unit": "usd", "basis": "client"} for i, v in enumerate(values)]
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            token = deck._FIGURES.set({f["id"]: f for f in figs})
            try:
                graphic = deck._chart(slide, {"content": {"figures": figs}},
                                      {"figure_ids": ["F1", "F2"], "labels": ["A", "B"], "title": "Cash"}, 0, 0, 100, 100)
            finally:
                deck._FIGURES.reset(token)
            with self.subTest(values=values):
                self.assertEqual(graphic.chart.value_axis.minimum_scale, floor)

    def test_an_assumption_rationale_shows_values_not_tags(self):
        figs = {"F1": {"id": "F1", "value": 7, "unit": "percent", "basis": "client"},
                "F2": {"id": "F2", "value": 2, "unit": "points", "basis": "assumption",
                       "rationale": "Half of the rise above [F1] is recoverable."}}
        token = deck._FIGURES.set(figs)
        try:
            self.assertEqual(deck._source_text(figs["F2"]), "Assumption: Half of the rise above 7% (F1) is recoverable.")
        finally:
            deck._FIGURES.reset(token)

    def test_formulas(self):
        self.assertEqual(deck.formula("difference", ["F2", "F1"]), "F2 − F1")
        self.assertEqual(deck.formula("percent_of", ["F5", "F2"]), "F5 × F2 ÷ 100")
        self.assertEqual(deck.formula("sum", ["F1", "F2", "F3"]), "F1 + F2 + F3")


if __name__ == "__main__":
    unittest.main()
