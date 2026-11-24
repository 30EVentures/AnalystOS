"""Role-written work products (Slice 126, phase 2 of role-specific outputs).

40 of the 73 roles list a native output the analysis formats do not cover: drafts,
registers, case files, reconciliations, plans and code. The model writes them in the
content's ``work`` list; this module defines each kind's fields, checks them with the
same number rules as the rest of the content, and says which kinds each role owes.

The checks are passed in by the consulting pack (``number_problems``,
``label_problems``) so this module adds rules without a second definition of "a
number". Never raises; every function is total.
"""

import math
import re

KINDS = ("draft", "register", "case_file", "reconciliation", "plan", "code")
# Catalog deliverable -> work kind. Report, memo, brief, workbook and deck are analysis formats (phase 1).
DELIVERABLE_KIND = {"draft": "draft", "register": "register", "case-file": "case_file",
                    "reconciliation": "reconciliation", "plan": "plan", "code": "code"}
RATINGS = ("low", "medium", "high")
STATUSES = ("open", "in progress", "closed")
EFFECTS = ("add_to_a", "subtract_from_a", "add_to_b", "subtract_from_b")
LANGUAGES = ("python", "sql", "javascript", "typescript", "java", "go", "bash", "yaml", "other")
FIELDS = {
    "draft": {"kind", "title", "for", "body"},
    "register": {"kind", "title", "rows"},
    "case_file": {"kind", "subject", "facts", "evidence", "open_questions", "for_decision"},
    "reconciliation": {"kind", "title", "side_a", "side_b", "items", "entries"},
    "plan": {"kind", "title", "steps"},
    "code": {"kind", "language", "purpose", "code"},
}
REQUIRED = {  # fields a renderer reads; missing or mistyped is refused before any paid call is wasted
    "draft": {"title", "for", "body"}, "register": {"title", "rows"},
    "case_file": {"subject", "facts", "evidence", "for_decision"},
    "reconciliation": {"title", "side_a", "side_b"}, "plan": {"title", "steps"},
    "code": {"language", "purpose", "code"},
}
ROW_FIELDS = {"rows": {"item", "rating", "owner", "status", "action"}, "steps": {"when", "task", "owner", "done_when"},
              "items": {"label", "figure_id", "effect"}, "entries": {"debit", "credit", "figure_id", "memo"}}
LANGUAGE_NAMES = {"python": "Python", "sql": "SQL", "javascript": "JavaScript", "typescript": "TypeScript",
                  "java": "Java", "go": "Go", "bash": "Bash", "yaml": "YAML", "other": "Code"}
MAX_TEXT, MAX_LABEL, MAX_PARAGRAPH, MAX_CODE = 300, 120, 1200, 6000
BALANCE_TOLERANCE = 0.005


def _s(n):
    return {"type": "string", "maxLength": n}


def _arr(items, lo, hi):
    return {"type": "array", "minItems": lo, "maxItems": hi, "items": items}


# One object schema with every kind's fields (the API's tool schema has no oneOf); the
# verifier enforces that each item carries only its own kind's fields.
SCHEMA = _arr({
    "type": "object", "required": ["kind"],
    "properties": {
        "kind": {"enum": list(KINDS)},
        "title": _s(MAX_LABEL), "for": _s(MAX_LABEL), "body": _arr(_s(MAX_PARAGRAPH), 1, 8),
        "rows": _arr({"type": "object", "required": ["item", "rating", "owner", "status", "action"],
                      "properties": {"item": _s(MAX_TEXT), "rating": {"enum": list(RATINGS)}, "owner": _s(80),
                                     "status": {"enum": list(STATUSES)}, "action": _s(MAX_TEXT)}}, 2, 15),
        "subject": _s(MAX_LABEL), "facts": _arr(_s(MAX_TEXT), 2, 10), "evidence": _arr(_s(MAX_TEXT), 1, 10),
        "open_questions": _arr(_s(MAX_TEXT), 0, 8), "for_decision": _s(MAX_TEXT),
        "side_a": {"type": "object", "required": ["label", "figure_id"],
                   "properties": {"label": _s(MAX_LABEL), "figure_id": {"type": "string"}}},
        "side_b": {"type": "object", "required": ["label", "figure_id"],
                   "properties": {"label": _s(MAX_LABEL), "figure_id": {"type": "string"}}},
        "items": _arr({"type": "object", "required": ["label", "figure_id", "effect"],
                       "properties": {"label": _s(MAX_LABEL), "figure_id": {"type": "string"},
                                      "effect": {"enum": list(EFFECTS)}}}, 0, 12),
        "entries": _arr({"type": "object", "required": ["debit", "credit", "figure_id", "memo"],
                         "properties": {"debit": _s(80), "credit": _s(80), "figure_id": {"type": "string"},
                                        "memo": _s(MAX_TEXT)}}, 0, 12),
        "steps": _arr({"type": "object", "required": ["when", "task", "owner", "done_when"],
                       "properties": {"when": _s(60), "task": _s(MAX_TEXT), "owner": _s(80),
                                      "done_when": _s(MAX_TEXT)}}, 2, 12),
        "language": {"enum": list(LANGUAGES)}, "purpose": _s(MAX_TEXT), "code": _s(MAX_CODE),
    },
}, 1, 6)

