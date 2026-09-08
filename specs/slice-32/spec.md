# Slice 32 — dated events as a verified, structured fact

## Goal

AnalystOS is rigorous with *numbers* — every figure traces to the source
or an independent recomputation. It is weak with *events*: an acquisition,
a regulatory action, a launch, a leadership change, a financing, a
litigation step. Today the model can mention one as a plain quote, but
nothing captures *when* it happened, *where it stands*, and *what's next*,
so the report says "an acquisition closed during the quarter" instead of
"the acquisition closed in May; integration costs peak this quarter;
management expects it accretive in 2027."

This slice adds an `event` segment type to `analyze_document` — with
`what` / `date` / `status` / `next_step`, **each verified as a real
substring of the source** exactly the way a quote is — and has L4 compose
those verified pieces into a timeline string wherever the narrator
references the event. It is the last piece of the diagnosis's Mechanism 4
(`docs/rich-report-diagnosis.md`); the narrator prompt was already
broadened past legal content in Slice 30.

## Design decisions

- **`event` is a fourth segment type**, alongside `quote` / `computed` /
  `prose`. It carries no numeric `value`. Its four text parts are held in
  a nested `event` object on the tool schema:
  `{what, date, status, next_step}` — every field required (the Slice 26
  all-required rule; nesting is fine, only *optional* properties broke the
  grammar compiler, and Slice 30's nested chart schema already proves
  nested-all-required works). Non-`event` segments fill it with `""`.

- **The model copies, it never composes.** `what` names the event and
  must be a verbatim substring of the document. `date`, `status`,
  `next_step` are each either `""` or a verbatim substring — a date the
  model half-remembers, or a "next step" it infers, is exactly what this
  guards against. `_verify_event` checks `what` is a non-empty real
  substring and drops the whole segment if not; it checks each *provided*
  (non-empty) `date` / `status` / `next_step` the same way and **drops the
  whole event if any provided part fails** — a half-verified timeline is
  worse than none.

- **The model never types the date into prose either.** The narrator
  references an event with `{{N}}` like any citable fact; L4 expands that
  to a composed timeline string built only from the verified parts —
  `acquired Halyard Analytics (May 14, 2026) — integration ongoing —
  next: expected accretive in 2027` — skipping any part the source didn't
  supply. This keeps the "the model never writes a number" guarantee
  intact and extends it to "the model never writes a date"; the digits in
  an event line are all verified substrings, never model-authored. (Slice
  27's calendar carve-out in `_validate_paragraph` still lets the model
  write "into 2027" as connective prose, but the *event's own* dates come
  through the verified channel.)

- **`horizon` still applies.** A planned or expected event is
  `projected`; Slice 31's marker renders on its line unchanged.

- **Charts are untouched.** An event has no `value`, so
  `_validate_chart` / `_resolve_chart` already exclude it — no change.

- **`coverage_summary` gains an `events` count** — a signal for the
  narrator and the tests, same status as `comparisons`.

- **Model unchanged** (Claude Sonnet 5). The `analyze.py` prompt and
  schema grow by the event object and its description; `narrate.py` gets
  one line pointing at the pre-structured `[event]` manifest entries. One
  model call each, as today.

- **Tested against a mocked client only** — no `ANTHROPIC_API_KEY` here.
  Real behaviour is the (still-owed) live Vercel smoke test.

## Included

- `analystos/l2/analyze.py`:
  - `type` enum + prompt gain `"event"`; nested `event` object added to
    `_TOOL` (all-required) and described in `_SYSTEM_PROMPT` (copy
    verbatim, `""` when absent / not an event).
  - `_verify_event(seg, normalized_document)` — `what` required + real;
    each provided `date`/`status`/`next_step` real or the event is
    dropped; returns `{"type": "event", "horizon": ..., "what": ...,
    "date": ..., "status": ..., "next_step": ..., "citation": <what>}`.
  - `_verify_segment` dispatches `"event"`.
  - `coverage_summary` — add `"events"`.
