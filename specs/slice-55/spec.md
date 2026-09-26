# Slice 55 - Gate 1 checks the relationships between numbers, not only the numbers

## Goal

`docs/audit-2026-09-25.md` findings 1 and 2. Gate 1 proves every *figure*
(a quote is a substring of the source; a calculation is recomputed) but not
the *sentence that joins figures*, and its "the writer cannot type a number"
rule only covers digits.

1. **Endpoint mismatch.** A real run (Orion, `jobs/orion/section.html`) passed
   both gates with "Gross margin moved (4.7%) points to 54.2% from 55.8%".
   The 4.7 is a correct four-quarter change (58.9 -> 54.2); 54.2 and 55.8 are
   correct quotes; but 55.8 -> 54.2 is 1.6 points. When a sentence cites a
   two-operand change fact (`growth_percent` or `difference`) and also names
   its endpoints ("from {{i}}", "from {{i}} to {{j}}", or a moved-to
   "... to {{j}}"), every named endpoint must equal one of that fact's own
   verified operands. Otherwise the paragraph is rejected with a reason the
   repair call can act on.
2. **Number words.** "grew twenty percent", "roughly doubled", "about
   two-thirds", "by nearly a third" all passed because only digits were
   checked. Spelled-out quantities outside a placeholder are now rejected:
   number word + percent/points/currency/scale word, fraction words
   ("two-thirds", "a third of"), multipliers ("doubled", "twofold",
   "double-digit"), and "twice/thrice".

## Included

- `_endpoint_problem(text, segments)` and `_number_word_problem(text)` in
  `analystos/l2/narrate.py`, both called from `_validate_paragraph`.
- Tests in `tests/test_l2_narrate.py`.
- A `docs/decisions.md` entry.

## Not in this slice

- Endpoints named without "from"/"to" wording ("between {{i}} and {{j}}",
  "versus") - not guessed at; a future, separately-diagnosed fix.
- Change facts with more than two operands, and `remainder`/`percent_of_total`.
- Number words inside verified prose segments or KPI/chart labels.
- Anything in the zero-model deterministic tier (its sentences are built from
  a change fact's own operands, so the mismatch cannot arise there).

## Done when

1. The exact Orion sentence shape is rejected, with a reason naming the
   mismatched fact.
2. The same sentence with endpoints that match the change fact's operands
   (either operand order) is accepted, as are "from {{a}} to {{b}}" and a
   sentence with a plain "compared to {{x}}".
3. Each of the four audit bypass sentences is rejected.
4. Ordinary prose that merely contains "one", "half", "the first half",
   "three quarters" (a period count) or "double" as a verb of other meaning is
   accepted.
5. The full suite still reports OK.
