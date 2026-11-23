"""Fix the live model's mechanical slips before verification (Slice 119).

The first paid test failed because the live model writes the natural way -
"churn rose to 7% [F2]", a whole two-number sentence as a quote, a percent
stored as 0.07 - where the worked examples had followed the rules exactly. This
module fixes only slips that cannot change what a reader is told, and leaves
every judgement to the unchanged verifier:

- A written number directly before a tag that states that tag's figure (at the
  precision shown, within 5%, the right kind) is removed, as is a matching unit
  or currency beside the tag; code prints the verified value instead. A number
  that does not state its figure is left in place, so the verifier refuses it.
- A client quote is narrowed, verbatim, to the part holding the one number that
  equals the figure's value; the figure then takes its value and unit from that
  number. A quote that is not the client's words is left for the verifier to
  refuse.
- A computed figure's value is recomputed and its unit derived from its inputs.
- Fields that are never shown are dropped; unused figures that feed no other
  figure are dropped; numeric strings become numbers.
- Common durations written in digits ("within 90 days") become words.

Pure and total: never raises, never mutates its input.
"""

import copy
import math
import re

from analystos.packs.numbers import find_numbers

_TAG_RE = re.compile(r"\[(F[1-9][0-9]{0,2})\]")
_FIGURE_KEYS = {
    "client": {"id", "label", "value", "unit", "basis", "quote"},
    "computed": {"id", "label", "value", "unit", "basis", "operation", "inputs"},
    "assumption": {"id", "label", "value", "unit", "basis", "rationale"},
}
_DURATIONS = {7: "a week", 14: "two weeks", 21: "three weeks", 30: "a month", 45: "six weeks", 60: "two months",
              90: "three months", 120: "four months", 180: "six months", 270: "nine months", 365: "a year"}
_DURATION_RE = re.compile(r"\b(7|14|21|30|45|60|90|120|180|270|365)[- ]days?\b", re.IGNORECASE)
_KIND_FOR_UNIT = {"percent": {"percent"}, "points": {"points"}, "usd": {"usd"}, "ratio": {"ratio", None},
                  "count": {None}, "months": {None}, "other": {None}}
_UNIT_AFTER = {
    "percent": re.compile(r"\s*(?:%|percent\b|per cent\b)", re.IGNORECASE),
    "points": re.compile(r"\s*(?:percentage points?\b|points?\b|pts\b|pp\b)", re.IGNORECASE),
    "usd": re.compile(r"\s*(?:USD\b|dollars?\b)", re.IGNORECASE),
    "ratio": re.compile(r"\s*(?:x\b|times\b)", re.IGNORECASE),
}
_USD_BEFORE = re.compile(r"(?:\$|\bUSD)\s*$")


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return value if math.isfinite(value) else None
        except OverflowError:
            return None
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").rstrip("%").lstrip("$").strip()
        try:
            number = float(cleaned)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def states(token, figure):
    """True when a written number states ``figure`` (the old prose rule, now used only to
    decide whether a number beside a tag is redundant)."""
    fv = figure.get("value")
    if token.value is None or not isinstance(fv, (int, float)) or isinstance(fv, bool):
        return False
    if token.kind not in _KIND_FOR_UNIT.get(figure.get("unit"), set()):
        return False
    if abs(token.value - fv) > token.tol:
        return False
    return token.value == 0 if fv == 0 else abs(token.value - fv) / abs(fv) <= 0.05


def strip_redundant_numbers(text, figures):
    """Remove a number written right before a tag when it states that figure, and a unit
    or currency beside the tag that the figure's own unit already carries."""
    if not isinstance(text, str) or "[F" not in text:
        return text
    out, pos = [], 0
    for m in _TAG_RE.finditer(text):
        figure = figures.get(m.group(1))
        before = text[pos:m.start()]
        if figure is not None:
            trimmed = before.rstrip()
            tokens = [t for t in find_numbers(trimmed) if t.end == len(trimmed)]
            if tokens and states(tokens[-1], figure):
                before = trimmed[:tokens[-1].start]
                if before and not before.endswith((" ", "(", "\n")):
                    before += " "
            if figure.get("unit") == "usd":
                before = _USD_BEFORE.sub("", before)
        out.append(before)
        out.append(m.group(0))
        pos = m.end()
        if figure is not None and figure.get("unit") in _UNIT_AFTER:
            after = _UNIT_AFTER[figure["unit"]].match(text, pos)
            if after:
                pos = after.end()
    out.append(text[pos:])
    return re.sub(r"[ \t]{2,}", " ", "".join(out))


def _durations(text):
    if not isinstance(text, str):
        return text
    return _DURATION_RE.sub(lambda m: _DURATIONS[int(m.group(1))], text)


def narrow_quote(quote, value):
    """``(quote, token)`` narrowed to the verbatim part of ``quote`` holding the one number
    that matches ``value`` (as given, as a percent of 1, or at a thousand/million/billion
    scale). ``(None, None)`` when there is no unique match."""
    every = find_numbers(quote)              # digits and number words: both bound the narrowed piece
    tokens = [t for t in every if t.value is not None]
    target = _number(value)
    candidates = []
    for token in tokens:
        forms = {target, target * 100, target * 1e3, target * 1e6, target * 1e9} if target is not None else set()
        if (len(tokens) == 1 and target is None) or any(
                math.isclose(token.value, f, rel_tol=1e-9, abs_tol=1e-9) for f in forms):
            candidates.append(token)
    if len(candidates) != 1:
        return None, None
    chosen = candidates[0]
    i = every.index(chosen)
    start = every[i - 1].end if i > 0 else 0
    end = every[i + 1].start if i + 1 < len(every) else len(quote)
    piece = quote[start:end].strip(" ,;:-–—")
    # Drop a dangling connector left at the cut ("went from 4% to" keeps its words; fine).
    return piece, next(t for t in find_numbers(piece) if t.value is not None)


