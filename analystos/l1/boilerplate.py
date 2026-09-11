"""L1 - detect and strip legal boilerplate (forward-looking-statements /
safe-harbor disclaimer language) from a document's extracted text, before
it ever reaches L2's fact extraction - see
``analystos.l2.analyze.analyze_document``'s own rule ("if the document
genuinely does not contain a comparison for a figure, leave the figure
without one") is about facts that exist; this is about text that was
never a factual claim in the first place, so it should never become one.

Not a keyword blocklist. A single word like "forward-looking" or "risk"
appears constantly in ordinary, substantive business prose too ("we see
forward momentum," "a key risk to the segment") - a one-word trigger
would wrongly strip real content, and a document author could trivially
dodge a one-word filter by rewording. Detection instead requires either
of two independent, structurally different signals:

1. A canonical section heading - "Forward-Looking Statements," "Safe
   Harbor Statement," "Cautionary Statement Concerning Forward-Looking
   Statements," and the small handful of near-identical phrasings real
   companies actually use. This heading language is remarkably
   standardized across real filings and press releases - a genuine
   legal-drafting convention, not something that varies freely.
2. A *density* of specific, near-verbatim statutory/legal phrase
   patterns this genre of disclaimer exists to satisfy - citing the
   actual securities-law sections, the specific "actual results...differ
   materially" formulation, "undertake no obligation to update," and
   similar. A block must match several of these before content-only
   detection (no heading present) fires - never a single incidental
   phrase, which is exactly the failure mode a naive keyword blocklist
   has.

Once a heading is matched, the disclaimer text that follows is consumed
line by line for as long as it keeps showing at least one of these
patterns (real disclaimers are often more than one sentence/paragraph);
the moment a line shows none, boilerplate mode ends and normal content
resumes - bounded, not a runaway strip of everything after the heading.

Runs on the narrated-default extraction path only: this module's
``strip_forward_looking_boilerplate`` is meant to sit between
``analystos.l1.document_text.extract_document_text`` and
``analystos.l2.analyze.analyze_document``. The old schema/template path
(``analystos.l1.detect.extract_any``) only ever reads literal table
cells, never prose - a forward-looking-statements disclaimer (always
prose) never appears there to begin with, so this has nothing to do on
that path.

See specs/slice-46/spec.md.
"""

import re

_HEADING_RE = re.compile(
    r"^\s*(forward[- ]looking statements?"
    r"|safe harbor(?: statement)?(?: for forward[- ]looking statements?)?"
    r"|cautionary (?:statement|note)(?: concerning| regarding)? forward[- ]looking statements?)"
    r"\s*:?\s*$",
    re.IGNORECASE,
)

# Phrase-level patterns tied to the specific legal content this genre of
# text exists to satisfy - never a single generic word. Each one is rare
# outside a genuine forward-looking-statements disclaimer.
_CONTENT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"private securities litigation reform act",
        r"section 27a of the securities act",
        r"section 21e of the securities exchange act",
        r"within the meaning of\W{0,3}(the\W{0,3})?safe harbor",
        r"forward[- ]looking statements?.{0,150}(involve|are subject to|based on)"
        r".{0,60}risks and uncertaint",
        r"actual results.{0,80}(could|may|might) differ materially",
        r"undertake no obligation to update",
        r"except as required by (applicable )?law",
    )
]
_MIN_STANDALONE_MATCHES = 3  # the bar for content-only detection, no heading present


def _is_boilerplate_heading(line):
    return bool(_HEADING_RE.match(line.strip()))


def _content_match_count(text):
    return sum(1 for p in _CONTENT_PATTERNS if p.search(text))


def strip_forward_looking_boilerplate(text):
    """Remove forward-looking-statements/safe-harbor disclaimer lines from
    ``text``, keeping everything else - including their relative order and
    spacing - exactly as extracted.

    Splits on ``"\\n"`` to match how ``analystos.l1.document_text`` already
    preserves one paragraph per line within a chunk. A line is dropped if
    it's a canonical disclaimer heading (and the disclaimer body that
    follows, consumed for as long as it keeps matching a content pattern),
    or if a heading-less line on its own matches at least
    ``_MIN_STANDALONE_MATCHES`` content patterns.
    """
    lines = text.split("\n")
    kept = []
    in_boilerplate = False
    for line in lines:
        if _is_boilerplate_heading(line):
            in_boilerplate = True
            continue
        if in_boilerplate:
            if not line.strip() or _content_match_count(line) >= 1:
                continue  # still the disclaimer's own body, or a blank line inside it
            in_boilerplate = False  # a real, unrelated line - the section ended
        if _content_match_count(line) >= _MIN_STANDALONE_MATCHES:
            continue
        kept.append(line)
    return "\n".join(kept).strip()
