"""L2 - Gate 2: a third, independent model call whose only job is language
quality - spelling, grammar, tense, punctuation, duplicated text, broken
sentences, inconsistent terminology. It never sees segments, citations, or
values - only the report's own prose - so it cannot be influenced by
whether the underlying facts are right, and a Gate 1 (correctness) bug can
never quietly satisfy this gate too, or vice versa. Both gates are
mandatory and independent; see ``analystos.pipeline`` for how a report
that fails either one never reaches a client.

``{{N}}`` placeholders are left in verbatim - the proofreader is told what
they mean and asked to judge the sentence as if a plausible number sits
there, never to flag the placeholder itself as an error.
"""

import re
import sys

from analystos.l2.analyze import _create_message, _resolve_client

_MODEL = "claude-sonnet-5"
_MAX_TOKENS = 2048

_SYSTEM_PROMPT = """\
You are a professional copy editor. You are shown only the prose of a \
financial report - no source document, no data, no citations - and your \
only job is language quality:

- spelling, subject-verb agreement, tense consistency, punctuation errors, \
  run-on sentences
- repeated or duplicated words, phrases, or sentences
- broken or incomplete sentences, and leftover template artifacts (a raw \
  label leaking through, a stray "next:", broken formatting)
- consistent capitalization and terminology for the same term everywhere \
  it appears

You must NOT judge whether any fact, figure, or claim is correct - you \
have no way to, and a separate process already checked that; commenting \
on it is out of scope. A "{{N}}" token is a placeholder a real, verified \
number is filled into afterward - read each sentence as if a plausible \
number were already there and judge only whether it reads naturally; \
never flag "{{N}}" itself as a problem.

Call report_issues exactly once. "passed" is true only if you find \
nothing worth fixing - a clean report should usually pass. "issues" is a \
list of {location, problem}: "location" quotes a short, exact fragment of \
the text the problem is in (so it can be found again), "problem" states \
the language issue plainly in one sentence. Empty list when passed is \
true.
"""

_TOOL = {
    "name": "report_issues",
    "description": "Submit the language-quality review of the report's prose.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "passed": {"type": "boolean"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "problem": {"type": "string"},
                    },
                    "required": ["location", "problem"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["passed", "issues"],
        "additionalProperties": False,
    },
}


def _report_text(report):
    """Every piece of reader-facing prose in a structured report, {{N}}
    placeholders intact, one block per paragraph - what Gate 2 actually
    reads. Section headings are included: a duplicated/leaking artifact
    (Gate 1's directly-observed Bug 2) shows up there too, and catching it
    here - blind to which facts are involved - is meant to be a second,
    independent line on the same class of defect, not a re-check of Gate 1.
    """
    parts = []
    for p in report.get("executive_summary") or []:
        parts.append(p.get("text", ""))
    insight = report.get("executive_insight")
    if insight:
        parts.append(insight)
    for section in report.get("sections") or []:
        parts.append(section.get("heading", ""))
        for p in section.get("paragraphs") or []:
            parts.append(p.get("text", ""))
    for gap in report.get("disclosure_gaps") or []:
        parts.append(gap.get("text", ""))
    for p in report.get("outlook") or []:
        parts.append(p.get("text", ""))
    interp = report.get("outlook_interpretation")
    if interp:
        parts.append(interp)
    return "\n\n".join(p for p in parts if p and p.strip())


def proofread_report(report, client=None):
    """Gate 2. Returns ``(passed, issues)`` - ``issues`` is a list of
    ``{"location": ..., "problem": ...}`` dicts, empty when ``passed`` is
    True. A report with no prose at all (shouldn't happen - Gate 1 already
    requires a non-empty executive summary and sections) trivially passes.

    Raises ``ValueError`` only if the API call itself fails - the same
    clean, generic message every other call in this codebase raises.
    ``analystos.pipeline`` treats that identically to a failed pass: a
    report whose language quality could not be confirmed is not shown,
    the same way an unverified number is dropped rather than displayed.
    """
    client = _resolve_client(client)
    text = _report_text(report)
    if not text.strip():
        return True, []

    response = _create_message(
        client,
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "report_issues"},
        messages=[{"role": "user", "content": text}],
    )

    tool_use = next(
        (b for b in getattr(response, "content", []) if getattr(b, "type", None) == "tool_use"),
        None,
    )
    if tool_use is None:
        print("[analystos.l2.proofread] response had no tool_use block", file=sys.stderr)
        return False, [{"location": "", "problem": "proofreading call returned no result"}]

    result = tool_use.input if isinstance(tool_use.input, dict) else {}
    passed = bool(result.get("passed"))
    issues = [
        i for i in (result.get("issues") or [])
        if isinstance(i, dict) and i.get("problem")
    ]
    ok = passed and not issues
    if not ok:
        print(f"[analystos.l2.proofread] Gate 2 failed: {issues or 'passed=false, no issues listed'}",
              file=sys.stderr)
    else:
        print("[analystos.l2.proofread] Gate 2 passed", file=sys.stderr)
    return ok, issues
