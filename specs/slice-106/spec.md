# Slice 106 - the public devlog, with a real privacy leak found and closed before it shipped

## Goal

Owner's decision, 2026-11-22: flip `.shiplog/config.json`'s `visibility` to
`public` and actually serve the record (not leave it parked in `drafts/`
forever). Doing this for real - re-deriving the whole history against the
new setting, not just new entries - surfaced a real problem before anything
went live: the vendored tool faithfully reproduces git history, and this
repository's early history includes merge-commit titles GitHub generated
from the owner's personal GitHub fork name (`CalebSolway/...`), plus this
session's own commit trailers (`Co-Authored-By: ... <noreply@anthropic.com>`,
`Claude-Session: ...`) riding inside the free-text `detail` field. Both
conflict with the standing rule: public identity is 30E Ventures only.

## Done when

1. `.shiplog/config.json`'s `visibility` is `public`; every entry in
   `shiplog.fragment.json`/`devlog.fragment.json` is re-derived against it
   (`--rederive`, not just new entries appended with the old private stamp).
2. The served projection moves from `drafts/devlog.fragment.json` to a real
   path, `site/.well-known/devlog.fragment.json`, with the matching
   `Content-Type`/CORS/`Cache-Control` headers in `vercel.json` every other
   `.well-known/*` file gets.
3. `tools/redact_served_devlog.py` cleans the served copy (never the full,
   private source) in two different ways for two different problems: an
   entry whose title or detail names the owner personally is dropped
   outright; an entry that only carries a commit trailer has `detail`
   truncated at the trailer, keeping the real written summary. The two are
   not the same fix - dropping every trailer-carrying entry too would have
   gutted the public record (every commit this session made carries one) for
   no privacy gain.
4. `tests/test_site_identity.py`'s existing, generic scan over every served
   file is the regression test - not duplicated, and it is what actually
   caught this live, the first time the suite ran after the flip.
5. `tests/test_redact_served_devlog.py` proves the cleaning function itself:
   personal-name drop, case-insensitivity, trailer-stripping leaves the real
   text, an already-clean entry is untouched.

## Not in this slice

- Handing the served URL to Flashy's fan-in. That is a separate, still-open
  outward decision (contacting FlashyLabs), not something this slice does on
  the strength of "make it public" alone.
- Touching `shiplog.fragment.json`/`devlog.fragment.json` at the repo root -
  those stay the full, private source exactly as Slice 99 designed them;
  only the served projection is filtered.
- A general-purpose PII scrubber. The two patterns fixed here are the ones
  actually found by running the real tool against this repository's real
  history, not a guess at what else might someday appear.
