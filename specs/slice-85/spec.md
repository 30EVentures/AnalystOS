# Slice 85 - a PDF cannot cost unbounded model calls or quadratic extraction time

## Goal

An external audit found two ways a single upload can multiply cost or time. (1) A PDF is read by
one vision (model) call per embedded image, with no limit: a PDF with hundreds of tiny images makes
hundreds of paid calls in one request. (2) For every table in a PDF, text extraction reopened the
file and re-extracted the tables of every page just to pick that one table out, so a document with
T tables over P pages did T x P page extractions where P is enough.

## Included

- `analystos/l1/image_facts.py` - `ANALYSTOS_MAX_IMAGES` (default 40, whole number 1-1000; anything
  else is a `ValueError`, not a silent default). A document with more images than the limit raises
  a clear `ValueError`; it never reads only the first N, because silently skipping images would
  silently drop facts. **Ordering:** the images are counted (a free pass over the page objects),
  then the limit is checked, and only then is a client resolved and any vision call made - so an
  over-limit document costs zero calls and does not even need an API key. A PDF with no images never
  reads the setting.
- `analystos/l1/extract_pdf.py` / `document_text.py` - `_raw_rows(..., table=)` parses a table the
  caller already extracted; the document pass hands it each page's tables, so each page is extracted
  once. `all_tables` opens the file once. The parsing code is still the one `_raw_rows`.
- `tests/test_l1_dos_caps.py`, `docs/decisions.md`, `docs/api.md` (the setting).

## Done when

- [ ] A document with cap + 1 images raises the clear error with zero vision calls and no client resolved.
- [ ] A document with exactly the cap is read in full.
- [ ] A malformed `ANALYSTOS_MAX_IMAGES` is an error; a PDF with no images ignores it.
- [ ] Counting `Page.extract_tables` calls on a multi-page, multi-table PDF gives one per page (it
      gave pages + tables x pages), for both `extract_document_text` and `all_tables`.
- [ ] Extracted text and `all_tables` output are identical to before (checked on the repo's PDF
      fixtures and a generated multi-page document; a golden is pinned in the tests).
- [ ] Existing tests pass unchanged, including the one that proves the narrated path and the
      schema-driven path share `_raw_rows`.

## Not in this slice

- A page-count or byte-size limit beyond the existing 10 MB upload limit, a time budget, or
  parallelism.
- Per-image size limits or deduplicating identical images.
