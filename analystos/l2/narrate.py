"""L2 - a second, narrower model call that decides how to *structure and
write* a report about facts ``analystos.l2.analyze`` already verified. It
never sees the raw document and it never gets to state a number itself.

``write_narrative`` builds a numbered manifest from a document's already-
verified ``segments`` (Slice 26/29 output - unchanged by this module) and
asks the model for a full report shape:

    {
        "title": "...",
        "executive_summary": [{"text": "... {{N}} ..."}, ...],
        "sections": [
            {"heading": "...", "paragraphs": [{"text": "..."}, ...],
             "chart": {"type": "bar"|"line"|"donut", "title": "...",
                       "format": "usd"|"percent"|"number",
                       "series": [{"label": "...", "fact_index": N}, ...]}
             or None},
            ...
        ],
        "outlook": [{"text": "..."}, ...] or None,
    }

- exactly the shape ``analystos.l4.rich_export.render_rich_report``
  consumes, so ``pipeline`` can hand one straight to the other.

Every value a paragraph states is a ``{{N}}`` placeholder - ``N`` is a
fact's index in ``segments`` - filled in later by
``render_rich_report`` with the exact value Slice 26/29 verified. The
model chooses structure, grouping, wording, and chart placement; it never
writes the number.

The prompt asks for real analytical writing - lead with the takeaway,
build each section around one point, five specific disciplines
(benchmark, name the mechanism, sequence past from future, narrate any
dated event, co-state cause and effect) - grounded in how equity research
and top consulting memos are actually structured (Minto Pyramid /
SCQA), not a generic "sound smart" instruction. See ``docs/decisions.md``,
2026-09-06 and Slice 30, for the real-world sources this is based on.

Validation, all before any of it is trusted:
- every ``{{N}}`` in every paragraph (summary, each section, outlook) must
  reference a real, citable fact, and no digit may appear outside a
  placeholder (calendar references carved out - see ``_CALENDAR_RE`` in
  ``analystos.l2.analyze``); no placeholder may be followed by a
  redundant spelled-out unit ("million"/"billion"/"thousand"/"percent" -
  a rendered value already carries its own). A failure never raises
  straight to the caller - see the repair-then-retry escalation in
  ``write_narrative`` below.
- ``executive_summary`` and ``sections`` must be non-empty; every section
  needs a heading and at least one paragraph. A malformed structure
  cannot be single-paragraph repaired; it always goes through a full
  regenerate.
- a malformed chart is the *one* non-fatal case - it is dropped
  (``chart`` -> ``None``), never rejects the paragraph, matching
  ``rich_export._resolve_chart``'s "a bad chart is left out, the report
  is never lost" rule.

A ``ValueError`` that survives repair and every retry is caught by
``analystos.pipeline``, which falls back to Slice 26's plain per-segment
rendering - a worse-structured
report, never a lost one. See ``specs/slice-27/spec.md`` and
``specs/slice-30/spec.md``.
"""

import re
import sys

from analystos.l2.analyze import (
    _CALENDAR_RE,
    _DIGIT_RE,
    _create_message,
    _resolve_client,
    coverage_summary,
)
from analystos.l4.export import display_value

_MODEL = "claude-sonnet-5"
_MAX_TOKENS = 8192  # a rich report over a dense document can outgrow 4096 - see analyze.py
# A single-paragraph repair (write_narrative's first line of defence) is a
# small, cheap call with a much smaller blast radius than regenerating the
# whole report, so it gets a more generous budget than the full-regenerate
# fallback below it.
_MAX_REPAIR_ATTEMPTS = 3
# 2, not 1 - two live runs back to back each burned their only retry fixing
# the reported violation while introducing a different one; see the retry
# loop in write_narrative and specs/slice-40/spec.md.
_MAX_RETRIES = 2
_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")
_CHART_TYPES = ("bar", "line", "donut", "waterfall")
_CHART_FORMATS = ("usd", "percent", "number")
_BRIDGE_TOL = 0.01  # a waterfall must actually bridge: start + Σcomponents ≈ end

