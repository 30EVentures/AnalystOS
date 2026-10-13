# Slice 91 - the homepage's machine-discovery links work from every domain that serves it

## Goal

The AnalystOS homepage is served on `analystos.dev` and also proxied at `https://www.30eventures.com/analystos/`.
Its `<head>` advertises the API catalog and `llms.txt` with root-relative links. On the studio domain those
resolve to the studio's own site: `/.well-known/api-catalog` is a 404 there, and `/llms.txt` is the studio's
file, not AnalystOS's. An agent that discovers AnalystOS through the studio gets nothing, or the wrong thing.
Make the two links absolute so they name AnalystOS's own files from wherever the page is read.

## Done when

1. In `site/index.html`, `rel="api-catalog"` points at `https://analystos.dev/.well-known/api-catalog` and the
   `rel="alternate"` llms.txt link at `https://analystos.dev/llms.txt`.
2. `tests/test_site_machine.py` pins the absolute hrefs, and a new test fails if any `<link>` in the homepage
   `<head>` that advertises a machine file is root-relative.
3. The full suite reports OK.

## Not in this slice

- The studio site serving its own `/.well-known/api-catalog` (that would claim AnalystOS's catalog as the studio's).
- Changing `canonical`, Open Graph or the page body.
