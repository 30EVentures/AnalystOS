# Slice 59 - AnalystOS publishes who it is (mesh identity files)

## Goal

R1 mesh steps 2-3 (`ROADMAP.md`; `docs/flashyos-alignment-2026-09-25.md`):
serve the two files FlashyOS's Level 1 and Level 2 conformance read.

- `site/.well-known/flashyos.json` - the `flashyos/1` handshake: `mesh`,
  `org{slug,name,profile}`. **No `capabilities`**: a capability is a claim that
  something is callable, and nothing is until Slice 61 is deployed and a token
  exists. No `api`, `join` or `wants` URL either - not needed to be discovered,
  and each would be one more claim to keep true.
- `site/.well-known/flashyos-charter.json` - an AAO 0.1 charter for slug
  `analystos` with three standing roles (`analysis`, `verification`,
  `evidence`), each with a `measure` that the audit log (Slice 61) can compute
  from what it records. `site/flashyos.roles.json` is an identical copy for the
  legacy path some estates serve (a test keeps them identical).
- `vercel.json` headers: JSON content type, `Access-Control-Allow-Origin: *`
  and a short cache for those paths.
- `docs/mesh-identity.md`: what is served, what is deliberately not, how to
  validate it (our checker and FlashyOS's), and the decisions still open.

## Deliberately not served (and why)

- `frontdoor.json` - a `frontdoor/1` document requires a working `endpoint`
  and a person who reads what arrives there. Neither exists.
- `directory.fragment.json` - a `directory/1` fragment asserts people and
  relationships on someone's authority; that is the owner's call.
- `canon.json`, `backlog.json` - later, once there is something to pin/publish.

## Not done here, and needs the owner

- **Nothing is deployed by this slice.** The files are in the repository; they
  go live only when the branch is merged and Vercel redeploys.
- **The `analystos` org already exists on the FlashyOS network with an unknown
  owner.** Serving a handshake for slug `analystos` before that is resolved
  would read as a claim to it. Merge only after the owner question is settled.
- `accountableTo` is the address already public on the homepage
  (`30eventures@gmail.com`); change it if a different reachable human should be
  accountable.
- Running the official `npx @flashyos/conformance analystos.dev --level 2`
  (needs deployment and permission to run the npm package).

## Done when

1. The charter passes `analystos.aao` with no errors and no warnings.
2. Both charter paths serve byte-identical content.
3. The handshake matches the documented `flashyos/1` shape and its slug equals
   the charter's slug.
4. `vercel.json` sets the JSON headers for both paths and stays valid JSON.
5. The measures are computable claims (each names a numerator and a
   denominator), and no role claims a capability the product lacks.
6. Full suite OK.
