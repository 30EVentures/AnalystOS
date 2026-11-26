# Ops: prepared, not executed

Scripts and runbooks for the live-API steps in `ROADMAP.md`'s Blocked list that
need a credential this session does not have, and that are outward actions
needing the owner's explicit yes regardless. **Nothing here has been run against
`api.flashyos.com` or any other live endpoint.**

## `flashy_declare.py` - capability and offer declaration

A re-minted join grant arrived 2026-11-25 (scopes `capabilities:declare` and
`offers:declare`, expires 2026-12-25). It is kept outside this repository and
passed in through `FLASHY_JOIN_GRANT_TOKEN`; it cannot mint agents. Confirmed
endpoint, from Flashy's 21 Nov reply:

    POST /api/v1/orgs/{orgId}/agents/{agentName}/capabilities   one request per capability
    header: x-join-grant: <token>
    body: {"capability": "<slug>", "description": "<the answering role's purpose>"}

    POST /api/v1/orgs/{orgId}/offers                            the org's whole offer list
    body: {"offers": [...]}

Both shapes are read from the published `@flashyos/agent@0.21.0` client. The
21 Nov reply had described `{"capabilities": [...]}`; the first live call
(2026-11-26) answered 400 "capability and description are required" to it,
and nothing was written.

```
python3 ops/flashy_declare.py capabilities analysis evidence verification \
    --org-id cmtkurcbs00je12tigb1rc6t1 --agent-name analystos-agent \
    --token "$FLASHY_JOIN_GRANT_TOKEN"        # prints the request, sends nothing

... --execute                                  # sends it for real
```

Defaults to a dry run: it always prints the exact request first, and refuses to
send anything unless `--execute` is also given. The token is never printed.

Two guards run before anything is built (Slice 132, `ops/mesh_ids.py`), both
from Flashy's 2026-11-25 measurements:

- `--org-id` must be the organisation's id (`cmtkurcbs00je12tigb1rc6t1` for
  analystos), never the slug: a slug in the path answers 404.
- Every capability must already be in the served charter, as a role name or an
  `x-capability`, and be a lowercase hyphenated slug. A declared capability
  cannot be withdrawn yet, so a typo would be permanent. More than 20 offers is
  refused, because Flashy silently keeps only 20.

A refusal from the live route is explained: 401 invalid or expired grant, 403
wrong organisation or scope, 404 wrong path, 501 grants switched off.

Which capabilities to declare is still the owner's decision. `docs/mesh-identity.md`'s
rule is that a discovery slug is declared only once its endpoint is deployed
and smoke-tested. Do not use `npx @flashyos/agent declare`: it publishes every
role's bare verbs and drops array-valued `x-capability`.

**Offers are organisation-level** (`/orgs/{orgId}/offers`), not per agent, and one
call replaces the whole list; `--agent-name` is ignored for them.

## Token rotation - resolved, no script needed

Turned out not to need a script at all. `@flashyos/agent`'s own README is
explicit: agent names are unique per org, and **re-minting rotates** - running
`npx @flashyos/agent init` again with the same agent name replaces that agent's
token and the old one stops working immediately. There is a separate `revoke`
command for killing a leaked token outright (no un-revoke; re-mint instead).
Done for real 2026-11-22: `analystos-agent`'s original never-expiring token was
replaced this way.

## `flashy_decide.py` - decision records

Confirmed endpoint, read from `@flashyos/agent@0.21.0`'s own published source
(the npm tarball's `dist/chunk-*.mjs`, not the README's prose alone, and not
guessed):

    POST /api/v1/orgs/{orgId}/decisions
    body: {orgId, token, agentName, summary, impact}

`impact` is one of `LOW` (auto-approves), `MEDIUM`, `HIGH`, `CRITICAL` (the
package's own tier 1-4 mapping). This is the exact call `@flashyos/agent`'s
`requestApproval()`/`decide()` make; `flashy_decide.py` mirrors it in Python
so AnalystOS's own tooling can log a decision without depending on Node.

```
python3 ops/flashy_decide.py "deploy the seven-role charter" --tier 2 \
    --org-id cmtkurcbs00je12tigb1rc6t1 --agent-name analystos-agent \
    --token "$FLASHYOS_AGENT_TOKEN"        # prints the request, sends nothing

... --execute                                # sends it for real
```

Defaults to a dry run, same shape as `flashy_declare.py`: always prints the
exact request first, needs `--execute` to send anything, never prints the
token in full.

**This only records; it does not block.** Straight from the package's own
docs: v1 is visibility and an audit trail, not enforcement - nothing here
stops AnalystOS's own code from doing the thing being logged. Calling this for
any specific real action remains a separate, per-use outward decision under
CLAUDE.md's own rule, regardless of how confirmed the endpoint now is. Nothing
in this repository calls it automatically.

## Testing discipline

Neither `tests/test_flashy_declare.py` nor `tests/test_flashy_decide.py` ever
calls `api.flashyos.com`. The dry-run tests run the real CLI without
`--execute`; the one test that proves `--execute` really reaches the
network-touching function does so in-process with that function mocked out
(`unittest.mock.patch`), never a real request. Any future script here follows
the same pattern - no test in this repository should ever make a live call to
a third party's API.
