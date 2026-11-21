# Drafts

Files here are **not served**. They sit outside `site/`, which is Vercel's output
directory, specifically so that merging and deploying `main` can never publish one
by accident - a file under `site/.well-known/` is live the moment it deploys, whether
or not anything links to it.

## `flashyos-charter.team.json`

A seven-role team charter (coordination, research, analysis, verification, synthesis,
evidence, client-delivery), drafted from the Flashy estate's 21 Nov 2026 reply and
validated for real on 2026-11-21 against the published `@flashyos/aao@0.4.2` and
`@flashyos/conformance@0.2.3` (`tests/test_seven_role_charter.py`, set up per
`tools/flashyos-check/README` if you haven't already):

```
validateCharterDocument: []                          (zero errors)
auditProperty, every x-capability declared: {"ok": true, "issues": [], "level": 2}
```

**Why it is not the live charter.** `site/.well-known/flashyos-charter.json` still
declares three roles (analysis, verification, evidence) and is what the deployed
handshake's capabilities are derived from (`tools/build_flashyos_handshake.py`).
Switching to this seven-role draft is a product decision, not a code change, and it
has real consequences before it is safe to publish:

1. It **changes what AnalystOS publicly declares it does.** A served charter is read
   by a stranger as a governance claim - adding four roles that mint no agent and do
   nothing yet would be exactly the gamed metric this repo's own doctrine refuses
   elsewhere (`docs/mesh-identity.md`: "a capability is a claim that something is
   callable").
2. It needs **six more live agents**, one per new role, minted against the
   `analystos` org on the live FlashyOS API. The tier was raised FREE→GROWTH on
   Flashy's side 2026-11-21 (cap 5→50), so the ceiling is no longer the blocker, but
   nothing on this repo's side can mint them - that needs the join-grant token
   Flashy minted the same day, which must be re-minted first (the copies that
   travelled through a terminal log into a chat are compromised; see
   `ROADMAP.md`'s Blocked list).
3. The `coordination`, `research`, `synthesis` and `client-delivery` roles'
   `x-capability` discovery slugs (`engagement-coordination`, `source-research`,
   `cross-document-synthesis`, `analyst-briefing`) name capabilities nothing in this
   codebase can actually serve yet - there is no coordination/intake endpoint, no
   source-research endpoint, no synthesis-across-documents endpoint, and no
   client-delivery endpoint. Declaring them before they exist is the claim
   `docs/mesh-identity.md` says never to make.

**To promote this draft to the live charter**, once the owner has decided to and the
six agents exist: copy this file over `site/.well-known/flashyos-charter.json` and
`site/flashyos.roles.json` (keep them byte-identical, per `tests/test_mesh_identity.py`),
run `python3 tools/refresh.py`, and run the full suite. Do this on a branch and open a
PR; nothing in this repository's tooling does it for you, by design.

## `measures.json`

A `measures/1` document, wrapping the existing `analystos.api_v1.audit.measures()`
(Slice 61) in a window/charter-URL envelope, built by `tools/build_measures.py`
(see `docs/decisions.md`, Slice 96, and
`tests/test_measures.py`). Unlike the charter draft above, this one asserts nothing
false even in its current, honestly-empty state (production's audit log is dormant
per Slice 84, so every value is correctly `null`). It is a draft only because Flashy's
21 Nov reply committed to pull a measures document but has not confirmed a path or a
format - propose it to them before publishing, not because the numbers need guarding.

To recompute against a real store directory: `python3 tools/build_measures.py --store-dir PATH`.

## `playbook-document-analysis.json`

A `playbook/1` document for AnalystOS's one real offer, validated against the real
`@flashyos/playbook@0.2.0` and proven against this repo's own running Flask app and
seal verifier (`tests/test_playbook.py`; see `docs/decisions.md`, Slice 97). Not
served, for the same reason as the other drafts: there is no live joint-initiative
infrastructure on either side to instantiate it against yet, and Flashy's own
`recipeKey` discovery path is not confirmed.

The acceptance check it references, `analystos/l4/acceptance.py::document_analysis_acceptance`,
is real product code (not a draft) - a client can run it today against any bundle
AnalystOS hands over, independent of anything in this file.

## `defined-analystos.json`

A `defined/1` fragment for the three terms AnalystOS can own outright (analyst
agent, decision-grade output, deliverable acceptance criteria; see
`docs/decisions.md`, Slice 98). `@flashyos/defined` is unpublished, so
`tools/defined_proxy_validator.py` checks only the *documented* rules - it says so
in its own docstring and is never a substitute for Flashy's real checker.

**Known, checked-for gap:** every entry's `basis` URL points at a `/defined/<slug>`
page that does not exist in `site/` yet (`tests/test_defined_fragment.py` fails the
moment one is added without this note being updated). The 18 Nov integration
document named exactly this - a fragment whose basis pages 404 - as the mistake to
avoid. Build the pages, or decide to publish with 404 links anyway and say why,
before serving this anywhere; see `ROADMAP.md`.

## `devlog.fragment.json` (the served projection)

The public projection of this repository's real `shipped/1`/`devlog/1` record
(root `shiplog.fragment.json` and `devlog.fragment.json` are the full, private
source - see `docs/decisions.md`, Slice 99). Currently has zero entries, matching
`.shiplog/config.json`'s `visibility: "private"`. Unlike every other file in this
directory, the *record itself* is real and already committed at the repo root;
only this served copy, and the decision to flip visibility and hand the URL to
Flashy's fan-in, remain open - see `ROADMAP.md`.