_SYSTEM_PROMPT = """\
You are a senior analyst writing the kind of report a Fortune 10 board or \
a top equity-research desk would actually publish - not a fact sheet, not \
a bulleted list of every verified number. Every fact in the manifest \
below has already been checked against the real source document; your job \
is judgment, structure, and writing, not verification, and you must not \
introduce any new number.

Call write_narrative once, structured the way real executive memos and \
research notes are (the Pyramid Principle / SCQA pattern McKinsey, BCG, \
and equity-research desks all use - lead with the answer, then support \
it):

- kpis: 3-5 headline metrics for the strip at the top of the report. Each \
  is {label, value_fact, delta_fact}: value_fact is the manifest number \
  of the metric's current value, delta_fact the manifest number of its \
  year-over-year change, or -1 if there is no such change fact. Use a \
  "growth_percent" fact for delta_fact, never a "difference" - the strip \
  colors the delta green/red by its sign, and a "difference"'s sign does \
  not reliably mean a rise or a fall (see "Directional words" below); \
  leave delta_fact -1 rather than point it at a "difference". Pick the \
  figures a decision-maker scans first. [] only if the document truly has \
  no headline numbers.
- executive_summary: 2-3 sentences stating the single most important \
  takeaway as a conclusion, not a fact. A reader who stops here should \
  already know what matters and why. Only verified facts here - no \
  interpretation. This is the densest prose in the report - several \
  figures in one sentence - and exactly where a bare digit slips in \
  instead of a placeholder most often. Every single figure still needs \
  its own {{N}}, with no exceptions for how naturally a percent or dollar \
  amount reads inline. Correct: "Revenue reached {{0}}, up {{1}} \
  year-over-year and {{2}} sequentially, driven by a segment now \
  generating {{3}} of total revenue." Wrong: the same sentence with any \
  one of those four numbers typed as a literal digit instead of {{N}} - \
  that single slip rejects the whole narrative.
- executive_insight: exactly ONE paragraph that reads two or three facts \
  together into a single synthesized judgment the individual facts don't \
  state on their own (e.g. margin compression + a new interest burden + \
  reiterated guidance, read together, as evidence a dip is temporary). \
  This is analysis, not a source claim - it renders in a distinct "boxed" \
  treatment. {"text": ""} if the material doesn't support one honest \
  synthesis.
- sections: 3-5 sections, each built around ONE analytical point - never \
  one number. The heading names the point. Weave facts into the point as \
  evidence: a number is a building block for a sentence, never the whole \
  sentence. Never write a section that is just "Label: sentence with one \
  number," repeated fact after fact.
- disclosure_gaps: things a real analyst reading this would want that the \
  document does NOT provide - a decline whose driver-split isn't broken \
  out, a metric (EPS, cash flow) absent entirely. State the gap plainly; \
  you may cite a verified figure it relates to via {{N}}. Never estimate \
  the missing number - flag it. [] if nothing material is missing.
- outlook: forward-looking or guidance material the source states, if \
  any. Leave it empty otherwise - do not manufacture an outlook.
- outlook_interpretation: ONE paragraph of your own forward-looking \
  judgment about what the guidance implies (e.g. "reiterating rather than \
  lowering margin guidance right after the steepest decline is itself a \
  signal"). Clearly labelled interpretation, not a source claim. \
  {"text": ""} if you have no defensible read.

Within that structure, five disciplines separate real analysis from a \
fact sheet - apply every one the source material supports:

- **Benchmark every number, and stack the comparison when the source \
  supports more than one.** A figure alone proves nothing - state it \
  against a prior period, a peer, a segment, an index, or a stated \
  target/guidance figure from the source. When more than one comparison \
  is available and each tells a different part of the story (e.g. the \
  multi-period trend AND the single-period move both matter), use more \
  than one rather than picking whichever looks cleanest.
- **Name the specific mechanism behind any tension, never a category \
  word.** When a result is mixed - a gain offset by a drag, growth \
  alongside compression, a win with a caveat - state the concrete, \
  specific driver behind each side exactly as the source describes it \
  (a named segment, a named cause, a named product line). "Headwinds," \
  "challenges," "pressures," and similar category words standing in for \
  an unstated cause are not acceptable substitutes for what the source \
  actually says.
- **Sequence past from future; never blend them in one sentence.** Fully \
  explain what already happened - with its own comparisons and named \
  mechanisms - before turning to what's expected, forecast, guided, or \
  pending. Keep forward-looking material in the outlook, or in a clearly \
  forward-marked part of a section - never stated as though it were \
  history.
- **Narrate any dated or sequential event as an unfolding process, not a \
  static label.** This covers a legal or regulatory step, an acquisition \
  or deal, a product launch, a leadership change, a financing - anything \
  with a date and a next move. Name the specific thing at stake (the \
  actual relief, remedy, claim, deal, or milestone - never a generic \
  "legal risk" or "M&A activity"). State the dates the source gives as a \
  concrete timeline, and give the specific next step where the source \
  provides one, rather than a vague "pending further developments." When \
  the source includes a party's own stated defense or position, \
  represent it faithfully rather than asserting your own verdict.
- **State a triggering event and its consequence together, in the same \
  sentence.** When the source ties a market, financial, or operational \
  reaction to a specific cause, state the magnitude and the cause \
  together - don't split them across two sentences and leave the reader \
  to connect them. Not "Revenue rose. Separately, an acquisition closed \
  in the quarter." but "Revenue rose, with roughly half the gain from \
  the acquisition's first full quarter" - when the source supports that \
  link.

Not every document has material for all five - a plain internal memo may \
have no legal content or market reaction, and that's fine. Apply each \
where the source supports it; never force one that doesn't fit. If the \
manifest note says no figure-to-figure comparison is available, say so \
plainly rather than dressing a lone figure as if it were benchmarked.

Directional words must match the fact's real direction - "rose," "grew," \
"increased," "up," "expanded" only when the change is genuinely positive; \
"fell," "declined," "decreased," "down," "compressed" only when it is \
genuinely negative. Use a "growth_percent" fact for a directional claim - \
its sign is well-defined (it is computed from-value to to-value, so \
positive always means a real increase and negative a real decrease). \
Never use a "difference" fact to justify a directional word - a \
"difference"'s sign only reflects which number happened to be listed \
first, not which period came later, so it proves nothing about direction. \
State a "difference" as a plain magnitude ("changed by {{N}}", "a gap of \
{{N}}") with no "rose"/"fell" attached. This is checked and a mismatch \
gets the whole narrative rejected - a real fact rendered with the wrong \
direction word is a wrong report, even though the number itself is real.

This rule bites hardest, and most often, on a margin or rate's \
period-over-period move (gross margin, operating margin, any percentage- \
point change) - the manifest almost always carries that as a "difference" \
in points, never a "growth_percent", because a growth_percent of two \
already-percentage values is not a number anyone reports. Writing \
"margin fell {{N}} points" is the natural instinct and exactly what gets \
rejected. Correct: "gross margin moved {{N}} points, from {{M}} to \
{{P}}" or "a {{N}}-point change in gross margin, to {{P}} from {{M}}" - \
magnitude and both endpoints, no "fell"/"rose"/"compressed"/"expanded". \
The reader sees {{M}} and {{P}} and draws the direction themselves; you \
never need the word for it to be clear.

This restriction is scoped to a "difference" fact specifically - it does \
NOT apply when you cite several individual period quotes in a row (e.g. \
five separate quarterly margin figures for a trend sentence). Each of \
those is its own verified value, not a "difference", so a plain, accurate \
direction word ("declined," "fell") is expected and correct there - \
avoiding it when it is warranted reads as evasive, not careful. Use the \
word exactly where a "growth_percent" or a run of raw period quotes \
supports it; withhold it only next to an actual "difference" fact.

A claim of "N consecutive quarters" or "N straight quarters" of a trend \
needs at least N+1 distinct period figures cited as {{N}} placeholders in \
that same sentence - N consecutive moves are the transitions between N+1 \
data points, not N of them. If the sentence doesn't cite that many period \
figures, either cite them or make a claim your citations actually \
support (fewer quarters, or a plain "declined across recent periods" \
with no specific count). This is checked the same way directional words \
are, and a shortfall gets the whole narrative rejected.

GAAP vs. non-GAAP: a fact's manifest entry says which it is. When the \
manifest has only one of the two for a metric, cite it plainly - most \
figures never have this distinction at all. When it has *both* - the \
standard/audited figure and management's own "adjusted"/"non-GAAP"/"pro \
forma" version - state the GAAP figure as the primary fact; you may also \
cite the non-GAAP figure as management's own adjusted view (it renders \
with its own visible tag automatically - you never need to write "non- \
GAAP" yourself, citing {{N}} is enough), but never in place of the GAAP \
figure, and never lead with the adjusted number as though it were the \
official one. If the manifest gives you a computed reconciling gap \
between the two, that gap - what's actually excluded from the adjusted \
figure - is usually the more informative sentence than either number \
alone.

Charts: give a section a chart only when it plots two or more facts you \
are already citing and the shape carries real information. The chart's \
"type" field is a formality, not your decision - fill it with any valid \
value, it is never consulted for rendering. What actually determines the \
chart's real, rendered type is the shape of the data you cite, decided \
by code: a start -> components -> end bridge (first series point is the \
start level, the middle points are the signed components, the last is \
the end level - only rendered if they actually sum to the move) renders \
as a waterfall; three or more period-labelled points (a quarter, a \
fiscal year, a month) render as a line, a trend over time; anything else \
- categories or segments compared side by side - renders as a bar. So \
what matters is which facts you plot and their order, never a type name: \
cite the start, then each component, then the end, in that order, for a \
bridge; cite periods in chronological order for a trend. Set has_chart \
false for every other section (a single number, or a point better made \
in prose). Reference each chart point by its fact number - the same \
numbers you cite in the text - and set the chart's format to match those \
facts (usd / percent / number). When has_chart is false, still fill \
chart with placeholders (type "bar", title "", format "number", \
series []) - it is ignored.

Forward-looking facts in the manifest are tagged [guidance] or \
[projected]. They belong in the outlook, or in a clearly forward-marked \
part of a section - never asserted as a historical result.

To use a "[citable]" fact's value, write {{N}} (its number in the \
manifest) exactly where the value belongs - never write the number \
itself, it is filled in for you afterward. A single paragraph typically \
weaves in several facts this way as evidence for one point. Every \
placeholder's rendered value already carries its own unit ("$34.0M", \
"58.7%") - never follow one with "million"/"billion"/"thousand"/"percent" \
spelled out; that either doubles the unit or, for a fact with no numeric \
value at all (see the next paragraph), silently misuses it as if it were \
one. An "[event]" \
fact's {{N}} substitutes just its short name - write the sentence around \
it normally ("the {{N}} closed in May" -> "the acquisition of Halyard \
Analytics closed in May") - it is never a number, so it can never be \
followed by "million" or any other unit. Its date/status/next-step \
already appear in a \
dedicated timeline elsewhere in the rendered report when the source \
supports one - never retype those details from the manifest into your \
own prose; that produces duplicated, run-on text. An event's \
date/status/next_step text is shown to you so you understand the event, \
not so you can cite what's inside it - it often contains a real number \
(a dollar figure, a percent) that has no {{N}} of its own, because the \
only placeholder an event carries substitutes its short name, never a \
number from within it. If that number matters enough to state, check \
whether it already exists as its own separate [citable] fact elsewhere \
in the manifest and cite that instead; if it doesn't, leave the specific \
figure out and describe the event qualitatively ("costs are expected to \
decline in Q4" rather than a dollar amount you have no placeholder for). \
Writing that number as a bare digit because you can see it in an event's \
status is exactly the violation this rule catches. A "[context, not \
citable]" fact is \
already-verified prose you may draw on for tone or content, but it has no \
number to cite - write your own sentence about it with no digits, except \
a quarter/half/year reference (e.g. "Q4 2026" or "heading into 2027"), \
which is fine anywhere. Never write any other digit outside a {{N}} \
placeholder.
"""

