# Slice 61 - an API an agent can call: analyses, sealed reports, verification

## Goal

Roadmap Phase 2 (`docs/flashyos-alignment-2026-09-25.md`). The mesh completes a
task with an https evidence URL and an optional digest, and FlashyOS's own
guidance says never to put document contents on the mesh. So AnalystOS needs
an endpoint another agent can call, a durable access-controlled URL for the
result, and a way for a stranger to check it. All under `/api/v1`.

| Method and path | Auth | What |
|---|---|---|
| `GET /api/v1` | none | machine-readable index: version, endpoints, links |
| `GET /api/v1/openapi.json` | none | OpenAPI 3.1 description of everything here |
| `POST /api/v1/analyses` | API key | upload one document; get the report, its seal, and (if a store is configured) links |
| `GET /api/v1/reports/{id}` | API key (creator) **or** signed link | `?format=html\|pdf\|seal` (the PDF the audit found the API never exposed) |
| `POST /api/v1/links` | API key (creator) | an expiring signed URL for one report and one format - the mesh's `evidenceUrl` |
| `GET /api/v1/verify/{id}` | none | seal metadata only (payload + signature info), never the report |
| `POST /api/v1/verify` | none | check any seal bundle offline logic (`docs/seal.md`); stateless |

Decisions:

- **Per-caller API keys**, not the shared access code: `ANALYSTOS_API_KEYS` is
  `name:sha256hex` pairs; the raw key is shown once by
  `python3 -m analystos.api_v1 newkey <name>` and never stored. No keys
  configured means the service refuses (fail closed).
- **Sync only.** One request runs the whole pipeline, so it is bounded by the
  platform's function time limit, as `/api/analyze` already is. Async jobs are
  a later slice.
- **Storage is optional and honest.** `ANALYSTOS_STORE_DIR` enables a file
  store (reports, PDF, seal, audit log). Without it the response still carries
  the report and the seal inline, `links` are absent, and `GET /reports` and
  `GET /verify/{id}` return 503 `store_not_configured`. Vercel's filesystem is
  not durable; a production store needs a persistent volume or an object-store
  adapter for the `FileStore` interface. **This slice does not provide durable
  hosted storage.**
- **Retention.** Stored reports expire after `ANALYSTOS_REPORT_TTL_DAYS`
  (default 30) and are purged.
- **Links.** Signed with `ANALYSTOS_LINK_SECRET` (no default; unset means
  `POST /links` returns 503). A link names one report, one format and an
  expiry (60 s to 7 days).
- **Seal key.** `ANALYSTOS_SEAL_KEY` as in Slice 60. A *malformed* configured
  key is a 503, never a silent downgrade to unsigned.
- **Audit log** (append-only JSONL in the store; else one JSON line to stderr):
  analysis (caller, tier, fallback reason, proposed/verified/dropped, signed,
  seal self-check), view, link. No document text, no filename. The charter's
  three measures are computed from it: `python3 -m analystos.api_v1 measures`.
- Errors are `{"error": {"code": "...", "message": "..."}}`.
- Vercel needs one file per route (see Slice 20/`test_api_vercel_routing`);
  `api/v1/*.py` are thin doors into one Flask app, and a test keeps them in
  step with the routes.

## Not in this slice

- Durable hosted storage; async/queued analyses; per-key spend caps (the
  existing per-IP limiter applies); webhooks; deployment; pricing.
- Anything on the mesh side (tokens, capability declaration): Phase 3.

## Done when

1. Every route works through Flask's test client with a mocked model: create,
   fetch (html/pdf/seal), link, verify (both), index, openapi.
2. Auth: no key, wrong key, and another caller's key are refused; unset key
   config fails closed; a link works without a key but only for its own
   report and format, and expired or tampered links are refused.
3. The upload is deleted and the audit log never contains document text or a
   filename; reports expire and purge.
4. The OpenAPI document covers every route and the index links resolve.
5. Every route has a Vercel door file.
6. `measures` reproduces the three charter measures from a known log.
7. A response's seal verifies with the standalone verifier.
8. Full suite OK.
