# Slice 98 - a defined/1 vocabulary fragment for AnalystOS's own terms

## Goal

The 18 Nov integration document found that no consulting, diligence or
analyst-work term is owned by anyone in the Flashy estate's term map or AUTHORITY
register - an open application-layer vocabulary AnalystOS could define in its own
words. Draft the three terms it can own outright (not the six that would sit beside
an estate term by link, which need the estate's own citation machinery to mean
anything) and check them against the documented rules, honestly, since there is no
real checker to run.

## Done when

1. `drafts/defined-analystos.json` defines exactly the three terms AnalystOS owns
   outright: analyst agent, decision-grade output, deliverable acceptance criteria.
2. `tools/defined_proxy_validator.py` checks the documented rules - 40-700 character
   definitions, `expires` exactly `asserted`+365 days, `https://` basis URLs, the
   fourteen forbidden keys at any depth, the seven forbidden keys on a citation -
   and says plainly in its own module docstring that it is a proxy for an
   unpublished, unverifiable real checker (`@flashyos/defined` 404s on npm, checked
   2026-11-21), never a conformance guarantee.
3. Every rule is proven to actually fire with a constructed violation, not only
   asserted against the one real fragment (`tests/test_defined_fragment.py`).
4. `deliverable-acceptance-criteria` links `decision-grade-output` via `seeAlso`
   rather than restating it, matching the estate's own "one owner per term, link
   don't copy" rule even though there is no real checker to enforce it here.
5. The known gap is checked for, not assumed away: the `basis` URLs
   (`https://analystos.dev/defined/<slug>`) do not resolve, because the three
   pages do not exist in `site/` yet - this is exactly the mistake the 18 Nov
   document said not to repeat (mlgblockchain's six dead `/defined/<slug>` links),
   and `ROADMAP.md` records it as unresolved rather than silently fixed.

## Not in this slice

- Writing the three `/defined/<slug>` pages this fragment's `basis` points at, or
  serving the fragment anywhere. Both need a decision (serve the pages first, or
  the owner decides the fragment goes out with 404 basis links until then - not
  something a loop should choose).
- The six terms that would sit beside an existing estate term (governed agent,
  agent team, evidence trail, outcome-based pricing, analyst-hour equivalent,
  named sign-off). Those need the estate's own `canon.lock.json`/citation
  machinery to link correctly, which this session did not build.
- Checking "decision-grade" for trademark conflicts before anything is published -
  a separate task (see `ROADMAP.md`), not blocked by this one.
