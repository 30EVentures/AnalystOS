# Slice 113 - the deck renderer: a verified deck spec in, a PowerPoint file out

## Goal

Second step of taking Management Consulting Analyst all the way through
(owner's decision, 2026-11-23). `analystos/l4/deck.py` lays out an
`analystos-deck-spec/1` (Slice 112) as a 16:9 PowerPoint deck in a consulting
house style, using `python-pptx` (already pinned since Slice 18; no new
dependency).

Process note: this spec was written after the code, against the convention
of spec-first, because the layout was iterated against rendered previews in
the working session. The checks below are what the code was held to before
commit.

## What the deck does

- An action title on every slide; the executive summary's title is the answer.
- Figure tags appear as small grey references (`F2`) beside each number.
- A footer on every slide names the figures it uses and flags any assumption:
  "Includes assumption F15: not from client data."
- Big-number tiles on the executive summary (the answer's own figures), each
  finding and the recommendation - drawn only from figures the slide already
  uses; an assumption's tile is greyed.
- Verdict pills (supported / refuted / untested) on the issue tree and findings;
  the recommended option is highlighted in the options table.
- Sources slides (eight figures each) list every figure: its value, its basis,
  and the client's exact words, the formula ("F5 × F2 ÷ 100") or the
  assumption's rationale.
- A percentage-point change has its own unit (`points`, shown "3 pts"); the
  consulting pack and its recorded case use it.
- The file's properties carry a SHA-256 of the canonical spec: a content
  digest tying the file to the spec, not a signature.

## Done when

1. `render_deck(spec)` returns PowerPoint bytes; refuses anything that is not
   a deck spec, an empty slide list or an unknown slide kind.
2. Tests on the recorded churn case: one slide per spec slide (sources split
   at eight figures), every action title present, the assumption flagged on the
   slide that uses it and not elsewhere, every figure on the sources slides with
   its basis and formula, the digest in the properties, and **no number in the
   file that is not a figure value, a figure reference, a slide number or
   formula notation**.
3. Every slide previewed as an image in the working session (macOS Quick
   Look) and checked by eye; fixes made for wrapped bullets, table width,
   empty space and the percent/points confusion.
4. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.

## Not in this slice

- PDF export, charts, a signed deck seal, client branding.
- Automatic text fitting: font sizes step down by text length; the preview
  check is by eye on the recorded cases.