def _client_unit(token, declared):
    if token.kind in ("percent", "points", "usd", "ratio"):
        return token.kind
    return declared if declared in ("count", "months", "other") else "count"


TOP_LEVEL_KEYS = {"answer", "exec_summary", "situation", "complication", "key_question", "titles", "figures",
                  "issue_tree", "options", "recommendation", "roadmap", "kpis", "risks"}


def normalize_content(content, derived_units, recompute, operations):
    """A copy of ``content`` with the mechanical slips above fixed. Anything it cannot fix
    is left for the verifier. ``derived_units``, ``recompute`` and ``operations`` come
    from the consulting pack (passed in to avoid an import cycle)."""
    if not isinstance(content, dict):
        return content
    try:
        doc = copy.deepcopy(content)
    except RecursionError:
        return content
    for key in list(doc):
        if key not in TOP_LEVEL_KEYS:  # never shown; dropping it cannot change what a reader is told
            del doc[key]
    figures = doc.get("figures")
    if isinstance(figures, list):
        fixed, by_id = [], {}
        for fig in figures:
            if not isinstance(fig, dict):
                fixed.append(fig)
                continue
            fig = dict(fig)
            basis = fig.get("basis")
            if basis in _FIGURE_KEYS:
                for key in list(fig):
                    if key not in _FIGURE_KEYS[basis]:
                        del fig[key]
            number = _number(fig.get("value"))
            if number is not None:
                fig["value"] = number
            if basis == "client" and isinstance(fig.get("quote"), str):
                piece, token = narrow_quote(fig["quote"], fig.get("value"))
                if piece:
                    fig["quote"] = piece
                    fig["value"] = token.value
                    fig["unit"] = _client_unit(token, fig.get("unit"))
            elif basis == "computed":
                inputs = fig.get("inputs")
                op = fig.get("operation")
                if (isinstance(inputs, list) and inputs and all(isinstance(x, str) and x in by_id for x in inputs)
                        and op in operations):
                    units = [by_id[x].get("unit") for x in inputs]
                    if op == "ratio" and fig.get("unit") == "percent" and len(inputs) == 2:
                        op = fig["operation"] = "percent_of_total"
                    allowed = derived_units(op, units)
                    if fig.get("unit") not in allowed and len(allowed) == 1:
                        fig["unit"] = next(iter(allowed))
                    values = [by_id[x].get("value") for x in inputs]
                    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
                        try:
                            result = recompute(op, values)
                        except (ArithmeticError, TypeError, ValueError):
                            result = None
                        if isinstance(result, (int, float)) and math.isfinite(result):
                            fig["value"] = result
            if isinstance(fig.get("id"), str):
                by_id[fig["id"]] = fig
            fixed.append(fig)
        doc["figures"] = fixed
        figure_map = {f["id"]: f for f in fixed if isinstance(f, dict) and isinstance(f.get("id"), str)}
    else:
        figure_map = {}

    def clean(value):
        if isinstance(value, str):
            return _durations(strip_redundant_numbers(value, figure_map))
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            return {k: (v if k in ("quote", "id", "inputs", "figure_ids", "operation", "basis", "unit", "verdict",
                                   "effort", "horizon", "label") else clean(v)) for k, v in value.items()}
        return value

    for key in list(doc):
        if key != "figures":
            doc[key] = clean(doc[key])
    if isinstance(figures, list):
        doc["figures"] = [dict(f, rationale=clean(f["rationale"])) if isinstance(f, dict) and isinstance(
            f.get("rationale"), str) else f for f in doc["figures"]]
        doc["figures"] = _drop_unused(doc)
    return doc


def _drop_unused(doc):
    figures = doc.get("figures")
    if not isinstance(figures, list):
        return figures
    text = repr({k: v for k, v in doc.items() if k != "figures"})
    used = set(_TAG_RE.findall(text))
    for branch in doc.get("issue_tree") or []:  # charted figures are used, though never tagged
        chart = branch.get("chart") if isinstance(branch, dict) else None
        if isinstance(chart, dict) and isinstance(chart.get("figure_ids"), list):
            used.update(x for x in chart["figure_ids"] if isinstance(x, str))
    for fig in figures:
        if isinstance(fig, dict):
            used.update(_TAG_RE.findall(str(fig.get("rationale", ""))))
    changed = True
    while changed:  # inputs of used figures are used too
        changed = False
        for fig in figures:
            if isinstance(fig, dict) and isinstance(fig.get("id"), str) and fig["id"] in used:
                for x in fig.get("inputs") or []:
                    if isinstance(x, str) and x not in used:
                        used.add(x)
                        changed = True
    return [f for f in figures if not isinstance(f, dict) or not isinstance(f.get("id"), str) or f["id"] in used]
