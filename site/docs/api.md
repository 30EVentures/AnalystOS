# AnalystOS API (v1)

Base: `/api/v1`. Machine-readable description: `GET /api/v1/openapi.json`;
index of endpoints: `GET /api/v1`. Errors are always
`{"error": {"code": "...", "message": "..."}}`.

| Method and path | Auth | What |
|---|---|---|
| `GET /api/v1` | none | index: version, endpoints, limits |
| `GET /api/v1/openapi.json` | none | OpenAPI 3.1 |
| `POST /api/v1/analyses` | API key | upload one document (`multipart`, field `file`, optional `title`); returns the report, its seal and, if storage is configured, links |
| `GET /api/v1/reports/{id}?format=html\|pdf\|seal` | API key (creator) or signed link | fetch a stored report |
| `POST /api/v1/links` | API key (creator) | `{"id","format","ttl_seconds"}` -> an expiring signed URL |
| `GET /api/v1/verify/{id}` | none | seal metadata only (payload, signature info) |
| `POST /api/v1/verify` | none | `{"bundle", "public_key"?, "text"?}` -> verification result (stateless) |

## A call, end to end

```bash
curl -s -H "Authorization: Bearer $KEY" -F file=@report.pdf https://analystos.dev/api/v1/analyses
# -> 201 {"id": "<64 hex>", "tier": "written", "counts": {...}, "seal": {...}, "html": "...", "links": {...}}

curl -s -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
     -d '{"id":"<id>","format":"html","ttl_seconds":3600}' https://analystos.dev/api/v1/links
# -> 201 {"url": "https://analystos.dev/api/v1/reports/<id>?format=html&exp=...&sig=...", "expires": "..."}
```

That `url` is what a FlashyOS task completion takes as `evidenceUrl`; the `id`
is the digest to carry alongside it. Whoever receives it can check the seal with
`POST /api/v1/verify` or, offline, `python3 -m analystos.l4.seal_verify`
(`docs/seal.md`).

## Default: nothing is kept

AnalystOS keeps no reports on a server by default (decision by 30E Ventures,
2026-09-26): the upload is deleted when the request ends and the result comes
back in the response, for the caller to save. `POST /api/v1/analyses` returns
the report (`html`) and its seal (`seal`); add `include_pdf=true` to also get the
generated PDF as `pdf_base64`. The hosted upload page does the same and saves the
report, the PDF and the seal to the reader's own Downloads folder.

For the mesh this means whoever receives a seal hosts it themselves. A seal
verifies anywhere (`docs/seal.md`), so a task's `evidenceUrl` can point at the
requester's own storage. Server-side storage and signed links, below, are
optional and stay off unless `ANALYSTOS_STORE_DIR` is set.

## The `id`

`sha256(canonical(seal payload))`. The payload holds the Merkle root, the source
and text hashes, the tier, a timestamp and a random nonce, so every analysis gets
its own id.

## Configuration (environment)

| Variable | Needed for | If unset |
|---|---|---|
| `ANALYSTOS_API_KEYS` | any authenticated call: comma-separated `name:sha256hex` | every authenticated call is a 503 (fails closed) |
| `ANALYSTOS_STORE_DIR` | *optional*: storing reports, links, `GET /reports`, `GET /verify/{id}`, the audit log file | the default: responses carry the report and seal inline; those routes are 503 `store_not_configured`; audit lines go to stderr |
| `ANALYSTOS_LINK_SECRET` | `POST /links` and honouring links | 503; no default secret |
| `ANALYSTOS_SEAL_KEY` | signing seals (`python3 -m analystos.l4.seal keygen`) | unsigned seals (integrity only), and they say so. A *malformed* value is a 503, not a downgrade |
| `ANALYSTOS_REPORT_TTL_DAYS` | retention of stored reports | 30 |
| `ANALYSTOS_PUBLIC_BASE_URL` | the host used in issued links | derived from the request (`X-Forwarded-*`) |
| `ANTHROPIC_API_KEY` | the analysis itself | as for `/api/analyze` |

Make a caller key (shown once, stored nowhere):

```
python3 -m analystos.api_v1 newkey partner-name
```

## Behaviour worth knowing

- **Synchronous.** One request runs the whole pipeline and is bounded by the
  host's function time limit, exactly like `/api/analyze`.
- **The upload is deleted** when the request ends. Document text is sent to
  Anthropic's API for the analysis.
- **Access.** A stored report is readable by the API key that made it, or via a
  signed link for one report, one format and an expiry (60 seconds to 7 days,
  never beyond the report's own expiry). Somebody else's report is
  indistinguishable from a missing one. Report pages are served with a locked-down
  `Content-Security-Policy`, `no-store`, and `nosniff`.
- **Rate limit.** The same per-IP limiter as the rest of the app (in-memory per
  process; see `docs/audit-2026-09-25.md` finding 11).
- **Storage is not durable on Vercel.** `FileStore` writes to the local
  filesystem. A production deployment needs a persistent volume, or an adapter
  with the same methods (`put`, `meta`, `read`, `purge_expired`, `append_audit`,
  `read_audit`) for an object store. Until then treat stored reports as
  short-lived.

## Audit log and the charter's measures

Every analysis, view and link appends one JSON line (`audit.jsonl` in the store,
else stderr): caller name, report id, tier, fallback reason, proposed / verified /
dropped counts, whether the seal was signed and re-verified. **No document text and no
filename.** The three measures in the published charter are computed from it:

```
python3 -m analystos.api_v1 measures [audit.jsonl]
```

Each is `{numerator, denominator, share}` and `share` is `null` on an empty log,
never a made-up 100%. A test keeps the measure wording identical to the published
charter.

## Vercel routing

Vercel maps one file to one path, so each route has a door in `api/v1/`
(`index`, `analyses`, `reports`, `links`, `verify`, `openapi`) that imports the
shared Flask app, and `vercel.json` rewrites `/api/v1/openapi.json`,
`/api/v1/reports/:digest` and `/api/v1/verify/:digest` onto them. The routes
accept both the pretty path and the `?digest=` form. **Not verified on Vercel
until deployed** (a test proves the doors and rewrites exist and agree, not
that Vercel forwards the paths as expected).
