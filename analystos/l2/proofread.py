"""L2 - Gate 2: a third, independent model call whose job is prose
quality - language mechanics (spelling, grammar, tense, punctuation,
duplicated text, broken sentences, inconsistent terminology) plus the
fuller rubric added in Slice 49 (no filler, genuine cross-section
synthesis, plain-language disclosure gaps). It never sees segments,
citations, or values - only the report's own prose - so it cannot be
influenced by whether the underlying facts are right, and a Gate 1
(correctness) bug can never quietly satisfy this gate too, or vice versa.
Both gates are mandatory and independent; see ``analystos.pipeline`` for
how a report that fails either one never reaches a client.

``{{N}}`` placeholders are left in verbatim - the proofreader is told what
they mean and asked to judge the sentence as if a plausible number sits
there, never to flag the placeholder itself as an error. Whether an
insight/interpretation actually cites two distinct facts (as opposed to
whether it reads as a genuine, non-mechanical synthesis of them) is a
separate, fully deterministic check in ``analystos.l2.narrate`` - this
gate judges only what a blind read of the prose itself can judge.
"""

import re
import sys

from analystos.l2.analyze import _create_message, _resolve_client

_MODEL = "claude-sonnet-5"
_MAX_TOKENS = 2048

_SYSTEM_PROMPT = """\
You are a senior editor for a financial-research desk. You are shown \
only the prose of a report - no source document, no data, no citations - \
and you judge it on two kinds of ground: language mechanics, and prose \
quality.

Language mechanics:

- spelling, subject-verb agreement, tense consistency, punctuation errors, \
  run-on sentences
- repeated or duplicated words, phrases, or sentences
- broken or incomplete sentences, and leftover template artifacts (a raw \
  label leaking through, a stray "next:", broken formatting)
- consistent capitalization and terminology for the same term everywhere \
  it appears

Prose quality - three further criteria, each grounded in a concrete \
example so your judgment is consistent:

- **No filler.** A sentence with no citable number, no named \
  mechanism/driver, and no specific claim - just generic positive \
  sentiment ("the Company remains committed to driving long-term \
  shareholder value") - is filler; flag it even if grammatically \
  perfect. A sentence that states a real number, names a real cause, or \
  makes a checkable claim is never filler, regardless of tone. Set \
  has_filler true if any such sentence appears anywhere in the report.
- **Genuine synthesis, clearly labeled.** Any paragraph presented as \
  interpretation/insight must read two or more facts *together* into a \
  judgment neither states alone - not one fact restated with an \
  adjective, and not two facts merely listed side by side with no \
  connecting judgment. ("Margin compression alongside reiterated \
  guidance suggests the dip is temporary" is synthesis; "Margin \
  compressed. Guidance was reiterated." is not - two facts, no \
  connecting judgment.) Set has_synthesized_insight true only if every \
  such paragraph in the report clears this bar; if the report has no \
  such paragraph at all, leave it true (nothing to fail here).
- **Disclosure gaps in plain language.** You cannot judge whether \
  *enough* gaps were flagged - that requires the source document, which \
  you don't have. What you CAN judge from prose alone: any gap that IS \
  stated must be specific and plain ("cash flow from operations is not \
  disclosed"), not vague hand-waving ("certain items were not fully \
  addressed"). Set disclosure_gaps_clear true if every stated gap is \
  specific and plain, or if the report states no gaps at all.

You must NOT judge whether any fact, figure, or claim is correct - you \
have no way to, and a separate process already checked that; commenting \
on it is out of scope. A "{{N}}" token is a placeholder a real, verified \
number is filled into afterward - read each sentence as if a plausible \
number were already there and judge only whether it reads naturally; \
never flag "{{N}}" itself as a problem.

Call report_issues exactly once. "passed" is true only if you find \
nothing worth fixing across BOTH language mechanics and the three prose- \
quality criteria above - a clean report should usually pass. "issues" is \
a list of {location, problem}: "location" quotes a short, exact fragment \
of the text the problem is in (so it can be found again), "problem" \
states the issue plainly in one sentence - for a prose-quality issue, say \
which of the three criteria it fails. Empty list when passed is true.
"""

_TOOL = {
    "name": "report_issues",
    "description": "Submit the prose-quality review of the report's writing.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "passed": {"type": "boolean"},
            "has_filler": {"type": "boolean"},
            "has_synthesized_insight": {"type": "boolean"},
            "disclosure_gaps_clear": {"type": "boolean"},
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
        "required": [
            "passed", "has_filler", "has_synthesized_insight",
            "disclosure_gaps_clear", "issues",
        ],
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

    ``passed`` (as judged by the model against every criterion in
    ``_SYSTEM_PROMPT``) stays the single source of truth for whether a
    report ships - the three structured fields the tool response also
    carries (``has_filler``, ``has_synthesized_insight``,
    ``disclosure_gaps_clear``) are logged for auditability, not folded
    into a second, competing pass/fail signal (Slice 49).

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
    print(
        "[analystos.l2.proofread] rubric: "
        f"has_filler={result.get('has_filler')} "
        f"has_synthesized_insight={result.get('has_synthesized_insight')} "
        f"disclosure_gaps_clear={result.get('disclosure_gaps_clear')}",
        file=sys.stderr,
    )
    ok = passed and not issues
    if not ok:
        print(f"[analystos.l2.proofread] Gate 2 failed: {issues or 'passed=false, no issues listed'}",
              file=sys.stderr)
    else:
        print("[analystos.l2.proofread] Gate 2 passed", file=sys.stderr)
    return ok, issues
