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
point is that nothing - the site, `/api/v2`, a sales conversation - can claim a
role works before its own evaluation says so, because the status ladder is
enforced in code:

| status | means | requires |
|---|---|---|
| `planned` | listed, not built | no `eval`, no rate |
| `built` | the pack runs end to end | no rate |
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

The 73 roles fall into 13 families, each built on one shared skill. Waves are
the build order: 1 = deliverables on the existing verified-evidence engine;
2 = new skills, still deliverables; 3 = needs connectors into client tools and
approval gates; 4 = the decision must stay with a qualified human.

## Done when

1. `analystos/catalog/roles.json` lists exactly the 73 roles the owner gave,
   by title, each in one of 13 families, all `planned`.
2. `validate_catalog()` returns no problems for it, and returns a problem
   (never raises) for each of: wrong format; an empty catalog (no vacuous
   pass); a duplicate or malformed id; an unknown family, status, boundary,
   deliverable or wave; a `human-decides` role with no `human_decides`; a
   `planned`/`built` role with a rate; an `evaluated` role with no eval; an
   `available` role whose eval did not pass or whose rate is not a positive
   integer (a float or a boolean is refused); a family whose listed role count
   does not match.
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
