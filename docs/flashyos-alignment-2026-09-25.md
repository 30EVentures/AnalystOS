# AnalystOS ⇄ FlashyOS — real conformance test and alignment, 2026-09-25

Companion to `docs/audit-2026-09-25.md` (your code) and `docs/flashyos-spec-notes-2026-09-25.md` (their specs). Tags: **CONFIRMED** (I ran/read it), **CLAIMED, UNVERIFIED**, **NOT FOUND / COULD NOT ACCESS**.

## 0. Bottom line

1. **Is `solwayholdings.aao.json` spec-conformant today?** **Structurally, yes** — it passes the published AAO JSON Schema plus the cross-field rules the schema documents (CONFIRMED, my re-implementation; §2). **But not in the sense FlashyOS means by "conformant."** The FlashyOS suite grades a *served* handshake and charter; **your site serves neither** (`/.well-known/flashyos.json` and `/.well-known/flashyos-charter.json` both return 404 on `analyst-os-phi.vercel.app`), so Level 1 fails and Level 2 is unreachable (CONFIRMED by fetching them). The manifest is also for `solwayholdings`, not AnalystOS, and its `description` ("Solwayholdings on the FlashyOS mesh") asserts something that is not true (no `solwayholdings` org exists on the network).
2. **The real gap** is not the file's shape. It is (a) nothing is served, (b) `analystos/aao/validate.py` disagrees with the published schema on **15 of 21** probe documents and emits no rule codes, so it cannot stand in for the real checks, and (c) **an org named `analystos` already exists on the live network** (created ~2026-09-03, 0 agents, one capability `analytics`) and I cannot tell who owns it.
3. **Single most concrete next step:** find out who owns the existing `analystos` org (ask Michael, or check the email you'd have used to sign in at `app.flashyos.com`) **before** publishing anything or creating an org. Everything else is downstream of that identity question, and duplicating an org would be a mess.

## 1. Part C.1 — running conformance-kit

**Feasible, and done.** Node v24.21 is now installed. I invoked the kit's CLI file directly from the cloned repo (`node src/cli.mjs …`) — no `npx`, no `npm install`, no network, only local files. I read all of its source first (see the spec notes §4) and it spawns only the command it is given.

**The result is a format mismatch, not a conformance score.** The only corpus the kit ships (and the only one I could legitimately obtain) is `examples/frontdoor-1.json` — profile `frontdoor/1`, 27 cases. Your validator checks AAO *charters*. The AAO corpus (`packages/aao/conformance/suite.json`) is advertised on flashyos.com/open but lives in `github.com/FlashyLabs/flashyos`, which returns **404** to outsiders (CONFIRMED). It may also ship inside the `@flashyos/aao` npm tarball — **NOT VERIFIED; I did not download it** (§4).

| Run | Program | agreed | disagreed | unanswered | unreadable |
|---|---|---|---|---|---|
| 1 (control) | `examples/always-valid.mjs` — accepts everything | **5 of 27** | 22 | 0 | 0 |
| 2 (control) | reject-everything script | **0 of 27** | 27 | 0 | 0 |
| **3 (asked for)** | **`analystos/aao/validate.py`** via a 6-line adapter | **0 of 27** | **27** | 0 | 0 |

Why Run 3 is 0/27: **5** accepting cases were refused (`expected valid=true, got valid=false` — a frontdoor document is not an AAO charter, so it fails your schema checks), and **22** refusals had the right verdict (`valid=false`) but were `disagreed` because the corpus asserts the specific rule **code** (`missing code(s): no-property`, `bad-contract`, `no-org`, …) and `validate_manifest` returns free-text strings with no machine-readable codes.

One thing I got wrong in advance, worth recording: I predicted the reject-everything control would score ~22/27 "by accident." It scored **0/27** — because refusal cases also require the named code. The kit is harder to game than I assumed.

**What this does and does not tell you.** It proves the kit runs here and that `validate.py` cannot take part in a code-asserting corpus as written. It says **nothing** about whether an AAO charter conforms. To test AAO conformance for real you need the AAO corpus or the official validator (§4).

Adapter used (kept outside your repo; `valid` = no problems, per the kit's "valid means no errors" rule):
```python
import json, sys
sys.path.insert(0, "/Users/calebsolway/AnalystOS/AnalystOS")
from analystos.aao.validate import validate_manifest
for line in sys.stdin:
    if not line.strip(): continue
    case = json.loads(line)
    problems = validate_manifest(case["input"])
    print(json.dumps({"id": case["id"], "valid": not problems, "codes": []}), flush=True)
```
Command: `cd conformance-kit && node src/cli.mjs examples/frontdoor-1.json -- python3 adapter.py`.

## 2. Part C.2 — field by field against the real spec

### 2a. `solwayholdings.aao.json` vs the published JSON Schema

Method: I fetched `https://flashyos.com/aao.schema.json`, verified it uses only keywords I could implement (`type const enum pattern min/maxLength minItems required properties patternProperties additionalProperties items $ref`), wrote a small checker for exactly those, and added the cross-field rules the schema's own description lists. **This is my re-implementation, not the official `@flashyos/aao` validator** (which also enforces a codename/vendor denylist I cannot see).

| Field in your file | Spec | Result |
|---|---|---|
| `aao: "0.1"` | const `"0.1"` | ✓ |
| `name: "Solwayholdings"` | required, non-blank | ✓ |
| `slug: "solwayholdings"` | `^[a-z0-9]+(-[a-z0-9]+)*$` | ✓ |
| `description: "Solwayholdings on the FlashyOS mesh."` | required, non-blank | ✓ structurally — **but factually false today**: no `solwayholdings` org exists on the network (spec notes §8) |
| `accountableTo: "calebsolway@gmail.com"` | email pattern; not `you@example.com` | ✓ |
| `roles[0]` `integration` / `roles[1]` `coordination` | name `^[a-z0-9]+(-[a-z0-9]+)*$`, 3–24 chars, ≤ 3 words | ✓ (11 and 12 chars, one word) |
| role `family`: `engineering`, `operations` | one of the ten | ✓ |
| role `capabilities`: `build deploy report` / `propose accept decline` | ≥ 1 action verbs | ✓ |
| role `humanApprovalAtOrAbove: "LOW"` (both) | `LOW MEDIUM HIGH CRITICAL` | ✓ |
| role `purpose` | required, non-blank | ✓ |
| unknown keys | `additionalProperties:false` (only `x-`) | none present ✓ |
| optional fields **absent**: `network`, `repositories`, `escalation`, role `measure` / `worksIn` / `renamedFrom` | optional | fine — "a manifest carrying none of them stays valid" |

**Missing / wrong / made up in the *file*:** nothing structurally wrong. Two substantive issues: the `description` claim, and that the roles (`integration`, `coordination`, capabilities `build/deploy/report`, `propose/accept/decline`) describe a generic engineering/coordination holding company — **nothing about analysis**, and it is not the charter of the product. The role names are legitimate function names (FlashyOS's own `/standard` example uses `coordination`).

### 2b. `analystos/aao/validate.py` vs the same spec

CONFIRMED by a 21-probe differential run (each probe varies exactly one property from a baseline that both validators accept; the "spec" verdict is derived from the published schema text and the rules it documents, and my checker agreed with my hand-derived expectation on every probe). **`validate.py` agrees with the published spec on 6 of 21 decidable probes and disagrees on 15.** (23 probes were run; 2 — a codename role `nova` and a four-word role name — are decided by the unpublished denylist / naming validator and are excluded as undecidable from the schema.)

The 15 disagreements:

| # | Probe | Published spec says | `validate.py` says | Kind |
|---|---|---|---|---|
| 1 | role omits `family` and `humanApprovalAtOrAbove` | **valid** (both optional) | refuses | **invented requirement** (`_ROLE_KEYS` requires both) |
| 2 | `humanApprovalAtOrAbove: "CRITICAL"` | **valid** | refuses | **missing a real value** |
| 3 | `humanApprovalAtOrAbove: "NONE"` | invalid | accepts | **made up** — `NONE` is not in the spec; Slice 7's "Done when #7" invented `{NONE,LOW,MEDIUM,HIGH}` |
| 4 | `family: "banana"` | invalid (closed list of ten) | accepts | **missing** (Slice 7 deferred it: "we just require a lowercase word") |
| 5 | `accountableTo: "Caleb Solway"` | invalid (must be an email) | accepts | **missing** email check |
| 6 | `accountableTo: "you@example.com"` | fails conformance (the one placeholder the spec names) | accepts | **missing** |
| 7 | unknown top-level key `_comment` | invalid (`additionalProperties:false`; only `x-`) | accepts | **missing** — and this exact mistake failed a real estate property (`/conformance`: "`_comment` instead of `x-comment`") |
| 8 | `aao: "0.2"` | invalid (const `"0.1"`) | accepts | **too loose** (`\d+\.\d+`) |
| 9 | slug `a--b` | invalid | accepts | **too loose** |
| 10 | slug `ab` (two characters) | valid (no minimum) | refuses | **invented** 3–24 length rule |
| 11 | slug `2fast` | valid | refuses | **invented** letter-first rule |
| 12 | `description: "   "` | invalid (must contain a non-space) | accepts | **missing** non-blank check |
| 13 | `escalation` naming a nonexistent role | invalid (cross-field) | accepts | **missing** cross-field rule |
| 14 | duplicate role names | invalid (cross-field) | accepts | **missing** cross-field rule |
| 15 | a role with an unknown key (`title`) | invalid (`additionalProperties:false`) | accepts | **missing** |

The 6 agreements: the both-valid baseline; `family: "finance"`; an `x-comment` extension key; a present `network` block; a valid `escalation`; and a role using the optional `measure`/`worksIn` charter fields with a declared repository.

**Also absent from `validate.py` entirely** (it neither validates nor rejects them): `network`, `repositories`, `escalation`, role `measure`/`worksIn`/`renamedFrom`, the `x-` extension convention, and the vendor/codename/machine-id/branch-name parts of the naming standard beyond a 7-word vendor list (`claude gpt openai anthropic gemini llama bard`; the spec's real list is not public).

**Verdict on the validator:** its docstring and Slice 7's spec are honest that it is "a stand-in… close enough to catch obvious mistakes." The measured reality: it is *not* close on inputs other than the one shipped manifest, and the 8 tests that "prove" it (`tests/test_aao_validate.py`) test the stand-in against itself. It is also **imported by no product code**.

**Not tested / not knowable from here:** the codename denylist (`nova`, `hermes`…); the official "static conformance questions" (`/aao` says four, `/conformance` says five — see the spec notes §10); anything `@flashyos/aao` does beyond the schema's documented rules.

## 3. Part C.3 — registering AnalystOS: the literal steps, and what is already true

Steps are from `/join`, `/onboard`, `/build`, `/conformance` (spec notes §6). "True today" and "to build" are my verified status.

| # | Step (as FlashyOS publishes it) | True today? | To build / do |
|---|---|---|---|
| 0 | **Resolve identity first**: the org slug `analystos` already exists on the network | **exists**, owner unknown (spec notes §8 / §5 below) | Find the owner. Claim it or agree its fate. **Do not mint a duplicate.** |
| 1 | Serve **`/.well-known/flashyos.json`** (handshake): `mesh:"flashyos/1"`, `org{slug,name,profile}` required; `capabilities` ≤ 32 kebab-case, `wants`, `api`, `join` optional; all URLs https | **NOT FOUND** — 404 on `analyst-os-phi.vercel.app` | Add the file under `site/` (or a Vercel rewrite). Proposal below. |
| 2 | Serve **`/.well-known/flashyos-charter.json`** (AAO 0.1 charter; estates also serve identical content at the legacy `/flashyos.roles.json`, and Rung 2 also asks for a `/directory.fragment.json` - CLAIMED) | **NOT FOUND** — 404. A charter file exists in the repo, but for the wrong slug. | Write an `analystos` charter; validate against `aao.schema.json`; serve it. Proposal below (validated). |
| 3 | Run **`npx @flashyos/conformance <your-domain> --level 2`** (exit 0 met / 1 failed / 2 could not tell) | not run (needs the npm package; §4) | Run it after 1–2. Level 1 and 2 are "self-claimed", need no account, make no call to FlashyOS beyond fetching your own files. |
| 4 | *(Rung 1)* "You published a charter" → reply within five business days from a named person | not started | after 1–3 |
| 5 | *(Rung 2)* Sign in at `app.flashyos.com`; create the org (GitHub App PR, direct, or `npx @flashyos/agent init`); receive an **agent token** (shown once; body-level secret; env `FLASHYOS_ORG_ID`/`FLASHYOS_AGENT_NAME`/`FLASHYOS_AGENT_TOKEN`) | **COULD NOT ACCESS** — needs an account | Probably resolves with step 0 (org may exist already). |
| 6 | Declare capabilities: `POST /api/v1/orgs/{orgId}/agents/{agentName}/capabilities` `{capability, description}` (description required; "a declaration, not a permission") | the org already declares `analytics` (someone did) | replace with an accurate tag; a real callable capability requires step 8 |
| 7 | Public listing requires: org public **and** ≥ 1 declared capability | already satisfied (it is listed) | — |
| 8 | To do anything cross-org: an agent joins an **ACTIVE joint initiative** (a human at each org must consent — agents cannot propose), claims a task, and completes it with an **https `evidenceUrl`** (+ optional `shipEvidence {entryId, sha256}`) | **NOT FOUND** — AnalystOS has no agent, no endpoint an agent could call, and no durable report URL | This is the large build (§6). |
| 9 | *(Level 3 / the mark)* live tokens naming the minting human, revocability, and decisions a human resolved — read from the register | not applicable yet | requires a running agent with a record |

**Proposed handshake** (not created; documented rules pass):
```json
{ "mesh": "flashyos/1",
  "org": { "slug": "analystos", "name": "AnalystOS", "profile": "https://analyst-os-phi.vercel.app" } }
```
Deliberately **no `capabilities`** — advertising a capability AnalystOS cannot yet serve to a mesh agent would repeat the kind of overstatement this project's own homepage tries to avoid. Trade-off worth knowing: `/conformance` says an estate property with "a handshake with no capabilities field" is "the P0 state the directory declines to list." (The existing `analystos` org is listed only because someone declared `analytics` through the API.) Your call.

**Proposed charter** — validated: passes the schema + documented cross-field rules (and `validate.py`). Not created as a file.
```json
{ "aao": "0.1", "name": "AnalystOS", "slug": "analystos",
  "description": "Reads a source document and writes an analytical report in which every figure is a verified quote or an independently recomputed calculation.",
  "accountableTo": "calebsolway@gmail.com",
  "roles": [{ "name": "report-generator", "family": "data",
    "purpose": "Produces a cited analytical report from one source document, discarding every figure it cannot verify.",
    "capabilities": ["analyze", "verify", "cite"], "humanApprovalAtOrAbove": "MEDIUM" }],
  "network": { "offers": ["document-analysis"] } }
```
Decisions that are yours, not mine: which email is the accountable human (I reused the one already in the repo); the `humanApprovalAtOrAbove` tier (semantics: "decisions at or above this impact wait for a human" — AnalystOS takes no consequential action, so this is a judgment call); whether to publish `network.offers` before the capability is real.

## 4. What I did not run, and how you can

I did **not** download or execute the official packages, because they were not among the sources you named:

```bash
# official structural + static AAO validation of a charter file (CI gate from flashyos.com/aao)
npm i @flashyos/aao && node --input-type=module -e '…validateCharterDocument, runStaticConformance…'
# official L1/L2 check of a live domain (after steps 1–2 above)
npx @flashyos/conformance analyst-os-phi.vercel.app --level 2
```
Expected today, from the documented rules (not a run): **Level 1 fails** (no handshake served). Whether the checker accepts a `*.vercel.app` host is **unverified** (the docs speak of "your domain"; a custom domain may be needed).

## 5. The `analystos` org that already exists (facts)

All CONFIRMED from documented public GETs on 2026-09-25:
- `network-directory` lists `{ id: "cmtkurcbs00je12tigb1rc6t1", name: "AnalystOS", slug: "analystos", headline: null, agentCount: 0, settledInitiatives: 0, capabilities: ["analytics"], seeking: [] }`.
- `conformance/{id}` → `accountable: false`; "no live agent tokens", "no agent events recorded; no decision records."
- INFERRED created **2026-09-03 01:34 UTC** (timestamp decoded from the id's format; not stated by FlashyOS).
- It is **not** in `graph.json` (that graph merges only estate properties).
- **Unknown:** who created it. It is consistent with you having signed up, with someone at Flashy having minted it, or with a third party. Do not assume.

## 6. Part C.4 — the MCP server (`/docs/mcp`)

**What the page says (CONFIRMED):** `@flashyos/mcp` is a thin wrapper over `@flashyos/agent`; one JSON config block for an MCP host (e.g. Claude Desktop) runs `npx -y @flashyos/mcp` with three env vars: `FLASHYOS_ORG_ID`, `FLASHYOS_AGENT_NAME`, `FLASHYOS_AGENT_TOKEN`. It exposes **29 tools**: 22 mesh actions and 7 wallet tools (testnets only). Relevant to AnalystOS: `flashyos_declare_capabilities`, `flashyos_discover` (open work), `flashyos_broadcast`/`offer`, `flashyos_join_initiative`, `flashyos_claim_task`, **`flashyos_complete_task` ("with an https evidence URL — the proof rides into the sealed settlement")**, `flashyos_resolve_initiative`. Proposing an initiative is deliberately not a tool.

**Is it a real near-term way to query or verify against FlashyOS from a tool like this one? Mostly no — reading too much into it if the goal is *verifying* things.**
- It is an **agent-side** integration for an org that already exists and holds an **agent token**. I have neither; **COULD NOT ACCESS**, not tested.
- **NOT FOUND:** any tool for verifying another org's conformance, reading a registry record, or checking a claim. Its discovery tools find *open work*, not credentials.
- The things I actually wanted to query — network membership, capability matching, an org's conformance record — are available today as **plain, unauthenticated HTTP GETs** documented at `/docs/rest` (`/public/network-directory`, `/public/ask`, `/public/conformance/{orgId}`); I called them successfully. For read-only checking, that is simpler and needs no token or package.
- Where MCP *would* be the right tool: **after** AnalystOS has an org + agent token and a callable capability, so that an MCP host could let an agent discover work, claim it, and complete it with evidence. That is a build-later path (§7), not a near-term verification path.

## 7. Cross-check of the earlier "Roadmap Feedback & AAO Integration Brief" (the PDF you gave me)

| Brief said | Against the public sources |
|---|---|
| Charter served at `/.well-known/flashyos-charter.json` | **CONFIRMED** present in the site's markup and the estate graph (not spelled out in the prose pages). |
| "seven fixed fields" | **Not as stated.** Schema: 6 required top-level fields (it names 6) + optional `network`, `repositories`, `escalation`. |
| `roles[]` names capped at 24 chars | **CONFIRMED** (3–24). |
| `accountableTo` "a single human email, no team alias" | Email pattern **CONFIRMED**; the "no team alias" rule is **not** stated anywhere I read (the schema cannot tell a person from an alias). |
| `npx @flashyos/conformance init` scaffolds the charter | **CONFIRMED present** (2026-09-26) - the published `@flashyos/conformance` 0.2.3 code has an `init` command that writes the charter, both well-known surfaces and a test, refusing to overwrite existing files. I read that code; I have not run `init`. *(An earlier version of this row said NOT FOUND, because I looked only in flashyos.com pages and the `@flashyos/agent` docs. That was wrong.)* |
| `completeTask(taskId, evidenceUrl)` is the primitive; "nothing constrains what that URL points to" | Primitive **CONFIRMED** (REST `POST /api/v1/initiative-tasks/{taskId}/complete`, SDK `completeTask`, MCP `flashyos_complete_task`). The second half is **wrong**: `evidenceUrl` must be `https://` ("a checkable artifact, not a vibe"), the task must belong to an **ACTIVE joint initiative** whose parties consented, and an optional `shipEvidence {entryId, sha256}` exists to carry a digest a counterparty recomputes offline. That last field is a natural home for the sealed fact-set digest proposed earlier. |
| Capability declaration is `POST …/capabilities {capability, description}` | **CONFIRMED** (`POST /api/v1/orgs/{orgId}/agents/{agentName}/capabilities`, description required; needs agent/session auth). |
| `partnerComplianceGate.ts`, `assertNotInvestmentAdvice`, status `pending-legal-review` | **NOT FOUND** in any public source (the monorepo is private). **CLAIMED, UNVERIFIED.** |
| "nothing has actually been registered… yet" | **Contradicted at the org level**: an `analystos` org exists in the live directory (§5). (No *charter* has been registered or served — that part holds.) |
| "Nothing on FlashyOS's side needs to be built" | True for the primitives (they exist); but joining still needs a FlashyOS-side sign-in/org/token, and cross-org work needs human consent on both sides. |
| Mesh privacy: report URL as evidence | **Tension found:** `/docs/mesh` says never send "document contents… evidence bundles" to the mesh, while `complete_task` wants an https evidence URL and an AnalystOS report quotes the source verbatim. A durable report URL therefore needs access control/expiry, and FlashyOS's expectations on evidence visibility are an open question (§8). |

## 8. Part C.6 — what I could not verify → questions for Michael Gord

**Could not verify** (needs account/token, private repo, or not published): ownership of the existing `analystos` org; the AAO conformance corpus and `aao.schema.json`/suite GitHub links (private monorepo); the behaviour of `@flashyos/aao` / `@flashyos/conformance` (not run); the "static questions" count; the rung-2 process; the `app.flashyos.com` flows; the MCP server and register-backed L3 for a real org; `partnerComplianceGate.ts` and the investment-advice gate; whether a `vercel.app` host is accepted by the checker.

Short list:
1. **The `analystos` org (id `cmtkurcbs00je12tigb1rc6t1`, created ~2026-09-03, capability `analytics`, 0 agents): who created it, and can it be handed to me or deleted/renamed?** I don't want a duplicate.
2. The `aao/0.1` portable conformance suite is advertised on `/open` but its GitHub link is a 404, and `flashyos-spec` says the specs "are not here yet." **Where can an outsider fetch the AAO corpus today, and is the monorepo going public?**
3. `/aao` says **four** static questions and `/conformance` says Level 2 means **five**. Which is right, and what are the exact static checks?
4. `/conformance` says flashyos.com is at Level 1 in one paragraph and lists it at L2 in the table. Which is current?
5. Does `npx @flashyos/conformance` accept a `*.vercel.app` domain, or must it be a custom domain? Is the charter path definitely `/.well-known/flashyos-charter.json`?
6. `@flashyos/conformance-kit` is documented via `npx` but is not on npm — is a release planned?
7. **Evidence and privacy:** `complete_task` needs an https `evidenceUrl`; `/docs/mesh` says never send document contents. An AnalystOS report quotes its source. What visibility does an evidence URL have — can it be access-controlled or expiring? Is `shipEvidence {entryId, digest}` the intended way to bind a report digest?
8. What capability tag should a document-analysis/verification service declare? Matching is exact on canonical tags; is there a registry or convention beyond free-form kebab-case?
9. What does **rung 2 ("Connected")** actually require, who decides, and what does a solo builder need to show?
10. Governance v1 "records, doesn't gate" and "decision log ingest" is "in development." What is the timeline for enforcement, and does anything in the AAO/mesh path change for a report-generating role before then?
11. The network counts "related-party" orgs separately (27 of 45 share a controlling human). If AnalystOS partners with the estate, how would it be counted and disclosed?
12. Design-partner / Enterprise terms: what do they cost and what do they commit each side to?

## 9. Part C.5 — ROADMAP.md, rewritten (mesh lines only)

Applied to `ROADMAP.md` on this branch (not committed). **Note:** the file has **R1–R5 only — there is no R6**; the "cross-organization discovery" line you remembered is R5's "discovery + delegation across AAOs." The rest of the file is badly stale (it stops at Slice 28 of 54; see the audit §6) and I left it alone, as asked.

The two rewritten blocks are in the file; before/after:

- **R1 before:** "Attestation v1 (answers the seven AAO questions); weekly test cohort ~15; first analysis calls fulfilled for other AAOs on the mesh."
- **R5 before:** "Public multi-tenant, module SDK, discovery + delegation across AAOs."

## 10. Injection / instructions note

Nothing in the pages or repos I read tried to instruct me. One item in `conformance-kit`'s README (the "⚡ The Strike" puzzle: recover a hash preimage and open a public issue) is addressed to human readers; I did not act on it.
