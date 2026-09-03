# Slice 13 — styled HTML output that auto-opens

## Goal

The pipeline writes a styled `section.html` alongside `section.md`, and opens
it automatically when you run the command yourself, so a clean PDF is one
keystroke away (browser → Print → Save as PDF).

## Included

- `analystos/l4/export.py` — `render_html(section_md)` → an HTML string. A
  purpose-built converter for the format `render_section` produces, not a
  general Markdown renderer.
- `analystos/pipeline.py` — `main()` writes `section.html`; on an interactive
  run (`stdout` is a terminal) it runs `open section.html` on macOS.
- `tests/test_l4_export.py`, `tests/test_pipeline.py` — new tests
- `docs/using-analystos.md` + `tests/test_docs.py` — the PDF step

## Done when

1. `python3 -m analystos <job-dir>` writes `<job-dir>/section.html` next to
   `section.md`.
2. The HTML has the title as `<h1>`, each sentence as a `<p>` with `[n]` as a
   superscript link, and a footnotes block whose `#fn<n>` anchors match.
3. `render_html` HTML-escapes the text — an `&` or `<` in the data does not
   break the page.
4. `run_job` and `section.md` are unchanged.
5. The auto-open is gated on `stdout` being a terminal, so it never fires
   during tests.
6. `python3 -m unittest discover -s tests -v` passes.

## Not in this slice

- Writing the `.pdf` file itself — that needs a third-party library (Option C),
  a later slice with its own `decisions.md` entry.
- A general Markdown renderer — `render_html` only handles our section format.
- Auto-open on Windows / Linux — macOS only for now.
- Print styling beyond a basic `@media print` block.
