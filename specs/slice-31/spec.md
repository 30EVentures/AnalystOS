# Slice 31 — horizon made visible in the rendered report

## Goal

Slice 29 tags every verified fact with a `horizon` (`reported` /
`guidance` / `projected`). Slice 30 surfaces that in the narrator's
manifest and instructs the model to keep forward-looking material in the
outlook. This slice makes `horizon` *enforced in the output*, not just
requested of the model: a `guidance` or `projected` figure is visibly
marked as forward-looking **everywhere it appears** — executive summary,
any section, or the outlook — so it can never be read as a verified
historical result no matter where the model placed it. Deterministic,
model-free, and it can never trigger a fallback.

## Design decisions

- **Mark at the point of substitution, not by policing the model.** When
  `render_rich_report` (and the plain-fallback `render_narrated_section`)
  fills a `{{N}}` / renders a segment whose `horizon` is `guidance` or
  `projected`, it appends a small, styled marker right after the value:
  `$15.0B` → `$15.0B GUIDANCE`. The reader sees it inline, wherever the
  fact is used. A hard "reject a guidance fact used in a history section"
  rule was considered and rejected: the Slice 30 prompt legitimately
  allows a forward fact in "a clearly forward-marked part of a section,"
  so a hard rule would cause frequent, needless fallbacks. Marking is
  strictly safer — the fact is always flagged, the report is never lost.

- **Two-pass HTML, matching the existing pattern.** `rich_export`'s
  `_substitute` runs before `html.escape` (Slice 28's bug: inserting real
  markup there gets double-escaped). So `_substitute` emits a plain-text
  sentinel — `⟦guidance⟧` / `⟦projected⟧` (U+27E6/27E7 mathematical
  brackets, which never occur in financial prose and pass through
  `html.escape` unchanged) — and `_para_html` converts it to
  `<span class="horizon-tag">…</span>` in the same escape-then-convert
  pass that already turns `[n]` into a footnote link.

- **The plain fallback marks it too.** `render_narrated_section` produces
  markdown (`{sentence} [n]`); a `guidance`/`projected` segment gets a
  literal ` (guidance)` / ` (projected)` before the `[n]` — plain text,
  no markup, flows through `render_html` / `render_pdf` untouched. The
  fallback path must not mislead any more than the rich path does.

- **The outlook block is unchanged structurally.** "Populated from
  horizon" is satisfied by the inline marker plus the block's existing
  "Interpretation, not a verified fact" caption — not by moving facts
  between the model's paragraphs, which would mangle prose. A forward
  fact the model put in a section is now unmistakably forward *in that
  section*; one it put in the outlook reads the same way, consistently.

- **`horizon` absent → no marker.** Existing callers and every current
  `test_l4_rich_export.py` / `test_l4_export.py` segment has no `horizon`
  key; `.get("horizon")` is `None`, so nothing changes for them. The
  marker is purely additive.

- **CSS**: one `.horizon-tag` rule added to `rich_export._STYLE` — small,
  uppercase, letter-spaced, in the same amber as the outlook accent, set
  slightly raised like a label. Legible in the print stylesheet too.

- **No model call anywhere in this slice.** Rendering only.

## Included

- `analystos/l4/rich_export.py`:
  - `_substitute` — append the `⟦horizon⟧` sentinel for a non-`reported`
    segment.
  - `_para_html` — convert `⟦guidance⟧` / `⟦projected⟧` to
    `<span class="horizon-tag">`.
  - `_STYLE` — the `.horizon-tag` rule (screen + `@media print`).
- `analystos/l4/export.py`:
  - `render_narrated_section` — append ` (guidance)` / ` (projected)` to a
    non-`reported` segment's line, before the `[n]` marker.
- `docs/decisions.md` — dated entry.
- Tests:
  - `tests/test_l4_rich_export.py` — a `guidance` segment referenced in a
    section renders with a `horizon-tag` span carrying "guidance"; the
    same segment in the executive summary and in the outlook is marked
    identically; a `reported` segment (or one with no `horizon`) is not
    marked; the marker never appears as a literal `⟦…⟧` in the output.
  - `tests/test_l4_export.py` — `render_narrated_section` marks a
    `guidance` / `projected` segment inline and leaves a `reported` one
    plain; the marked output still parses cleanly through `render_html`
    and `render_pdf`.
  - every existing `test_l4_rich_export.py` / `test_l4_export.py` case
    passes unchanged.

## Done when

1. A `guidance` or `projected` fact rendered by `render_rich_report`
   carries a visible `<span class="horizon-tag">` immediately after its
   value, in the executive summary, in any section, and in the outlook —
   proven with one test per location.
2. A `reported` fact, and a fact with no `horizon` key at all, render with
   no marker — existing tests unchanged.
3. The sentinel (`⟦guidance⟧` / `⟦projected⟧`) never survives into the
   final HTML as literal text.
4. `render_narrated_section` (the plain fallback) marks a
   `guidance` / `projected` segment inline, and the result still renders
   through `render_html` and `render_pdf` without error.
5. `python3 -m unittest discover -s tests -v` passes with the venv
   active — no model call in this slice's tests.

## Not in this slice

- **Rejecting or relocating a forward fact by `horizon`.** Marking, not
  policing — see the design note.
- **Dated-event segment structure** (`date` / `what` / `status` /
  `next_step` in `analyze.py`, quote-verified, so an acquisition or
  regulatory step can be narrated as a real timeline). This is the other
  half of the diagnosis's Mechanism 4 and it's a genuine `analyze.py` +
  `narrate.py` change — its own slice (proposed Slice 32), not pre-
  approved. Slice 30 already broadened discipline 4 in the prompt; the
  model narrates events from `quote` / `prose` segments until 32 lands.
- **Share-of-total shift, the mix-vs-rate bridge, peer benchmarks** — as
  scoped out since Slice 29.
- **A real `.pdf` of the rich layout** — still Slice 24's `reportlab`
  renderer extended, its own follow-up.
- **Any real paid model call.**

## Verified beyond the test suite

Extend the Slice 30 hand-authored end-to-end run: the same multi-period
mock document, now checked that the full-year guidance figure and the
implied-remaining figure both render with the `GUIDANCE` marker in the
executive summary and the outlook, and that the reported quarterly
figures do not. Open the rendered HTML directly to confirm the marker
reads as a label, not as part of the number.
