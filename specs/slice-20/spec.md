# Slice 20 — the API: `api/analyze.py` (Flask, on Vercel)

## Goal

The first HTTP boundary: `POST /api/analyze` takes an uploaded document,
runs it through the exact same pipeline the CLI uses, and returns a cited
report - entirely in memory, nothing persisted. This is the piece that turns
AnalystOS from a CLI tool into something a browser can talk to.

## Included

- `analystos/pipeline.py` — extracted `build_report(source_path, schema,
  title, *, asks=None, template=None, currency_unit="actual",
  evidence_dir=None, extract_options=None)`: the actual pipeline, independent
  of job.json. `run_job` becomes a thin wrapper that reads a job folder and
  calls it. Fixed a real edge case found while refactoring: `asks=[]`
  (given, empty) was being treated the same as "not given" by a truthiness
  check - fixed to check `is None` explicitly.
- `api/analyze.py` — the Flask app and the one route
- `vercel.json` — explicit `functions` config for `api/*.py`, per Vercel's
  documented "file-based Python functions in /api" model (researched before
  writing code - see docs/decisions.md)
- `requirements.txt` — adds `flask==3.1.3`
- `tests/test_api_analyze.py` — via Flask's own test client

## Done when

1. A well-formed multipart upload (file + schema, template optional) returns
   200 with a rendered, cited section and an HTML page.
2. A missing file is a clean 400, not a crash.
3. An unsupported file extension is a clean 400.
4. A missing or invalid `schema` is a clean 400.
5. A pipeline error (e.g. a column named in `schema` that isn't in the file)
   becomes a 400 with that error's message, not a 500.
6. Nothing is left on disk after a request - checked directly (no
   `analystos-*` temp directory remains), on both success and failure.
7. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Verified beyond the test suite

Ran the Flask app as a real local server (`app.run()`) and hit it with an
actual `curl` multipart upload - a genuine HTTP round trip, not just the test
client - and got back a fully-cited, correctly-formatted report. Confirmed
directly on disk (not just via the test's own check) that no temp directory
survived the request.

## Not in this slice

- Deploying to Vercel itself and confirming it behaves identically there -
  that can only be verified once it's actually deployed; the code follows
  Vercel's documented Python-in-`/api` model as closely as research allowed,
  but this is real residual uncertainty, same category as the Root Directory
  picker surprise earlier.
- Auto-guessing `schema` from the upload - the caller (eventually, the
  upload page in Slice 21) must supply it. A real, scoped-out limitation.
- Access control - Slice 22. This endpoint is wide open once deployed.
- Selecting a specific sheet/table/slide via the API - the first one found
  is used, same defaults as the extractors themselves.
