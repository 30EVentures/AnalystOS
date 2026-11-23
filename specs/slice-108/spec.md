# Slice 108 - the role catalog: 73 entry-level jobs, every one honestly "planned"

## Goal

Owner's decision, 2026-11-23: AnalystOS becomes a one-stop shop for
entry-level white-collar work - reporting, consulting and 71 other roles the
owner listed - hireable by people and by agents, billed in engagement hours.
Each role is a configuration of a shared engine plus its own evaluation set,
not a separate product.

Before any role is built, this slice writes down the whole catalog as data a
machine can read and a test can hold to account: `analystos/catalog/roles.json`
(format `analystos-role-catalog/1`), validated by
`analystos/catalog/validate.py`. Every role starts at status `planned`. The
catalog itself cannot mark a role for hire without a recorded passing
evaluation and an integer rate, because the status ladder is enforced in code.
What that does not yet prove: nothing reads the catalog yet (serving it, and
making the site and `/api/v2` read from it rather than restate it, comes with
the front door), and an `eval` record is a claim, not evidence, until each
evaluation run is sealed and checkable (roadmap Phase 4).

| status | means | requires |
|---|---|---|
| `planned` | listed, not built | no `eval`, no rate |
| `built` | the pack runs end to end | no `eval`, no rate |
| `evaluated` | its eval set has been run | an `eval` record (pass or fail) |
| `available` | for hire | an `eval` record with `passed: true`, and an integer rate |

Rates are integer US cents per engagement hour (`rate_cents_per_engagement_hour`),
never floats. An engagement hour is a fixed, published budget of agent work
(decided 2026-11-23); its exact size is Slice 12x's to define, so no role
carries a rate yet.

Each role also states its **boundary** - what it may do at full capability:

- `deliverable-only`: produces work product (a brief, deck, workbook, memo,
  report, code, a draft); acts on nothing.
- `approval-gated`: may act in the client's own tools (post, send, schedule,
  book an entry), but only after a named human approves each action.
- `human-decides`: prepares the full case; a qualified, named human makes the
  call. The role lists exactly which decisions stay human (`human_decides`).

## Families and waves

The 73 roles fall into 13 families, each built on one shared skill; a family's
`wave` is the earliest wave of its roles. Waves are defined by what blocks the
build, and the validator holds the data to them:

1. buildable on the existing verified-evidence engine (a role may still leave
   decisions to a human: credit, model validation, actuarial, equity research);
2. needs a new skill, output is still work product;
3. acts in the client's own tools, so needs connectors and per-action approval
   gates - wave 3 is exactly the `approval-gated` roles;
4. the role's core output is a regulated decision, filing or disposition, so it
   needs a review of the applicable rules and a decision-recording workflow
   first - every wave-4 role is `human-decides`.

`human-decides` therefore appears in waves 1, 2 and 4: the boundary says who
decides, the wave says what blocks the build.

## Done when

1. `analystos/catalog/roles.json` lists exactly the 73 roles the owner gave,
   by title, each in one of 13 families, all `planned`.
2. `validate_catalog()` returns no problems for it, and returns a problem
   (never raises) for each of: wrong format; an empty catalog (no vacuous
   pass); a duplicate or malformed id; an unknown family, status, boundary,
   deliverable or wave; a `human-decides` role with no `human_decides`; a
   `planned`/`built` role with a rate; an `evaluated` role with no eval; an
   `available` role whose eval did not pass or whose rate is not a positive
   integer no larger than 2**53 - 1 (a float, a string or a boolean is
   refused); an eval with unknown fields or a non-boolean `passed`; a family
   whose listed role count or wave does not match its roles; a wave that
   contradicts the boundary rules above; duplicate JSON keys on load. Every
   guarded rule has a test that fails when the rule is removed.
3. `python3 -m analystos.catalog` prints a per-wave summary and exits 0, or
   prints problems and exits 1.
4. ROADMAP.md carries the rebuild plan; `docs/decisions.md` records the
   one-stop-shop decision.
5. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.

## Not in this slice

- Building any role, the engagement intake (Slice 109) or any renderer.
- Serving the catalog. `/api/v2` comes with the front door; the file is shaped
  so serving it is a read, not a rewrite.
- The size of an engagement hour and any rate.
- Anything on the FlashyOS mesh. These roles are not the charter's seven team
  roles, and declaring them anywhere is a separate decision for the owner.
