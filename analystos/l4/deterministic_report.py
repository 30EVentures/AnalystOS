"""L4 - a mandatory, deterministic "advanced" floor for when Gate 1/Gate 2
reject the model's narrative. See specs/slice-52/spec.md.

``build_deterministic_report(segments, title)`` produces the *exact
same* report-dict shape ``analystos.l2.narrate._assemble_report``
already returns (``title``, ``kpis``, ``executive_summary``,
``executive_insight``, ``sections``, ``disclosure_gaps``, ``outlook``,
``outlook_interpretation``) - not a new shape, not a new renderer.
``render_rich_report``/``render_rich_pdf`` render it completely
unchanged: no new rendering code, no visual "degraded" signal, ever,
because it is the same rendering code either way. Every generated
sentence uses the same ``{{N}}`` placeholder convention the rich
narrative already writes, substituted by the renderer's own existing
mechanism - no new text-rendering logic exists here either.

Charts are "reused, not reimplemented" the same way: this module never
calls a chart-type detector itself - it only ever produces a plain
``chart`` spec (a list of ``fact_index``es), the exact shape
``render_rich_report``/``render_rich_pdf`` already know how to turn into
a real chart via ``analystos.l4.rich_export._detect_chart_type``. That
one function decides bar/line/waterfall from the data's own shape no
matter who produced the chart spec - a model's narrative or this
module - so there is only ever one chart-type decision in the whole
codebase, never a second guess.

Zero model calls anywhere in this module - every word and every chart
point is derived directly from already-verified segment data, so there
is no free-form generation step that could need (or fail) a quality
gate. ``analystos.l2.narrate._direction_problem``/
``_consecutive_count_problem`` (the same validators Gate 1 itself runs)
are still run over generated sentences as a belt-and-suspenders self
check - correctness here comes from construction, not review, so these
should never actually trip; if one ever does, that is a bug in this
module's own generation logic, not a false positive to silence, and the
offending sentence is dropped (logged) rather than shown.
"""

import re
import sys

from analystos.l2.narrate import _consecutive_count_problem, _direction_problem

_MAX_KPIS = 5
_MAX_BENCHMARK_SENTENCES = 6
_MAX_DISCLOSURE_GAPS = 5
_MAX_BAR_FALLBACK_POINTS = 6

# A fixed, short checklist of commonly-expected financial metrics - not a
# reuse of anything (see the module docstring / specs/slice-52/spec.md's
# "Correction to the task's own framing": disclosure_gaps is today
# content the *model* writes inside write_narrative's response, which
# doesn't exist at all when Gate 1 fails - this is a genuinely new,
# deterministic replacement, a keyword check, not an open-ended judgment
# about what's missing).
_DISCLOSURE_GAP_CHECKLIST = (
    ("earnings per share", "Earnings per share"),
    ("cash flow from operations", "Cash flow from operations"),
    ("free cash flow", "Free cash flow"),
    ("effective tax rate", "Effective tax rate"),
    ("gross margin", "Gross margin"),
)

_PERIOD_TOKEN_RE = re.compile(
    r"(Q[1-4]\s*'?\s*\d{2,4}"
    r"|FY\s*'?\s*\d{2,4}"
    r"|(?:H[12]|1H|2H)\s*'?\s*\d{2,4}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*'?\s*\d{2,4}"
    r"|\b\d{4}\b)",
    re.IGNORECASE,
)
_QUARTER_RE = re.compile(r"^Q([1-4])\s*'?\s*(\d{2,4})$", re.IGNORECASE)
_FY_RE = re.compile(r"^FY\s*'?\s*(\d{2,4})$", re.IGNORECASE)
_YEAR_RE = re.compile(r"^(\d{4})$")


def _full_year(raw):
    year = int(raw)
    if year >= 100:
        return year
    return 2000 + year if year < 70 else 1900 + year


def _period_sort_key(token):
    """A best-effort chronological ordering key for a period token - a
    heuristic for sequencing chart/trend points, never a verified fact
    itself."""
    m = _QUARTER_RE.match(token)
    if m:
        return (_full_year(m.group(2)), int(m.group(1)))
    m = _FY_RE.match(token)
    if m:
        return (_full_year(m.group(1)), 0)
    m = _YEAR_RE.match(token)
    if m:
        return (int(m.group(1)), 0)
    return (0, 0)


