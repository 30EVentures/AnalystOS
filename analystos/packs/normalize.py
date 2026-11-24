"""Fix the live model's mechanical slips before verification (Slices 119-120).

The first paid test failed because the live model writes the natural way -
"churn rose to 7% [F2]", a whole two-number sentence as a quote, a percent
stored as 0.07 - where the worked examples had followed the rules exactly. This
module is meant to fix only slips that do not change what a reader is told, and
to leave every judgement to the verifier; two release reviews found cases where
it did change it, each now a regression test (tests/test_normalize.py):

- A written number directly before a tag that states that tag's figure (at the
  precision shown, within 5%, the right kind) is removed, as is a matching unit
  or currency beside the tag; code prints the verified value instead. A number
  that does not state its figure is left in place, so the verifier refuses it.
- A client quote is narrowed, verbatim, to the part holding the one number that
  equals the figure's value in the figure's own unit; the figure then takes that
  number's value. It cuts only at an explicit break before that number
  (punctuation, "and", "to", "but", "against", ...) when the words after the
  break do not tie the two numbers together ("of", "out of", "times", "above",
  "short of", "among", ...), or across plain words with no linking word or sign
  anywhere ("850 customers paying on average $1,200"). "340 out of our 850",
  "3 times the $1,200" and "a third of our 420" are left whole for the verifier
  to refuse. The declared unit is
  never overridden; a quote that is not the client's words is left for the
  verifier to refuse.
- A computed figure's value is never filled or recomputed: the verifier
  recomputes it and refuses a mismatch, so reversed or wrong inputs are caught.
  The one change made to a computed figure: its unit is set to the only unit its
  operation and inputs allow (percent minus percent is points), and a ratio
  declared as a percent becomes percent_of_total; the value is still checked.
- Fields that are never shown (not in the tool schema, at any depth) are
  dropped; unused figures that feed no other figure are dropped; numeric
  strings become numbers; a recommendation naming an option with extra words
  ("Option A: Save desk") is set to that option's exact name when exactly one
  option name is inside it.
- A parenthetical right after a tag that states that figure ("[F2] (7%)") is
  removed.

Slice 120 (release review of PR #100): earlier versions recomputed every computed
value, matched quotes by scale and unit regardless of kind, cut across word
quantities and rewrote "90 days" anywhere; each could make a wrong deck pass.

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
_KIND_FOR_UNIT = {"percent": {"percent"}, "points": {"points"}, "usd": {"usd"}, "ratio": {"ratio", None},
                  "count": {None}, "months": {None}, "other": {None}}
_UNIT_AFTER = {
    "percent": re.compile(r"\s*(?:%|percent\b|per cent\b)", re.IGNORECASE),
    "points": re.compile(r"\s*(?:percentage points?\b|points?\b|pts\b|pp\b)", re.IGNORECASE),
    "usd": re.compile(r"\s*(?:USD\b|dollars?\b)", re.IGNORECASE),
    "ratio": re.compile(r"\s*(?:x\b|times\b)", re.IGNORECASE),
}
_PAREN_AFTER = re.compile(r"\s*\(\s*([^()\[\]]{1,20}?)\s*\)")
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
        if figure is not None:  # "[F2] (7%)": a parenthetical that only restates the figure
            paren = _PAREN_AFTER.match(text, pos)
            if paren:
                inner = find_numbers(paren.group(1))
                if len(inner) == 1 and inner[0].start == 0 and inner[0].end == len(paren.group(1)) and states(
                        inner[0], figure):
                    pos = paren.end()
    out.append(text[pos:])
    return re.sub(r"[ \t]{2,}", " ", "".join(out))


_OPTION_LABEL = re.compile(r"^\s*(?:option|choice)?\s*(?:[a-z]|[0-9]{1,2})?\s*[:.)\u2013\u2014-]\s+", re.IGNORECASE)
_UNIT_ALIASES = {"%": "percent", "pct": "percent", "percentage": "percent", "$": "usd", "dollars": "usd", "dollar": "usd",
                 "pts": "points", "pp": "points", "percentage points": "points", "x": "ratio", "times": "ratio"}
_BREAK = re.compile(r"[,;:]|[.!?](?=\s|$)|\b(?:and|but|to|then|while|whereas|versus|vs|against|compared (?:with|to))\b",
                    re.IGNORECASE)
_LINK = re.compile(r"[+*/×÷=()\-–—]|\b(?:of|out|times|x|above|below|under|over|more|less|fewer|short|among|amongst|"
                   r"within|inside|across|between|beyond|than|in|from(?=\s+(?:our|the|its|their|all|these|those|this|that|each|"
                   r"every|your|his|her|a|an)\b)|per|share|percent|part|portion|fraction|half|"
                   r"double|twice|third|quarter|fifth|tenth|whole|total|each|every|all)\b", re.IGNORECASE)
_RELATION = re.compile(r"\s*(?:or so\s+)?(?:of|out|times|x|above|below|under|over|more|less|fewer|short|among|"
                       r"within|in|from|per|share|percent|part|portion|fraction|half|double|twice|"
                       r"a\s+(?:share|part|portion|fraction|third|quarter|half))\b", re.IGNORECASE)
_SCALED = re.compile(r"[kKmMB]$|thousand|million|billion|trillion|bn|mm|mn|mln|mio|mill?|crores?|lakhs?", re.IGNORECASE)
_UNITS_FOR_KIND = {"percent": {"percent"}, "points": {"points"}, "usd": {"usd"}, "ratio": {"ratio"},
                   None: {"count", "months", "other"}}
_UNITS = {"percent", "points", "usd", "ratio", "count", "months", "other"}


def _fits(token, unit):
    """True when the written number can be the figure's declared unit (any unit, if none is declared)."""
    return unit not in _UNITS or unit in _UNITS_FOR_KIND.get(token.kind, set())


