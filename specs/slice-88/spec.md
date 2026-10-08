# Slice 88 - a test that the site's machine-readable surface agrees with itself (Flashy integration J2)

## Goal

The 2026-10-07 audit confirmed a contradiction no test covered: `site/robots.txt` said `Disallow: /api/`
while the sitemap, `llms.txt` and the API catalog advertised `/api/v1` and `/api/v1/openapi.json`. An
agent or crawler that obeys robots.txt is told not to fetch the entry points the site tells it to use.
Add the missing class of test, and fix the contradiction in the generator.

## Done when

1. `tests/test_site_consistency.py` parses `robots.txt` (RFC 9309: longest match wins, Allow wins a tie,
   `*` and `$`), `sitemap.xml`, `llms.txt`, `llms-full.txt`, `.well-known/api-catalog`, the
   `.well-known/flashyos*.json` and `flashyos.roles.json` files, the homepage `<link>` tags, the served docs
   and the OpenAPI document, and asserts:
   - nothing the site advertises as a GET-able URL is disallowed for `User-agent: *`;
   - every advertised same-site path (and each OpenAPI path) is a file under `site/`, a `vercel.json` rewrite
     or an `api/` function, and every advertised in-page anchor exists;
   - every markdown link in the served docs resolves;
   - `vercel.json` has a Content-Type (and CORS) header rule for every `.well-known` file.
   The checks are not vacuous (they assert how many URLs they saw) and the robots matcher is itself tested.
2. Before the fix the test fails on exactly the known contradiction (`/api/v1` and `/api/v1/openapi.json`).
3. The fix is made in `tools/build_site_machine.py` (robots.txt is generated), by adding more specific
   `Allow:` lines for the two advertised entry points and keeping `Disallow: /api/` for the rest, then
   regenerating. `vercel.json` routing is not touched.

## Not in this slice

- Any change to `vercel.json`, including the 405-versus-404 behaviour of POST-only routes (recorded in
  `docs/decisions.md`).
- Allowing `POST /api/v1/verify` in robots.txt: it is advertised as an instruction to an agent, not as a link
  for a crawler, so the test checks that it is routed, not that it is crawlable.
