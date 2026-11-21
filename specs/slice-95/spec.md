# Slice 95 - draft and validate the seven-role team charter

## Goal

Flashy's 18/21 Nov integration documents validated a seven-role "team" charter
(coordination, research, analysis, verification, synthesis, evidence,
client-delivery) for AnalystOS and argued that the chartered organisation, not any
individual agent, is what an enterprise can engage. Draft it here, check it for real,
and make the decision to go live a single, informed, owner-made step rather than
something a loop does on its own - the two reasons this must not become the live
charter without that decision are in `drafts/README.md`.

## Done when

1. `drafts/flashyos-charter.team.json` exists, outside `site/` so it can never be
   served by an ordinary deploy (checked by `DraftLocationTest`).
2. It passes the real `@flashyos/aao` validator with zero errors and all five static
   `runStaticConformance` checks.
3. `auditProperty`, run with every role name and discovery slug declared (the state it
   would need to be served in, not today's state), returns level 2 with zero issues.
4. The three roles already live (`analysis`, `verification`, `evidence`) keep the same
   family and human-approval gate in the draft as in `site/.well-known/flashyos-charter.json`
   - a silent change to an already-published governance fact would be worse than
   adding new ones.
5. `drafts/README.md` states plainly why this is not switched on, and exactly what
   switching it on would need (six more live agents, a re-minted join-grant token,
   endpoints for four roles that do not exist yet).

## Not in this slice

- Minting any agent, raising a tier, or calling `api.flashyos.com` at all.
- Deciding whether to switch. That decision is explicitly left to the owner,
  recorded in `ROADMAP.md`'s Blocked list.
- Building the coordination, research, synthesis or client-delivery endpoints
  this charter's new roles would need before any of their discovery slugs could
  honestly be declared.
