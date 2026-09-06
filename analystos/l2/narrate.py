"""L2 - a second, narrower model call that decides how to *write about*
facts ``analystos.l2.analyze`` already verified. It never sees the raw
document and it never gets to state a number itself.

``write_narrative`` builds a numbered manifest from a document's already-
verified ``segments`` (Slice 26's output - unchanged by this module) and
asks the model for an ordered list of paragraphs. Each paragraph is free-
form text that may reference any *citable* fact (a ``quote``/``computed``
segment - never a ``prose`` one, which has no citation to attach) via a
``{{N}}`` placeholder, where ``N`` is that fact's index in ``segments``.
The model chooses structure, grouping, and wording; it never gets to write
the number itself - the placeholder is filled in later, by
``analystos.l4.export.render_narrative_section``, with the exact value
Slice 26 already verified.

Every paragraph is validated before any of this is trusted: every
placeholder must reference a real, citable fact, and every digit outside
a placeholder is treated as an unverified number (the same rule
``analyze_document``'s ``_verify_prose`` already applies, calendar
references carved out the same way - see ``_CALENDAR_RE`` in
``analystos.l2.analyze``) and rejects the whole narrative. There is no
partial acceptance and no retry - a rejected narrative raises
``ValueError``, and the caller (``analystos.pipeline``) falls back to
Slice 26's plain per-segment rendering. See ``specs/slice-27/spec.md``.
"""

import re
import sys

from analystos.l2.analyze import _CALENDAR_RE, _DIGIT_RE, _create_message, _resolve_client
from analystos.l4.export import display_value

_MODEL = "claude-sonnet-5"
_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")

_SYSTEM_PROMPT = """\
You are a senior financial/business analyst turning a list of already-\
verified facts into an executive-quality written report. Every fact \
listed below has already been checked against the real source document -
you are not verifying anything and you must not introduce any new number.

You must call write_narrative exactly once, with an ordered list of \
paragraphs. For each paragraph, write "text" - real prose, structured \
however best serves an executive reader (lead with what matters most; \
group related facts together; add a transition sentence connecting two \
figures if that reads better than listing them separately).

To use a "[citable]" fact's value in a sentence, write {{N}} (its number \
below) exactly where the value belongs - never write the number itself, \
it is filled in for you afterward. One paragraph may reference several \
facts this way. A "[context, not citable]" fact is already-verified \
prose you may draw on for tone or content, but it has no single number to \
cite - write your own sentence about it with no digits in it at all.

You do not have to use every fact - use your judgment about what's \
genuinely worth the reader's attention. Never write a digit that isn't \
inside a {{N}} placeholder - except a quarter/half/year reference (e.g. \
"Q4 2026" or "heading into 2027"), which needs no citation and is fine \
anywhere.
"""

_TOOL = {
    "name": "write_narrative",
    "description": "Submit the report as an ordered list of paragraphs.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "paragraphs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["paragraphs"],
        "additionalProperties": False,
    },
}


def _build_manifest(segments):
    lines = []
    for i, segment in enumerate(segments):
        if segment["type"] == "prose":
            lines.append(f'Fact {i} [context, not citable]: "{segment["text"]}"')
        else:
            label = segment.get("label") or "Fact"
            lines.append(
                f'Fact {i} [citable]: label="{label}", '
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


def write_narrative(segments, title, client=None):
    """Ask Claude how to write about already-verified ``segments``; return
    a list of ``{"text": ...}`` paragraph dicts, each safe to pass to
    ``analystos.l4.export.render_narrative_section``.

    Raises ``ValueError`` on any failure - no citable fact at all, a bad
    or missing tool response, a paragraph that fails validation, or the
    Anthropic API call itself failing (see ``_resolve_client``/
    ``_create_message`` in ``analystos.l2.analyze``, shared with this
    module). Callers should catch this and fall back to Slice 26's plain
    rendering - a worse-structured report, never a lost one.
    """
    if not any(segment["type"] != "prose" for segment in segments):
        raise ValueError("no citable facts to narrate")

    client = _resolve_client(client)
    manifest = _build_manifest(segments)

    response = _create_message(
        client,
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "write_narrative"},
        messages=[{"role": "user", "content": f'Title: "{title}"\n\n{manifest}'}],
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        print("[analystos.l2.narrate] response had no tool_use block", file=sys.stderr)
        raise ValueError("model did not return a narrative")

    paragraphs = tool_use.input.get("paragraphs", [])
    if not paragraphs:
        print("[analystos.l2.narrate] model returned an empty paragraphs list", file=sys.stderr)
        raise ValueError("model returned no paragraphs")

    for paragraph in paragraphs:
        text = paragraph.get("text", "")
        reason = _validate_paragraph(text, segments)
        if reason is not None:
            # Never echo the paragraph's own text in the response, but log
            # it server-side - "the narrative failed" alone isn't
            # diagnosable, and this exact gap was found live (a rejection
            # with no clue why until the actual Anthropic responses were
            # compared against what the code did with them).
            print(
                f"[analystos.l2.narrate] narrative rejected - paragraph {reason}: {text!r}",
                file=sys.stderr,
            )
            raise ValueError(
                "narrative referenced an unverifiable fact or a stray "
                "number - falling back to the plain rendering"
            )

    print(f"[analystos.l2.narrate] narrative accepted: {len(paragraphs)} paragraphs", file=sys.stderr)
    return paragraphs
