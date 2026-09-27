# Slice 68 - a post-deploy smoke script (roadmap Q5)

## Goal

After the Slice 63 deploy the checks that mattered (does Vercel serve
`.well-known`, do the rewrites reach the app, is the API closed, does the live
charter validate) were run by hand with curl. They should be one command that
anyone can run against any deployment, so "deployed" stops meaning "the build
went green" and starts meaning "the advertised surface works".

`python3 tools/smoke.py [BASE_URL] [--json] [--no-post]` (default
`https://analystos.dev`; standard library only) checks:

- every URL a deployment advertises (the generated machine files, the mesh
  identity files, the docs, the homepage and upload page) returns 200 with the
  intended content type;
- the JSON files parse; the live charter passes `analystos.aao`; the handshake's
  slug equals the charter's; the two charter paths are byte-identical;
- every link in `llms.txt` and every URL in the sitemap resolves;
- `/api/v1` and `/api/v1/openapi.json` are well-formed and agree;
- the rewritten `reports`/`verify` routes reach the app (both the pretty path and
  the `?digest=` form) and fail *closed* (not 200) for an unknown id;
- unless `--no-post`: an analysis without a key is refused (401/503, never 200 or
  5xx-crash), and `POST /verify` with junk answers `ok: false`;
- nothing sends a document, a key or any secret; the two POSTs carry no data.

Exit code 0 if every check passes, 1 otherwise; `--json` prints a machine-readable
result list.

## Not in this slice

- Authenticated checks (a real analysis needs a key and spends money).
- Running it automatically in CI or after each deploy.

## Done when

1. Against a local server that mimics Vercel's routing and header rules from
   `vercel.json` plus the real Flask app, every check passes.
2. It fails, naming the check, for: a missing file, a wrong content type, an invalid
   charter, an API that answers 200 without a key, and a dead link in `llms.txt`.
3. `--json` output is parseable and `--no-post` sends no POST.
4. Full suite OK (no external network).