def _period_token(*texts):
    for text in texts:
        if not text:
            continue
        m = _PERIOD_TOKEN_RE.search(text)
        if m:
            return m.group(1).strip()
    return None


def _citation_text(segment):
    citation = segment.get("citation")
    if isinstance(citation, list):
        return citation[0] if citation else None
    return citation


def _current_quote_index(segments, computed_segment):
    """Which of a computed segment's own cited quotes is the *current*
    (most recent) value, as opposed to a comparison baseline -
    determined from each candidate quote's own period token
    (``_period_token``/``_period_sort_key``), never from citation
    *position*. Found live 2026-09-12 against a real document: a naive
    "operand order tells you which is current" rule (growth_percent
    last, difference/remainder first) is not actually trustworthy -
    ``analystos.l2.analyze``'s own growth_percent verification explicitly
    tries operands in *either* order and accepts whichever matches the
    model's claimed result, so a model is never actually constrained to
    one order, and a plain two-point ``difference`` has no ordering
    convention at all. Trusting position produced exactly the bug this
    function exists to prevent: "Net Income Q3 2025 was $22.4M, a change
    of $-2.8M" - attached to the *older* quarter, when it was Q3 2026's
    figure that actually changed. Chronology from the data itself is a
    real signal a model can't get backwards by choosing operand order;
    position was never a real signal at all.
    """
    citations = computed_segment.get("citation") or []
    candidates = []
    for citation in citations:
        idx = next(
            (j for j, other in enumerate(segments)
             if other.get("type") == "quote" and _citation_text(other) == citation),
            None,
        )
        if idx is not None:
            candidates.append(idx)
    if not candidates:
        return None
    tokened = [
        (idx, _period_token(segments[idx].get("label"), _citation_text(segments[idx])))
        for idx in candidates
    ]
    with_tokens = [(idx, token) for idx, token in tokened if token]
    if with_tokens:
        return max(with_tokens, key=lambda pair: _period_sort_key(pair[1]))[0]
    return candidates[-1]  # no period info anywhere to compare - arbitrary, but rare


def _metric_key(segment):
    """A period-stripped, normalized label - so "Q3 2026 Revenue" and "Q2
    2026 Revenue" group under the same key ("revenue")."""
    label = (segment.get("label") or "").strip()
    token = _period_token(label)
    if token:
        label = label.replace(token, "")
    return re.sub(r"\s+", " ", label).strip(" :-,").lower()


def _numeric_segments(segments):
    return [
        i for i, seg in enumerate(segments)
        if seg.get("type") in ("quote", "computed") and seg.get("value") is not None
    ]


def _select_kpis(segments):
    """Up to ``_MAX_KPIS`` KPIs, deterministically: the most *recent*
    reported quote for each *distinct* metric (``_metric_key`` - so five
    quarters of the same "Revenue" figure produce one headline KPI, not
    five copies of it; a real KPI strip needs variety, not one metric's
    whole history) - "most recent" by each quote's own period token
    (``_period_sort_key``) where one exists, else the first one
    encountered. Paired with a matching ``growth_percent`` computed
    segment when this quote is that segment's own *current* value
    (``_current_quote_index`` - chronology-based, never a
    ``difference``/``remainder`` delta - their sign isn't reliable, the
    same rule Gate 1's own KPI-writing guidance already states). Same
    ``{label, value_fact, delta_fact}`` shape
    ``analystos.l2.narrate._resolve_kpis`` already consumes unchanged.
    """
    best_by_key = {}  # key -> (sort_key, first_seen_order, segment_index)
    order = {}
    for i, seg in enumerate(segments):
        if seg.get("type") != "quote" or seg.get("horizon") != "reported":
            continue
        if seg.get("value") is None:
            continue
        key = _metric_key(seg) or f"__unkeyed_{i}"
        order.setdefault(key, i)
        token = _period_token(seg.get("label"), _citation_text(seg))
        sort_key = _period_sort_key(token) if token else (0, 0)
        current = best_by_key.get(key)
        if current is None or sort_key > current[0]:
            best_by_key[key] = (sort_key, order[key], i)

    # keep insertion order stable (first-seen metric first), not sorted
    # by recency across *different* metrics
    chosen = sorted(best_by_key.items(), key=lambda item: order[item[0]])

    kpis = []
    for _key, (_sort_key, _first_seen, i) in chosen:
        delta_fact = -1
        for j, other in enumerate(segments):
            if other.get("type") != "computed" or other.get("operation") != "growth_percent":
                continue
            if _current_quote_index(segments, other) == i:
                delta_fact = j
                break
        kpis.append({"label": segments[i].get("label") or "", "value_fact": i, "delta_fact": delta_fact})
        if len(kpis) == _MAX_KPIS:
            break
    return kpis


