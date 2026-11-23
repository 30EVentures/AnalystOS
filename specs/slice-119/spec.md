# Slice 119 - survive the live model's natural writing (first paid test failed)

## Goal

The first paid test (owner's consent, 2026-11-23; at most about $0.21) failed:
the live model's content failed verification twice (40 problems), so nothing
was delivered. The visible problems were quotes holding two numbers ("went from
4% to 7%") and an unexpected field on a figure; the rest were cut off by the
API's 300-character error. The worked examples had all been written knowing the
rules; the live model writes the natural way. The owner: fix it so the next
test runs, and stop wasting money.

## What changes

1. **A deterministic normaliser runs before verification**, fixing only slips
   that cannot change what a reader is told, and leaving everything else to the
   unchanged verifier:
   - a written number directly before a tag that states that tag's figure (at
     the precision shown, within 5%, right kind) is removed, and a matching unit
     or currency beside a tag is removed: code prints the verified value;
   - a client quote holding several numbers is narrowed, verbatim, to the part
     holding the one number equal to the figure's value (as given, or as a
     percent or scaled value), so the quote stays the client's exact words;
   - a client figure's value and unit are taken from its quote; a computed
     figure's value is recomputed and its unit derived (a ratio declared as a
     percent becomes percent_of_total);
   - fields that are never shown (unexpected keys) are dropped; unused figures
     that are not inputs are dropped; numeric strings become numbers;
   - "30/60/90 days" and similar become words ("a month", "three months").
   Bare integers 0-12 with no unit are allowed in prose like the words one to
   twelve; years 2020-2035 after a time word are allowed.
2. **The prompt shows a short correct example** (figures, tags, a chart) and the
   common mistakes.
3. **The full problem list** is returned by `/api/v2/engagements` on a 502 and
   shown on the hire page, so a failure is diagnosable.
4. **A free stand-in for the live model:** every one of the 16 worked examples
   is rewritten the way a model naturally writes (numbers before tags, full
   two-number sentences as quotes, wrong units, drifted computed values, extra
   fields, unused figures, "within 90 days") and must pass after normalising,
   render, and pass the independent no-new-numbers check.

5. **The release review of PR #99** (merged before the review finished) failed
   it on two gaps in "every number traced", fixed here:
   - B1: a quote's number must be the whole number the client wrote at that
     spot (same span, value and kind), so "$12.2" cannot be quoted out of
     "$12.2 million", nor "12" out of "12.5%";
   - B2: a year from the client's text is allowed only after a time word or in a
     year range, never anywhere ("we lose 2019 clinics" is refused); every tag
     needs a space or punctuation on both sides ("2019[F5]", "l[F5]" refused).
   And its not-blockers: a currency symbol of any kind, more unit and scale
   words (mn, lakh, crore, grand, CAD, ...), Latin-lookalike letters and
   fullwidth signs beside a tag, and a number word before a tag are refused; the
   sources slides show the exact value wherever the deck rounds, so every
   calculation can be redone by hand; a nonzero value is never written as 0; an
   assumption's rationale shows values, not raw tags; a chart with a negative
   bar is drawn below zero; the 60 roles checked only on another role's worked
   example say so (`eval.method` "mock-family"); decisions entries for Slices
   117 and 118 corrected.

## Done when

1. All 16 natural-style variants pass end to end with no paid call.
   Each case in item 5 has a test that fails without the fix.

## Results (2026-11-23)

- Full suite OK; `tools/refresh.py --check` clean; Flashy fence holds.
- Every item-5 fix: its tests fail on the pre-fix `consulting.py` and `deck.py`.
- Mutation check: `normalize.py` 6/6 guards, 9/9 semantic; `deck.py` 5/5
  guards, 11/11 semantic; `consulting.py` full run 80/81 guards and 22/27
  semantic, where three semantic entries no longer matched the rewritten tag
  and year code and one guard (one-number check in `quote_number_is_whole`) was
  unexercised - all four fixed, then a targeted run of those plus six new
  mutants for this slice's rules: 10/10 caught or equivalent (three equivalent
  mutants in all, each with its reason in `tools/mutants/consulting.json`).
2. Every existing refusal test still passes: normalising never makes a wrong
   number acceptable (a written number that does not state its figure is still
   refused; a quote not in the client's words is still refused).
3. The full suite is `OK`, `tools/refresh.py --check` is clean,
   `tools/flashy_freeze.py --check` holds, and the mutation check passes.
4. The next paid test is run only with the owner's yes right before it and the
   exact maximum cost stated.