def narrow_quote(quote, value, unit=None):
    """``(quote, token)`` narrowed to the verbatim part of ``quote`` holding the one number
    that matches ``value`` (as given, as a percent of 1, or at a thousand/million/billion
    scale). ``(None, None)`` when there is no unique match."""
    every = find_numbers(quote)              # digits and number words: both bound the narrowed piece
    tokens = [t for t in every if t.value is not None]
    target = _number(value)
    candidates = []
    for token in tokens:
        if target is None:
            if len(tokens) == 1 and _fits(token, unit):
                candidates.append(token)
            continue
        forms = [target] if _fits(token, unit) else []
        if unit == "percent" and token.kind == "percent":
            forms.append(target * 100)           # a percent stored as a fraction (0.07 for 7%)
        if _SCALED.search(token.text) and _fits(token, unit):
            forms += [target * 1e3, target * 1e6, target * 1e9]  # "$12.2 million" stored as 12.2
        if any(math.isclose(token.value, f, rel_tol=1e-9, abs_tol=1e-9) for f in forms):
            candidates.append(token)
    if len(candidates) != 1:
        return None, None
    chosen = candidates[0]
    i = every.index(chosen)
    if i > 0:
        prev, gap = every[i - 1], quote[every[i - 1].end:chosen.start]
        breaks = list(_BREAK.finditer(gap))
        plain = (prev.value is not None and prev.kind != "ratio" and re.search(r"[^\W\d_]", gap)
                 and not _LINK.search(gap))  # "850 customers paying on average $1,200": nothing ties them
        if not plain and (not breaks or _RELATION.match(gap[breaks[-1].end():])):
            # Cut only at an explicit break (punctuation, "and", "to", "but", "against", ...) whose following
            # words do not tie the numbers together, or across plain words with no linking word anywhere:
            # "340 out of our 850", "3 times the $1,200", "40%, or about a third, of our 850" stay whole.
            return None, None
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


def _drop_unknown(value, schema):
    """``value`` without keys its schema does not list, at every depth (figures excepted:
    their keys depend on the basis and are handled separately)."""
    if not isinstance(schema, dict):
        return value
    if isinstance(value, dict) and isinstance(schema.get("properties"), dict):
        props = schema["properties"]
        return {k: _drop_unknown(v, props[k]) for k, v in value.items() if k in props}
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        return [_drop_unknown(v, schema["items"]) for v in value]
    return value


def _match_option(doc):
    """A recommendation naming an option with a label in front ("Option A: Save desk", "B) Save
    desk") gets that option's exact name; anything else is left for the verifier."""
    rec, options = doc.get("recommendation"), doc.get("options")
    if not isinstance(rec, dict) or not isinstance(rec.get("option"), str) or not isinstance(options, list):
        return
    names = [o["name"] for o in options if isinstance(o, dict) and isinstance(o.get("name"), str) and o["name"].strip()]
    said = rec["option"].strip().lower()
    if said in {n.strip().lower() for n in names}:
        return
    bare = _OPTION_LABEL.sub("", said, count=1).strip()
    inside = [n for n in names if n.strip().lower() == bare]  # exact after the label: "Do not X" never becomes "X"
    if len(inside) == 1:
        rec["option"] = inside[0]


def normalize_content(content, derived_units, recompute, operations, schema=None):
    """A copy of ``content`` with the mechanical slips above fixed. Anything it cannot fix
    is left for the verifier. ``derived_units`` and ``operations`` come from the consulting
    pack (passed in to avoid an import cycle); ``recompute`` is no longer used (Slice 120)
    and kept so callers need not change."""
    if not isinstance(content, dict):
        return content
    try:
        doc = copy.deepcopy(content)
    except RecursionError:
        return content
    for key in list(doc):
        if key not in TOP_LEVEL_KEYS:  # never shown; dropping it cannot change what a reader is told
            del doc[key]
    if isinstance(schema, dict) and isinstance(schema.get("properties"), dict):
        for key in list(doc):
            if key != "figures" and key in schema["properties"]:
                doc[key] = _drop_unknown(doc[key], schema["properties"][key])
    _match_option(doc)
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
            if isinstance(fig.get("unit"), str) and fig["unit"].strip().lower() in _UNIT_ALIASES:
                fig["unit"] = _UNIT_ALIASES[fig["unit"].strip().lower()]  # "%" is percent, "USD" is usd
            if basis == "client" and isinstance(fig.get("quote"), str):
                piece, token = narrow_quote(fig["quote"], fig.get("value"), fig.get("unit"))
                if piece:
                    fig["quote"] = piece
                    fig["value"] = token.value
                    if fig.get("unit") is None:  # filled only when absent; never overridden
                        fig["unit"] = _client_unit(token, None)
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
                    # A computed value is never filled or recomputed here (Slice 120): with wrong inputs the
                    # recomputation is a correct sum of the wrong things. The verifier recomputes and refuses.
            if isinstance(fig.get("id"), str):
                by_id[fig["id"]] = fig
            fixed.append(fig)
        doc["figures"] = fixed
        figure_map = {f["id"]: f for f in fixed if isinstance(f, dict) and isinstance(f.get("id"), str)}
    else:
        figure_map = {}

    def clean(value):
        if isinstance(value, str):
            return strip_redundant_numbers(value, figure_map)
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