def _select_bridge(segments):
    """A start -> components -> end bridge, reconstructed purely from a
    ``difference``/``remainder`` computed segment's own ``operands`` +
    ``citation`` (``analystos.l2.analyze._recompute``: operands[0] is the
    end/total value, operands[1] the start value, operands[2:] named
    components - citations mirror that same order) - matched back to the
    real quote segments that state those same values, by exact citation-
    string equality (a real match, never a value/proximity guess).
    Returns a ``[start, computed, *components, end]`` index list (the
    exact series shape ``_is_bridge_shape`` already checks: start + the
    computed remainder + components == end), or ``None``.

    Requires at least 3 citations (end, start, and at least one named
    component) - an ordinary two-point ``difference``/``remainder``
    (e.g. a plain YoY change with no named component at all) is not a
    bridge and must not be forced into a "start/end" narrative; unlike
    ``growth_percent``, there's no swap-and-retry at the verification
    layer for these two operations, so a real 3+-operand bridge that
    survived verification did use operand order consistently (the
    extraction prompt's own "total minus a named component" framing) -
    but a plain 2-operand difference has no such framing to hold it to
    a specific order at all, which is exactly what produced a real bug
    here (see ``_current_quote_index``).
    """
    for i, seg in enumerate(segments):
        if seg.get("type") != "computed" or seg.get("operation") not in ("difference", "remainder"):
            continue
        citations = seg.get("citation")
        if not isinstance(citations, list) or len(citations) < 3:
            continue
        matched = []
        for citation in citations:
            match = next(
                (j for j, other in enumerate(segments)
                 if other.get("type") == "quote" and _citation_text(other) == citation),
                None,
            )
            if match is None:
                matched = None
                break
            matched.append(match)
        if matched is None:
            continue
        end_index, start_index, *component_indices = matched
        return [start_index, i, *component_indices, end_index]
    return None


def _select_time_series(segments):
    """The longest run of 3+ same-metric reported quotes with a real
    period in their label/citation - grouped by ``_metric_key``, ordered
    chronologically by ``_period_sort_key``. Returns ``[(token, index),
    ...]`` or ``None``."""
    groups = {}
    for i, seg in enumerate(segments):
        if seg.get("type") != "quote" or seg.get("horizon") != "reported":
            continue
        if seg.get("value") is None:
            continue
        token = _period_token(seg.get("label"), _citation_text(seg))
        if not token:
            continue
        key = _metric_key(seg)
        if not key:
            continue
        groups.setdefault(key, []).append((token, i))

    best = None
    for points in groups.values():
        if len(points) < 3:
            continue
        ordered = sorted(points, key=lambda p: _period_sort_key(p[0]))
        if best is None or len(ordered) > len(best):
            best = ordered
    return best


def _select_bar_fallback(segments):
    """A plain comparison of same-format numeric facts - never mixing,
    say, a dollar figure with a percentage on one bar chart, which would
    be visually meaningless. The largest same-format group, capped."""
    by_format = {}
    for i in _numeric_segments(segments):
        by_format.setdefault(segments[i].get("format"), []).append(i)
    candidates = [indices for indices in by_format.values() if len(indices) >= 2]
    if not candidates:
        return None
    best = max(candidates, key=len)
    return best[:_MAX_BAR_FALLBACK_POINTS]


def _select_chart(segments):
    """One chart spec, deterministically - a bridge if the data has one,
    else the longest real time series, else a same-format bar
    comparison. ``None`` if nothing in the data supports even a bar
    chart (fewer than 2 same-format numeric facts anywhere).

    A time series' points are labelled with their bare period token
    ("Q3 2026"), not the segment's full descriptive label ("Q3 2026
    Revenue") - ``_detect_chart_type``'s own trend check
    (``_is_time_series_shape``) requires every label to match a period
    pattern *exactly*, the same way the rich narrative's own chart
    labels already have to for a model-declared trend chart to render
    as a line rather than a bar.
    """
    labels = None
    indices = _select_bridge(segments)
    if indices is None:
        series = _select_time_series(segments)
        if series:
            indices = [i for _token, i in series]
            labels = [token for token, _i in series]
    if indices is None:
        indices = _select_bar_fallback(segments)
    if indices is None or len(indices) < 2:
        return None
    if labels is None:
        labels = [segments[idx].get("label") or "" for idx in indices]
    return {
        "type": "bar",  # a formality - _detect_chart_type decides for real (rich_export.py)
        "title": "",
        "format": segments[indices[0]].get("format", "number"),
        "series": [
            {"label": label, "fact_index": idx}
            for label, idx in zip(labels, indices)
        ],
    }


