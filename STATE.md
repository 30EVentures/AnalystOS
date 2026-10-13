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

### Round 2 - verifiers and seals (1063 -> 1069 tests, all OK)
Method: fuzzed every position of a real signed bundle (and a key file, and an audit log) with 15-17 wrong-typed / oversized / deeply nested values, with and without a pinned key and source text [RAN]. The deterministic checks themselves fail closed (empty, vacuous, unsigned, wrong-key cases all returned ok/authentic false); what failed was *totality*:
- FIXED [RAN] `verify_bundle` raised instead of returning a verdict on: `signature.public_key` / `signature.sig` of a non-string type (TypeError; `POST /api/v1/verify` is unauthenticated and answered HTTP 500), a report reference of > 4300 digits (ValueError from `int()`), and JSON nested past the recursion limit in a record, the report or the payload (RecursionError). Now a failing `structure` check; the signature type check also gets its own message. Public name unchanged: `verify_bundle` wraps `_verify_bundle`.
- FIXED [RAN] `validate_key_file` raised RecursionError on a deeply nested key file (the "no private key anywhere" walk); now an invalid-file problem. The CLI now answers a too-deeply-nested bundle file with exit 2 + JSON error instead of a traceback.
- Tests: `tests/test_verifier_totality.py` (6): 39+ error/failure cases on the unfixed code [RAN].
- Checked, no bug found: `audit_chain.verify_entries` (deep lines, wrong types, bool seq, stripped signatures) never raised; unsigned/empty/legacy-only logs fail closed; `authentic` requires a pinned key everywhere.
- Left as-is on purpose (your earlier instruction): audit-line duplicate-key last-wins and NaN literal acceptance.
- [INFERENCE, not changed] `load_signing_key` / `_b64u_decode` use lenient `urlsafe_b64decode`, which silently drops characters outside the alphabet, so a seed with stray punctuation can decode to a valid 32-byte key. Harmless for signing, but `ANALYSTOS_SEAL_KEY` typos are not caught. Proposal below.

### Round 3 - LLM boundary (1069 -> 1075 tests, all OK)
Method: fed mocked model replies with wrong *shapes* (not wrong values) to each stage, 18 hand-written cases for extraction and a positional fuzz (every field x 13 values) for the narrator [RAN]. Values were already verified in code and dropped on mismatch; shapes were not.
- FIXED [RAN] `analyze_document`: one malformed segment (a string, `text` a number, `operands` an entry that is not an object, `event` a string, a non-list `segments`, ...) raised AttributeError/TypeError out of the pipeline, aborting the whole analysis (HTTP 500 / a stuck job) instead of dropping that segment. 14 of 18 shapes crashed. `_verify_segment` now drops it with a reason; a non-list `segments` is "no segments".
- FIXED [RAN] `write_narrative`: 26 positions in the narrator's output (null paragraph, numeric `text`/`heading`, string `sections`, ...) raised out of `_assemble_report`, whose docstring promised "never raises". It now returns a rejection reason like any other, so the existing repair/retry/plain-fallback path runs. `_locate_problem` in the repair loop is guarded too.
- FIXED [RAN] Gate 2 (`proofread_report`): `passed = bool(result["passed"])`, so a verdict of the string "false" (or "no", `["x"]`, 1) passed the gate. Now only the boolean `True` passes. This is the one fail-open found in the LLM boundary.
- Tests: `tests/test_l2_malformed_model_output.py` (6), failing first [RAN].
- Checked, no bug: hash-seed independence of the deterministic report on the one fixture available (5 seeds, identical) and no clock/random in report generation [RAN, narrow]; prompt-delimiter neutralization; the spend ceiling sits on the single `_create_message` choke point.
- NOT FIXED, see PROPOSALS: no cap on the document text sent to the model (a text-heavy 10 MB upload is a paid call that the API then refuses; the one empty-result retry resends it all), and `NO VERIFIABLE CONTENT` logs the first 80 characters of up to 5 quoted document passages to stderr (host logs) - intentional per its comment, but at odds with "confidential documents" once that is supported.