_PARAGRAPH_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}

_CHART_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": list(_CHART_TYPES)},
        "title": {"type": "string"},
        "format": {"type": "string", "enum": list(_CHART_FORMATS)},
        "series": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "fact_index": {"type": "integer"},
                },
                "required": ["label", "fact_index"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["type", "title", "format", "series"],
    "additionalProperties": False,
}

_SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "heading": {"type": "string"},
        "paragraphs": {"type": "array", "items": _PARAGRAPH_SCHEMA},
        "has_chart": {"type": "boolean"},
        "chart": _CHART_SCHEMA,
    },
    # Every property required - the Slice 26 rule. "not applicable" is the
    # has_chart boolean plus placeholder values, never an absent key, so
    # the strict-mode grammar compiler has no optional-property
    # combinatorics to enumerate (that is what produced the live
    # "400 Schema is too complex"). Nesting is fine; only optionality was.
    "required": ["heading", "paragraphs", "has_chart", "chart"],
    "additionalProperties": False,
}

# Slice 36: a KPI strip entry - a headline metric, its year-over-year delta
# (a computed segment), or -1 for "no delta". Both indices point into the
# already-verified segments; the ✓ / ∑ tag comes from segments[i]["type"].
_KPI_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "value_fact": {"type": "integer"},
        "delta_fact": {"type": "integer"},
    },
    "required": ["label", "value_fact", "delta_fact"],
    "additionalProperties": False,
}

_TOOL = {
    "name": "write_narrative",
    "description": (
        "Submit the finished report: a KPI strip, an executive summary with "
        "one boxed cross-section insight, 3-5 sections (each with an "
        "optional chart), any disclosure gaps, and an outlook."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "kpis": {"type": "array", "items": _KPI_SCHEMA},
            "executive_summary": {"type": "array", "items": _PARAGRAPH_SCHEMA},
            "executive_insight": _PARAGRAPH_SCHEMA,
            "sections": {"type": "array", "items": _SECTION_SCHEMA},
            "disclosure_gaps": {"type": "array", "items": _PARAGRAPH_SCHEMA},
            "outlook": {"type": "array", "items": _PARAGRAPH_SCHEMA},
            "outlook_interpretation": _PARAGRAPH_SCHEMA,
        },
        "required": [
            "kpis", "executive_summary", "executive_insight", "sections",
            "disclosure_gaps", "outlook", "outlook_interpretation",
        ],
        "additionalProperties": False,
    },
}

