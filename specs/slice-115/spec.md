# Slice 115 - make "every number is traced" true (review of Slices 112-114)

## Goal

A fresh-context review of Slices 112-113 found the product claim - every
number in the deck is traced to the client's words, a recomputed calculation
or a labelled assumption, and the model cannot get an untraced one in - false
as built. Nothing had been pushed or published. This slice closes every gap the
review reproduced, before evaluation (Slice 116) or the website (Slice 117).

## What changes

**Finding numbers (H1).** A number is anything a reader reads as a quantity:
digits (ASCII or not, with a leading dot, a sign, a suffix, or glued to a word),
fractions and superscripts, number words above twelve, number words with a
unit ("seven percent"), scale words ("thousand", "million"), multiplier words
("double", "tripled", "twice", "half", "halved") and Roman numerals with a unit.
Exempt only: labels from a closed list (Q1-Q4, H1-H2, FY plus a year, F#
figure tags, version strings) and a four-digit year after a time word ("in
2025", "since 2024"). Small counting words one to twelve stay allowed as
structure ("two hires", "three options"). Every number needs a figure tag; a
number this rule cannot parse into a value is refused outright.

**Fields that may carry no number at all (H2, M3).** Figure labels, the key
question, branch names, option names, KPI names and chart labels: these are
drawn as labels (on tiles, the title slide, the issue tree, tables), so a
number there is refused, tagged or not.

**Units (H3).** A client figure's unit comes from its quote: a `%` makes it
percent, a `$` makes it usd, a bare number may not be either. A computed
figure's unit is derived from its operation and inputs (a difference of two
percents is points; a product with one usd input is usd; percent_of keeps the
total's unit; growth_percent and percent_of_total are percent), and must equal
the declared unit. Every prose number's kind must match its figure's unit,
bare numbers included ("7 [F2] clinics" against a 7% figure is refused).
Signs must agree.

**One number per quote, canonical values (M1, M2).** A client quote must
contain exactly one number, and the figure's value is that number exactly. A
computed figure may be stated within 1% (models round), but verification then
replaces every figure's value with the canonical one - the quote's number or
the exact recomputation from canonical inputs - so drift cannot compound and
every formula on the sources slide recomputes by hand.

**Rounding at coarse scales (L3).** A prose number must match its figure both
at the precision shown and within 5%: "1K" no longer passes for 850.

**The renderer re-verifies (M4, L4).** A deck spec now carries the client's
text. `render_deck` re-runs verification on the spec's content, rebuilds the
slides from it and refuses a spec whose slides differ, so a spec edited after
verification cannot be rendered. Malformed specs raise `ValueError`.

**An exact no-new-numbers test (M5).** Every number token on every rendered
slide must be one of: a token written in the verified content, a formatted
figure value, a slide number, sources pagination or formula notation - matched
as whole tokens, not substrings. A negative test injects a number into a
rendered deck and requires the check to fail.

**Smaller fixes.** The repair-retry prompt neutralises the previous output and
the check messages (L1). The issue-tree slide no longer says every part was
tested (L5). The mutation check is committed as `tools/mutation_check.py` so
the counts in commit messages can be reproduced. The overclaims the review
listed are corrected in `docs/decisions.md`.

## Done when

1. Every probe the review reported passing - number words, multipliers,
   fractions, glued and leading-dot numbers, year-shaped counts, numbers in
   labels, wrong units, a two-number quote, drifted values, coarse rounding, an
   edited spec, a forged repair marker - is a test that is refused.
2. The four recorded cases verify under the new rules (their wording updated
   where the old rules let a number through).
3. `tools/mutation_check.py` reproduces the guard and logic mutation counts for
   the consulting pack and renderer, and the commit message quotes its output.
4. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.

## Not in this slice

- Checking qualitative claims ("the customer base stayed the same size") or the
  direction of a change ("fell" against a rise). Those are judgement, read by a
  person; the fixture's unsupported phrasing is removed.
