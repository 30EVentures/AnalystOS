# AnalystOS

An operating system for the analyst's core loop: gather evidence, impose
structure on it, reason across it, produce a defensible answer, and keep a
trail that survives review. Its one rule: every figure in a report is a
verbatim quote checked against the source or a calculation recomputed by code,
and the report is sealed so anyone can re-verify it offline.

## Status

Early stage. Not ready for confidential documents (one shared access code plus
per-caller API keys; no per-user accounts, SOC 2 or external review). What is
built and what is not, layer by layer: [`docs/architecture.md`](docs/architecture.md).
Plan: [`ROADMAP.md`](ROADMAP.md). Code-verified audit of the claims:
[`docs/audit-2026-09-25.md`](docs/audit-2026-09-25.md).

**Live:** [analystos.dev](https://analystos.dev) - the homepage (`site/index.html`)
and an upload page, deployed on Vercel from `main` (Output Directory: `site`).

## Getting started

Requires Python 3.11+ (developed on 3.14). Dependencies are pinned in
`requirements.txt`, each with a reason in `docs/decisions.md`.

```
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v      # must report OK
python3 -m analystos fixtures/golden          # the worked example
```

Run it on your own document: [`docs/using-analystos.md`](docs/using-analystos.md).

## Find your way (people and machines)

| You want | Read |
|---|---|
| To call it from another program | [`docs/api.md`](docs/api.md), `GET /api/v1/openapi.json` |
| To check a report you were given | [`docs/seal.md`](docs/seal.md), `python3 -m analystos.l4.seal_verify` |
| The FlashyOS mesh side | [`docs/mesh-identity.md`](docs/mesh-identity.md), [`docs/aao.md`](docs/aao.md) |
| Why a choice was made | [`docs/decisions.md`](docs/decisions.md) |
| What each slice was for | `specs/slice-N/spec.md` |
| An index for an AI agent | [`site/llms.txt`](site/llms.txt) (served at `/llms.txt`) |

## Layout

| Path | What's in it |
|------|--------------|
| `analystos/l0`-`l4` | the layers: store, read, reason, deliver (and the seal) |
| `analystos/aao/` | the AAO charter checker, its pinned schema, a conformance-kit adapter |
| `analystos/api_v1/` | the agent-callable API (routes, keys, links, store, audit) |
| `api/` | Vercel doors; one file per route |
| `site/` | the public site, the well-known mesh files, and generated machine files |
| `docs/` | guides, the decision log, the audit (single source for `site/docs/`) |
| `specs/` | one folder per slice: goal, scope, "done when" |
| `tests/` | the automated suite (no network, no cost) |
| `live_tests/` | a manual suite with real, paid model calls under a $1.00 ceiling |
| `tools/` | `build_site_machine.py` regenerates the machine files from `docs/`; `refresh.py` regenerates all of these in order; `smoke.py` checks a live deployment; `site_counts.py` keeps the homepage's test and spec counts true; `build_specs_index.py` regenerates the spec index; `studio_chrome.py` keeps the 30E Ventures bar and footer line on the public pages; `build_flashyos_handshake.py` derives the handshake's capabilities from the charter; `build_measures.py` builds a measures/1 document; `defined_proxy_validator.py` checks `drafts/defined-analystos.json` against the documented (unpublished) defined/1 rules |
| `tools/flashyos-check/` | pinned, gitignored `node_modules/` for the real `@flashyos/*` packages some tests validate against (`npm install --ignore-scripts` once per checkout, like the Python venv) |
| `fixtures/golden/` | the regression set; add cases, never edit existing ones |
| `drafts/` | files validated against a real or documented FlashyOS format but not yet served - never under `site/`, so a deploy can't publish one by accident; see `drafts/README.md` |
| `mcp-server/` | AnalystOS's own MCP server (Slice 100) - not routed through `@flashyos/mcp`, not deployed; `npm install --ignore-scripts` once, then `node --test test.mjs` |
| `findings/` | the 30E Ventures findings register (Slice 101): schema, validator, generator. `registry.json` holds one template entry only - the real findings are not in this repository; see `findings/README.md` |
| `.shiplog/config.json`, `vendor-shiplog.mjs`, `shiplog.fragment.json`, `devlog.fragment.json`, `DEVLOG.md` | this repository's own shipped/1 and devlog/1 record, adopted with `@flashyos/shiplog` (Slice 99); committed and private, never served - `drafts/devlog.fragment.json` is the public projection, currently empty on purpose |

## Working here

One slice at a time, a `specs/` folder written before the code, small commits
on a branch, a pull request, never a commit to `main`. After editing docs, adding
tests or adding a spec, run `python3 tools/refresh.py` (it regenerates the site's machine
files, the spec index and the homepage's counts in the right order; `--check` only
reports). The suite fails if any of them is stale. After a deploy, run `python3 tools/smoke.py` (see `docs/mesh-identity.md`). See `CLAUDE.md`.