# A small, scoped tool for fixing one rejected paragraph in place - see
# write_narrative's repair loop and specs/slice-40/spec.md. Reuses
# _PARAGRAPH_SCHEMA: the response is just the corrected text.
_REPAIR_TOOL = {
    "name": "fixed_paragraph",
    "description": "Return a corrected version of one rejected report paragraph.",
    "strict": True,
    "input_schema": _PARAGRAPH_SCHEMA,
}

_REPAIR_SYSTEM_PROMPT = """\
You are fixing exactly one paragraph from a verified financial report that \
failed a specific, stated check - not writing a new report. Keep the \
paragraph's point and as much of its original wording as you reasonably \
can; change only what the rejection reason requires.

Every number is a {{N}} placeholder referencing the manifest below - never \
a literal digit (a bare quarter/year reference like "Q4 2026" is the one \
exception). A directional word ("rose"/"fell"/"grew"/"declined"/etc.) next \
to a {{N}} is only allowed beside a "growth_percent" fact whose sign \
matches - never beside a "difference" fact; state a "difference" as a \
plain magnitude with no directional word. This bites hardest on a margin \
or rate's period-over-period move (gross margin, operating margin, any \
percentage-point change) - that is almost always a "difference" in \
points, not a "growth_percent", so "margin fell {{N}} points" is exactly \
the violation this rule catches. Correct: "gross margin moved {{N}} \
points, from {{M}} to {{P}}" - magnitude and both endpoints, no "fell"/ \
"rose"/"compressed"/"expanded"; the reader sees {{M}} and {{P}} and draws \
the direction themselves. This scoping is only for an actual "difference" \
fact - if instead you're citing several individual period quotes in a \
row (raw values, not a computed difference), a plain accurate direction \
word is correct and expected there; do not strip one out that was \
already fine. A claim of "N consecutive" or "N straight \
quarters" needs at least N+1 distinct period figures cited as {{N}} \
placeholders in that same sentence - cite that many or claim less. Every \
placeholder's rendered value already carries its own unit ("$34.0M", \
"58.7%") - never follow one with "million"/"billion"/"thousand"/"percent" \
spelled out, and never treat an event's {{N}} (a short name, not a \
number) as if it had one. If the digit you're being asked to remove came \
from an event's date/status/next_step text in the manifest, it has no \
{{N}} of its own - check for a separate [citable] fact with that same \
number elsewhere in the manifest and cite that instead; if there isn't \
one, drop the specific figure and describe the event qualitatively \
instead of inventing a placeholder for it.
"""


def _build_manifest(segments):
    lines = []
    for i, segment in enumerate(segments):
        horizon = segment.get("horizon", "reported")
        labels = [] if horizon == "reported" else [horizon]
        if segment.get("gaap_status") == "non_gaap":
            labels.append("non-gaap")
        tag = f" [{', '.join(labels)}]" if labels else ""
        if segment["type"] == "prose":
            lines.append(f'Fact {i} [context, not citable]{tag}: "{segment["text"]}"')
        elif segment["type"] == "event":
            # Show the whole structure so the model narrates it as a
            # timeline and references it with {{i}}, not by retyping a date.
            parts = [f'what="{segment["what"]}"']
            for key in ("date", "status", "next_step"):
                if segment.get(key):
                    parts.append(f'{key}="{segment[key]}"')
            for m in segment.get("milestones") or []:
                parts.append(f'milestone("{m["date"]}": {m["detail"]})')
            lines.append(f"Fact {i} [event]{tag}: " + ", ".join(parts))
        else:
            # "quote" = a direct source figure (renders with a ✓ tag);
            # "computed" = independently recomputed (renders with a ∑ tag).
            kind = "quote" if segment["type"] == "quote" else "computed"
            label = segment.get("label") or "Fact"
            lines.append(
                f'Fact {i} [citable, {kind}]{tag}: label="{label}", '
                f'value={display_value(segment, "actual")}'
            )
    return "\n".join(lines)


_UP_WORDS_RE = re.compile(
    r"\b(rose|rising|grew|grow|grown|growing|increased|increasing|gained|gaining|"
    r"expanded|expanding|climbed|climbing|jumped|jumping|improved|improving)\b",
    re.IGNORECASE,
)
_DOWN_WORDS_RE = re.compile(
    r"\b(fell|falling|declined|declining|decreased|decreasing|dropped|dropping|"
    r"shrank|shrunk|shrinking|compressed|compressing|contracted|contracting|"
    r"worsened|worsening|deteriorated|deteriorating)\b",
    re.IGNORECASE,
)
_DIRECTION_WINDOW = 70  # chars of prose that may precede a {{N}} and still describe it


