# Slice 120 - close the release review of PR #100 before the second paid test

## Goal

The fresh-context release review of PR #100 (Slice 119) failed it, after the
owner had merged it: the normaliser could make a wrong deck pass verification,
the opposite of what Slice 119 claimed ("fixes only slips that cannot change
what a reader is told"). Close every blocker before the second paid test, and
cover the live-model slips the review predicted, so that money is not spent on
a run that fails or, worse, on a deck that misleads.

## What changes

1. The normaliser may no longer change a number the verifier would refuse:
   - a computed value that is present is never recomputed (only a missing one
     is filled), so reversed or wrong inputs are refused again;
   - quote narrowing matches only in the figure's own unit (x100 only for a
     percent written as a fraction, x1e3-1e9 only when the quote has a scale
     word), never overrides the declared unit, and refuses when a word quantity
     comes before the number ("a third of our 420");
   - "90 days" is no longer rewritten anywhere.
2. Bare digits 0-12 in prose are numbers again (Slice 119 allowed them; "We
   have 1 [F5] customers" and "from 3 to [F2]" passed).
3. Scale words in any case ("Million", "MM", "mn", "crore") are part of the
   number, so "$12.2" cannot be quoted out of "$12.2 Million"; a quote cannot
   cut a grouped number ("12 200"), drop a detached sign ("- 4%") or a currency
   other than the dollar ("EUR12.2 million" written with the euro sign).
4. Years: a year followed by a plural noun is a count ("by 2030 customers");
   more time words are allowed ("end of 2026", "mid-2026", "March 2025"). Tags
   glued to tags ("[F2][F5]", "[F2].[F5]") are refused.
5. Live-model slips the review predicted: unknown fields are dropped at every
   depth (the first live failure was an extra field); "Option A: X" is matched
   to the option named X; "[F2] (7%)" loses the parenthetical when it restates
   the figure; the prompt lists the rest (digits for small counts and days,
   dates, numbers beside tags, a fall as a negative figure, digits in labels).
6. Wording: the catalog API defines "mock-family"; the hire page no longer says
   each role names its worked example; Slice 119's claims are corrected in the
   decisions log.

## Done when

1. Every blocker case from the review is a test that is refused (or, for
   "$12.2 Million", read correctly as 12.2 million), and fails on main.
2. A slip the normaliser now leaves alone (a drifted value, "90 days") is
   refused on the first attempt and fixed on the second: a deck is delivered.
3. The 48 natural-writing variants still build in one attempt and render.
4. Full suite OK; `tools/refresh.py --check` clean; Flashy fence holds; the
   mutation check covers the new rules; a fresh review passes before the PR.
5. Left open, stated: an accounting-style "(4%)" quote is read as +4%; a
   two-number contrast can be narrowed to the wrong one (as on main).

## Second review (same day)

The fresh review of the first Slice 120 commit (e11ec07) failed it: a quote
could still be cut across a quantity written in digits ("About 40% of our 850
customers" became "of our 850 customers"); "$12.2-million" and "$12.2 millions"
still became $12.20; and "of" taken as a time word let "A loss of 2031 each
month" pass. Fixed: a quote is never cut where the number before may change the
kept one (followed by "of", a multiple, or a quantity in words) unless
punctuation or "and"/"to"/"but" separates them; hyphenated, plural and short
scale words ("-million", "millions", "mil") are part of the number; "of" marks
a year only as "end/start/beginning/middle of". Also: a computed value is never
filled (a missing value with a wrong input passed); "Option A: X" is matched
only by exact name after a label (it inverted "Do not X"); "%"/"USD" unit
aliases are read, never replaced by the quote's kind; "Phase 1", "Tier 2" and
similar names are allowed; "in/since/during 2025" is a year even before a
plural noun. Each is a test in tests/test_normalize.py (SecondReviewTest).

## Third review (same day)

The quick review of 249ae08 failed it: the cut rule, a list of dangerous words
checked only right after the first number, still cut "340 out of our 850" and
"3 times the $1,200"; and allowing "Tier 1" let "Tier 1 [F5] customers" (read
as 1,850) through. Now a cut needs an explicit break whose following words do
not tie the numbers, or plain words with no linking word or sign anywhere
between the numbers; a numbered name is allowed only before punctuation or a
joining word. Every case from that review's bypass script is refused except
true excerpts ("Up 40% to 850 customers") and the open after-the-number case.

## Fourth review (same day): quote cutting removed

The quick review of d77fdf0 failed it again on the same step: a cut quote could
still mislead ("a 25% discount to the $1,200 list price" cut to "discount to the
$1,200 list price"; "$1,200 every 3 months" cut to "$1,200 every"), some of it
already possible on main. Four reviews each found a phrasing past the latest cut
rule, so code no longer cuts a quote at all: a quote with two numbers is refused
with guidance ("quote only the client's words around that one number") that the
repair request carries to the model. The cost: when the live model quotes whole
two-number sentences, as in the first paid test, the run needs its second call.
Open, judged not realistic enough to block: "Tier 1, [F5] customers" and
"Plan 3 of the hires" pass with a numbered name before punctuation or "of".

## Results (2026-11-23)

- Every blocker case from the review: a regression test that fails on main
  (30 subtests across 8 tests) and passes here; the reviewer's own reproduction
  scripts now refuse each case (or, for "$12.2 Million", read it as 12.2 million).
- Mutation check: `normalize.py` 8/8 guards, 19/19 semantic; `numbers.py` 2/2
  guards; `consulting.py` targeted run over every rule added or changed in Slices
  119-120: all caught except one recorded equivalent (the same-span check), after
  five survivors in the first pass were closed with tests.
- Full suite OK; refresh check clean; Flashy fence holds (the regenerated
  `drafts/measures.json` is left out, as in Slice 119).
- After the second review: a targeted mutation run over every rule it changed
  (normaliser cut rule, option matching, unit aliases; year and label rules;
  hyphenated and plural scale words): 12/12 caught, after two survivors were
  closed with tests.
- After the third review: targeted mutation over the new cut rule and the
  numbered-name rule, all caught after two survivors were closed with tests.
