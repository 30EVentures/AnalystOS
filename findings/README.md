# Findings register

The discipline both sides agreed to in the 18/21 Nov integration documents: 30E
Ventures publishes each finding it makes about a Flashy estate package at a
stable URL with a discovery date, and Flashy's fix commit cites that id - so a
stranger can check the finding predated the fix, not the other way round.

## What is here, and what is not

`schema.json` and `validate.py` define the shape of one entry; `build_findings.py`
renders `registry.json` into one page per finding plus an index, in `findings/pages/`
(not under `site/` - see "Publishing" below).

`registry.json` holds exactly one entry, `F-00`, and it is a **template, not a
real finding** - its `status` field says so and its summary explains why. The
real findings (24, per the owner's own count as of 18 Nov 2026) live in the
owner's local `flashy-audit` material, which this session could not read. This
repository does not, and must not, invent finding content: a plausible-sounding
security finding that was never actually verified would be worse than publishing
nothing.

## Adding a real finding

1. Copy `F-00`'s shape in `registry.json`, give it the next real `F-NN` id, and
   fill in `title`, `discovered` (the date it was actually found, even if that
   predates today - see `docs/decisions.md` on publishing late and honestly
   rather than silently), `severity`, `affected`, `summary` (no exploit steps -
   that is what `reproducer_exists` is for, without publishing the reproducer
   itself), and set `status` to `open`.
2. Run `python3 findings/build_findings.py` and `python3 -m unittest tests.test_findings`.
3. When Flashy's fix lands and cites the id, set `status` to `fixed` and fill in
   `fix_commit_url`.

## Publishing

Nothing here is served by the live site today - `build_findings.py` writes to
`findings/pages/`, not `site/`, the same safety rule every draft in this session
follows. Once real entries exist, publishing them (to `site/findings/` or
wherever the owner decides) is a separate decision: the 18 Nov document's whole
argument is that the finding's published date matters, so publishing a batch of
pages should be a deliberate, dated act, not a side effect of running a build
script.