def _direction_problem(text, segments):
    """A direction word ("rose"/"fell") next to a {{N}} must match what
    that fact actually shows - found live 2026-09-11: net income
    described as "rose... up $2.8M" when it had fallen $22.4M -> $19.6M.
    The $2.8M was real and correctly computed; the direction word was
    simply wrong, and nothing checked it against the fact's own sign.

    Only "growth_percent" has a sign this codebase actually defines
    (operands are [from, to] - analystos.l2.analyze - so positive is a
    real increase). "difference"'s sign depends only on which operand the
    model listed first, which nothing can verify after the fact - so a
    direction word next to a "difference" fact is refused outright, not
    sign-checked: the narrator must cite a "growth_percent" fact for a
    directional claim, or drop the direction word and state the plain
    magnitude (see the "Directional words" rule in _SYSTEM_PROMPT).
    "remainder" (Slice 47's organic-vs-inorganic split) is the same
    arithmetic as "difference" and gets the same treatment - nothing
    verifies that operand[0] genuinely is "the total" as opposed to just
    the first number listed, so its sign is exactly as untrustworthy.
    """
    for match in _PLACEHOLDER_RE.finditer(text):
        index = int(match.group(1))
        if index < 0 or index >= len(segments):
            continue
        seg = segments[index]
        if seg.get("type") != "computed" or seg.get("operation") not in (
            "growth_percent", "difference", "remainder",
        ):
            continue
        window = text[max(0, match.start() - _DIRECTION_WINDOW):match.start()]
        # A direction word only describes *this* {{N}} if no other
        # placeholder sits between the word and {{N}} - found live
        # 2026-09-11: "Net income declined to {{7}} from {{8}}, a change
        # of {{6}}" correctly used "declined" for the {{7}}-vs-{{8}}
        # comparison, but the word still fell inside {{6}}'s lookback
        # window and got flagged as though it described the "difference"
        # fact {{6}} instead - a false positive on an already-correct
        # sentence, not a real violation.
        other_placeholders = list(_PLACEHOLDER_RE.finditer(window))
        if other_placeholders:
            window = window[other_placeholders[-1].end():]
        up_matches = list(_UP_WORDS_RE.finditer(window))
        down_matches = list(_DOWN_WORDS_RE.finditer(window))
        nearest_up = up_matches[-1].start() if up_matches else -1
        nearest_down = down_matches[-1].start() if down_matches else -1
        if nearest_up < 0 and nearest_down < 0:
            continue
        said_up = nearest_up > nearest_down
        if seg["operation"] in ("difference", "remainder"):
            return (
                f"fact {index} is a {seg['operation']!r} (its sign isn't a reliable "
                f"direction) but a directional word appears next to it - cite a "
                f"'growth_percent' fact for direction, or state the plain magnitude"
            )
        value = seg.get("value", 0)
        if said_up and value < 0:
            return f"fact {index} is described as an increase but its verified change is negative ({value})"
        if not said_up and value > 0:
            return f"fact {index} is described as a decrease but its verified change is positive ({value})"
    return None


_CONSECUTIVE_RE = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
    r"(?:consecutive|straight)\s+quarters?\b",
    re.IGNORECASE,
)
_NUMBER_WORDS = {w: i + 1 for i, w in enumerate(
    ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
)}


def _consecutive_count_problem(text, segments):
    """"N consecutive quarters" needs N+1 data points (N is a count of
    *transitions* between periods, not of periods) - found live
    2026-09-11: a claim of five consecutive declines from what was, in a
    different run, only four cited period figures (three real declines).
    Only checks a sentence where the model itself cites the period
    figures as {{N}} quotes - if it doesn't, there's nothing here to
    verify the claim against, so this stays silent rather than guess.
    """
    for match in _CONSECUTIVE_RE.finditer(text):
        word = match.group(1).lower()
        claimed = _NUMBER_WORDS.get(word) or (int(word) if word.isdigit() else None)
        if not claimed:
            continue
        start = text.rfind(".", 0, match.start()) + 1
        stop = text.find(".", match.end())
        sentence = text[start:] if stop == -1 else text[start:stop]
        cited_periods = {
            int(pm.group(1))
            for pm in _PLACEHOLDER_RE.finditer(sentence)
            if int(pm.group(1)) < len(segments)
            and segments[int(pm.group(1))].get("type") == "quote"
            and segments[int(pm.group(1))].get("value") is not None
        }
        if cited_periods and claimed > len(cited_periods) - 1:
            return (
                f"claims {claimed} consecutive quarters but only cites "
                f"{len(cited_periods)} period figures in that sentence - "
                f"{claimed} consecutive moves need at least {claimed + 1} data points"
            )
    return None


_REDUNDANT_UNIT_RE = re.compile(
    r"\{\{(\d+)\}\}\s*(million|billion|thousand|percent)\b", re.IGNORECASE
)


def _redundant_unit_problem(text):
    """A {{N}}'s rendered value already carries its own unit - "$34.0M" for
    a usd fact, "58.7%" for a percent one - display_value/format_number
    never spell "million"/"billion"/"thousand"/"percent" out. Typing one of
    those words right after a placeholder is always wrong: at best it
    doubles up the unit, at worst it silently repurposes a non-numeric
    fact (an event, a qualitative quote) as if it were a dollar or percent
    figure with no numeric value behind it at all.

    Found live 2026-09-11: {{18}} correctly named an acquisition event in
    one sentence ("the {{18}}") and was then written as "approximately
    {{18}} million" in another - Gate 2 (language quality) caught the
    inconsistency, but nothing before it refused the paragraph outright,
    so a report could still be internally inconsistent and merely
    "sound wrong" rather than fail a checked rule. ("Points"/"pts" is
    deliberately not covered - a percentage-point disambiguator like
    "{{N}} points" is a real, necessary clarification a percent-formatted
    value doesn't carry on its own; see the "Directional words" rule in
    _SYSTEM_PROMPT.)
    """
    match = _REDUNDANT_UNIT_RE.search(text)
    if match:
        return (
            f'fact {match.group(1)} is followed by the spelled-out word '
            f'"{match.group(2)}" - its rendered value already includes its own unit'
        )
    return None


def _validate_paragraph(text, segments):
    """``None`` if the paragraph is trustworthy - every {{N}} points to a
    real, citable fact, no digit appears outside a placeholder, no
    placeholder is followed by a redundant spelled-out unit, any
    directional word next to a computed fact matches its real direction,
    and any "N consecutive quarters" claim is consistent with the period
    figures cited in the same sentence - otherwise a short human-readable
    reason it isn't, so a rejection can be logged with something more
    useful than just "it failed."
    """
    for match in _PLACEHOLDER_RE.finditer(text):
        index = int(match.group(1))
        if index < 0 or index >= len(segments):
            return f"references fact {index}, which doesn't exist"
        if segments[index]["type"] == "prose":
            return f"references fact {index}, which isn't citable (a prose segment)"
    stripped = _CALENDAR_RE.sub("", _PLACEHOLDER_RE.sub("", text))
    if _DIGIT_RE.search(stripped):
        return "has a digit outside any {{N}} placeholder"
    problem = _redundant_unit_problem(text)
    if problem:
        return problem
    problem = _direction_problem(text, segments)
    if problem:
        return problem
    return _consecutive_count_problem(text, segments)


