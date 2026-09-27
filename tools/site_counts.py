"""Keep the homepage's test and spec counts true (Slice 69).

    python3 tools/site_counts.py            # rewrite the figures in site/index.html
    python3 tools/site_counts.py --check    # exit 1 if any is stale

Tests are counted by *discovering* the suite (nothing is run); specs are the
``specs/slice-N/spec.md`` files. Every figure is matched by an explicit pattern
below. A pattern that no longer matches exactly once is an error, so rewording the
page cannot silently turn a live number into a frozen one.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "index.html"

# (name, regex with one group around the number(s) to replace, kind)
PATTERNS = [
    ("hero stat", r"<strong>(\d+)</strong><span>automated tests passing", "tests"),
    ("built list", r"(\d+) automated tests with mocked calls", "tests"),
    ("evidence card", r"(\d+) / \d+</b><p class=\"note\"[^>]*>automated tests passing", "tests_pair"),
    ("specs card", r"(\d+) specs</b>", "specs"),
    ("faq", r"(\d+) automated tests, a live suite", "tests"),
    ("about", r"with (\d+) automated tests passing", "tests"),
    ("measure", r"meas:'(\d+) mocked tests passing", "tests"),
]


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
        if kind == "tests_pair":
            text = regex.sub(lambda m: re.sub(r"^\d+ / \d+", f"{tests} / {tests}", m.group(0)), text, count=1)
        else:
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
        elif kind == "tests_pair" and not re.search(rf"{tests} / {tests}<", m.group(0) + "<"):
            stale.append(f"{name}: the second number of the pair is wrong")
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
        print("\n".join(stale) if stale else f"homepage counts are true ({tests} tests, {specs} specs)")
        return 1 if stale else 0
    PAGE.write_text(new, encoding="utf-8")
    print(f"homepage counts set to {tests} tests, {specs} specs" if new != text else "already true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
