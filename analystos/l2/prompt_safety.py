"""Prompt-safety helpers shared by the extraction and narration stages (Slice 82).

Two things reach a model prompt that the caller or the document controls: the
report ``title`` and verbatim document substrings (they pass through the
verified segments into the narrator's fact manifest). Neither is an
instruction, and neither may be able to look like one:

- ``sanitize_title`` caps a title's length and strips control characters,
  newlines and the manifest's delimiter tokens, so a title cannot add lines,
  forge structure or flood the prompt. One function, used at both prompt sites.
- ``neutralize`` does the same for untrusted text inside a manifest entry
  (except length: a quote must stay whole).
- ``wrap_fact`` puts one manifest entry between explicit delimiters. Because
  ``neutralize`` guarantees untrusted text contains no ``<<`` or ``>>``, a
  forged ``<</FACT>>`` inside document text cannot close an entry early.

This is a mitigation, not a proof: the model is still told, in both system
prompts, that anything between the markers is data. The numbers cannot be
changed by an injection in any case - every figure is re-verified in code.
"""

import re
import unicodedata

MAX_TITLE_CHARS = 200
DEFAULT_TITLE = "Untitled document"

# Open/close markers for one manifest entry. Chosen so ``neutralize`` can
# remove every occurrence of their building blocks ("<<", ">>") from untrusted text.
FACT_OPEN = "<<FACT {i}>>"
FACT_CLOSE = "<</FACT {i}>>"

_ANGLE_RUN_RE = re.compile(r"<(?=<)|>(?=>)")
_SPACES_RE = re.compile(r"\s+")


def neutralize(text):
    """Return ``text`` safe to embed inside a delimited prompt entry.

    Control, format (zero-width, bidi override) and line/paragraph-separator
    characters become spaces, whitespace collapses to single spaces, and any
    ``<<`` / ``>>`` is broken up (``<<`` becomes ``< <``) so no delimiter
    token can be forged. Non-strings are converted with ``str``.
    """
    text = "" if text is None else str(text)
    cleaned = "".join(
        " " if unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") else ch for ch in text
    )
    cleaned = _SPACES_RE.sub(" ", cleaned).strip()
    return _ANGLE_RUN_RE.sub(lambda m: m.group(0) + " ", cleaned)


def sanitize_title(title):
    """The caller-supplied report title, made safe for a prompt.

    Strips control characters and delimiter tokens (``neutralize``), replaces
    double quotes with single quotes (the prompt wraps the title in double
    quotes), and caps the length at ``MAX_TITLE_CHARS``. An empty result falls
    back to ``DEFAULT_TITLE``. The report's own title is not changed; this is
    only the form the model sees.
    """
    cleaned = neutralize(title).replace('"', "'")
    cleaned = cleaned[:MAX_TITLE_CHARS].rstrip()
    return cleaned or DEFAULT_TITLE


def wrap_fact(index, body):
    """One manifest entry between its open and close markers."""
    return f"{FACT_OPEN.format(i=index)} {body} {FACT_CLOSE.format(i=index)}"