def _validate_chart(chart, segments):
    """Return a cleaned chart spec, or ``None`` if what's left isn't a real
    chart. A chart is usable only if it plots at least two facts that are
    real, citable, and numeric (a ``quote``/``computed`` segment carrying a
    ``value`` - never ``prose``, never a qualitative quote). Bad points are
    dropped; a chart under two points is dropped whole. A bad chart is
    never fatal - the report renders without it - matching
    ``rich_export._resolve_chart``, which stays as defence in depth.
    """
    if not isinstance(chart, dict) or chart.get("type") not in _CHART_TYPES:
        return None
    fmt = chart.get("format")
    if fmt not in _CHART_FORMATS:
        fmt = "number"
    series = []
    for point in chart.get("series") or []:
        try:
            index = int(point.get("fact_index"))
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= len(segments):
            continue
        segment = segments[index]
        if segment["type"] == "prose" or segment.get("value") is None:
            continue
        series.append({"label": str(point.get("label") or ""), "fact_index": index})
    if len(series) < 2:
        return None

    if chart["type"] == "waterfall":
        # start -> signed components -> end. Only render it if it genuinely
        # bridges: a waterfall that doesn't add up is a fabricated
        # attribution, exactly what the verification guarantee forbids for
        # a chart. Needs at least start + one component + end.
        vals = [segments[p["fact_index"]]["value"] for p in series]
        if len(vals) < 3:
            return None
        bridged = vals[0] + sum(vals[1:-1])
        if abs(bridged - vals[-1]) > _BRIDGE_TOL * max(abs(vals[-1]), 1.0):
            return None

    return {
        "type": chart["type"],
        "title": str(chart.get("title") or ""),
        "format": fmt,
        "series": series,
    }


def _locate_problem(report, segments):
    """Find the single paragraph responsible for ``report`` failing
    validation, if any - the exact same walk ``_assemble_report`` uses, so
    what this finds is exactly what would reject the report. Used to
    repair just that one paragraph instead of regenerating the whole
    narrative (see ``write_narrative``'s repair loop).

    Returns ``None`` if the report is clean, ``("structural", reason)`` for
    a problem no single-paragraph fix can address (missing/malformed
    sections - needs a real rewrite), or ``(get, set_text, reason)`` for one
    repairable paragraph: ``get()`` returns its current text, ``set_text(t)``
    replaces it in place within ``report``.
    """
    def _leaf(container, index=None):
        if index is None:
            return (lambda: container.get("text") or "",
                    lambda t: container.__setitem__("text", t))
        return (lambda: container[index].get("text") or "",
                lambda t: container[index].__setitem__("text", t))

    executive_summary = report.get("executive_summary") or []
    raw_sections = report.get("sections") or []
    outlook = report.get("outlook") or []

    if not executive_summary:
        return ("structural", "empty executive_summary")
    if not raw_sections:
        return ("structural", "no sections")

    for i, p in enumerate(executive_summary):
        reason = _validate_paragraph(p.get("text", ""), segments)
        if reason:
            get, set_text = _leaf(executive_summary, i)
            return get, set_text, f"executive-summary paragraph {reason}"

    for si, section in enumerate(raw_sections):
        heading = (section.get("heading") or "").strip()
        paragraphs = section.get("paragraphs") or []
        if not heading or not paragraphs:
            return ("structural", f"section {si} has no heading or no paragraphs")
        for pi, p in enumerate(paragraphs):
            reason = _validate_paragraph(p.get("text", ""), segments)
            if reason:
                get, set_text = _leaf(paragraphs, pi)
                return get, set_text, f"section {si} paragraph {reason}"

    for i, p in enumerate(outlook):
        reason = _validate_paragraph(p.get("text", ""), segments)
        if reason:
            get, set_text = _leaf(outlook, i)
            return get, set_text, f"outlook paragraph {reason}"

    insight_obj = report.get("executive_insight")
    if isinstance(insight_obj, dict):
        insight = (insight_obj.get("text") or "").strip()
        if insight:
            reason = _validate_paragraph(insight, segments)
            if reason:
                get, set_text = _leaf(insight_obj)
                return get, set_text, f"executive_insight {reason}"

    interp_obj = report.get("outlook_interpretation")
    if isinstance(interp_obj, dict):
        interp = (interp_obj.get("text") or "").strip()
        if interp:
            reason = _validate_paragraph(interp, segments)
            if reason:
                get, set_text = _leaf(interp_obj)
                return get, set_text, f"outlook_interpretation {reason}"

    return None


def _clean_paragraphs(items, segments):
    """Keep only the paragraphs in ``items`` that pass ``_validate_paragraph``
    - used for advisory blocks (disclosure gaps) where one bad entry should
    drop that entry, not the whole report."""
    out = []
    for p in items or []:
        text = (p.get("text") or "").strip()
        if text and _validate_paragraph(text, segments) is None:
            out.append({"text": text})
    return out


def _resolve_kpis(raw_kpis, segments):
    """Up to 5 KPI-strip entries. Each keeps only if ``value_fact`` points
    at a numeric verified segment; ``delta_fact`` is kept when it points at
    a computed one, else set to -1 (no delta). Bad entries are dropped, not
    fatal."""
    out = []
    for k in raw_kpis or []:
        try:
            vi = int(k.get("value_fact"))
        except (TypeError, ValueError):
            continue
        if not (0 <= vi < len(segments)) or segments[vi].get("value") is None:
            continue
        try:
            di = int(k.get("delta_fact"))
        except (TypeError, ValueError):
            di = -1
        if not (0 <= di < len(segments)) or segments[di].get("type") != "computed":
            di = -1
        out.append({"label": str(k.get("label") or ""), "value_fact": vi, "delta_fact": di})
        if len(out) == 5:
            break
    return out


