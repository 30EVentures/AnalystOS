# What FlashyOS actually specifies — reading notes, 2026-09-25

Everything here comes from sources I fetched and read myself on 2026-09-25 (raw HTML converted to text, JSON parsed, code read). Nothing was submitted, no account was created, no form was filled, and **no npm package was downloaded or executed** (see §9). Tags: **CONFIRMED** (I read it / ran it), **CLAIMED, UNVERIFIED** (a source says so; I could not check), **NOT FOUND / COULD NOT ACCESS**.

## 1. Sources and access status

| Source | Result | Needs an account? |
|---|---|---|
| `github.com/FlashyLabs` | **CONFIRMED a *user* account (`type: User`), not an organization** — the org API returns 404, the user API returns 200. 12 public repos, created 2022-12-25. | no |
| 6 named repos cloned (shallow) to a scratch dir outside your project: `flashyos-spec` @8ae43f3, `conformance-kit` @681452c, `flashyos-tools` @4603c4a, `flashy-ledger` @140142f, `flashyos-wdk` @f32ea5f, `wdk-staking-kit` @a7f3b1c | all cloned | no |
| 23 flashyos.com pages you listed (`/aao /protocols /ritual /ritual/spec /intentmesh /assetmesh /standard /conformance /docs /docs/rest /docs/mesh /docs/mcp /network /join /onboard /build /packages /open /directory /directory/graph /shipped /status /graph.json`) | **all HTTP 200.** Read in full: `/aao /protocols /standard /conformance /docs /docs/rest /docs/mesh /docs/mcp /network /join /onboard /build /open /status /directory/graph /graph.json`. **Only skimmed** (opening sections): `/ritual /ritual/spec /intentmesh /assetmesh /packages /shipped`; **`/directory` (the page, as opposed to `/directory/graph`) not read.** | no |
| `flashyos.com/aao.schema.json` | 200, 7,016 bytes, read in full | no |
| npm registry metadata (read-only JSON) for `@flashyos/aao`, `@flashyos/conformance`, `@flashyos/agent`, `@flashyos/conformance-kit` | first three exist; **`@flashyos/conformance-kit` → 404 (not published)** | no |
| `api.flashyos.com/api/v1/public/{network-stats,network-directory,conformance/{id},ask}` (documented public GETs) | 200, read | no ("No account · no org · no key") |
| The 6 pages behind the nav's **LIVE** badges (`/defined /ask /audit /deliverability /concierge /live-hq`) | pages fetched and read; see §7 for which I actually *exercised* | see §7 |
| `github.com/FlashyLabs/flashyos` (the monorepo that `@flashyos/*` packages and many page links point at) | **NOT FOUND — 404 for everyone outside** (repo API and web UI). It is not among the 12 public repos. | — |

## 2. The headline finding: `flashyos-spec` does not contain the spec

**CONFIRMED.** `flashyos-spec` has one branch (`main`), no tags, 16 files (licence, security policy, CI, CODEOWNERS, README, CHANGELOG…) and **zero schema, profile or corpus files** — checked both in the clone and via the GitHub tree API (19 paths, none `.json`). Its own README says: *"The specifications are not here yet. They are Apache-2.0 today; carrying the packages out of the monorepo… is a deliberate operation."* and *"Not released yet."* It also shows example commands (`ls profiles/`, `jq … profiles/frontdoor-1/conformance.json`) that reference a `profiles/` directory that does not exist. The CHANGELOG's only entry is "Initial public release preparation."

So the AAO format has to be read from **flashyos.com/aao** and **flashyos.com/aao.schema.json**, which are the only public normative sources I could reach.

## 3. What the AAO format actually requires

Source: `/aao`, `/standard`, and the machine-readable schema (`$id https://flashyos.com/aao.schema.json`, JSON Schema draft 2020-12, title "AAO charter document (aao 0.1)"). **CONFIRMED** unless tagged.

**What it is.** One JSON file, conventionally `*.aao.json`, declaring an organization of AI agents "the way a cap table declares ownership": who each agent is, what it may do, which human answers for it, and what must wait for human approval. It deliberately excludes model configuration, prompts and infrastructure ("those change weekly").

**Top level** (`additionalProperties: false`, except keys beginning `x-`, the explicit extension convention — "carried, never enforced"):

