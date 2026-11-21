# Ops: prepared, not executed

Scripts and runbooks for the live-API steps in `ROADMAP.md`'s Blocked list that
need a credential this session does not have, and that are outward actions
needing the owner's explicit yes regardless. **Nothing here has been run against
`api.flashyos.com` or any other live endpoint.**

## `flashy_declare.py` - capability and offer declaration

Ready to run, once re-minted tokens exist (the ones Michael minted 2026-11-21 are
compromised - they travelled through a terminal log into a chat; ask for
replacements). Confirmed endpoint, from Flashy's 21 Nov reply:

    POST /api/v1/orgs/{orgId}/agents/{agentName}/capabilities
    header: x-join-grant: <token>
    body: {"capabilities": [...]}

```
python3 ops/flashy_declare.py capabilities analysis evidence verification \
    --org-id analystos --agent-name analystos-agent \
    --token "$FLASHY_JOIN_GRANT_TOKEN"        # prints the request, sends nothing

... --execute                                  # sends it for real
```

Defaults to a dry run: it always prints the exact request first, and refuses to
send anything unless `--execute` is also given. The token is never printed.

**The `offers` path is this script's own guess**, not a path Flashy confirmed -
they gave the scope name (`offers:declare`) but not the exact endpoint. The
script prints a warning every time `offers` is used and before it ever
constructs the real request; confirm the path with Flashy before passing
`--execute` on it.

## Token rotation and decision records - no script, because no confirmed endpoint

`ROADMAP.md`'s L3 criteria need `analystos-agent`'s never-expiring token rotated
(`revocable`) and gated actions to produce decision records (`auditable`).
Neither Flashy document gave an exact endpoint for either - only that the
register checks for them. Writing a script against a guessed path here would be
worse than not writing one: a confidently-wrong request looks the same as a
correct one until it runs.

**Before building these for real:**
1. Ask Flashy (or read `/api/v1/openapi.json` on the live hub, if reachable
   with a real token) for the exact token-rotation endpoint.
2. Confirm whether "decision records" are something AnalystOS's own API must
   start emitting (most likely - `analystos.api_v1.store`'s existing audit log is
   the natural place), or something FlashyOS's own side reads differently. If
   it's the former, this is product work in `analystos/api_v1/`, not an ops
   script - see `ROADMAP.md`.
3. Only then write a script matching `flashy_declare.py`'s shape: confirmed
   endpoint, redacted token in every printed request, a dry run by default, and
   tests that mock the one network-touching function rather than ever calling
   the real host.

## Testing discipline

`tests/test_flashy_declare.py` never calls `api.flashyos.com`. The dry-run tests
run the real CLI without `--execute`; the one test that proves `--execute` really
reaches the network-touching function does so in-process with that function
mocked out (`unittest.mock.patch`), never a real request. If a script is added
for token rotation or decision records, follow the same pattern - no test in
this repository should ever make a live call to a third party's API.
