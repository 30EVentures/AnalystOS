# Slice 104 - prepared, not executed: decision records on FlashyOS's governance feed

## Goal

ROADMAP.md's Level 3 item names token rotation and decision records as "entirely
ours" but says neither has a confirmed endpoint in anything available to this
session. Token rotation turned out not to need a script at all - re-minting an
agent (`npx @flashyos/agent init` with the same name) rotates it, done for real
2026-11-22. Decision records do need one: `@flashyos/agent@0.21.0`'s own
published source (`dist/chunk-NL5JM7HU.mjs`, read from the npm tarball, not
guessed) confirms `POST /api/v1/orgs/{orgId}/decisions`, body
`{orgId, token, agentName, summary, impact}`, response `{decision: {id, status}}`.
`status` is one of `AUTO_APPROVED` (LOW impact), `PENDING` (MEDIUM+, waits for a
human with OWNER/ADMIN on the org), `APPROVED`, `REJECTED`.

Their own docs are explicit that this **records, it does not block**: v1 is a
visibility/audit trail, not enforcement. Nothing here is a hard gate on
anything; it is a log entry on FlashyOS's side for an action AnalystOS's human
operator already decided or is deciding.

## Done when

1. `ops/flashy_decide.py` builds the exact request `@flashyos/agent@0.21.0`
   itself sends - same body shape, same endpoint, same tier-to-impact mapping
   (1 LOW, 2 MEDIUM, 3 HIGH, 4 CRITICAL) - confirmed against their source, not
   invented from the README's prose alone.
2. Defaults to a dry run, same as `ops/flashy_declare.py` (Slice 102): always
   prints the exact request first, needs `--execute` to send anything. The
   token is never printed in full.
3. `send_request()` is the only function that touches the network; no test in
   this repository calls it for real. `--execute`'s path to `send_request()`
   is proven with that function mocked, in-process.
4. Response parsing matches the SDK's own `STATUS_TO_STATE` mapping exactly
   (`AUTO_APPROVED` -> `auto`, `PENDING` -> `pending`, `APPROVED`/`REJECTED`
   -> `reviewed`), so a caller reading this script's output gets the same
   three states the SDK's `requestApproval()` would have returned.
5. `docs/decisions.md` and `ROADMAP.md` record that this is confirmed, prepared
   software, and that actually calling it (`--execute`) for any specific
   AnalystOS action remains a separate, per-use outward decision - this slice
   does not wire it into any of AnalystOS's own code paths, and does not call
   it automatically on a deploy, publish, or any other gated action.

## Not in this slice

- Enforcement. The upstream package's own docs say enforcement is still on
  their roadmap (their `docs/roadmap.md` Phase 2.75); building a hard gate on
  top of a `pending` response is a different, later decision, not assumed here.
- Calling this for real against any specific AnalystOS action. That is an
  outward action under CLAUDE.md's own rule regardless of how confirmed the
  endpoint is, and needs the owner's yes each time, not a standing one.
- The `--owner` field's exact meaning on Flashy's side (who it notifies, how
  it is matched to an org member) - passed through verbatim, not interpreted.