| Field | Required? | Rule |
|---|---|---|
| `aao` | **required** | the literal `"0.1"` |
| `name` | **required** | non-blank string |
| `slug` | **required** | `^[a-z0-9]+(-[a-z0-9]+)*$` (lowercase letters/digits, single hyphens) |
| `description` | **required** | non-blank string |
| `accountableTo` | **required** | one human's email, `^[^@\s]+@[^@\s.]+\.[^@\s]+$`; conformance additionally **fails the template placeholder `you@example.com`** |
| `roles` | **required** | array, ≥ 1 |
| `network` | optional | `{offers: string[], wants: string[]}` only |
| `repositories` | optional (charter field) | array of `{name, url, holds[≥1], default?}`; `name` `^[a-zA-Z0-9._-]+$`, `url` and `holds` required |
| `escalation` | optional (charter field) | must name an existing role (cross-field) |

**Each role** (`additionalProperties: false` except `x-`):

| Field | Required? | Rule |
|---|---|---|
| `name` | **required** | `^[a-z0-9]+(-[a-z0-9]+)*$`, **3–24 chars**; a standing responsibility, never a person/codename |
| `purpose` | **required** | non-blank one-liner |
| `capabilities` | **required** | array ≥ 1 of non-blank strings — "actions, not departments" (`deploy`, `review`, never `engineering`) |
| `humanApprovalAtOrAbove` | optional | enum **`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`** ("matches FlashyOS `DecisionImpact` exactly"). "Omit for a role that never needs approval; LOW for one that always does." |
| `family` | optional | closed enum of ten: `growth revenue product engineering operations data finance risk governance support` ("closed on purpose") |
| `measure`, `worksIn[≥1]`, `renamedFrom[]` | optional (charter fields) | `worksIn` names must be declared repositories |

**Cross-field rules the schema explicitly does *not* enforce** (it says it is "necessary but not sufficient"; they live in the npm validator): duplicate role names; `worksIn` naming an undeclared repository; `escalation` naming a nonexistent role; more than one default repository; a repository with no owning role; and "the full role-naming standard's codename/vendor denylist."

**The naming standard** (`/standard`, "shipped in `@flashyos/aao` v0.2"): lowercase, hyphen-separated, 3–24 chars, **at most three words**. The validator refuses: a model vendor in the name (`claude-agent`), a branch name (`main`), a task-like name over three words, a placeholder (`test-agent`; generic words only when the whole name is generic), a machine id (`audit-bxq1t0`), and codenames (`nova`, `hermes`, `aura`, `sage`, `atlas`, `forge` shown as failing). The page states the codename rule "cannot be checked mechanically… a denylist of the ones in circulation plus a reviewer."

**The seven questions** (`/aao`): a manifest is "conformant when it can answer these." Four are **static** (answerable from the file, checked in CI): who is this agent; what can it do; which human is responsible; what happens before something consequential. Three are **runtime facts** (who authorized it; can I revoke it; what did it do), which conformance reports as **deferred** "until the org is live on a network, rather than pretending a JSON file can prove revocation works."

**A conforming manifest** (verbatim shape from `/aao`): `aao`, `name`, `slug`, `description`, `accountableTo`, `roles[{name, purpose, capabilities, humanApprovalAtOrAbove}]`, optional `network{offers,wants}`. `/standard` shows the extended "charter" form (adds `repositories`, `family`, `measure`, `worksIn`, `renamedFrom`, `escalation`). Charter fields are "additive — a manifest carrying none of them stays valid."

**Tooling** (`npm i @flashyos/aao`, v0.4.2, Apache-2.0, published 2026-09-06, no dependencies): `validateManifest`, `validateCharterDocument`, `validateCharter`, `runStaticConformance`, `validateRoleName`, three reference charters (PERSONAL_OS, AMBASSADOR_OS, FINANCIAL_OS). **CLAIMED, UNVERIFIED** — I did not download or run it (§9). **NOT FOUND** — its source: `github.com/FlashyLabs/flashyos/packages/aao` returns 404.

## 4. conformance-kit: exactly how it tests a program

Read in full: `README.md`, `src/cli.mjs` (279 lines; `src/conformance-run.mjs` is the same code), `examples/`. **CONFIRMED.**