GUIDE = {
    "draft": ('a "draft": {kind, title, for, body}. The actual text the role would write (copy, an email, a job '
              'post, a policy passage, an outreach message), 1-8 paragraphs in body. "for" names the audience or '
              'channel. Numbers only as figure tags.'),
    "register": ('a "register": {kind, title, rows}. 2-15 rows of {item, rating (low, medium, high), owner (a role, '
                 'never a person\'s name), status (open, in progress, closed), action}.'),
    "case_file": ('a "case_file": {kind, subject, facts, evidence, open_questions, for_decision}. Facts and evidence '
                  'from the client\'s words and figures; for_decision is the question a qualified person must '
                  'decide, ending with "?". Never decide it.'),
    "reconciliation": ('a "reconciliation": {kind, title, side_a, side_b, items, entries}. side_a and side_b each '
                       '{label, figure_id} (for example bank balance and ledger balance); items {label, figure_id, '
                       'effect} move one side (add_to_a, subtract_from_a, add_to_b, subtract_from_b) until both '
                       'sides are equal - code checks they balance on the verified figures. entries are proposed '
                       'journal entries {debit, credit, figure_id, memo} with accounts named in words, for approval.'),
    "plan": ('a "plan": {kind, title, steps}. 2-12 steps of {when (in words, e.g. "week one"), task, owner (a role), '
             'done_when}.'),
    "code": ('a "code": {kind, language, purpose, code}. A draft change, at most a few dozen lines, for a person to '
             'review; it is shown as "not run or reviewed".'),
}


def required_kinds(role):
    """The work kinds a catalog role owes, from its deliverables (sorted, possibly empty)."""
    if not isinstance(role, dict):
        return []
    return sorted({DELIVERABLE_KIND[d] for d in role.get("deliverables", []) if d in DELIVERABLE_KIND})


def prompt_text(role):
    """The work-product instructions for a role's system prompt, or None when it owes none."""
    kinds = required_kinds(role)
    if not kinds:
        return None
    lines = ["Work product: besides the analysis, write the role's own work in the content's \"work\" list. "
             "Include at least one of each:"]
    lines += [f"- {GUIDE[k]}" for k in kinds]
    lines.append("Every number rule above applies to work products too (code excepted). Owners and accounts are "
                 "named in words, never by a person's name or a number. In drafts, case files and plans write no "
                 "dates, durations, IDs, clause, form, version or ticket numbers: use words (\"by month end\", "
                 "\"within a day\") or leave them out. Ratings, statuses and effects are lower case, as listed.")
    if role.get("boundary") == "approval-gated":
        lines.append("Everything in work is a draft for the named approver; never write as if it was sent, posted "
                     "or booked.")
    return "\n".join(lines)


TITLES = {"draft": "Draft", "register": "Register", "case_file": "Case file", "reconciliation": "Reconciliation",
          "plan": "Plan", "code": "Draft code"}


def title_of(item):
    """A work product's heading: its kind and its own title or subject or purpose."""
    kind = item.get("kind") if isinstance(item, dict) else None
    name = item.get("title") or item.get("subject") or ("" if kind != "code" else LANGUAGE_NAMES.get(item.get("language"), ""))
    return f"{TITLES.get(kind, 'Work')}: {name}" if name else TITLES.get(kind, "Work")


def _list(value):
    return value if isinstance(value, list) else []


def work_texts(work):
    """(where, text) for every prose field in ``work`` that the number rules check (code excepted)."""
    out = []
    for i, item in enumerate(_list(work)):
        if not isinstance(item, dict):
            continue
        w = f"work[{i}]"
        kind = item.get("kind")
        if kind == "draft":
            out += [(f"{w}.body[{j}]", p) for j, p in enumerate(_list(item.get("body")))]
        elif kind == "register":
            for j, row in enumerate(_list(item.get("rows"))):
                if isinstance(row, dict):
                    out += [(f"{w}.rows[{j}].item", row.get("item")), (f"{w}.rows[{j}].action", row.get("action"))]
        elif kind == "case_file":
            for key in ("facts", "evidence", "open_questions"):
                out += [(f"{w}.{key}[{j}]", t) for j, t in enumerate(_list(item.get(key)))]
            out.append((f"{w}.for_decision", item.get("for_decision")))
        elif kind == "reconciliation":
            out += [(f"{w}.entries[{j}].memo", e.get("memo")) for j, e in enumerate(_list(item.get("entries")))
                    if isinstance(e, dict)]
        elif kind == "plan":
            for j, step in enumerate(_list(item.get("steps"))):
                if isinstance(step, dict):
                    out += [(f"{w}.steps[{j}].task", step.get("task")),
                            (f"{w}.steps[{j}].done_when", step.get("done_when"))]
        elif kind == "code":
            out.append((f"{w}.purpose", item.get("purpose")))
    return out


