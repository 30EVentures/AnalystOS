# Slice 73 - citation matching stops accepting a number inside a bigger one

## Goal

Found while spiking a standalone extraction of `seal_verify.py` (never published;
work abandoned, the code stays here): rule 10's citation match
(`citation_in_text`) is a plain substring test, so a citation can be satisfied
by a number it is not actually part of. Two real cases:

1. `$22.4 million` (folds to `22.4 million` then `22.4`) is found "in the text"
   when the source only says `$122.4 million` - the citation is a substring of
   a bigger number.
2. A citation with its trailing scale word stripped becomes a bare number
   (`$5 million` -> `5`) that then matches any standalone digit sequence
   containing it, including inside an unrelated number like `2025`.

Reproduce against the current code:

```python
from analystos.l4.seal_verify import citation_in_text, match_key
citation_in_text("$22.4 million", match_key("Net income was $122.4 million."))  # True - should be False
citation_in_text("$5 million", match_key("Only 5 employees remain in 2025."))    # True - should be False
```

Separately: rule 1 (`docs/seal.md`) says every number in a sealed `record`,
`report` or `payload` field (other than `version`/`entries`) is a string, so no
verifier has to agree with another about how to print a float. Nothing enforces
it. A bundle holding a raw JSON number in a fact hashes internally-consistently
and passes today, but would hash differently under a verifier written in a
language whose float-to-string differs from Python's `repr`.

## Included

`citation_in_text` (`analystos/l4/seal_verify.py`) and `_really_in_document`
(`analystos/l2/analyze.py`) are deliberately two copies of the same check -
`seal_verify.py` imports nothing from the rest of AnalystOS by design (the
standalone-verifier promise in its own docstring), so it cannot share code
with `analyze.py`. `tests/test_l4_seal.py::DifferentialAgainstTheAnalyzerTest`
already asserts the two stay in agreement. This bug lives in both; both get
the identical fix, independently, so they stay identical:

- `analystos/l4/seal_verify.py` and `analystos/l2/analyze.py`:
  - The match now requires a whole-number boundary: if the folded citation (or
    its scale-stripped form) starts with a digit, no ASCII digit, and no `.`/`,`
    that is itself adjacent to a digit, may sit immediately before the match; if
    it ends with a digit, the same applies immediately after. A sentence-ending
    full stop, a comma separating list items, or a closing bracket still count
    as a match. If one occurrence in the text fails the boundary test, later
    occurrences are tried before giving up.
  - This tightens acceptance, not just re-verification: `_really_in_document`
    is what the live pipeline uses to decide a model's proposed quote is real
    in the first place (`analystos/l2/analyze.py`'s whole job), so a figure
    that only matched by accident inside a bigger number will now be dropped
    at analysis time, not just flagged later by a stranger's offline check.
  - Neither change touches `values_match_citations` / `value_supported`
    (Slice 66) or `_value_matches_text` (`analyze.py`) - those parse numbers
    out of citation text for a different purpose (does a fact's *value* equal
    a number the citation spells, at the document's declared scale) and are
    unaffected by this text-matching boundary.
- `analystos/l4/seal_verify.py` only: `verify_bundle`'s `structure` check
  additionally fails if any JSON number (`int` or `float`, not `bool`) appears
  anywhere in a fact's `record`, in `report`, or in a `payload` field other
  than `version`/`entries`; those two must themselves be integers. (Not
  relevant to `analyze.py`, which builds live Python objects, not an untrusted
  serialized bundle.)
- `tests/test_l4_seal.py` - boundary cases for `citation_in_text` (sentence
  punctuation, brackets, thousands separators, and each of the two bugs above
  with a same-shaped honest citation that must still pass) and the four
  raw-number `structure` cases (a fact record, a report, `payload.version` as
  `1.0`, any other payload field holding a number).
- `tests/test_l2_analyze.py` - the same boundary cases against
  `_really_in_document` directly, plus confirmation that every existing
  passing case in `test_match_key_folds_typography_not_digits` and
  `test_a_bare_cell_number_locates_but_a_mislabelled_pair_does_not` is
  unaffected (checked by running them, not just by reasoning about it).
- `docs/seal.md` - rule 1 states the enforcement; rule 10 states the boundary
  rule in the same terms as the code comment.

## Done when

1. Both reproduction cases above return `False`.
2. Every existing passing citation in `tests/test_l4_seal.py` and
   `test_l1_footnotes.py`/`test_l2_narrate.py`'s citation-shaped fixtures still
   passes - the stricter rule must not create new false rejections. Checked by
   running the full suite, and by a targeted scan (see "Verified beyond the
   test suite" below) over every citation the live-tested fixtures produce.
3. A bundle with a raw JSON number in a fact's record, in the report, or in a
   non-version/entries payload field fails `structure`; `payload.version: 1.0`
   and `payload.entries: "3"` (a string) both fail `structure` too.
4. `python3 -m unittest discover -s tests -v` reports `OK`.

## Not in this slice

- `values_match_citations`'s own number-parsing (`parse_numbers`,
  `value_supported`) - untouched; it solves a different problem (does the
  *value* match a number the citation spells) and was not found to share this
  bug.
- Any change to how `analystos/l4/seal.py` *builds* a bundle - only the
  verifier's checking logic changes.
- The abandoned standalone-package spike itself - it produced this fix and a
  test corpus, and was then dropped per instruction; nothing from it is
  published or referenced from here.
