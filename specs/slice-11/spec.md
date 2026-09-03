# Slice 11 — a one-page guide for analysts

## Goal

A one-page `docs/using-analystos.md` an analyst can follow with no help: the
three steps, what each file is, how to write an `ask`, what a footnote means,
and the common mistakes.

## Included

- `docs/using-analystos.md` — the guide
- `tests/test_docs.py` — a test that the guide names the current commands, so
  it can't silently go stale
- `README.md` — a link to the guide

## Done when

1. `docs/using-analystos.md` walks scaffold → edit → run in plain language.
2. It shows the `ask` shape (`text` / `where` / `select`) with a worked example.
3. It explains a footnote line — source fingerprint + row + column = trace to
   the exact cell.
4. It lists the three common mistakes (JSON pasted into the Terminal, wrong
   folder, `where` value doesn't match the CSV).
5. `tests/test_docs.py` confirms the guide contains
   `python3 -m analystos.scaffold`, `python3 -m analystos `, `job.json`,
   `section.md`, and `{answer}`.
6. `README.md` links to the guide. `python3 -m unittest discover -s tests -v`
   passes.

## Not in this slice

- Screenshots or video.
- Anything past the CSV → section flow (no L0 internals, no AAO).
- A full troubleshooting guide — just the top three mistakes.
