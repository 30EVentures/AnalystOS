# Slice 99 - adopt shipped/1 and devlog/1 for real, with @flashyos/shiplog@0.2.0

## Goal

Of every FlashyOS record plane this repo has drafted, this is the one Flashy's own
20/21 Nov messages said is real and large (25,014 leaves, 23 sources) and that pays
off at N=1 - it needs no counterparty at all. Unlike the charter, measures, playbook
and defined drafts, this is the one format where "adopt it for real, right now" is
itself the correct first move, because the tool's own first-run default is private:
adopting publishes nothing by itself.

## Done when

1. `.shiplog/config.json` is written by the real `flashy-shiplog adopt` command, not
   by hand, with `visibility: "private"` (the tool's own first state) and a real
   `prBase` auto-detected from this repository's actual GitHub remote - never an
   opaque fallback ref, which the 18 Nov integration document named as a silent
   failure mode (a fragment that emits validly and folds zero leaves, with nothing
   red anywhere).
2. `node vendor-shiplog.mjs emit` runs against this repository's full git history
   (the clone was deepened from a shallow depth-1 checkout for this) and produces
   `shiplog.fragment.json` and `devlog.fragment.json` (private, full) plus
   `drafts/devlog.fragment.json` (the public projection, served path kept in
   `drafts/` per every other draft's safety rule, not `site/`).
3. `flashy-shiplog check shiplog.fragment.json` - the real package, not a
   reimplementation - reports every seal recomputed, and is shown to actually
   refuse a tampered copy, not merely asserted to.
4. No git commit author's email address appears anywhere in a committed file.
   Two addresses came back unmapped on the real run (one the repository owner's
   personal address); both already fall back to the safe `defaultAuthor` node id,
   and this slice deliberately does not add an explicit mapping that would require
   writing a personal email into a tracked file for no behavioural gain.
5. `drafts/devlog.fragment.json`'s projection has zero entries today, matching
   `visibility: "private"` - proven, not merely asserted.

## Not in this slice

- Flipping `visibility` to `"public"`. That decision changes what AnalystOS
  discloses and is the owner's to make (`ROADMAP.md`), not something to do by
  re-running a tool with a different flag.
- Handing the served URL to Flashy's notary fan-in. That is one commit on their
  side once there is a real URL to give them - there is not yet, because nothing
  here is deployed.
- The GitHub Actions workflow `flashy-shiplog adopt` can write to refresh the log
  automatically (`--no-workflow` was passed). Adding a workflow that runs on every
  future commit is an infrastructure change, not a draft, and needs the owner's
  own decision the same way any CI change would.
