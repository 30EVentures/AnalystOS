# Slice 30 — structured narrator, wired end to end

## Goal

Slice 28 built `analystos/l4/rich_export.py` (executive summary, section-by-
section body, per-section charts, a visually distinct outlook block) and
wired it to nothing — no L2 stage produces its input shape. Slice 29 made
`analyze_document` guarantee the comparison set and tag each fact's
`horizon`. This slice closes the loop: `write_narrative` returns the
structured report shape instead of a flat `paragraphs` list, and
`pipeline.build_report`'s default path renders it through
`render_rich_report`. From this slice on, the default output of AnalystOS
is the rich report, not a wall of paragraphs — by default, for any
document, with the verification contract untouched.

## Design decisions

- **`write_narrative` returns a `report` dict, not a `paragraphs` list.**
  The new tool schema (`_TOOL` in `analystos/l2/narrate.py`) is exactly
  what `render_rich_report` consumes:

  ```
  {
    "executive_summary": [{"text": "... {{N}} ..."}, ...],
    "sections": [
      {"heading": "...", "paragraphs": [{"text": "..."}, ...],
       "has_chart": bool,
       "chart": {"type": "bar"|"line"|"donut", "title": "...",
                 "format": "usd"|"percent"|"number",
                 "series": [{"label": "...", "fact_index": N}, ...]}},
      ...
    ],
    "outlook": [{"text": "..."}, ...]
  }
  ```

  `write_narrative` validates it, then returns the plain dict
  `render_rich_report` wants (`title` added, `has_chart` folded away — a
  section's `chart` is `None` when `has_chart` is false or the chart
  didn't survive validation, `outlook` is `None` when empty).

- **Schema stays all-required, no optional properties — the exact pattern
  that fixed Slice 26's `400 Schema is too complex`.** Every object
  (report, section, chart, series item, paragraph) has only required
  properties; "not applicable" is carried by the `has_chart` boolean and
  by empty strings / empty arrays, never by a property's absence. Nested
  depth is fine; it was *optional*-property combinatorics that blew the
  grammar compiler, and there are none here.

- **Validation, in `write_narrative`, all before anything is trusted:**
  - Every paragraph in `executive_summary`, every `section.paragraphs`,
    and `outlook` runs the existing `_validate_paragraph` (every `{{N}}`
    in range and pointing at a citable, non-`prose` segment; no bare digit
    outside a placeholder except a calendar reference). Any failure raises
    `ValueError` — no partial acceptance, same contract as today.
  - Structural checks: `executive_summary` non-empty; `sections` non-empty;
    every section has a non-empty `heading` and at least one paragraph.
    A malformed structure raises (→ fallback), it is not patched.
  - **Chart validation is the one place a partial result is allowed**, and
    it drops the chart, never the report — matching
    `rich_export._resolve_chart`'s existing "a bad point drops the point,
    a chart under two points is dropped entirely, the render is never
    killed" rule. `write_narrative` runs the same check up front (in range,
    points at a numeric `quote`/`computed` segment, ≥ 2 points survive)
    and sets `chart` to `None` if it fails. `_resolve_chart` stays as
    defence in depth — it just no longer has to be the only line.
  - `_MODEL`, `_resolve_client`, `_create_message` (shared with
    `analyze.py`), the empty-response and no-tool-use raises, and the
    server-side logging on every failure path — all unchanged.

