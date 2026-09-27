# Slice 69 - the homepage's test and spec counts are generated, not typed (roadmap Q6)

## Goal

The homepage states how many automated tests pass and how many specs exist, in
seven places. They were hand-maintained and drifted at every slice ("503" was
still on the page after 158 more tests). The audit's rule applies: a public number
that can silently go stale eventually will.

`python3 tools/site_counts.py [--check]` counts the tests (by discovering the
suite, not running it) and the spec folders, and rewrites those seven figures in
`site/index.html`. Each is matched by an explicit pattern; if a pattern stops
matching (someone reworded the page) the tool fails loudly instead of skipping it,
so drift cannot hide behind a rewording. `tests/test_site_counts.py` fails when the
page's numbers differ from the real ones.

## Not in this slice

- The "about 3 seconds" timing (it varies by machine; the text says "about").
- Counting tests by running them, or any figure not derivable offline.

## Done when

1. `--write` updates all seven figures; `--check` exits 1 when any is wrong and 0
   when all are right.
2. A reworded page (a pattern that no longer matches) makes the tool fail.
3. The suite fails if the homepage's numbers are stale.
4. The homepage numbers are correct now.
5. Full suite OK.