def work_labels(work):
    """(where, text) for short name fields: no digits and no tags, like the deck's labels."""
    out = []
    for i, item in enumerate(_list(work)):
        if not isinstance(item, dict):
            continue
        w = f"work[{i}]"
        for key in ("title", "for", "subject"):
            if key in item:
                out.append((f"{w}.{key}", item.get(key)))
        for j, row in enumerate(_list(item.get("rows"))):
            if isinstance(row, dict):
                out.append((f"{w}.rows[{j}].owner", row.get("owner")))
        for side in ("side_a", "side_b"):
            if isinstance(item.get(side), dict):
                out.append((f"{w}.{side}.label", item[side].get("label")))
        for j, line in enumerate(_list(item.get("items"))):
            if isinstance(line, dict):
                out.append((f"{w}.items[{j}].label", line.get("label")))
        for j, entry in enumerate(_list(item.get("entries"))):
            if isinstance(entry, dict):
                out += [(f"{w}.entries[{j}].debit", entry.get("debit")), (f"{w}.entries[{j}].credit", entry.get("credit"))]
        for j, step in enumerate(_list(item.get("steps"))):
            if isinstance(step, dict):
                out += [(f"{w}.steps[{j}].when", step.get("when")), (f"{w}.steps[{j}].owner", step.get("owner"))]
    return out


def figure_ids_used(work):
    """Figure ids a work list refers to by id (reconciliation sides, items and entries)."""
    used = set()
    for item in _list(work):
        if isinstance(item, dict) and item.get("kind") == "reconciliation":
            for side in ("side_a", "side_b"):
                if isinstance(item.get(side), dict) and isinstance(item[side].get("figure_id"), str):
                    used.add(item[side]["figure_id"])
            for key in ("items", "entries"):
                for line in _list(item.get(key)):
                    if isinstance(line, dict) and isinstance(line.get("figure_id"), str):
                        used.add(line["figure_id"])
    return used


def _nonempty(value, limit):
    return isinstance(value, str) and value.strip() != "" and len(value) <= limit


def _count(where, value, lo, hi):
    if not isinstance(value, list) or not lo <= len(value) <= hi:
        return [f"{where} must list {lo} to {hi} items"]
    return []


def verify_work(work, figures, number_problems, label_problems, client_years, kinds_owed):
    """Every problem with a ``work`` list. ``figures`` maps id -> verified figure;
    ``kinds_owed`` are the kinds the role must deliver (others are refused)."""
    problems = []
    if kinds_owed is None:  # role unknown: check what is there, require nothing
        kinds_owed = [i.get("kind") for i in _list(work) if isinstance(i, dict) and i.get("kind") in KINDS]
    owed = set(kinds_owed)
    if work is None:
        return [f"work must include {', '.join(sorted(owed))}"] if owed else []
    if not owed:
        return ["work is not part of this role's output; leave it out"]
    if not isinstance(work, list) or not 1 <= len(work) <= 6:
        return ["work must be a list of 1 to 6 items"]
    seen = set()
    for i, item in enumerate(work):
        w = f"work[{i}]"
        if not isinstance(item, dict) or item.get("kind") not in KINDS:
            problems.append(f"{w} needs a kind in {list(KINDS)}")
            continue
        kind = item["kind"]
        seen.add(kind)
        if kind not in owed:
            problems.append(f"{w}: a {kind} is not part of this role's output")
            continue
        extra = set(item) - FIELDS[kind]
        if extra:
            problems.append(f"{w}: fields {sorted(extra)} do not belong to a {kind}")
        shape = _shape_problems(w, kind, item)
        if shape:
            problems += shape
            continue
        problems += _KIND_CHECKS[kind](w, item, figures)
    for kind in sorted(owed - seen):
        problems.append(f"work must include a {kind}; this role delivers one")
    for where, text in work_texts(work):
        if not _nonempty(text, MAX_PARAGRAPH):
            problems.append(f"{where} must be non-empty text")
        else:
            problems += number_problems(where, text, figures, client_years)
    for where, text in work_labels(work):
        if not _nonempty(text, MAX_LABEL):
            problems.append(f"{where} must be a short non-empty name")
        else:
            problems += label_problems(where, text, client_years)
    return problems