- **Prompt — extends the five disciplines already in `_SYSTEM_PROMPT`,
  does not replace them.**
  - **New structural instruction:** produce an `executive_summary` (2–3
    sentences, the bottom line stated as a conclusion), 3–5 `sections`
    (each one analytical point, a heading that names the point), and an
    `outlook` (forward-looking; may be empty when the source has no
    forward material). The Pyramid/SCQA framing already in the prompt now
    maps onto real structure rather than one flat block.
  - **Discipline 4 broadened past legal.** Current text covers only
    "legal/regulatory content." New text: *any* dated or sequential event
    — a legal or regulatory step, an acquisition or deal, a product
    launch, a leadership change, a financing — is narrated as an unfolding
    process: name the specific thing at stake, lay out the dates the
    source gives as a timeline, and state the concrete next step where the
    source provides one, never a vague "pending further developments."
  - **Discipline 5 strengthened with a worked example** of co-stating a
    trigger and its consequence in one sentence instead of two separate
    ones.
  - **Chart guidance:** propose a chart for a section only when it plots
    two or more facts already cited by `{{N}}` and the shape carries real
    information — a line for a metric across three or more periods, a bar
    to compare categories/segments, a donut for parts of a stated whole.
    Never a chart of a single number, never decorative. Each point is
    referenced by its fact number (the same numbers used in prose).
  - **`horizon` is surfaced in the manifest** (`_build_manifest` adds
    `[guidance]` / `[projected]` to a fact's line when it isn't
    `reported`), with a prompt line: forward-looking facts belong in the
    `outlook`, or in a clearly forward-marked part of a section — never
    stated as history. Slice 31 *enforces* this (a `projected` fact
    refused in a history section); this slice surfaces it and instructs.
  - `coverage_summary` (Slice 29) is passed in so the prompt can tell the
    model when a document is thin on comparisons — "state that plainly
    rather than dress a lone figure as analysis," consistent with the
    existing "don't invent a mechanism the source doesn't give" rule.