def _benchmark_sentences(segments):
    """"{label} was {{i}}, which grew/declined {{comparison}}[, and
    {{comparison2}}]." - stacks up to 2 comparisons per quote, matching
    the rich narrative's own "stack the comparison when more than one is
    available" rule. The direction verb is read directly off the
    matching growth_percent fact's own sign (never guessed) - a
    difference/remainder match gets no direction verb at all, the exact
    same "sign isn't reliable" rule Gate 1's _direction_problem already
    enforces, so this generator cannot make the mistake that check
    exists to catch.
    """
    sentences = []
    for i, seg in enumerate(segments):
        if seg.get("type") != "quote" or seg.get("horizon") != "reported":
            continue
        if seg.get("value") is None:
            continue
        if _citation_text(seg) is None:
            continue
        # only a computed fact's own *current* value gets attached here -
        # never its comparison baseline (see _current_quote_index) - which
        # is what stopped "Q2 revenue was $455.0M, which grew 9.5%" (the
        # 9.5% move belonged to Q3, not Q2, even though Q2's own figure
        # is also cited by that computed fact).
        comparisons = [
            j for j, other in enumerate(segments)
            if other.get("type") == "computed"
            and other.get("operation") in ("growth_percent", "difference", "remainder")
            and _current_quote_index(segments, other) == i
        ]
        if not comparisons:
            continue
        comparisons = comparisons[:2]
        label = (seg.get("label") or "This figure").strip()

        first = segments[comparisons[0]]
        if first["operation"] == "growth_percent":
            verb = "grew" if first["value"] >= 0 else "declined"
            lead = f"which {verb} {{{{{comparisons[0]}}}}}"
        else:
            lead = f"a change of {{{{{comparisons[0]}}}}}"
        tail_parts = [f"{{{{{j}}}}}" for j in comparisons[1:]]
        tail = (" and " + " and ".join(tail_parts)) if tail_parts else ""

        text = f"{label} was {{{{{i}}}}}, {lead}{tail}."
        problem = _direction_problem(text, segments)
        if problem:
            print(
                f"[analystos.l4.deterministic_report] dropped a benchmark sentence "
                f"that failed its own safety check: {problem}",
                file=sys.stderr,
            )
            continue
        sentences.append({"text": text})
        if len(sentences) == _MAX_BENCHMARK_SENTENCES:
            break
    return sentences


def _trend_sentences(segments):
    """"{label} has grown/declined for N consecutive periods, from {{a}}
    to {{b}}." only when every consecutive step moves the same direction
    - otherwise states the bare values with no trend word at all,
    mirroring _consecutive_count_problem's own "stay silent rather than
    guess" rule. The assembled sentence is run through that same
    validator before use - see the module docstring.
    """
    series = _select_time_series(segments)
    if not series:
        return []
    indices = [i for _token, i in series]
    values = [segments[i]["value"] for i in indices]
    diffs = [values[k + 1] - values[k] for k in range(len(values) - 1)]
    consistent_up = all(d > 0 for d in diffs)
    consistent_down = all(d < 0 for d in diffs)

    label = (segments[indices[-1]].get("label") or "The metric").strip()
    token = _period_token(label)
    if token:
        label = label.replace(token, "").strip(" :-,") or "The metric"
    first_index, last_index = indices[0], indices[-1]

    if consistent_up or consistent_down:
        word = "grown" if consistent_up else "declined"
        text = (
            f"{label} has {word} for {len(diffs)} consecutive periods, from "
            f"{{{{{first_index}}}}} to {{{{{last_index}}}}}."
        )
        problem = _consecutive_count_problem(text, segments)
        if problem:
            print(
                f"[analystos.l4.deterministic_report] dropped a trend sentence "
                f"that failed its own safety check: {problem}",
                file=sys.stderr,
            )
            return []
        return [{"text": text}]

    chain = " to ".join(f"{{{{{i}}}}}" for i in indices)
    return [{"text": f"{label} across the period: {chain}."}]


