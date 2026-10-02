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
- Per-image size limits or deduplicating identical images (**reversed after review, see "Follow-up"
  below**).

## Follow-up after review (2026-10-02): the cap counts distinct, non-tiny images

Review measured the cap on 12 real PDFs (counts only; none were SEC filings, none were available locally).
Counting every `page.images` placement, a 30-page designed whitepaper had **53** (over the cap of 40) but only
**14** distinct images over half an inch, and a 13-page slide deck had 26 raw but 15 distinct. A repeated header
logo counts once per page and rejects a normal document with advice to "remove the images". So the rule changed:

- `pending_images(pdf)` keeps each *distinct* image once (a hash of the stream's raw bytes, else its object id; an
  image with neither is never treated as a duplicate) and drops any image placed under `MIN_IMAGE_POINTS` (36 pt, half
  an inch) in either direction; an image of unknown size is kept, not silently dropped.
- The cap and the vision calls both use that list, so repeats and tiny images also stop costing a model call.
- The default stays 40: on the 12 documents the largest selection is 15. The error message now says it counts
  distinct images and ignores repeats and tiny ones.
- Behaviour change to know about: a chart image repeated on several pages is transcribed once (at its first page), and
  an exhibit smaller than half an inch in either direction is no longer read.
- Done when (added): a logo repeated 30 times is one image; images under 36 pt are neither counted nor read; the
  boundary is inclusive and either dimension can disqualify; one logo plus two exhibits is three calls under a cap of 3;
  distinct images over the cap still fail closed with zero calls; unknown sizes and inline images are kept.