- `analystos/l4/export.py`:
  - `event_line(segment)` — compose the verified parts into one string,
    omitting empty parts. Public, like `display_value` / `narrated_footnote`
    (one implementation, shared by the plain and rich renderers).
  - `display_value` — return `event_line(segment)` for an `event` segment
    (before the `"value" in segment` branch).
  - `render_narrated_section` — an `event` segment renders its line with a
    footnote, same as a qualitative quote; Slice 31's `(guidance)` /
    `(projected)` suffix still applies via `horizon`.
- `analystos/l2/narrate.py`:
  - `_build_manifest` — an `event` segment lists as
    `Fact i [event]: <what> — <date> — status: <status> — next: <next_step>`
    (omitting empty parts), so the model sees the whole structure.
  - `_SYSTEM_PROMPT` — one line: an `[event]` fact already carries its
    date / status / next step; reference it with `{{N}}` and write the
    sentence around it, don't retype the date.
  - `_validate_paragraph` — no change needed: an `event` isn't `prose`,
    so a `{{N}}` to it already passes the citable check.
- `analystos/l4/rich_export.py` — no change: `_substitute` already routes
  through `display_value`, which now knows `event`; `_resolve_chart`
  already skips value-less segments.
- `docs/decisions.md` — dated entry.
- Tests:
  - `tests/test_l2_analyze.py` — a fully-real event kept with all parts;
    an event whose `what` is absent dropped; an event with empty
    date/status/next_step kept (only `what` required); an event with a
    fabricated (non-substring) `next_step` dropped whole;
    `coverage_summary` reports `events`.
  - `tests/test_l4_export.py` — `event_line` composes present parts and
    omits absent ones; `render_narrated_section` renders an event with a
    footnote and (for a `projected` event) the Slice 31 marker; the output
    still parses through `render_html` / `render_pdf`.
  - `tests/test_l4_rich_export.py` — an `event` `{{N}}` in a section
    paragraph substitutes the composed line + a shared footnote; a
    `projected` event carries the `horizon-tag`.
  - `tests/test_l2_narrate.py` — the manifest lists an event with its
    structure; an event `{{N}}` is accepted (not treated as non-citable).
  - `tests/test_pipeline.py` — end-to-end with a mocked client: a
    document containing an event yields a report whose prose references
    the composed event line.
  - every existing test still passes (the new type is additive).

## Done when

1. `analyze_document` returns an `event` segment with `what` / `date` /
   `status` / `next_step`, each a verified substring of the source; an
   event whose `what` is not in the source, or any of whose supplied
   parts is not in the source, is dropped whole — one mocked test each.
2. An event with only `what` (empty date/status/next_step) is kept and
   renders as just that phrase.
3. `event_line` composes the present parts into one timeline string and
   omits the absent ones.
4. A narrator paragraph that references an event via `{{N}}` renders the
   composed line plus one shared footnote, in both the plain
   (`render_narrated_section`) and rich (`render_rich_report`) paths; a
   `projected` event also carries Slice 31's marker.
5. `coverage_summary` reports an `events` count.
6. `python3 -m unittest discover -s tests -v` passes with the venv
   active, mocked client only.

## Not in this slice

- **Any numeric reasoning about an event** (deal size, % accretion) —
  that is still a `quote` / `computed` segment; an `event` is the
  timeline, numbers stay in the verified numeric channel.
- **Ordering multiple events into a combined timeline** — each event is
  narrated where the model places it; a multi-event chronology is a
  later refinement if it proves needed.
- **Mix-vs-rate bridge, share-of-total shift, peer benchmarks** — as
  scoped out since Slice 29.
- **A real `.pdf` of the rich layout** — still Slice 24's `reportlab`
  renderer extended.
- **Any real paid model call** — mocked client only; live smoke test on
  Vercel after merge, flagged first.

## Verified beyond the test suite

Hand-author an `analyze_document` response containing an `event` (real
substrings for all four parts) plus a `write_narrative` response that
references it with `{{N}}`, run both through the real verification +
`render_rich_report` with a mocked client, and read the rendered HTML —
confirming the event renders as a dated timeline with a next step, its
digits all trace to the source, and (made `projected`) it carries the
Slice 31 marker.
