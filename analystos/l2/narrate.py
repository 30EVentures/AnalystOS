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
  ``analystos.l2.analyze``). A failure raises ``ValueError``; no partial
  acceptance, no retry.
- ``executive_summary`` and ``sections`` must be non-empty; every section
  needs a heading and at least one paragraph. A malformed structure
  raises.
- a malformed chart is the *one* non-fatal case - it is dropped
  (``chart`` -> ``None``), never raised, matching
  ``rich_export._resolve_chart``'s "a bad chart is left out, the report
  is never lost" rule.

A raised ``ValueError`` is caught by ``analystos.pipeline``, which falls
back to Slice 26's plain per-segment rendering - a worse-structured
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
_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")
_CHART_TYPES = ("bar", "line", "donut")
_CHART_FORMATS = ("usd", "percent", "number")

_SYSTEM_PROMPT = """\
You are a senior analyst writing the kind of report a Fortune 10 board or \
a top equity-research desk would actually publish - not a fact sheet, not \
a bulleted list of every verified number. Every fact in the manifest \
below has already been checked against the real source document; your job \
is judgment, structure, and writing, not verification, and you must not \
introduce any new number.

Call write_narrative once with three parts, structured the way real \
executive memos and research notes are (the Pyramid Principle / SCQA \
pattern McKinsey, BCG, and equity-research desks all use - lead with the \
answer, then support it):

- executive_summary: 2-3 sentences stating the single most important \
  takeaway as a conclusion, not a fact. A reader who stops here should \
  already know what matters and why.
- sections: 3-5 sections, each built around ONE analytical point - never \
  one number. The heading names the point. Weave facts into the point as \
  evidence: a number is a building block for a sentence, never the whole \
  sentence. Group related figures together instead of listing them as \
  separate lines. You do not have to use every fact - one that doesn't \
  serve a point is better left out. Never write a section that is just \
  "Label: sentence with one number," repeated fact after fact.
- outlook: forward-looking or risk material, if the source supports any. \
  Leave it empty otherwise - do not manufacture an outlook.

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

Charts: give a section a chart only when it plots two or more facts you \
are already citing and the shape carries real information - a "line" for \
one metric across three or more periods, a "bar" to compare categories \
or segments, a "donut" for parts of a stated whole. Set has_chart false \
for every other section (a single number, or a point better made in \
prose). Reference each chart point by its fact number - the same numbers \
you cite in the text - and set the chart's format to match those facts \
(usd / percent / number). When has_chart is false, still fill chart with \
placeholders (type "bar", title "", format "number", series []) - it is \
ignored.

Forward-looking facts in the manifest are tagged [guidance] or \
[projected]. They belong in the outlook, or in a clearly forward-marked \
part of a section - never asserted as a historical result.

To use a "[citable]" fact's value, write {{N}} (its number in the \
manifest) exactly where the value belongs - never write the number \
itself, it is filled in for you afterward. A single paragraph typically \
weaves in several facts this way as evidence for one point. An "[event]" \
fact already carries its date, status, and next step - reference it with \
{{N}} and write the sentence around it (it renders as a dated timeline); \
do not retype the date yourself. A "[context, not citable]" fact is \
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

_TOOL = {
    "name": "write_narrative",
    "description": (
        "Submit the finished report: an executive summary, 3-5 sections "
        "(each with an optional chart), and an outlook."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "executive_summary": {"type": "array", "items": _PARAGRAPH_SCHEMA},
            "sections": {"type": "array", "items": _SECTION_SCHEMA},
            "outlook": {"type": "array", "items": _PARAGRAPH_SCHEMA},
        },
        "required": ["executive_summary", "sections", "outlook"],
        "additionalProperties": False,
    },
}


def _build_manifest(segments):
    lines = []
    for i, segment in enumerate(segments):
        horizon = segment.get("horizon", "reported")
        tag = "" if horizon == "reported" else f" [{horizon}]"
        if segment["type"] == "prose":
            lines.append(f'Fact {i} [context, not citable]{tag}: "{segment["text"]}"')
        elif segment["type"] == "event":
            # Show the whole structure so the model narrates it as a
            # timeline and references it with {{i}}, not by retyping a date.
            parts = [f'what="{segment["what"]}"']
            for key in ("date", "status", "next_step"):
                if segment.get(key):
                    parts.append(f'{key}="{segment[key]}"')
            lines.append(f"Fact {i} [event]{tag}: " + ", ".join(parts))
        else:
            label = segment.get("label") or "Fact"
            lines.append(
                f'Fact {i} [citable]{tag}: label="{label}", '
                f'value={display_value(segment, "actual")}'
            )
    return "\n".join(lines)


def _validate_paragraph(text, segments):
    """``None`` if the paragraph is trustworthy - every {{N}} points to a
    real, citable fact and no digit appears outside a placeholder -
    otherwise a short human-readable reason it isn't, so a rejection can
    be logged with something more useful than just "it failed."
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
    return None


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
    return {
        "type": chart["type"],
        "title": str(chart.get("title") or ""),
        "format": fmt,
        "series": series,
    }


