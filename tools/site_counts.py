"""Keep the homepage's test and spec counts true (Slice 69).

    python3 tools/site_counts.py            # rewrite the figures in site/details.html
    python3 tools/site_counts.py --check    # exit 1 if any is stale

Tests are counted by *discovering* the suite (nothing is run); specs are the
``specs/slice-N/spec.md`` files. Every figure is matched by an explicit pattern
below. A pattern that no longer matches exactly once is an error, so rewording the
page cannot silently turn a live number into a frozen one.

The test figure is the number of tests *in the suite*, not the number that pass
(Slice 111): some tests are skipped on a machine without Node.js, so a pass count
would depend on who ran this. The page's wording must say "in the suite", never
"passing"; ``PASSING_CLAIM`` is the shape the suite refuses.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "details.html"  # the full page; the homepage carries no counts (Slice 122)

# (name, regex with one group around the number to replace, kind)
PATTERNS = [
    ("hero stat", r"<strong>(\d+)</strong><span>automated tests in the suite", "tests"),
    ("hero specs", r"<strong>(\d+)</strong><span>written specs behind the build", "specs"),
    ("built list", r"(\d+) automated tests with mocked calls", "tests"),
    ("evidence card", r"(\d+) automated tests</b><p class=\"note\"[^>]*>in the suite", "tests"),
    ("specs card", r"(\d+) specs</b>", "specs"),
    ("faq", r"(\d+) automated tests, a live suite", "tests"),
    ("about", r"backed by (\d+) automated tests", "tests"),
    ("measure", r"meas:'(\d+) mocked tests in the suite", "tests"),
]

# A test count presented as a pass count ("1352 automated tests passing", "1352
# tests with mocked calls: ..., passing in under a minute") or as a pass ratio
# ("1352 / 1352"). The count includes skipped tests, so neither is true. Matches
# within one sentence and one text node, plus the hero's </strong><span> split.
PASSING_CLAIM = r"\d+(?:</strong><span>|\s)[^.<]{0,80}?\btests\b[^.<]{0,80}?\bpassing\b|\b(\d+) / \1\b"


def passing_claims(text):
    """Every place the page presents the test count as a count of passing tests."""
    return [m.group(0) for m in re.finditer(PASSING_CLAIM, text)]


def count_tests():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    return suite.countTestCases()


def count_specs():
    return len(list((ROOT / "specs").glob("slice-*/spec.md")))


def rewrite(text, tests, specs):
    """``(new_text, problems)``. A problem is a pattern that did not match once."""
    problems = []
    for name, pattern, kind in PATTERNS:
        regex = re.compile(pattern)
        matches = regex.findall(text)
        if len(matches) != 1:
            problems.append(f"{name}: pattern matched {len(matches)} times, expected exactly 1 (was the page reworded?)")
            continue
        value = specs if kind == "specs" else tests
        text = regex.sub(lambda m: m.group(0).replace(m.group(1), str(value), 1), text, count=1)
    return text, problems


def stale_figures(text, tests, specs):
    """Names of figures whose number on the page differs from the truth."""
    stale = []
    for name, pattern, kind in PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue
        want = specs if kind == "specs" else tests
        if int(m.group(1)) != want:
            stale.append(f"{name}: page says {m.group(1)}, actual {want}")
    return stale


def main(argv=None):
    check = "--check" in (sys.argv[1:] if argv is None else argv)
    text = PAGE.read_text(encoding="utf-8")
    tests, specs = count_tests(), count_specs()
    new, problems = rewrite(text, tests, specs)
    if problems:
        print("\n".join(problems))
        return 1
    if check:
        stale = stale_figures(text, tests, specs)
        stale += [f"claims tests pass, but the count includes skipped ones: {c!r}" for c in passing_claims(text)]
        print("\n".join(stale) if stale else f"homepage counts are true ({tests} tests, {specs} specs)")
        return 1 if stale else 0
    PAGE.write_text(new, encoding="utf-8")
    print(f"homepage counts set to {tests} tests, {specs} specs" if new != text else "already true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