def _relationship_sentences(segments):
    """"{label} moved from {{start}} to {{end}}; of that change, {{c}}
    came from {component label}, and the remaining {{r}} reflects
    {remainder label}." - only when _select_bridge finds a genuine
    start -> components -> end shape; never invents one."""
    bridge = _select_bridge(segments)
    if bridge is None:
        return []
    start_index, computed_index, *rest = bridge
    *component_indices, end_index = rest

    label = (segments[end_index].get("label") or segments[start_index].get("label") or "The metric").strip()
    component_phrases = [
        f"{{{{{ci}}}}} came from {(segments[ci].get('label') or 'a named component').strip()}"
        for ci in component_indices
    ]
    remainder_label = (segments[computed_index].get("label") or "organic growth").strip()

    if component_phrases:
        text = (
            f"{label} moved from {{{{{start_index}}}}} to {{{{{end_index}}}}}; of that change, "
            f"{' and '.join(component_phrases)}, and the remaining {{{{{computed_index}}}}} "
            f"reflects {remainder_label.lower()}."
        )
    else:
        text = (
            f"{label} moved from {{{{{start_index}}}}} to {{{{{end_index}}}}}, "
            f"a change of {{{{{computed_index}}}}}."
        )
    return [{"text": text}]


def _disclosure_gap_sentences(segments):
    """A fixed checklist of commonly-expected metrics, keyword-matched
    against every segment's label/text/citation - anything not mentioned
    anywhere becomes one plain "X is not disclosed" sentence, capped at
    _MAX_DISCLOSURE_GAPS. See the module docstring's "Correction" note -
    this is new logic, not a reuse of the model-written version."""
    haystack_parts = []
    for seg in segments:
        for key in ("label", "text"):
            value = seg.get(key)
            if value:
                haystack_parts.append(value.lower())
        citation = seg.get("citation")
        if isinstance(citation, list):
            haystack_parts.extend(c.lower() for c in citation if c)
        elif citation:
            haystack_parts.append(citation.lower())
    haystack = "\n".join(haystack_parts)

    sentences = []
    for keyword, display_name in _DISCLOSURE_GAP_CHECKLIST:
        if keyword not in haystack:
            sentences.append({"text": f"{display_name} is not disclosed in this document."})
        if len(sentences) == _MAX_DISCLOSURE_GAPS:
            break
    return sentences


def build_deterministic_report(segments, title):
    """The deterministic tier's entry point. Returns a report dict in the
    exact shape ``render_rich_report``/``render_rich_pdf`` already
    render, or ``None`` if fewer than 2 numeric facts exist anywhere in
    ``segments`` - the genuine tier-3 trigger (too few facts for a KPI,
    a chart, or even one benchmarking pair); see specs/slice-52/spec.md's
    "How often does tier 3 actually fire."
    """
    numeric = _numeric_segments(segments)
    if len(numeric) < 2:
        return None

    kpis = _select_kpis(segments)
    chart = _select_chart(segments)

    paragraphs = []
    paragraphs.extend(_benchmark_sentences(segments))
    paragraphs.extend(_trend_sentences(segments))
    paragraphs.extend(_relationship_sentences(segments))
    if not paragraphs:
        # Defensive only - len(numeric) >= 2 almost always yields at
        # least one benchmark sentence; this is the one shape that
        # can't (two isolated, unrelated numeric facts with no
        # comparison between them) and still needs a non-empty section.
        paragraphs = [{"text": f"{{{{{numeric[0]}}}}} was reported alongside {{{{{numeric[1]}}}}}."}]

    # The first sentence leads the executive summary (the headline
    # figure, same as the rich narrative's own convention) and is not
    # also repeated verbatim in the section body below it.
    executive_summary = [{"text": paragraphs[0]["text"]}]
    section_paragraphs = paragraphs[1:] or paragraphs

    return {
        "title": title,
        "kpis": kpis,
        "executive_summary": executive_summary,
        "executive_insight": None,
        "sections": [{
            "heading": "Key figures",
            "paragraphs": section_paragraphs,
            "chart": chart,
        }],
        "disclosure_gaps": _disclosure_gap_sentences(segments),
        "outlook": None,
        "outlook_interpretation": None,
    }
