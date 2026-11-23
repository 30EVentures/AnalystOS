# Slice 112 - the consulting skill: a scoped engagement in, a verified deck spec out

## Goal

Owner's decision, 2026-11-23: take one role all the way through first -
**Management Consulting Analyst** - in days, not months, and prove it with
mocks in the working session instead of paying for a model call on every try;
then wire the proven pipeline into the website.

This slice is the pipeline's core. An accepted engagement (Slice 109/110) goes
in; one model call (at most one repair retry) proposes the consulting content;
**code verifies every part of it**; the output is an `analystos-deck-spec/1`
document - the full storyline, slide by slide, with every number traced -
ready for the renderer (Slice 113).

The model never writes slides directly. It writes structured content (answer
first, situation and complication, an issue tree of hypotheses, figures,
options, a recommendation, a 30/60/90 roadmap, KPIs, risks); code assembles the
slides in a fixed consulting storyline. That keeps the deck's shape out of the
model's hands and every rule below checkable.

## The rules code enforces (the reason this is not "ChatGPT makes slides")

1. **Every figure has a basis.** `client`: its `quote` must be found verbatim
   in the client's own words (problem and answers) and must spell out its
   value (the existing L2 quote and value matchers). `computed`: its operation
   is one of L2's known operations over earlier figures and recomputes to its
   value (the existing L2 recomputation). `assumption`: allowed, but it must
   give a rationale, and the deck labels it as an assumption wherever it is
   used.
2. **No untagged numbers.** Every number in any sentence the model writes must
   be followed in that sentence by a `[F#]` tag naming a figure whose value it
   matches at the precision shown (`7%` matches 7.0 or 6.96, not 6.9). Bare
   years and labels like "Q3" are exempt; durations are written in words.
3. **Structure.** 2-5 issue-tree branches, each with an action-title finding
   and 1-4 hypotheses marked supported, refuted or untested; 2-4 distinct
   options; the recommendation names one of them; exactly three roadmap
   horizons; 2-6 KPIs and 2-6 risks. Every title is a sentence that states its
   point (4-20 words).
4. **Evidence mix is shown, not hidden.** The spec counts client, computed and
   assumption figures and the deck's sources slide lists every one.

On a failed check the model gets the problem list once and may repair; a
second failure is an error (no partial deck). Client text reaches the prompt
only through `analystos/l2/prompt_safety.neutralize` between explicit markers.
All calls go through the existing `_create_message` choke point, so the
`ANALYSTOS_MAX_API_CALLS` spend ceiling applies.

## Mocks instead of spend

`analystos/packs/replay.py` provides `ReplayClient`: a stand-in with the same
`messages.create` shape that returns recorded responses and records every
request. Recorded responses live in `fixtures/consulting/<case>/`, written in
the working session; tests and the in-chat evaluation run on them for free.
**What mocks prove**: the pipeline, the verifier and the rendering. **What they
do not prove**: that the production model writes content this good. That needs
a small number of live runs before the role is marked `evaluated` (Slice 114).

## Done when

1. `analystos/packs/consulting.py`: `build_deck_spec(engagement, catalog,
   client=None)` refuses an engagement that is not `accepted` or whose roles do
   not include a consulting-family role, and otherwise returns a valid
   `analystos-deck-spec/1` or raises `ValueError` naming what failed.
2. `verify_content()` returns a problem (never raises) for each rule above:
   a client quote not in the client's text, a quote that does not spell its
   value, a computed figure that does not recompute, an unknown operation or a
   forward reference, an assumption with no rationale, an untagged number, a
   tag naming an unknown figure or a figure whose value the number does not
   match, a recommendation naming no option, wrong counts, and non-sentence
   titles.
3. One recorded case (a churn problem) produces a deck spec end to end through
   `ReplayClient`; a recorded bad-then-good pair proves the single repair
   retry; two bad responses raise.
4. The prompt carries the client's text only inside markers, neutralised.
5. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.

## Not in this slice

- Rendering the deck (Slice 113), the evaluation set and the in-chat runs
  (Slice 114), the website (Slice 115).
- Client documents beyond the problem and answers (uploads come later through
  the existing L1 ingest).
- Changing the catalog: the role stays `planned` until it is built and
  evaluated.