def _assemble_report(report, segments, title):
    """Validate one ``write_narrative`` tool response, already unwrapped to
    its plain dict (``None`` if the model's response had no usable
    tool_use block), into a render-ready report dict. Returns
    ``(report, None)`` or ``(None, reason)`` and never raises - so the
    caller can retry with the reason before falling back. A malformed
    chart is dropped (``chart`` -> ``None``), never a reason to reject the
    whole report. Validation itself is ``_locate_problem`` - the single
    source of truth also used to find and repair one bad paragraph without
    rejecting the rest of an otherwise-good report.
    """
    if report is None:
        return None, "response had no tool_use block"

    problem = _locate_problem(report, segments)
    if problem is not None:
        if problem[0] == "structural":
            return None, problem[1]
        get, _set_text, reason = problem
        return None, f"{reason}: {get()!r}"

    executive_summary = report.get("executive_summary") or []
    raw_sections = report.get("sections") or []
    outlook = report.get("outlook") or []

    sections = []
    for section in raw_sections:
        heading = (section.get("heading") or "").strip()
        paragraphs = section.get("paragraphs") or []
        chart = _validate_chart(section.get("chart"), segments) if section.get("has_chart") else None
        sections.append(
            {
                "heading": heading,
                "paragraphs": [{"text": p["text"]} for p in paragraphs],
                "chart": chart,
            }
        )

    insight = (report.get("executive_insight") or {}).get("text", "").strip()
    interp = (report.get("outlook_interpretation") or {}).get("text", "").strip()

    return {
        "title": title,
        "kpis": _resolve_kpis(report.get("kpis"), segments),
        "executive_summary": [{"text": p["text"]} for p in executive_summary],
        "executive_insight": insight or None,
        "sections": sections,
        "disclosure_gaps": _clean_paragraphs(report.get("disclosure_gaps"), segments),
        "outlook": [{"text": p["text"]} for p in outlook] or None,
        "outlook_interpretation": interp or None,
    }, None


def _repair_paragraph(client, manifest, text, reason):
    """One small, scoped call to fix a single rejected paragraph instead of
    regenerating the whole narrative - see write_narrative's repair loop
    and specs/slice-40/spec.md. Returns the corrected text, or ``None`` if
    the call didn't produce a usable one (caller falls back to a full
    retry). A real API failure still becomes ``ValueError`` via
    ``_create_message``, exactly as it does everywhere else in this file -
    not caught here.
    """
    response = _create_message(
        client,
        model=_MODEL,
        max_tokens=1024,
        system=_REPAIR_SYSTEM_PROMPT,
        tools=[_REPAIR_TOOL],
        tool_choice={"type": "tool", "name": "fixed_paragraph"},
        messages=[{
            "role": "user",
            "content": (
                f"{manifest}\n\nThis paragraph was rejected: {reason}.\n\n"
                f"Original paragraph: {text!r}\n\nReturn the corrected paragraph."
            ),
        }],
    )
    tool_use = next(
        (b for b in getattr(response, "content", []) if getattr(b, "type", None) == "tool_use"),
        None,
    )
    if tool_use is None or not isinstance(tool_use.input, dict):
        return None
    fixed = (tool_use.input.get("text") or "").strip()
    return fixed or None


def write_narrative(segments, title, client=None):
    """Ask Claude how to structure and write a report about already-
    verified ``segments``; return a ``report`` dict ready for
    ``analystos.l4.rich_export.render_rich_report`` (see the module
    docstring for its shape).

    Raises ``ValueError`` on any failure - no citable fact at all, a
    bad/missing tool response, a paragraph that fails validation, an empty
    executive summary or sections list, a section with no heading or
    body, or the Anthropic API call itself failing (shared
    ``_resolve_client``/``_create_message`` with ``analystos.l2.analyze``).
    The caller (``analystos.pipeline``) catches it and falls back to
    Slice 26's plain per-segment rendering. A malformed chart is the one
    non-fatal case - dropped, not raised.
    """
    if not any(segment["type"] != "prose" for segment in segments):
        raise ValueError("no citable facts to narrate")

    client = _resolve_client(client)
    manifest = _build_manifest(segments)
    coverage = coverage_summary(segments)
    forward = coverage["horizons"]["guidance"] + coverage["horizons"]["projected"]

    user_content = (
        f'Title: "{title}"\n\n{manifest}\n\n'
        f"(Comparisons available: {coverage['comparisons']}; "
        f"forward-looking facts: {forward}.)"
    )
    if coverage["comparisons"] == 0:
        user_content += (
            "\n\nThis document supports no figure-to-figure comparison. Say that "
            "plainly rather than presenting a lone figure as if it were benchmarked."
        )

    def _call(extra=""):
        response = _create_message(
            client,
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "write_narrative"},
            messages=[{"role": "user", "content": user_content + extra}],
        )
        if getattr(response, "stop_reason", None) == "max_tokens":
            print(
                f"[analystos.l2.narrate] response hit max_tokens ({_MAX_TOKENS}) - "
                "the narrative was truncated",
                file=sys.stderr,
            )
        tool_use = next(
            (b for b in getattr(response, "content", [])
             if getattr(b, "type", None) == "tool_use"),
            None,
        )
        return tool_use.input if tool_use is not None and isinstance(tool_use.input, dict) else None

    raw_report = _call()
    report, reason = _assemble_report(raw_report, segments, title)

    # Repair phase: the common failure is one bad paragraph in an
    # otherwise-good report - fix just that paragraph (a small, cheap call)
    # rather than regenerating the whole document, where every other
    # paragraph gets a fresh, independent chance to break a *different*
    # rule. Found live 2026-09-11, three runs in a row: a full regenerate
    # reliably fixed the reported violation while introducing a new one
    # elsewhere, burning every retry on lateral moves instead of progress.
    # See specs/slice-40/spec.md.
    for repair_attempt in range(1, _MAX_REPAIR_ATTEMPTS + 1):
        if report is not None or raw_report is None:
            break
        problem = _locate_problem(raw_report, segments)
        if problem is None or problem[0] == "structural":
            break  # nothing a single-paragraph fix can do - fall through
        get, set_text, para_reason = problem
        print(
            f"[analystos.l2.narrate] repairing one paragraph "
            f"(attempt {repair_attempt} of {_MAX_REPAIR_ATTEMPTS}): {para_reason}",
            file=sys.stderr,
        )
        fixed = _repair_paragraph(client, manifest, get(), para_reason)
        if fixed is None:
            break
        set_text(fixed)
        report, reason = _assemble_report(raw_report, segments, title)

    # Full-regenerate fallback - a nudge fixes it far more often than a
    # fresh call. Falling back to the plain rendering over a fixable
    # writing slip is what made real reports look "grade 1" (found live
    # 2026-09-09). Kept as the safety net for a structural problem (missing
    # sections, an empty executive summary) that no paragraph-level repair
    # can address, or if repair itself didn't converge.
    for attempt in range(1, _MAX_RETRIES + 1):
        if report is not None:
            break
        print(
            f"[analystos.l2.narrate] narrative rejected ({reason}) - "
            f"retrying (attempt {attempt} of {_MAX_RETRIES})",
            file=sys.stderr,
        )
        report, reason = _assemble_report(
            _call(
                f"\n\nYour previous narrative was rejected: {reason}. Fix exactly "
                "that - and check every other rule below still holds, since "
                "fixing one violation must never introduce another: (1) every "
                "number is a {{N}} placeholder, never a digit outside one (a "
                'date like "September 30, 2026" or "Q4 2026" is fine); (2) a '
                'directional word ("rose"/"fell"/etc.) next to a {{N}} only '
                'appears beside a "growth_percent" fact whose sign matches - '
                'never a "difference" fact; (3) "N consecutive/straight '
                'quarters" cites at least N+1 distinct period figures in that '
                "same sentence, or claims less. Return kpis, executive_summary "
                "(3-5 sentences, verified facts only), executive_insight, 3-5 "
                "sections each with a heading "
                "and a paragraph, disclosure_gaps, outlook, outlook_interpretation."
            ),
            segments,
            title,
        )
    if report is None:
        raise ValueError(
            f"narrative rejected after paragraph repair and {_MAX_RETRIES} "
            f"full retries: {reason}"
        )

    print(
        f"[analystos.l2.narrate] narrative accepted: {len(report['sections'])} "
        f"sections, {sum(1 for s in report['sections'] if s['chart'])} chart(s), "
        f"outlook={'yes' if report['outlook'] else 'no'}",
        file=sys.stderr,
    )
    return report


