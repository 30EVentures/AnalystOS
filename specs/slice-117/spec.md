# Slice 117 - every role on the verified pipeline, each family with a worked example

## Goal

Owner's direction, 2026-11-23: the website and the product carry **all 73
roles by the end of the day**; Management Consulting Analyst gets one paid
real-model test (only with the owner's yes right before it, after being told
the exact maximum cost); every other role is proven with worked examples
written and tested in the working session, with no paid calls. Price: open for
to be determined: no price has been set for any role (owner, 2026-11-23; first
recorded as "open for negotiation", changed the same day).

## What changes

1. **One pipeline, every role.** `analystos/packs/consulting.py`'s verified
   pipeline (answer first, an issue tree of hypotheses, traced figures, options,
   one recommendation, a 30/60/90 plan, KPIs, risks) becomes the shared skill.
   Each role adds a short brief and each family a method brief
   (`analystos/packs/briefs.json`), so a Fraud Analyst and a Pricing Analyst
   reason differently but are held to the same number rules. Every rule from
   Slice 115 applies unchanged to every role.
2. **Boundaries shape the output.** A `human-decides` role is told to prepare
   the decision, not make it, and its deck says "For your decision" where an
   advisory deck says "We recommend", and names the decisions that stay human.
   An `approval-gated` role's actions are drafts for a named approver.
3. **Honest about the deliverable.** Every role today produces this verified
   deck. Native work products (code for a developer, copy for a writer, a
   reconciliation for a bookkeeper) are not built yet, and the catalog says so
   per role.
4. **The catalog.** An `eval` record gains `method` (`mock` or `live`) so a
   role tested only on a worked example in the session can never be shown as
   live-tested. Pricing may be `"tbd"` instead of a fixed rate (the
   owner's decision): `available` then needs a passed eval and either a positive
   integer rate or `"tbd"`. All 73 roles become `available` with a
   mock eval pointing at their family's worked example.
5. **Worked examples.** One synthetic case per family (13), each a client's
   problem and answers plus the role's recorded response, verified by the real
   verifier and rendered by the real renderer in tests. The consulting family
   keeps its four cases (churn, bakery margin, fulfilment, subscription).

## Done when

1. Every role id in the catalog has a brief, every family a method brief; a
   test fails on a missing or empty one.
2. `build_deck_spec` works for any catalog role (one per engagement for now),
   puts the role and family briefs and the boundary rule in the system prompt,
   and the deck shows the role's title and the right recommendation framing.
3. Each of the 16 worked examples verifies with no problems and renders; the
   no-new-numbers check holds on every one.
4. The catalog validator accepts `method` and `"tbd"` pricing and still
   refuses `available` without a passed eval; the 73 roles validate.
5. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.

## Not in this slice

- The website (Slice 118), any paid call, billing, native deliverables.
