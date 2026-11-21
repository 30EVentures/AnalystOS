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

**Promoted to the live charter 2026-11-21 (Slice 103, owner's decision).**
`site/.well-known/flashyos-charter.json` and `site/flashyos.roles.json` now serve
this seven-role charter; this file stays here only as the validated source copy with
its own history. The handshake's `capabilities` array (`tools/build_flashyos_handshake.py`,
Slice 94) derives from it automatically and now lists all seven role names - still
only role names, never the `x-capability` discovery slugs, per `docs/mesh-identity.md`'s
rule.

What switching the *file* did **not** do, and what still needs the owner's separate
yes before any of it is real (tracked in `ROADMAP.md`'s Blocked list):

1. **No agent was minted.** The four new roles (coordination, research, synthesis,
   client-delivery) have no live agent on the FlashyOS API - that needs the
   join-grant token re-minted (the copies that travelled through a terminal log into
   a chat are compromised) and is an outward mesh action, not a file change.
2. **No endpoint was built.** Their `x-capability` discovery slugs
   (`engagement-coordination`, `source-research`, `cross-document-synthesis`,
   `analyst-briefing`) stay out of the handshake because nothing in this codebase
   can serve them yet - there is no coordination/intake endpoint, no
   source-research endpoint, no synthesis-across-documents endpoint, and no
   client-delivery endpoint.
3. `measures()` (Slice 61/96) stays honest about this gap on its own: it computes
   a real share only for the three roles with an audit-log event type
   (`tests/test_api_v1.py::MeasuresTest::test_measure_text_matches_the_published_charter`),
   and `tools/build_measures.py` marks the other four `"instrumented": false` with
   null values rather than inventing a number.

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
agent, action-ready output, deliverable acceptance criteria; see
`docs/decisions.md`, Slice 98 and the 2026-11-21 rename below). `@flashyos/defined`
is unpublished, so `tools/defined_proxy_validator.py` checks only the *documented*
rules - it says so in its own docstring and is never a substitute for Flashy's real
checker.

**Renamed from "decision-grade output" 2026-11-21 (owner's decision)**, after a
trademark check found a live USPTO filing on DECISION-GRADE in AnalystOS's own
services class, plus a third party's existing branding on a near-identical phrase
(see `docs/decisions.md`). Same definition, no term anywhere public depended on the
old name - nothing in this fragment has ever been served.

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
