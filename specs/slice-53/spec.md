# Slice 53 — root cause: a fake, non-numeric placeholder

## Goal

Diagnose and fix the actual reason Test #4/#8 fell back to the flat
renderer (tracked as outstanding since Slice 52, deliberately not
excused by that slice's own new floor). Found via a real, captured live
run against the actual source document:

```
[analystos.l2.narrate] narrative rejected (outlook paragraph has a
digit outside any {{N}} placeholder: 'Integration and purchase-
accounting costs tied to the Halyard acquisition are projected to
decline to approximately {{5.0M}} in Q4 2026, down from the {{22}}
peak in Q3 2026.') - retrying (attempt 1 of 2)
```

The model wrote `{{5.0M}}` - not a real `{{N}}` manifest index, a
literal value dressed up to look like one, for a real, source-stated
figure ("...projected to decline to approximately $5.0 million in the
fourth quarter of 2026") that simply had no verified segment behind it
to cite. `_PLACEHOLDER_RE` (`\{\{(\d+)\}\}`) correctly never matches
`{{5.0M}}`, so its digits are correctly flagged as "outside any
placeholder" - the *existing* check is not wrong. But the message it
produces is generic, and 3 single-paragraph repair attempts plus 2 full
retries all failed to fix it - because nothing tells the repair model
(or the original writer) *specifically* that it invented a fake
placeholder instead of citing a real fact or dropping the number, so
every attempt just produced a new variation of the same mistake.

This is a genuinely different failure class from Slice 38's bugs 1-4
(a fabricated-looking placeholder, not a wrong direction word or an
overclaimed streak) - not previously named or specifically guarded
against.

## Included

- A new deterministic check, `_fake_placeholder_problem(text)` in
  `analystos/l2/narrate.py`: any `{{...}}` whose contents are *not*
  purely digits (e.g. `{{5.0M}}`, `{{$5.0 million}}`, `{{N}}` literally)
  is caught with a specific, actionable reason - distinct from the
  generic digit-outside-placeholder message, and wired into
  `_validate_paragraph` before that generic check runs (so this failure
  gets its own clear diagnosis, not just an incidental catch by a
  different rule).
- `_SYSTEM_PROMPT` (the writer) gains an explicit, blunt rule: a
  placeholder is *only* ever a bare integer referencing a real manifest
  fact index - never a value, a unit, or anything else inside `{{}}`.
  If a number can't be cited via a real index, it must be omitted or
  described qualitatively, never approximated inside fake braces.
- `_REPAIR_SYSTEM_PROMPT`'s existing "if there isn't one, drop the
  specific figure" guidance is generalized: today it's scoped narrowly
  to a digit that came from an *event's* date/status/next_step text.
  The real failure here was an ordinary missing quote/computed fact
  (a projected figure that was never extracted as its own segment) -
  the same "drop it or describe qualitatively" instruction, stated so
  it applies whenever *any* number has no matching manifest fact, not
  only the event-specific case.

## Not in this slice

- Making extraction (`analyze_document`) guarantee it never misses a
  real number in the source text - not achievable with certainty for
  an LLM-driven extraction step, and not the actual point of failure
  here (the number's absence from the manifest is a normal, expected
  possibility this system must already tolerate everywhere else -
  Gate 1's whole job is refusing to let an uncited number through, not
  guaranteeing every real number gets extracted).

## Done when

1. `_fake_placeholder_problem` is proven directly: `{{5.0M}}` and
   similar non-integer placeholders are caught with a specific reason;
   a real `{{22}}` is never flagged.
2. Wired into `_validate_paragraph`/`_locate_problem` - a report
   containing a fake placeholder is rejected with the new, specific
   reason, not the old generic one.
3. `python3 -m unittest discover -s tests -v` passes.
4. Confirmed against the real document behind Test #4/#8/#9's
   original failure - via a mocked reproduction of the exact captured
   failure text (not a second live API call, per the explicit
   requirement not to need another live run to confirm this fix).

## Built (post-implementation note)

- `_fake_placeholder_problem(text)` added to `analystos/l2/narrate.py`,
  wired first in `_validate_paragraph` (before the generic digit-outside
  check, so this failure always gets its own specific reason).
- `_SYSTEM_PROMPT` (the writer) and `_REPAIR_SYSTEM_PROMPT` (the single-
  paragraph repair pass) both gained the explicit rule: `{{N}}` is
  always a bare manifest index, never a value/unit inside the braces;
  a number with no matching fact must be dropped or described
  qualitatively, never approximated. The repair prompt's prior
  "event digit" guidance was generalized to any missing fact, not only
  one from an event's date/status/next_step text.
- `tests/test_l2_narrate.py::FakePlaceholderGateTest` (6 tests) -
  including a direct reproduction of the exact captured live failure
  text (`test_the_exact_captured_live_failure_is_caught_with_a_specific_reason`),
  proving this exact real-world case is now caught with a specific,
  actionable reason instead of the old generic one - no second live API
  call needed to confirm the fix, per the explicit requirement.
- Full suite: 498/498 passing.
