# AnalystOS API (v1)

Base: `/api/v1`. Machine-readable description: `GET /api/v1/openapi.json`;
index of endpoints: `GET /api/v1`. Errors are always
`{"error": {"code": "...", "message": "..."}}`.

| Method and path | Auth | What |
|---|---|---|
| `GET /api/v1` | none | index: version, endpoints, limits |
| `GET /api/v1/openapi.json` | none | OpenAPI 3.1 |
| `POST /api/v1/analyses` | API key | upload one document (`multipart`, field `file`, optional `title`); returns the report, its seal and, if storage is configured, links |
| `POST /api/v1/jobs` | API key | same upload; returns immediately, `202 {"id","status":"pending"}` - no model calls yet |
| `POST /api/v1/jobs/{id}/run` | API key (creator) | run a pending job (idempotent once no longer pending) |
| `GET /api/v1/jobs/{id}` | API key (creator) | poll a job's status; never executes anything |
| `GET /api/v1/reports/{id}?format=html\|pdf\|seal` | API key (creator) or signed link | fetch a stored report |
| `POST /api/v1/reports/{id}/review` | API key (creator) | `{"approved"?: bool}` -> record that a human reviewed this report |
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

## Async jobs

`POST /api/v1/analyses` holds one connection open for the whole pipeline.
For an agent that would rather not do that, `/jobs` splits it into three
calls:

```bash
curl -s -H "Authorization: Bearer $KEY" -F file=@report.pdf https://analystos.dev/api/v1/jobs
# -> 202 {"id": "<32 hex>", "status": "pending", "created": "..."}

curl -s -X POST -H "Authorization: Bearer $KEY" https://analystos.dev/api/v1/jobs/<id>/run
# -> 200 {"id", "status": "done", "created", "report_id": "<64 hex>", "links": {...}}

curl -s -H "Authorization: Bearer $KEY" https://analystos.dev/api/v1/jobs/<id>
# -> 200 {"id", "status": "done", "report_id", "links"}   (or "pending" / "running" / "failed": {"error"})
```

Once `status` is `done`, `links` and `report_id` work exactly like
`/analyses`'s - `GET /reports/{id}`, `POST /reports/{id}/review`,
`POST /links`, `GET|POST /verify` - because a finished job's result is
stored through the same report store, not a separate mechanism.

**This is not a background worker.** `/run` executes the same pipeline
`/analyses` does, in one bounded call with the same time ceiling - Vercel
runs nothing between requests. What changes is *when* that call happens:
the upload is accepted (and can sit safely, briefly, in the job store)
before the caller commits to waiting on the actual analysis, and the
caller can poll `GET /jobs/{id}` afterward instead of holding the original
connection. A document whose analysis alone exceeds the platform's ceiling
still fails at `/run` exactly as it would at `/analyses`. Calling `/run`
again on a job that is no longer `pending` never re-runs it - it just
returns the current status.

The uploaded file is kept only between `POST /jobs` and `POST /jobs/{id}/run`
(deleted the moment `/run` finishes, success or failure) - the same "nothing
kept longer than it has to be" rule as `/analyses`, just delayed by one
extra request. A `pending` job that is never run is not purged automatically
(see `ROADMAP.md`).

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
| `ANALYSTOS_MODEL` | *optional*: which model every stage asks (default `claude-sonnet-5`). Recorded in each audit event | the default |

Make a caller key (shown once, stored nowhere):

```
python3 -m analystos.api_v1 newkey partner-name
```

## Behaviour worth knowing

- **Synchronous.** One request runs the whole pipeline and is bounded by the
  host's function time limit, exactly like `/api/analyze`. `/jobs` (above)
  splits submit from run from collect, but `/run` is still one such call -
  see "Async jobs" for exactly what that does and doesn't fix.
- **Jobs need `ANALYSTOS_STORE_DIR`.** Unlike `/analyses`, which can run with
  no store configured (the result just comes back inline), `/jobs` has
  nowhere to hold the upload between "submit" and "run" without one - `POST
  /jobs` is 503 `store_not_configured` if it's unset.
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

## Human review

The intended shape: an agent calls `/api/v1/analyses` and gets the report
back; a human reviews it. `POST /api/v1/reports/{id}/review` (optional body
`{"approved": true|false}`) records who reviewed a report and when -
same auth and ownership rule as fetching the report. It does not gate
anything: a report is deliverable and verifiable whether or not it has been
reviewed. The recorded review (or `null`) is returned by
`GET /api/v1/verify/{id}` alongside the seal metadata. Reviewing again
overwrites who/when/approved.

## Audit log and the charter's measures

Every analysis, view, link, review and job appends one JSON line (`audit.jsonl`
in the store, else stderr): caller name, report id, tier, fallback reason,
proposed / verified / dropped counts, the model used, whether the seal was
signed and re-verified. A job run's `analysis` event is identical to
`/analyses`'s, plus `"via": "job"`, so it counts toward the measures below the
same way; `job_created` and `job_failed` are separate event types. **No
document text and no filename.** The three measures in the published charter
are computed from it:

```
python3 -m analystos.api_v1 measures [audit.jsonl]
```

Each is `{numerator, denominator, share}` and `share` is `null` on an empty log,
never a made-up 100%. A test keeps the measure wording identical to the published
charter.

### The log is a hash chain (Slice 84)

Each line is chained to the one before it (`seq`, `prev_hash`, `entry_hash`) and,
when `ANALYSTOS_SEAL_KEY` is set, signed (`signature`, `key_id`; Ed25519 over the hash
with the domain `analystos.audit-entry/1`). With no key, lines are chained and say
`"log_signing": "none"`. Check a log offline:

```
python3 -m analystos.api_v1 verify-audit audit.jsonl [--public-key B64URL] [--expect-head HASH]
```

Exit `0` if no check failed, `1` if one did, `2` for unreadable input. Editing, deleting,
reordering or inserting a line fails the `chain` check. `authentic` is true only when every
line is signed and verifies under a public key **you** supplied. Lines written before the
chain existed are tolerated as a prefix; an empty or legacy-only log fails (nothing to
verify). Tamper-evident, not tamper-proof: a shortened log is only caught if you pin the
`head` you saw earlier (`--expect-head`), and a holder of the signing key can re-sign a
rewritten tail. Event fields are unchanged; the chain fields are added.

## Vercel routing

Vercel maps one file to one path, so each route has a door in `api/v1/`
(`index`, `analyses`, `jobs`, `reports`, `links`, `verify`, `openapi`) that imports
the shared Flask app, and `vercel.json` rewrites `/api/v1/openapi.json`,
`/api/v1/reports/:digest`, `/api/v1/reports/:digest/review`, `/api/v1/verify/:digest`,
`/api/v1/jobs/:job` and `/api/v1/jobs/:job/run` onto them. The routes accept both
the pretty path and the `?digest=`/`?id=` form. **Verified on the deployed site, 2026-09-26:** `/api/v1`,
`/api/v1/openapi.json` and both forms of the `reports` and `verify` routes reach
the app (an unconfigured store answers 503 `store_not_configured`, an unconfigured
key set answers 503 `unavailable`, as designed). Not yet exercised in production: a
real analysis upload, and the jobs routes added in Slice 74.
