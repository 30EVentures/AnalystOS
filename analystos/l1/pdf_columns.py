"""L1 - real multi-column reading order for a PDF page's text.

``pdfplumber``'s own ``page.extract_text()`` sorts words primarily by
vertical position across the *full* page width. For a genuine two-column
layout that means it reads "left column line 1, right column line 1, left
column line 2, right column line 2, ..." - both columns interleaved line by
line - never "all of the left column, then all of the right column," the
way a person actually reads it. Confirmed by direct experiment building a
real two-column PDF for specs/slice-50/spec.md.

``extract_page_text`` detects a real column split from the words' own
bounding boxes (``page.extract_words()``) - a wide, mostly-empty vertical
gutter separating two non-trivial word groups - and, only when one is
found, reads the left column in full (top to bottom) before the right.
No such gutter -> falls back to ``page.extract_text()`` unchanged, so
every existing single-column document (the overwhelming majority) is
completely unaffected.

Scope: exactly one gutter (two columns). A page with three or more real
columns is not specifically handled - it still improves on interleaving
(the biggest gap gets split correctly), just not fully. Not attempted here
because the stated goal (specs/slice-50/spec.md) is the two-column case
actually observed, not a general N-column layout engine.
"""

_MIN_GUTTER_FRACTION = 0.06  # a gutter must span at least this fraction of the page width
_MIN_WORDS_PER_COLUMN = 3    # fewer than this on one side isn't a real column - stray margin text
_LINE_TOLERANCE = 3          # points; words within this "top" distance are treated as one line


def _used_bands(words):
    """Merge every word's horizontal extent ``[x0, x1]`` into the fewest
    non-overlapping, sorted intervals that still cover them all."""
    intervals = sorted((w["x0"], w["x1"]) for w in words)
    merged = []
    for x0, x1 in intervals:
        if merged and x0 <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], x1))
        else:
            merged.append((x0, x1))
    return merged


def _detect_gutter(words, page_width):
    """Return the x-coordinate of a real two-column gutter, or ``None``
    if this page doesn't have one."""
    if len(words) < _MIN_WORDS_PER_COLUMN * 2:
        return None

    bands = _used_bands(words)
    if len(bands) < 2:
        return None

    best_gap, best_mid = 0.0, None
    for (_a0, a1), (b0, _b1) in zip(bands, bands[1:]):
        gap = b0 - a1
        if gap > best_gap:
            best_gap, best_mid = gap, (a1 + b0) / 2

    if best_mid is None or best_gap < page_width * _MIN_GUTTER_FRACTION:
        return None

    left = [w for w in words if w["x1"] <= best_mid]
    right = [w for w in words if w["x0"] >= best_mid]
    if len(left) < _MIN_WORDS_PER_COLUMN or len(right) < _MIN_WORDS_PER_COLUMN:
        return None

    return best_mid


def _text_from_words(words):
    """Words on one page (or one column) grouped into lines by vertical
    position - top to bottom, each line left to right."""
    ordered = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines = []
    for w in ordered:
        if lines and abs(w["top"] - lines[-1][0]) <= _LINE_TOLERANCE:
            lines[-1][1].append(w)
        else:
            lines.append([w["top"], [w]])

    text_lines = []
    for _top, line_words in lines:
        line_words.sort(key=lambda w: w["x0"])
        text_lines.append(" ".join(w["text"] for w in line_words))
    return "\n".join(text_lines)


def extract_page_text(page):
    """This page's text in real reading order - column-aware when a real
    two-column layout is detected, ``page.extract_text()`` unchanged
    otherwise."""
    words = page.extract_words()
    if not words:
        return page.extract_text() or ""

    gutter = _detect_gutter(words, page.width)
    if gutter is None:
        return page.extract_text() or ""

    left = [w for w in words if w["x1"] <= gutter]
    right = [w for w in words if w["x0"] >= gutter]
    return _text_from_words(left) + "\n" + _text_from_words(right)
