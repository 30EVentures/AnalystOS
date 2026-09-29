# Slice 78 - the 30E Ventures studio bar and footer on the public site

## Goal

AnalystOS is a 30E Ventures product, but analystos.dev does not say so: a
visitor, a journalist or an agent landing on it cannot tell what studio is
behind it. 30eventures.com now presents the portfolio as one body of work.
This slice puts a shared, minimal studio identity on the AnalystOS pages so the
two sites visibly belong together, without changing AnalystOS's own look.

- **A studio bar** at the very top of each public page: the 30E mark and name
  (linking to https://30eventures.com), the line "AnalystOS is a 30E Ventures
  product", and links to the studio's Portfolio, About and Press pages. It is
  near-black with the studio's own colours in both light and dark themes, so it
  is the same strip on every product site.
- **A studio footer line** in each page's footer: who builds it, where, and the
  studio's Portfolio, About, Brand, Press and Contact links.
- **One source of truth.** The markup and its CSS are defined once, in
  `tools/studio_chrome.py`, and written into `site/index.html` and
  `site/upload.html` between explicit marker comments, the same way
  `tools/site_counts.py` keeps the homepage's numbers true. Editing a link means
  editing one place and running `python3 tools/refresh.py`.
- **Plain HTML and CSS.** No JavaScript, no external request, no new
  dependency: an agent that reads the page without running scripts sees the
  same studio identity a person does.

## Done when

- [ ] `python3 tools/studio_chrome.py` writes the bar, its CSS and the footer
      line into `site/index.html` and `site/upload.html`; running it twice
      changes nothing more (idempotent).
- [ ] `python3 tools/studio_chrome.py --check` exits 1 when a page's generated
      block differs from the source, and 0 otherwise. A page missing a marker
      is an error, never a silent skip.
- [ ] Each page has exactly one studio bar, one studio CSS block and one studio
      footer line, and all studio links point at `https://30eventures.com`.
- [ ] The bar is hidden in print, is legible at phone width without horizontal
      scroll, and uses no inline script and no third-party request.
- [ ] `tools/refresh.py` runs the new step, so the one command still fixes
      everything generated.
- [ ] `docs/decisions.md` records why the bar is generated markup and not a
      script include or a copied snippet.
- [ ] The full suite reports `OK`.

## Not in this slice

- **No change to AnalystOS's own header, fonts, colours or wording.** The bar
  sits above them; it does not replace them.
- **No change on 30eventures.com.** That site already lists AnalystOS; this
  slice does not add anything to it or read anything from it.
- **No claim beyond what is true today:** the studio's name, that it is in
  Toronto, and that AnalystOS is one of its products. Nothing about funding,
  customers or scale.
- **No machine-file changes** (`llms.txt`, `api-catalog`, the mesh handshake).
  Whether and how the studio should appear there is a separate decision.
- **The docs pages** served from `site/docs/` are markdown and are unchanged.
