#!/usr/bin/env python3
"""Mutation check (Slice 115): do the tests notice when a rule is removed?

    python3 tools/mutation_check.py analystos/packs/consulting.py \\
        tests.test_consulting_pack tests.test_deck_render --semantic tools/mutants/consulting.json

Two methods, both reported:
- guards: every ``if``/``elif`` line whose next line records a problem, raises,
  returns or skips is turned into ``if False:`` one at a time;
- semantic: hand-written replacements from a JSON list of {"name", "old", "new"},
  each of which changes logic rather than switching a guard off. An entry may
  carry "equivalent": "<why>" for a mutant that cannot change behaviour; it is
  still run and reported, but its survival is expected and does not fail.

A mutant is "caught" when the named test modules fail with it. Each mutant is
written to the file and the tests run in a fresh process (so modules that import
the mutated one see it); the original file is always restored. Run it on a clean
working tree. Exit 1 if any mutant survives.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_GUARD_RE = re.compile(r"\s*(el)?if .*:\s*$")
_EFFECT_RE = re.compile(r"problems\.(append|extend)|problems \+=|raise ValueError|return \[|return None|continue\b|return False")


def guard_mutants(source):
    lines = source.splitlines(keepends=True)
    for i, line in enumerate(lines[:-1]):
        if _GUARD_RE.match(line) and _EFFECT_RE.search(lines[i + 1]):
            indent = re.match(r"\s*", line).group(0)
            keyword = "elif" if line.strip().startswith("elif") else "if"
            mutated = lines[:]
            mutated[i] = f"{indent}{keyword} False:\n"
            yield f"guard line {i + 1}: {line.strip()}", "".join(mutated)


def semantic_mutants(source, path):
    for item in json.loads(Path(path).read_text(encoding="utf-8")):
        name = item["name"] + (f" [equivalent: {item['equivalent']}]" if item.get("equivalent") else "")
        if source.count(item["old"]) != 1:
            yield name, None
        else:
            yield name, source.replace(item["old"], item["new"], 1)


def tests_fail(test_modules):
    done = subprocess.run([sys.executable, "-m", "unittest", "-q", *test_modules], cwd=ROOT,
                          capture_output=True, text=True)
    return done.returncode != 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("module")
    parser.add_argument("tests", nargs="+")
    parser.add_argument("--semantic")
    args = parser.parse_args(argv)
    target = ROOT / args.module
    original = target.read_text(encoding="utf-8")
    if tests_fail(args.tests):
        print("the tests fail on the unmutated code; fix that first")
        return 2
    results = {"guards": [], "semantic": []}
    try:
        for name, mutated in guard_mutants(original):
            target.write_text(mutated, encoding="utf-8")
            results["guards"].append((name, tests_fail(args.tests)))
        if args.semantic:
            for name, mutated in semantic_mutants(original, args.semantic):
                if mutated is None:
                    results["semantic"].append((name + " (pattern not found)", False))
                    continue
                target.write_text(mutated, encoding="utf-8")
                results["semantic"].append((name, tests_fail(args.tests)))
    finally:
        target.write_text(original, encoding="utf-8")
    survived = 0
    for kind, items in results.items():
        if not items:
            continue
        caught = sum(1 for _, ok in items if ok)
        print(f"{args.module} {kind}: {caught}/{len(items)} caught")
        for name, ok in items:
            if not ok:
                expected = "[equivalent:" in name
                survived += 0 if expected else 1
                print(f"  {'SURVIVED (expected)' if expected else 'SURVIVED'} {name}")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
