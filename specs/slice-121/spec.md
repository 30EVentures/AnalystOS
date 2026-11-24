# Slice 121 - problem messages that say where (second paid test)

## Goal

The second paid test (owner's run, 2026-11-23, at most $0.28) failed with two
problems, down from forty: both in one assumption's rationale (the model
repeated the client's "doubled" and wrote a percent without a figure tag). Every
figure, quote and calculation passed. The repair request did not fix it because
the message said what was wrong but not where, and the prompt never said the
number rule covers rationales. Make every number problem quote the words and
the fix, and say so in the prompt. Nothing about what is accepted changes.

## What changes

1. `number_problems` quotes the offending words (about 40 characters each side)
   and the fix: digits ("define a figure and write its tag, or remove it"), a
   loose percent or currency ("use a figure tag, or remove it"), a quantity in
   words ("make it a figure and tag it, or rephrase without a quantity").
2. The prompt says the rule holds in every text field, including each
   assumption's rationale and the recommendation's rationale.

## Done when

1. The live failure, replayed, gets both problems with the words quoted, and the
   repair request carries them; a correct second answer then builds a deck.
2. No acceptance rule changes: full suite OK, refresh check clean, Flashy fence
   holds.
3. The next paid test is run only with the owner's yes and the maximum cost
   stated ($0.28).
