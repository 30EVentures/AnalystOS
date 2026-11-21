# Slice 97 - a playbook for the document-analysis offer, and acceptance as a check

## Goal

The Engageable Workforce document argued that an outcome-based price needs
acceptance criteria agreed before work starts and checkable after delivery, "written
as a test rather than a description", and that a joint initiative instantiates its
tasks from a published `playbook/1` document naming each step's role and the
evidence it closes on. Both exist for AnalystOS's one real offer, document-analysis,
built on code this repo already has and already tests - not a new trust surface.

## Done when

1. `drafts/playbook-document-analysis.json` is a well-formed `playbook/1` document
   under the real, published `@flashyos/playbook@0.2.0`: `isPlaybook` true,
   `validate` returns no errors.
2. Every step names one of this charter's roles (live three, or the Slice 95 draft's
   seven), and the dependency graph (`after`) has no cycle.
3. Each step's evidence kind is checked for real against this repo, not asserted:
   - the two steps closing on `endpoint` evidence (`draft-the-cited-report`,
     `recompute-and-refuse`) are proven against the actual running Flask app's
     `POST /api/v1/verify` - a genuine bundle gets 200 and a body containing
     `content_checked`, a tampered one still gets 200 with `ok: false` (never a 500).
   - the `attested` steps' claims pass the real `checkClaim`, and a self-attestation
     (the org attesting its own step) is shown to be refused, proving the check is
     not vacuous.
   - the `sealed` step's claim is shown to be honestly `unverified` with no verifier
     supplied - correct today, because Track C's shipped/1 fan-in does not exist yet.
4. `analystos/l4/acceptance.py::document_analysis_acceptance` is built entirely on
   `verify_bundle` (no second, parallel notion of "verified"), requires the source
   text be supplied (treats its absence as a failure, not a free pass), never
   raises on a hostile bundle, and its `CRITERIA` constant is the text the
   playbook's `seal-the-report` step brief also uses.

## Not in this slice

- Wiring `document_analysis_acceptance` into the live delivery API. It is a check a
  client (or anyone) can run against a handed-over bundle; making it a gate inside
  AnalystOS's own pipeline is a separate product decision.
- A real `verifiers.sealed` implementation for `@flashyos/playbook`'s `verifyEvidence`.
  That needs Track C (shipped/1) to exist first; today's honest answer is "unverified".
- Any other playbook kind from the closed 13-key `@flashyos/playbook` catalogue
  (data-pilot, joint-research, integration, ...). Those describe collaboration
  *types* between two organisations generally, not AnalystOS's own service.