- **Interface.** `conformance-kit <corpus-path-or-URL> -- <command> [args…]`. The command is spawned **once** and fed every case on stdin, one JSON object per line: `{id, set, input, context?}`. It must write one JSON object per line on stdout: `{id, valid, codes?}` (or `{id, verdict, codes?}` for `decide`-kind sets). No SDK, no bindings.
- **`valid` means *no errors*.** Warnings do not make a document invalid; the README records that the first adapter ever written got this wrong.
- **Four outcomes, never a single score:** `agreed` (verdict matches, and codes match *where the case states them*), `disagreed` (answered, wrong), `unanswered` (no verdict for that id — crash, hang, or unrecognized case), `unreadable` (a line that is not a valid verdict, or the wrong shape). `unanswered`/`unreadable` are reported separately and "enter no ratio."
- **Codes:** compared only when the case states `expect.codes`; extra codes from the program are allowed; a missing expected code is `disagreed`.
- **Robustness:** non-JSON stdout lines and lines without an `id` are collected as "extra" and ignored; a program silent for 60 s is `SIGKILL`ed and the run errors.
- **Exit codes:** 0 iff every case agreed, 1 otherwise, 2 for bad usage / no runnable cases.
- **Network/exec behaviour** (I read every use of the relevant primitives): it fetches only if the corpus argument is an `http(s)://` URL; otherwise it reads a file. It spawns only the command it is given. No `eval`, no environment reads, no telemetry.
- **What ships to run:** one corpus, `examples/frontdoor-1.json` — contract `conformance/1`, profile **`frontdoor/1`**, 27 cases (5 accept, 22 refuse; every refusal names a rule code). **Not an AAO corpus.**
- **Distribution.** README says `npx @flashyos/conformance-kit …`; the npm registry returns **404** for that package (**CONFIRMED not published**). It works today only by cloning the repo and running `node src/cli.mjs` (which I did — see the alignment doc).
- The README ends with a "⚡ The Strike" puzzle asking readers to recover a hash preimage and open a public GitHub issue. It is addressed to human readers, is outside this task, and I did not act on it.

## 5. What each page defines