def _reject(where, detail):
    """Log a rejection server-side (never echo model text to a client
    response) and raise the caller's fallback signal. The exact "no clue
    why it failed" gap this closes was found live - see the module
    docstring history.
    """
    print(f"[analystos.l2.narrate] narrative rejected - {where}: {detail}", file=sys.stderr)
    raise ValueError(
        "narrative referenced an unverifiable fact or was malformed - "
        "falling back to the plain rendering"
    )


def _check_paragraphs(paragraphs, segments, where):
    for paragraph in paragraphs:
        text = paragraph.get("text", "")
        reason = _validate_paragraph(text, segments)
        if reason is not None:
            _reject(f"{where} paragraph", f"{reason}: {text!r}")


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

    response = _create_message(
        client,
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "write_narrative"},
        messages=[{"role": "user", "content": user_content}],
    )

    if getattr(response, "stop_reason", None) == "max_tokens":
        print(
            f"[analystos.l2.narrate] response hit max_tokens ({_MAX_TOKENS}) - "
            "the narrative was truncated",
            file=sys.stderr,
        )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        print("[analystos.l2.narrate] response had no tool_use block", file=sys.stderr)
        raise ValueError("model did not return a narrative")

    report = tool_use.input or {}
    executive_summary = report.get("executive_summary") or []
    raw_sections = report.get("sections") or []
    outlook = report.get("outlook") or []

    if not executive_summary:
        _reject("structure", "empty executive_summary")
    if not raw_sections:
        _reject("structure", "no sections")

    _check_paragraphs(executive_summary, segments, "executive-summary")

    sections = []
    for i, section in enumerate(raw_sections):
        heading = (section.get("heading") or "").strip()
        paragraphs = section.get("paragraphs") or []
        if not heading or not paragraphs:
            _reject(f"section {i}", "no heading or no paragraphs")
        _check_paragraphs(paragraphs, segments, f"section {i}")
        chart = None
        if section.get("has_chart"):
            chart = _validate_chart(section.get("chart"), segments)
        sections.append(
            {
                "heading": heading,
                "paragraphs": [{"text": p["text"]} for p in paragraphs],
                "chart": chart,
            }
        )

    _check_paragraphs(outlook, segments, "outlook")

    print(
        f"[analystos.l2.narrate] narrative accepted: {len(sections)} sections, "
        f"{sum(1 for s in sections if s['chart'])} chart(s), "
        f"outlook={'yes' if outlook else 'no'}",
        file=sys.stderr,
    )
    return {
        "title": title,
        "executive_summary": [{"text": p["text"]} for p in executive_summary],
        "sections": sections,
        "outlook": [{"text": p["text"]} for p in outlook] or None,
    }
