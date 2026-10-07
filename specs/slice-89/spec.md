# Slice 89 - a deployed-bytes check: are the live files the repository's files? (Flashy integration J3)

## Goal

`tools/smoke.py` checks that a deployment serves the advertised surface with the right content types. It
does not check that the bytes are the ones in the repository, so a stale CDN copy or a deploy that missed a
file looks healthy. `python3 tools/smoke.py [BASE_URL] --deployed [--json]` GETs the live URL of every
machine-readable file under `site/` and compares bytes with the file.

## Done when

1. Each file is reported as exactly one of **SAME** (200, identical bytes), **DIFFERS** (200, other bytes),
   **UNREACHABLE** (no HTTP answer: DNS, connect, timeout, or a body cut short of its Content-Length) or
   **REFUSED** (an answer that is not a comparable 200: another status, a redirect to a different scheme or
   host, a redirect loop, a body over the size cap, a Content-Encoding we did not ask for). The states are never
   merged, in text or in `--json`.
2. Any state other than SAME is a nonzero exit; so is checking zero files; a certificate Python cannot verify is
   exit 2 with the existing TLS help (verification is never disabled).
3. Standard library only; timeouts; a body size cap; `Accept-Encoding: identity` so bytes are comparable; no
   cookies or credentials; same-host redirects only, never another host.
4. `--deployed` cannot be combined with the other modes (usage error, exit 2).
5. Unit tests run against a local `http.server` fixture (same, differs, 404, 500, timeout, nothing listening,
   truncated body, redirect to another host, redirect loop, oversize, gzip), with no real network.
6. Run once against the real site, reported in `docs/decisions.md`.

## Not in this slice

- Comparing the dynamic API responses (`/api/v1`, `/api/v1/openapi.json`); only static files are compared.
- Running it from CI or on a schedule.