| Page | What it actually says (in my words) |
|---|---|
| **/aao** | The AAO spec v0.1: the manifest, the seven questions (4 static / 3 deferred), a copy-paste CI gate using `@flashyos/aao`, and the `aao.schema.json` link. |
| **/standard** | The role-naming standard v0.2 (rules above), the ten closed families, and the "charter" extension (repositories, jurisdiction, escalation). |
| **/conformance** | `flashyos/1` conformance in **three levels**: **L1 Discoverable** = serve a valid handshake at `/.well-known/flashyos.json`; **L2 Chartered** = publish an AAO charter passing the static questions; **L3 Accountable** = the three runtime facts verified **from the register, never from the site checked**. L1 and L2 are "self-claimed" and need no account; **L3 "carries the mark"** and is granted by FlashyOS. CLI: `npx @flashyos/conformance <domain> [--level N]`; exit 0 = level met, 1 = a check failed, 2 = could not reach a verdict. Only public orgs have a record; a private org's is indistinguishable from a missing one. The page lists the estate's own nine properties at L2, "none claiming L3." Terms of the "FlashyOS Conformant" mark ship as `MARK.md` in the package (**not read**). |
| **/protocols** | Catalogue of **29** open formats: 15 published, 5 published by other estate properties, 9 written but deliberately held back "until somebody outside adopts one." Includes `aao` charter, `flashyos/1` handshake, `frontdoor/1`, `directory/1`, `countersign/1`, `shipped/1`, `backlog/1`, `checkpoint/1`, `rwa/1`, `ritual/1`, `mail/1`, `holding/1`, `playbook/1`, `delivery/1`, `defined/1`, and others. |
| **/open** | "The spec is open. The network is a product." Lists which formats ship a portable conformance suite (**"7 of 14"**, `aao/0.1` marked ✓) and the npm packages. |
| **/docs** | SDK reference for `@flashyos/agent`: presence/heartbeat, events, `decide()`/`requestApproval()`, cross-org calls (`declareCapabilities`, `declareFromCharter(charter)` — derives an agent's declarations from its AAO role, `broadcast`, `offer`, `joinInitiative`, `resolveInitiative`), a header-authenticated "work layer" (`claimTask`, `completeTask(taskId, evidenceUrl)` — `evidenceUrl` "must be a real https:// link… the server refuses anything else, and the evidence rides into the sealed settlement"), roadmap items, operator questions. Publishes an explicit **enforced-vs-recorded** table: *recorded, not enforced* — `decide()` ("does not block the agent"), `declareCapabilities()` ("nothing yet checks a declared capability before an agent acts"), reporting delivery; *enforced* — tokens hashed at rest and expiring, the naming standard at mint, revocation, cross-org consent, sealed settlements. An org that declares no capability is **absent from the public directory**. Note two auth styles in transition: body credentials on most endpoints; `Authorization: Bearer` + `x-org-id` + `x-agent-name` headers on the work layer. |
| **/docs/rest** | The language-neutral wire contract. **Auth is in the JSON body** (`orgId`, `token`, `agentName`), **not a header**. Endpoints include heartbeat, events, `POST /orgs/{orgId}/decisions`, **`POST /orgs/{orgId}/agents/{agentName}/capabilities`** (description required; "a declaration, not a permission"), offers, work-broadcasts, contribute, **joint initiatives** (proposal is human-only, session-only), initiative tasks (`claim`, **`complete` with a required `https://` `evidenceUrl`** and optional `shipEvidence {entryId, digest}`), roadmap items, `agents/questions`, grants, and a set of **public, no-auth reads**: `/public/ask`, `/public/network-directory`, `/public/network-stats`, `/public/network-agents`, `/public/conformance/{orgId}`, `/public/settlements`, `/public/directory`, `/public/deliverability`, `/public/receipt/{slug}`. |
| **/docs/mesh** | "The mesh as an edge, never a core": eight rules — one adapter, enforce locally/mirror to the mesh, **redact by allowlist**, default to PRIVATE if regulated, stay correct with the mesh unreachable, token is a body-level secret, map states to rooms, a human consents to cross-org. Explicit "**never send**: amounts, counterparties, account numbers, customer names, **document contents**… evidence bundles." |
| **/docs/mcp** | `@flashyos/mcp` — a thin wrapper over `@flashyos/agent`. One config block; reads `FLASHYOS_ORG_ID`, `FLASHYOS_AGENT_NAME`, `FLASHYOS_AGENT_TOKEN`. **29 tools** — 22 mesh tools (set task, decide, declare capabilities, broadcast/offer/discover, initiative board/thread/resolve, claim/**complete task with an https evidence URL**, ask operator, roadmap, incident, done) plus 7 **testnet-only** wallet tools. **No tool that verifies another org's conformance**; discovery tools find *open work*, not credentials. Proposing a joint initiative is deliberately *not* a tool. |
| **/join** | The "ladder" (§6). "Knocking is open. Standing is earned." Nothing typed in a form can raise a rung; they "check what you publish, not what you tell us." |
| **/onboard** | Three ways to set up an org (GitHub App PR / create directly / terminal `npx @flashyos/agent init`), all beginning with a sign-in on `app.flashyos.com`. |
| **/network** | Marketing-level: invite, discover (shared capability registry), broadcast, partner, grow. Access is by "Request access." |
| **/build** | The builder hub, and the **`flashyos/1` handshake**: one static file at `/.well-known/flashyos.json` with required `mesh:"flashyos/1"` and `org{slug,name≤120,profile?}`, optional `capabilities` (≤32 kebab-case), `wants`, `api`, `join` (all URLs https; unknown top-level keys allowed). |
| **/packages** | Package catalogue with versions (e.g. `@flashyos/mcp 0.6.0`, `@flashyos/create-mesh-agent 0.2.0`, `@flashyos/create-mesh-node 0.1.0` — "one command from a domain to a node the mesh can see and grade", `@flashyos/verify 0.4.0`). Only skimmed. **CLAIMED, UNVERIFIED** beyond the three `@flashyos/*` packages I checked on npm (`aao`, `conformance`, `agent`; the fourth check, `conformance-kit`, returned 404). |
| **/status** | Candid: "automated health probes are planned, not yet wired"; "Decision log ingest — In development"; uptime history "No data." |
| **/directory, /directory/graph, /shipped** | The directory/1 estate graph and merged `shipped/1` records (details in §8). |
| **/ritual, /ritual/spec, /intentmesh, /assetmesh** | Other protocol families: `ritual/1` (recurring witnessed observances, "the present tense"), IntentMesh (consent + verifiable record layered on A2A/MCP), AssetMesh (`rwa/1`, real-world-asset records with five refusing rules). **Not relevant to a document-analysis product**; skimmed, not analysed. |

## 6. The literal steps to join the network (from `/join`, `/onboard`, `/build`, `/conformance`)

**CONFIRMED** as published; **not performed** by me.

1. **Rung 0 — Open (~2 minutes):** send a message via the `/join` form (no account). "We read everything. We do not promise a reply."
2. **Rung 1 — Identified (~20 minutes):** publish a charter at your **own domain**. Reply "within five business days from a named person"; your charter is read before the meeting.
   - Serve `/.well-known/flashyos.json` (handshake, §5 /build).
   - Serve the AAO charter at **`/.well-known/flashyos-charter.json`** — this path appears in the page's raw markup and in the estate graph (**CONFIRMED present**), but the *prose* pages I read never spell it out (see §10).
   - Run `npx @flashyos/conformance yourdomain.com --level 2` (exit 0 = met).
3. **Rung 2 — Connected (an afternoon):** "You are in the mesh." Needs an org on `app.flashyos.com` (sign-in): (a) install the GitHub App on one repo (it opens a PR you merge), or (b) create the org directly, or (c) `npx @flashyos/agent init`. (Per gord.holdings/engage, `npx @flashyos/conformance init` also scaffolds the charter and well-known surfaces - CONFIRMED present in the published 0.2.3 code on 2026-09-26, not run. Estates serve the charter at both `/.well-known/flashyos-charter.json` and `/flashyos.roles.json`; Rung 2 also asks for a `directory.fragment.json`.) You receive an **agent token** (shown once; a body-level secret for env/CI, never a commit). Declare capabilities (`POST /api/v1/orgs/{orgId}/agents/{agentName}/capabilities`, description required). To appear in the public directory an org must be **public and declare ≥ 1 capability**. Reward: a call, a registry listing, your record in the estate graph. **NOT FOUND:** the "what rung 2 costs" page (linked, not in your list, not read).
4. **Rung 3 — Integrated (real engineering):** "Something of yours runs on something of ours." Diligence begins.
5. **Level 3 conformance** (the mark): needs live tokens naming the minting human, revocability, and decisions a human actually resolved — read from the register, cannot be self-declared.

Cross-org work never starts by machine: a joint initiative starts PROPOSED and needs a human at each org to consent.

## 7. Which "LIVE" tools I could and could not test

| Tool | Result |
|---|---|
| **Ask the network** (`/ask` ⇄ `GET /api/v1/public/ask`) | **Tested** (read-only GET, no account). `?need=analytics` returned exactly one match: the `analystos` org. |
| **Public directory / stats / conformance record** | **Tested** via documented public GETs (details §8, and the alignment doc). |
| **Audit a site** (`/audit`) | Page read ("no signup"). **Not exercised** — it takes a domain to audit and I did not submit one. |
| **Check your mail** (`/deliverability` ⇄ `/public/deliverability`) | Page read ("free · no account · nothing recorded"). **Not exercised** (needs a domain). |
| **The concierge** (`/concierge`) | Page read ("A person reads it"). **Not exercised** — submitting sends a message on your behalf. |
| **Vocabulary** (`/defined`) | Page read (a static list of terms). |
| **Live HQ** (`/live-hq`) | Page read ("172 agents reporting from 33 orgs… 12 more on the network keeping theirs private" → 45 orgs, consistent with `/join`); real-time embed, "request access" for a private walkthrough. |
| Anything on `app.flashyos.com` (sign-in), the MCP server, the register-backed L3 check for a real org | **COULD NOT ACCESS** — requires an account/token I do not have. |

## 8. Are you in the data? (`graph.json` and the live directory)

**`/graph.json` — CONFIRMED absent.** I parsed the file (337,448 bytes; generated 2026-09-23; 361 nodes, 787 edges, all `visibility: public`) and searched **the entire raw text, case-insensitively**, for `solway`, `solwayholdings`, `analystos`, `analyst-os`, `analyst os`, `analyst`, `caleb`, `30eventures`, `gmail.com`, `vercel.app`, `analyst-os-phi`. **0 hits for every term.** Control searches prove the method works: `gord` 100, `gda` 150, `flashy` 651, `michael` 1,202.

**But `graph.json` is not what it was described as.** It is **not** "a raw data dump of every registered organization." It is the *estate directory graph* (`directory/1`): merged from **17 of 19 properties** that publish a `directory.fragment.json` (2 returned 404), with `sources.external = 0` and only **13 `Organization` nodes** (4.ventures, Botz Group, ClaimYour.Gold, Flashy.Academy, Flashy Gold, Flashy Group, Flashy Network, Flashy ID, FlashyOS, GDA Capital, Gord Holdings, Metaverse Group, MLG Blockchain). An external organization would not appear unless it were a merge source, so its absence says little about network registration.

**The better question is answered by the live registry, and the answer is different — CONFIRMED:**

- `GET https://api.flashyos.com/api/v1/public/network-directory` (fetched 2026-09-25) lists **29** public orgs. One is **`analystos` — "AnalystOS"**: id `cmtkurcbs00je12tigb1rc6t1`, `headline: null`, **`agentCount: 0`**, `settledInitiatives: 0`, one declared capability, **`analytics`**, `seeking: []`. It is the only org declaring `analytics` (`/public/ask?need=analytics` → one match).
- `GET …/public/conformance/cmtkurcbs00je12tigb1rc6t1`: **`accountable: false`**; all three runtime facts unverified — "no live agent tokens", "no agent events recorded; no decision records."
- **Creation time (INFERRED, not stated by any FlashyOS source):** the id is a `cuid`-style string whose leading characters encode a millisecond timestamp; decoded, `analystos` was created **2026-09-03 01:34 UTC** — individually, unlike the 2026-09-05 creations that minted ten estate orgs within about four seconds (15:21:39–43 UTC) and three more at 16:30.
- **NOT FOUND:** `solwayholdings`, `solway`, `caleb`, or `30eventures` in the 29-org list. **CANNOT DETERMINE:** who created `analystos` and whether that person is you — no source I could read names an owner. `/public/network-stats` reports 6 orgs "minted and never claimed," and I cannot tell whether this is one of them.
- **The people you named:** `graph.json` has one `Person` node, "Michael Gord — Accountable for the estate." `GDA Capital`, `Gord Holdings`, `Flashy Finance` and `RitualOS` (spelled that way) all appear. **NOT FOUND in any source I read:** "Alpaca" / "Alpaca Network." I cannot confirm from these sources what Michael Gord founded; the sources say only that he is accountable for the estate.

## 9. What I deliberately did *not* run

`@flashyos/aao` (the official validator) and `@flashyos/conformance` (the official domain checker) are published on npm, but they are not among the sources you named, so I did **not** download or execute them. That means **I did not run the official AAO validation or the official L1/L2 check** — see the alignment doc for what I did instead and how to run them (two commands).

## 10. Inconsistencies on flashyos.com itself (CONFIRMED, quoted from the pages)

1. `/aao`: "**Four** are static… **three** are runtime facts." `/conformance` (Level 2): "pass **all five** static questions." Both cannot be the count.
2. `/conformance`: "Today the suite reports flashyos.com at **Level 1**" — while the table on the same page lists flashyos.com "**L2 · 10 roles**" and says "Every property below is at Level 2."
3. `/open` marks `aao/0.1` "portable suite ✓" with a link to `…/packages/aao/conformance/suite.json` in a repository that returns 404. Same for the schema/suite links for `flashyos/1`, `frontdoor/1`, `directory/1`, etc.
4. `flashyos-spec`'s README describes a `profiles/` tree that is not in the repository.
5. `conformance-kit`'s README says `npx @flashyos/conformance-kit`; the package is not on npm.
6. The site says the charter is checked at `/.well-known/flashyos-charter.json` only in markup/graph data, not in the prose I read.

## 11. flashyos-wdk and wdk-staking-kit — relevant to AnalystOS?

**No — a different part of the ecosystem.** **CONFIRMED** from their READMEs: both are wallet/money-movement tooling for **Tether's WDK**. `flashyos-wdk` is "governed economic agency" (an authorization plane, an isolated signer, an agent object; **testnets only, by decision**; a public mirror of an Apache-2.0 subset; "not a partnership with Tether"). `wdk-staking-kit` is a staking primitive (a lock earmarks a balance at a published rate; only yield moves). AnalystOS holds no assets and makes no payments, and the mesh's own `wallet-wdk` capability is unrelated to reading a document and writing a report. The other two repos you named: `flashy-ledger` is an append-only multi-asset settlement ledger (the rules FlashyNetwork audits its books against); `flashyos-tools` is two tiny utilities ("which directory publishes at which URL"; "was a silent fetch the host or my proxy"), tied to a `.deploy/config.json` convention AnalystOS's Vercel setup does not use. Repos that exist but were not on your list and that I did **not** read: `agentfile` ("seven questions, three files at well-known paths" — *not released yet*), `mesh-lint`, `wdk-policy-guard`, `wdk-capability-audit`.
