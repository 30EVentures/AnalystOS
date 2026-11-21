# Slice 102 - prepared live-API scripts, never executed

## Goal

Three ROADMAP items need a credential this session does not have (the join-grant
tokens must be re-minted) and are outward actions needing the owner's yes
regardless: declaring capabilities and offers, rotating the never-expiring agent
token, and producing decision records. Prepare what can honestly be prepared
without guessing at an unconfirmed API surface and presenting the guess as fact.

## Done when

1. `ops/flashy_declare.py` builds the exact, confirmed request (from Flashy's 21
   Nov reply) for `POST /api/v1/orgs/{orgId}/agents/{agentName}/capabilities`,
   defaults to printing it and stopping, and only sends it for real when
   `--execute` is passed - and even then needs a real token nobody has given it.
2. The token never appears in anything printed; `build_request()` only ever
   carries a redacted placeholder, proven by test.
3. The `offers` variant is clearly labelled as this script's own guess at the
   path (Flashy named the scope, `offers:declare`, never the exact endpoint) -
   the warning prints before the request is built, every time.
4. No test in this repository makes a real call to `api.flashyos.com`. The dry-run
   tests run the real CLI without `--execute`; the test proving `--execute`
   reaches the network-touching function does so with that function mocked,
   in-process, never over the network.
5. Token rotation and decision records get a written runbook (`ops/README.md`),
   not a script - there is no confirmed endpoint for either, and a confidently
   wrong request looks identical to a correct one until it runs.

## Not in this slice

- Running any of this against the live FlashyOS API, with any token, re-minted
  or otherwise. This slice prepares; running it is the owner's call, same as
  everything else gated behind `--execute` and a real credential.
- Guessing the token-rotation or decision-record endpoints. `ops/README.md` says
  exactly what to find out first and from whom.
- Deciding whether "decision records" belongs in AnalystOS's own API
  (`analystos/api_v1/store`'s existing audit log being the natural place) or
  somewhere else - flagged as a real open question, not resolved here.
