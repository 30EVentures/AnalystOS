# Slice 23 — L1: PDF input, extraction + human confirm-before-cite step

## Goal

Add PDF as a fourth structured-table input format — but honestly, not like the
other three. Excel/Word/PowerPoint tables are real structured objects (a
cell/table object AnalystOS reads directly); a PDF table is not — pdfplumber
*infers* column boundaries and row splits from the page's visual layout, and
that inference can be wrong in ways the other extractors can't be. Per
`docs/decisions.md` (2026-09-04) that's exactly why a PDF-extracted table must
never be cited directly: this slice adds the extractor *and* a real gate that
refuses to build a report from a PDF source until a person has reviewed the
extracted table and explicitly confirmed it.

## Design decisions (surfacing before building, same as Slice 20's Vercel research)

- **Extraction library: `pdfplumber==0.11.10`.** Verified directly (not just
  read about): installs with no system dependencies (its own deps —
  `pdfminer.six`, `Pillow`, `pypdfium2` — all ship self-contained wheels, no
  Poppler/Ghostscript/Java needed), same Vercel-serverless-friendly reasoning
  already used to pick `reportlab` over `weasyprint`. Ran a real bordered
  table through it end to end (built with `reportlab`, read back with
  `pdfplumber.page.extract_tables()`) and got back exactly the right rows.
  Rejected `camelot` (needs Ghostscript) and `tabula-py` (needs Java) for the
  same reason `weasyprint` was rejected for output.
- **`reportlab==5.0.1` is pulled forward into this slice too — for tests
  only.** Every existing format extractor's tests build their own fixture
  file at test time with that format's own writer library (`openpyxl` for
  `.xlsx`, etc.) — there's no committed binary fixture anywhere in the repo.
  A real PDF table `pdfplumber` can reliably detect needs actual ruling
  lines, which means *something* has to write a real PDF, and inventing a
  second, throwaway PDF-writing dependency just for tests would be strictly
  worse than using the one already decided on for Slice 24. Slice 24 remains
  the slice that wires `reportlab` into `analystos/l4/export.py` for real
  report output — this slice's tests just import it the same way
  `test_l1_extract_xlsx.py` imports `openpyxl`.
- **The confirm-before-cite gate is a non-interactive, scriptable flag, not a
  terminal prompt.** The CLI's whole execution model (`python3 -m analystos
  <job-dir>`) is currently non-interactive end to end — no `input()` anywhere.
  Rather than break that, `build_report` refuses to proceed past extraction
  for a `.pdf` source unless the job explicitly says `"pdf_confirmed": true` —
  raising a `ValueError` that includes the *actual extracted table* so
  whoever runs it sees exactly what needs reviewing, and only after they've
  looked can they add that key to `job.json` and re-run. This satisfies "shown
  to a person to confirm... first" without a `input()`-driven UI, which
  wouldn't fit the CLI's automation model or Vercel's request/response API
  anyway.
- **Correcting a misread value is explicitly not supported.** Only
  accept-as-extracted-or-don't-use-it. A real, disclosed gap — see "Not in
  this slice."

## Included

- `requirements.txt` — `pdfplumber==0.11.10`, `reportlab==5.0.1`, both pinned;
  `docs/decisions.md` records why (see above).
- `analystos/l1/extract_pdf.py` — `extract_table_pdf(path, schema, page=None,
  table_index=0)`: finds tables across the document's pages in page order
  (mirrors `extract_table_pptx`'s `slide_index`/`table_index` shape exactly,
  with `page` in place of `slide_index`); row 1 is the header, row 2 the
  first data row, same convention as every other extractor; shares
  `analystos.l1.schema.apply_schema` for type-checking, same as the other
  three. Raises `ValueError` on an unknown schema type, a missing required
  column, a bad value, no table at the requested index, or an empty table —
  identical error shape to the other extractors.
- `analystos/pipeline.py`:
  - `_extract_rows` dispatches `.pdf` to `extract_table_pdf`, reading
    `page`/`table_index` from the job the same way `.pptx` reads
    `slide_index`/`table_index`.
  - `build_report`: right after L1 extraction, if the source is a `.pdf` and
    `extract_options` doesn't have `"pdf_confirmed": true`, raises
    `ValueError` with a message naming the requirement *and* a plain-text
    preview of the actually-extracted rows (column headers + every row,
    tagged with its row number) — so the error itself is the review step.
  - Module docstring and the unsupported-extension error message updated to
    include `.pdf`.
- `tests/test_l1_extract_pdf.py` — builds real PDFs with `reportlab` at test
  time (mirrors `test_l1_extract_xlsx.py`'s pattern with `openpyxl`): a
  well-formed table returns typed rows; a missing schema column, a bad
  number, no table at the requested index, and an empty table each raise
  `ValueError`; `page`/`table_index` correctly select among several tables.
- `tests/test_pipeline.py` — new cases: a `.pdf` source without
  `"pdf_confirmed"` raises with the extracted values visible in the message;
  the same source with `"pdf_confirmed": true` builds the report normally,
  citing the PDF's real source hash; `run_job` reads a confirmed PDF source
  end to end (mirrors `test_run_job_reads_an_xlsx_source`).
- `tests/test_api_analyze.py` — one added case locking in that `.pdf` is
  still rejected by the API with the existing "unsupported file type" `400`
  (see "Not in this slice" — deliberately unchanged).

## Done when

1. `extract_table_pdf` reads a real, ruled PDF table into typed rows,
   matching a schema exactly the way the other three extractors do.
2. `page`/`table_index` correctly narrow which table is read when a document
   has more than one.
3. `build_report` refuses to build a report from an unconfirmed `.pdf`
   source — the raised error names the requirement and shows the real
   extracted values, not a generic message.
4. Adding `"pdf_confirmed": true` to a job (CLI) or passing it via
   `extract_options` (`build_report` directly) is the only way past that
   gate; once past it, everything downstream (L0 citation, L2 answers, L4
   rendering) works identically to any other format — no PDF-specific
   branching below L1.
5. `api/analyze.py` still returns its existing `400` for a `.pdf` upload —
   unchanged, not newly wired in this slice.
6. `python3 -m unittest discover -s tests -v` passes (with the venv active).

## Not in this slice

- **Correcting a misread value.** The gate is accept-or-reject, not
  accept-with-edits — a real gap decisions.md's "confirm or correct" phrasing
  implies but this slice doesn't build. Fixing it means either hand-editing
  the source PDF and re-extracting, or (future work) a real review UI that
  lets someone patch specific cells — exactly the "review-step UI" the
  roadmap already named as the reason PDF was pushed after the MVP.
- **Wiring `.pdf` into `api/analyze.py` / `site/upload.html`.** A stateless
  multipart request has no natural place for a human-in-the-loop confirm
  step without that same review UI; `_ALLOWED_EXTENSIONS` stays
  `{.csv, .xlsx, .docx, .pptx}`. PDF support in the live MVP is real,
  scoped-out future work, not an oversight.
- **Scanned/image PDFs (OCR).** Explicitly out of scope per decisions.md —
  slow, and a genuinely different, heavier problem than table-layout
  inference.
- **`analystos/scaffold.py` support for PDF sources.** Scaffolding a
  `job.json` from a PDF isn't added; job files for a PDF source are still
  hand-written the way any non-CSV source's job already is.
- **Real `.pdf` report *output*.** That's Slice 24, unchanged — this slice's
  use of `reportlab` is test-fixture-only, not wired into `analystos/l4/`.
