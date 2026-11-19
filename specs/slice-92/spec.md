# Slice 92 - hardening: a size cap before the paid call, no upload text in the audit log, a logged verifier fault

## Goal

Three gaps the overnight hardening run found and left for a decision. None changes a verified number, a seal or a
verdict; each closes a way for a hostile or accidental input to cost money or leave a trace it should not.

1. **No cap on the document text sent to the model.** A text-heavy upload under the 10 MB request cap became a paid
   call that the API then refused, and the one empty-result retry resent all of it. Refuse over a cap, before any
   model call, with a clear message.
2. **A fragment of an upload outlived the upload.** A failed job's audit line carried `str(exc)`, and an extractor
   error can quote a cell from the document ("row 3, column 'X': '...' is not a number"). The audit log has no
   expiry. The `title` field also had no length cap and was stored in the job record.
3. **The verifier's catch-all was silent.** `verify_bundle` turns any internal fault into a failing `structure`
   check (fail-closed), which is right, but a bug in the verifier then looked exactly like a hostile bundle and
   nothing was logged.

## Done when

1. `analyze_document` raises `ValueError` ("too long ... N characters, limit M") when the document text is over
   `MAX_DOCUMENT_CHARS` (600,000), before `_resolve_client` and before any model call; a document at the limit is
   still analyzed. The message contains no document text. On `/api/v1/analyses` this is the existing 422; on a job
   it is a failed job.
2. A job that fails on the document writes an audit line whose `error` is a fixed sentence and whose `error_type`
   is the exception class name; the document's own text never appears in `audit.jsonl`. The job record and the
   response still carry the message (the caller's own upload; purged with the job). Configuration failures
   (`load_signing_key`, `code_version`) keep their message in the audit line: they are operator text, not document text.
3. `POST /api/v1/analyses` and `POST /api/v1/jobs` refuse a `title` over 200 characters with 400 `bad_request`.
   200 is the length the model already sees (`prompt_safety.MAX_TITLE_CHARS`); a title at 200 works.
4. When `verify_bundle`'s catch-all fires it writes one line to stderr naming the exception class (never the
   bundle, a value or a message), and the returned verdict is unchanged.
5. Each of 1-4 has a test that fails on the unfixed code. The full suite reports OK, also reversed.

## Not in this slice

- The unscaled-table-number rule (owner decision; docstring and `decisions.md` still disagree).
- Duplicate-key and `NaN` handling in audit lines (owner said to leave them; writer and verifier change together).
- New conformance-corpus cases for a sealed `inf`/`nan` (changes the corpus Flashy's kit runs; agree it first).
- Logging fewer document fragments in `NO VERIFIABLE CONTENT` (only matters once confidential documents are supported).
