# Slice 130 - dropdown navigation, the AnalystOS footer, an institutional look, a glossary

## Goal

The owner's comments on the 30E Ventures site (2026-11-24), applied to AnalystOS
(2026-11-25): "it looks too ai generated, reverse engineer a fortune 10 website",
"in the subsections add dropdown options", "glossary add more", "make a footer for
analystOS: add concepts, glossary, press, reverse engineer fortune 10 navigation",
"show me mocks before we push"; and, approving the plan, "add dropdowns in the
sections at the top". The owner approved the plan and then the local mock.

## What changes

- **Header** (`tools/studio_chrome.py`, one source for every page): five top
  sections, each a full-width dropdown in the 30E Ventures pattern - Roles (the 13
  families with role count and format, from the catalog), Samples, How it works, For
  agents, Learn - and a "Hire a specialist" button. `site/nav.js` opens on hover or
  click, closes on Escape (focus returns to the menu's button), outside click or tabbing
  away; a phone drawer below 860px. Without the script the menus do not open; the footer
  still links every page's main sections.
- **Footer**: the `analystos-footer` branch (built 2026-11-24 by the 30E site session,
  never merged), brought up to date: today's headline, roles and samples, the
  AnalystOS glossary, studio Concepts, glossary, Why, FAQ, Press.
- **Look**: the 30E Ventures system - serif headings from system fonts, ink on paper,
  square buttons, rules instead of rounded cards, underlined family tabs. The pill
  badge and Google Fonts are gone from every page. Content and numbers are unchanged.
- **Glossary** (`site/glossary.html`): 35 AnalystOS terms in five groups with a filter;
  counts tied to the catalog by test; listed in llms.txt and the sitemap.
- **Explorer links**: `/?family=<id>&role=<id>#samples` opens on that family and role.
- The details page keeps its section bar and theme button under the new header.

## Done when

- [x] Every top section is a dropdown; every menu link resolves to a served file,
      anchor, API path or the studio site; family and role links name real ones.
- [x] Every page has the header once and only the same-origin `nav.js`; no Google Fonts.
- [x] The menu script writes no HTML; Escape closes menus and the drawer.
- [x] The glossary's role, family and work-product counts match the catalog.
- [x] The owner saw the local mock (desktop and phone) before any push.
- [x] Full suite OK, `refresh.py --check`, `build_samples.py --check`, Flashy fence.

## Not in this slice

- The 30E site's own AnalystOS card still uses the old tagline (other repository).
