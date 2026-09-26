# Slice 62 - navigable by machines; documentation brought up to date

## Goal

The user's ask: "add tests and documentation to everything; make it super easy
to navigate natively for machines." An agent (or a person's script) arriving at
analystos.dev should be able to find, without scraping a marketing page: what
this is, how to call it, how to check its output, and who is accountable.

Published, all generated from one source so nothing drifts:

- `/llms.txt` - the llms.txt convention: one H1, a one-line summary, then
  linked sections (API, verification, identity, docs, limits).
- `/llms-full.txt` - the same documentation concatenated for one fetch.
- `/docs/*.md` - the guides as markdown (`api`, `seal`, `aao`, `mesh-identity`,
  `architecture`, `using-analystos`), served as `text/markdown`. Copies of
  `docs/`, which stays the single source.
- `/.well-known/api-catalog` - RFC 9727 linkset pointing at the OpenAPI
  document (`/api/v1/openapi.json`) and the API guide.
- `/sitemap.xml` and `/robots.txt` (crawlers allowed; `/api/` excluded).
- `<link rel>` hints in the homepage head for `api-catalog`, `llms.txt`.
- `tools/build_site_machine.py` generates all of the above; `--check` exits 1
  if any generated file is stale. A test runs the check, so a doc edit that is
  not re-published fails the suite.

Documentation brought up to date (the audit's docs-vs-code table):
`README.md` (status, dependencies, layout, docs index), `docs/architecture.md`
(a real "current state" instead of "nothing built yet"), `ROADMAP.md` (slices
29-62 recorded), `docs/using-analystos.md` (seal, API pointers), and the public
test/spec counts on the homepage.

## Not in this slice

- Rendering the markdown to HTML pages (a converter would be a dependency for
  no machine benefit; markdown is what agents want).
- `security.txt` (needs a decision on a disclosure contact and policy).
- Deploying anything.

## Done when

1. `--check` passes on a clean tree and fails when a source doc is edited.
2. Every URL listed in `llms.txt` and the sitemap resolves to a file in `site/`
   (or a documented API route).
3. The API catalog is valid linkset JSON whose links point at real documents.
4. Homepage `<link>` hints and `vercel.json` headers exist for the new types.
5. README/architecture no longer say "nothing built" / "no third-party packages".
6. Full suite OK.