def _field_leaf(container, index, field):
    return (lambda: container[index].get(field) or "",
            lambda t: container[index].__setitem__(field, t))


def _top_level_leaf(report, key):
    return (lambda: report.get(key) or "", lambda t: report.__setitem__(key, t))


def _report_text_locations(report):
    """Every ``(get, set_text)`` pair for a piece of reader-facing prose in
    an *assembled* report - the exact traversal
    ``analystos.l2.proofread._report_text`` uses to build what Gate 2
    reads, so one of its quoted ``location`` fragments can be found and
    patched in place. Unlike ``_locate_problem`` (the pre-assembly shape,
    where every text field is nested in a ``{"text": ...}`` dict),
    ``executive_insight``/``outlook_interpretation`` are plain strings on
    an assembled report - hence the separate top-level leaf.
    """
    locations = []
    for i in range(len(report.get("executive_summary") or [])):
        locations.append(_field_leaf(report["executive_summary"], i, "text"))
    if report.get("executive_insight"):
        locations.append(_top_level_leaf(report, "executive_insight"))
    for si in range(len(report.get("sections") or [])):
        locations.append(_field_leaf(report["sections"], si, "heading"))
        paragraphs = report["sections"][si].get("paragraphs") or []
        for pi in range(len(paragraphs)):
            locations.append(_field_leaf(paragraphs, pi, "text"))
    for i in range(len(report.get("disclosure_gaps") or [])):
        locations.append(_field_leaf(report["disclosure_gaps"], i, "text"))
    for i in range(len(report.get("outlook") or [])):
        locations.append(_field_leaf(report["outlook"], i, "text"))
    if report.get("outlook_interpretation"):
        locations.append(_top_level_leaf(report, "outlook_interpretation"))
    return locations


def repair_language_issues(report, issues, segments, client=None):
    """Best-effort patch of each Gate 2 (language-quality) issue's flagged
    text in place, rather than losing the whole report to a wording nit -
    the same "repair one small piece instead of a full regenerate"
    principle ``write_narrative``'s own repair loop already uses, applied
    to Gate 2 instead of Gate 1. Mutates and returns ``report``; never
    raises (a real API failure surfaces as ``ValueError`` from
    ``_create_message``, same as everywhere else, and just leaves that one
    issue unpatched rather than losing every other fix in progress - see
    the try/except below).

    A repair is only kept if the result still satisfies Gate 1's own
    ``_validate_paragraph`` - a wording fix must never quietly reintroduce
    a correctness violation (a dropped placeholder, a stray digit, a
    flipped direction word). An issue whose ``location`` can't be found in
    the report, or whose repair doesn't validate, is left as-is; the
    caller re-runs Gate 2 afterward to see what's actually still wrong.
    """
    client = _resolve_client(client)
    manifest = _build_manifest(segments)
    locations = _report_text_locations(report)
    for issue in issues:
        loc_text = (issue.get("location") or "").strip()
        if not loc_text:
            continue
        # Exact-uniqueness match only - a short/generic location (Gate 2's
        # prompt only promises "a short, exact fragment," not a unique
        # one) can be a substring of more than one field. Patching the
        # first hit risks silently rewriting the wrong sentence; safer to
        # skip an ambiguous issue than to guess which one it meant.
        matches = [entry for entry in locations if loc_text in entry[0]()]
        if len(matches) != 1:
            continue
        get, set_text = matches[0]
        try:
            fixed = _repair_paragraph(client, manifest, get(), issue.get("problem") or "")
        except ValueError:
            continue
        if fixed is None or _validate_paragraph(fixed, segments) is not None:
            continue
        set_text(fixed)
    return report
