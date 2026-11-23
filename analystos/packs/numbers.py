"""Find every number a reader would read as a quantity (Slice 115).

The consulting verifier's rule is that every number in model-written text
carries a figure tag. That rule is only as strong as the definition of "a
number", and the first version (Slice 112) counted only ASCII-style digit runs
not glued to a letter - so "seven percent", "tripled", "½", "NRR96%", ".5%"
and "2000 clinics" (read as a year) all slipped through. This module is the
wider definition, kept separate so it can be tested on its own.

``find_numbers(text)`` returns tokens. A token has a value when it can be read
as one (digits, with sign, currency, scale and unit), and ``value is None`` when
it is a quantity that cannot be checked against a figure (number words above
twelve, number words with a unit, scale words, multipliers, fractions,
superscripts, Roman numerals with a unit) - the verifier refuses those outright:
write the number as digits and tag it.

Exempt, by design and nothing else: labels from a closed list (Q1-Q4, H1-H2,
FY plus a year, [F#] figure tags, version strings like v1.2), a digit with letters
directly on both sides (a name such as B2B or H2O; "NRR96%" still counts), a four-digit year
directly after a time word ("in 2025", "since 2024"), and the counting words
one to twelve on their own ("two hires", "three options") - those are allowed
and are not checked.
"""

import re
import unicodedata
from collections import namedtuple

Token = namedtuple("Token", "start end text value kind tol")

_LABEL_RE = re.compile(
    r"\[F[1-9][0-9]{0,2}\]"
    r"|\b(?:Q[1-4]|H[12])\b"
    r"|\bFY ?(?:[0-9]{4}|[0-9]{2})\b"
    r"|\bv[0-9]+(?:\.[0-9]+)+\b"
)
_YEAR_RE = re.compile(r"\b(?:in|since|during|until|before|after|through|Q[1-4]|H[12])\s+((?:19|20)[0-9]{2})\b(?![%.,]?[0-9])",
                      re.IGNORECASE)
# Digits: \d is Unicode-aware, and float() reads any Unicode decimal digit.
_DIGIT_RE = re.compile(
    r"(?P<cur>\$)?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
    r"(?:\s?(?P<suf>%|percent\b|per cent\b|percentage points?\b|pp\b|points?\b|pts\b"
    r"|bn\b|billion\b|million\b|thousand\b|[kKmMB]\b|x\b))?"
)
_SCALE = {"k": 1e3, "K": 1e3, "thousand": 1e3, "m": 1e6, "M": 1e6, "million": 1e6,
          "B": 1e9, "bn": 1e9, "billion": 1e9}
_KIND = {"%": "percent", "percent": "percent", "per cent": "percent", "pp": "points", "point": "points",
         "points": "points", "pts": "points", "percentage point": "points", "percentage points": "points",
         "x": "ratio"}

SMALL_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
               "eleven", "twelve")
_LARGE_WORDS = ("thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
                "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
                "hundreds?", "thousands?", "millions?", "billions?", "trillions?", "dozens?")
_MULTIPLIERS = (r"doubl(?:e|ed|es|ing)", r"tripl(?:e|ed|es|ing)", r"quadrupl(?:e|ed|es|ing)",
                r"twice", r"thrice", r"half", r"halv(?:e|ed|es|ing)", r"\w+fold", r"thirds?")
_UNIT_AFTER = r"\s*(?:-\s*)?(?:%|percent\b|per cent\b|pct\b|bps\b|percentage points?\b|points?\b|pts\b|dollars?\b|x\b|times\b)"
_ANY_NUMBER_WORD = r"(?:" + "|".join(SMALL_WORDS + _LARGE_WORDS) + r")"
_FRACTIONS = (r"\b(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten)[- ]"
              r"(?:half|halves|thirds?|quarters?(?= of\b)|fifths?|sixths?|sevenths?|eighths?|ninths?|tenths?)\b"
              r"|\b" + _ANY_NUMBER_WORD + r"\s+(?:in|out of)\s+" + _ANY_NUMBER_WORD + r"\b")
_WORD_RE = re.compile(
    _FRACTIONS + r"|"
    r"\b(?:(?:" + "|".join(_LARGE_WORDS) + r")(?:[- ](?:" + "|".join(SMALL_WORDS) + r"))?"
    r"|(?:" + "|".join(_MULTIPLIERS) + r"))\b"
    r"|\b(?:" + "|".join(SMALL_WORDS) + r")\b(?=" + _UNIT_AFTER + r")"
    r"|\b[IVXLCDM]{2,}\b(?=" + _UNIT_AFTER + r")",
    re.IGNORECASE,
)


def _mask(text, spans):
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def find_numbers(text):
    """Every quantity in ``text``, in order, as ``Token``s (see the module docstring)."""
    if not isinstance(text, str):
        return []
    exempt = [m.span() for m in _LABEL_RE.finditer(text)] + [m.span(1) for m in _YEAR_RE.finditer(text)]
    masked = _mask(text, exempt)
    tokens = []
    taken = []
    for m in _DIGIT_RE.finditer(masked):
        start, end = m.span()
        # A digit with letters directly on both sides is part of a name (B2B, P2P, H2O), not a quantity.
        glued_before = start > 0 and masked[start - 1].isalpha()
        glued_after = (end < len(masked) and masked[end].isalpha()) or (
            m.group("suf") and m.group("suf")[-1:].isalpha() and " " not in m.group(0))
        if glued_before and glued_after and not m.group("cur"):
            continue
        raw, dec = m.group("num"), ""
        if "." in raw:
            raw, dec = raw.split(".", 1)
            dec = "." + dec
        places = len(dec) - 1 if dec else 0
        suf = m.group("suf")
        scale = _SCALE.get(suf, 1.0) if suf else 1.0
        try:
            value = float((raw.replace(",", "") or "0") + dec) * scale
        except ValueError:
            value = None
        # A sign counts only when it stands before the number, not inside a range ("4-7%").
        before = masked[start - 1] if start > 0 else ""
        before2 = masked[start - 2] if start > 1 else " "
        if before and before in "-−" and not before2.isalnum() and value is not None:
            value, start = -value, start - 1
        kind = _KIND.get(suf.lower() if suf and suf not in ("M", "B", "K") else suf) if suf else None
        if m.group("cur"):
            kind = "usd"
        tokens.append(Token(start, end, text[start:end], value, kind, 0.5 * 10 ** -places * scale + 1e-9))
        taken.append((start, end))
    masked_digits = _mask(masked, taken)
    for m in _WORD_RE.finditer(masked_digits):
        tokens.append(Token(m.start(), m.end(), text[m.start():m.end()], None, None, None))
    for i, ch in enumerate(masked_digits):
        # Fractions, superscripts, circled and Roman-numeral characters: numeric but not a decimal digit.
        if not ch.isdecimal() and unicodedata.numeric(ch, None) is not None:
            tokens.append(Token(i, i + 1, ch, None, None, None))
    return sorted(tokens)