- **`pipeline.build_report`, default path:** `write_narrative` →
  `render_rich_report(report, segments, source_hash, "actual")`. On any
  `ValueError` from the narrator, fall back to `render_narrated_section`
  (Slice 26's plain rendering) exactly as today — a worse-structured
  report, never a lost one. `render_narrative_section` (the flat narrative
  renderer) stays in `export.py` for its own tests but leaves the
  pipeline path.

- **`build_report`'s default path now returns a full HTML document**
  (what `render_rich_report` produces), where before it returned section
  markdown. Contained by two small guards:
  - `render_html` becomes **idempotent** — given something that already
    starts with `<!doctype html>`, it returns it unchanged. So
    `api/analyze.py` (`jsonify(section=section, html=render_html(section))`)
    needs no change; `html` is the rich page, `section` carries it too
    (the live frontend only reads `html` — `site/upload.html` sets
    `frame.srcdoc = data.html`).
  - `pipeline.main()` writes `section.html` directly for an
    already-HTML section and skips the `.md`/`.pdf` writes for it (a real
    `.pdf` of the rich layout is Slice 24's `reportlab` path extended —
    its own follow-up, noted below). The table/`template` path is
    completely unchanged: still section markdown, still `.md` + `.html` +
    `.pdf`.

- **Model unchanged** (Claude Sonnet 5). One model call, as today — the
  narrator prompt and its response schema get larger, nothing else.

- **Tested against a mocked client only** — no `ANTHROPIC_API_KEY` in this
  environment. Whether a real model produces good structure, chart
  choices, and outlook placement from a real document is the post-merge
  Vercel smoke test in the agreed proof plan, flagged before any paid
  call.

## Included

- `analystos/l2/narrate.py`:
  - `_TOOL` — the report/section/chart/series schema above, all-required.
  - `_SYSTEM_PROMPT` — structural instruction, broadened discipline 4,
    strengthened discipline 5, chart guidance, `horizon` handling, thin-
    document handling.
  - `_build_manifest` — add `[guidance]`/`[projected]` to a fact's line.
  - `_validate_chart(chart, segments)` — new; returns a cleaned chart or
    `None`.
  - `write_narrative(segments, title, client=None)` — new return type
    (`report` dict), full validation, chart cleaning, `coverage_summary`
    used in the prompt. Same `ValueError`-on-failure contract.
- `analystos/l4/export.py` — `render_html` idempotency guard only.
- `analystos/pipeline.py` — default path renders via `render_rich_report`;
  `main()` HTML-section guard. No change to the table path.
- `docs/decisions.md` — dated entry.
- Tests:
  - `tests/test_l2_narrate.py` — rewritten for the new shape: a valid
    structured report is returned and normalized; a bad `{{N}}` anywhere
    (summary / section / outlook) raises; an empty `executive_summary` or
    `sections` raises; a section with no paragraphs raises; a bad chart is
    dropped, not raised, and the rest of the report survives; a chart with
    fewer than two valid points is dropped; `outlook` may be empty →
    `None`; the no-citable-facts, empty-response, no-tool-use, and
    API-error paths still raise and still log.
  - `tests/test_pipeline.py` — the narrative-success test's mock payload
    updated to the new `write_report`/`write_narrative` shapes; it now
    asserts the output is the rich HTML document (`<!doctype html>`, an
    `<h2>` section heading, the narrator's own wording) and not a silent
    fallback. The two fallback tests (`...narrated_default`,
    `...actual_currency_scale`) are unchanged — their mock still returns
    the wrong tool shape, so they still exercise the fallback.
  - `tests/test_l4_export.py` — `render_html` idempotency: a full HTML
    document in returns byte-identical out.
  - Every existing `test_l4_rich_export.py` case still passes untouched
    (this slice produces its input; it doesn't change the renderer).

## Done when

1. `write_narrative` returns a `report` dict (`executive_summary`,
   `sections` with optional `chart`, `outlook`) that `render_rich_report`
   renders with no adaptation, proven with a mocked client.
2. A `{{N}}` that is out of range or points at a `prose` segment —
   anywhere in the summary, any section, or the outlook — raises
   `ValueError`; a stray non-calendar digit likewise. No partial
   acceptance.
3. An empty `executive_summary`, empty `sections`, or a section with no
   paragraphs raises `ValueError` (→ pipeline fallback).
4. A chart whose `series` has an out-of-range or non-numeric `fact_index`,
   or fewer than two valid points, is dropped (`chart` → `None`); the
   report still returns and still renders every paragraph.
5. `pipeline.build_report` with neither `asks` nor `template` returns the
   rich HTML document on the narrator's success and falls back to
   `render_narrated_section`'s plain output on any narrator `ValueError`.
6. `render_html` is idempotent on an already-complete HTML document;
   `api/analyze.py` needs no change and still returns usable `html`.
7. The `template`/`asks` table path is byte-for-byte unchanged — same
   section markdown, same `.md`/`.html`/`.pdf` from `main()`.
8. `python3 -m unittest discover -s tests -v` passes with the venv
   active, mocked client only — no real `ANTHROPIC_API_KEY` or network.

## Not in this slice

- **Enforcing `horizon`** — refusing a `guidance`/`projected` fact stated
  as history in a section, and building the outlook block *from* horizon
  rather than from the model's placement. Slice 31.
- **Dated-event segment structure** in `analyze.py` (`date` / `what` /
  `status` / `next_step`). Slice 31 — discipline 4 is broadened in the
  prompt here, but the model still narrates events from `quote`/`prose`
  segments until then.
- **A real `.pdf` of the rich layout.** `main()` skips the PDF write for
  an HTML section this slice; extending Slice 24's `reportlab` renderer to
  the sectioned/charted shape is its own follow-up.
- **`site/upload.html` changes.** It already renders `data.html`; the
  richer page just appears. Any UI affordance for the new structure
  (a table of contents, collapsible sections) is later, optional work.
- **Share-of-total shift, the mix-vs-rate bridge, peer benchmarks** — as
  scoped out in Slice 29.
- **Any real paid model call.** Mock client only; live smoke test on
  Vercel after merge, flagged first.

## Verified beyond the test suite

Before merge: hand-author a realistic structured `write_narrative`
response for the Slice 29 multi-period mock document (a fictional,
clearly-labelled draft), run it through the real `write_narrative`
validation + `render_rich_report` with a mocked client, and open the
rendered HTML directly — confirming the executive summary, 3–5 sections,
at least one real chart drawn only from cited facts, a distinct outlook
block, and a single shared footnote sequence across all of it. The
confirmation that a *real* model produces this well from a real document
is the post-merge Vercel smoke test.