def _shape_problems(w, kind, item):
    """Missing fields, lists that are not lists, and rows that are not objects with their fields."""
    problems = [f"{w}: a {kind} needs {field!r}" for field in sorted(REQUIRED[kind] - set(item))]
    for key in ("body", "facts", "evidence", "open_questions"):
        if key in item and not (isinstance(item[key], list) and all(isinstance(x, str) for x in item[key])):
            problems.append(f"{w}.{key} must be a list of text")
    for key, fields in ROW_FIELDS.items():
        if key not in item:
            continue
        if not isinstance(item[key], list) or not all(isinstance(x, dict) and fields <= set(x) for x in item[key]):
            problems.append(f"{w}.{key} must be a list of objects with {sorted(fields)}")
    for side in ("side_a", "side_b"):
        if side in item and not (isinstance(item[side], dict) and {"label", "figure_id"} <= set(item[side])):
            problems.append(f"{w}.{side} must be an object with a label and a figure_id")
    return problems


def _draft(w, item, figures):
    return _count(f"{w}.body", item.get("body"), 1, 8)


def _register(w, item, figures):
    problems = _count(f"{w}.rows", item.get("rows"), 2, 15)
    for j, row in enumerate(_list(item.get("rows"))):
        if not isinstance(row, dict) or row.get("rating") not in RATINGS or row.get("status") not in STATUSES:
            problems.append(f"{w}.rows[{j}] needs a rating in {list(RATINGS)} and a status in {list(STATUSES)}")
    return problems


def _case_file(w, item, figures):
    problems = _count(f"{w}.facts", item.get("facts"), 2, 10) + _count(f"{w}.evidence", item.get("evidence"), 1, 10)
    problems += _count(f"{w}.open_questions", item.get("open_questions", []), 0, 8)
    decision = item.get("for_decision")
    if not isinstance(decision, str) or not decision.rstrip().endswith("?"):
        problems.append(f"{w}.for_decision must be the question a qualified person decides, ending with \"?\"")
    return problems


def _value(figures, fid):
    fig = figures.get(fid) if isinstance(fid, str) else None
    value = fig.get("value") if isinstance(fig, dict) else None
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _reconciliation(w, item, figures):
    problems = []
    sides = {}
    for side in ("side_a", "side_b"):
        part = item.get(side)
        value = _value(figures, part.get("figure_id")) if isinstance(part, dict) else None
        if value is None:
            problems.append(f"{w}.{side} needs a label and the id of a verified figure")
        sides[side] = (value, figures.get(part.get("figure_id"), {}).get("unit") if isinstance(part, dict) else None)
    if item["side_a"].get("figure_id") == item["side_b"].get("figure_id"):
        problems.append(f"{w}: side_a and side_b must be two different figures; a figure always agrees with itself")
    adjusted = {"a": sides["side_a"][0], "b": sides["side_b"][0]}
    units = {sides["side_a"][1], sides["side_b"][1]}
    for j, line in enumerate(_list(item.get("items"))):
        value = _value(figures, line.get("figure_id")) if isinstance(line, dict) else None
        if value is None or line.get("effect") not in EFFECTS:
            problems.append(f"{w}.items[{j}] needs a verified figure id and an effect in {list(EFFECTS)}")
            continue
        units.add(figures[line["figure_id"]].get("unit"))
        side = line["effect"][-1]
        if adjusted[side] is not None:
            adjusted[side] += -value if line["effect"].startswith("subtract") else value
    if len(units - {None}) > 1:
        problems.append(f"{w}: every line must share one unit (found {sorted(u for u in units if u)})")
    if not problems and abs(adjusted["a"] - adjusted["b"]) > BALANCE_TOLERANCE:
        problems.append(f"{w} does not balance: side A adjusted is {adjusted['a']:,.2f}, side B adjusted is "
                        f"{adjusted['b']:,.2f}; every difference needs an item")
    for j, entry in enumerate(_list(item.get("entries"))):
        if not isinstance(entry, dict) or _value(figures, entry.get("figure_id")) is None:
            problems.append(f"{w}.entries[{j}] needs the id of a verified figure for its amount")
        elif figures[entry["figure_id"]].get("unit") != "usd":
            problems.append(f"{w}.entries[{j}]: a journal entry's amount must be a usd figure")
    return problems


def _plan(w, item, figures):
    return _count(f"{w}.steps", item.get("steps"), 2, 12)


def _code(w, item, figures):
    problems = []
    if item.get("language") not in LANGUAGES:
        problems.append(f"{w}.language must be one of {list(LANGUAGES)}")
    code = item.get("code")
    if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE:
        problems.append(f"{w}.code must be non-empty and at most {MAX_CODE} characters")
    elif re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", code):
        problems.append(f"{w}.code contains control characters")
    return problems


_KIND_CHECKS = {"draft": _draft, "register": _register, "case_file": _case_file,
                "reconciliation": _reconciliation, "plan": _plan, "code": _code}
