# Overnight run STATE (branch overnight/analystos-bugs, from origin/main 68e38ed)

Baseline: 1051 tests OK [RAN].

## BLOCKED
(none yet)

## Rounds

### Round 1 - upload and file handling (1051 -> 1063 tests, all OK)
- FIXED [RAN] a damaged/mislabelled .xlsx/.docx/.pptx/.pdf upload returned HTTP 500 (an HTML page) from `/api/extract`, `/api/analyze` (both paths) and `/api/v1/analyses` (BadZipFile / pdfminer error escaped). Now 400 / 400 / 422 with the normal JSON error and a message naming no library or path. `analystos/l1/guard.py::unreadable_is_value_error`, used in `detect.extract_any` and `document_text.extract_document_text` (the model-calling PDF image step is deliberately outside the guard).
- FIXED [RAN] a filename over 255 bytes made `upload.save` raise OSError -> 500 on all routes. `guard.upload_name` now refuses it up front (400), at job submission too.
- FIXED [RAN] `/api/v1/jobs/<id>/run`: any error that was not a ValueError (full disk, library bug) left the job `running` forever with its upload still on disk (the upload is supposed to be dropped as soon as the job has run; `purge_expired` does not purge jobs). Now marks it failed with a fixed message, drops the upload, and leaks nothing in the response or audit line.
- FIXED [VERIFIED by reading zipfile: it never reads past a member's declared size] zip-bomb guard for docx/xlsx/pptx: refuses an archive declaring > 250 MB uncompressed or > 10000 entries before any parser opens it. Test patches the caps down; it does not build a 250 MB file.
- Tests: `tests/test_upload_robustness.py` (12), written first; 23 failures + 4 errors on the unfixed code [RAN].
- NOT FIXED, noted: `report.csv` containing NUL bytes passes through to the preview as `\u0000` (cosmetic). `store.purge_expired` never purges `jobs/` dirs or report dirs without a meta.json (leak of stale pending jobs / partial writes) [VERIFIED by reading; not exercised].
