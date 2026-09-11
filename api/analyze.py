"""The live MVP's HTTP endpoints: upload a document, get a cited report.

    POST /api/extract
    header:
        X-Access-Code   required - same code as /api/analyze below
    multipart/form-data:
        file            required - any of SUPPORTED_EXTENSIONS

    A preview step, not a report: extracts the table and guesses its schema
    (analystos.l1.detect.extract_any), returns them for a person to look at
    before generating anything. Nothing is stored, nothing is cited - see
    specs/slice-25/spec.md for why every format gets this step now, not just
    PDF.

    Response: ``{"schema": {...}, "preview": [{"row": n, "cells": {...}}],
    "warning": "..."|null}`` on success (200) - ``warning`` is set for a
    ``.pdf`` source, since its table is inferred from layout and can be
    misread - or ``{"error": "..."}`` on a bad request/access failure.

    POST /api/analyze
    header:
        X-Access-Code   required - must match the ANALYSTOS_ACCESS_CODE
                        environment variable (see Slice 22's spec) - this is
                        a single shared code for the whole preview cohort,
                        not per-user auth
    multipart/form-data:
        file            required - any of SUPPORTED_EXTENSIONS
        schema          optional - only meaningful together with `template`
                        (below); a JSON object, e.g. {"period": "text",
                        "revenue": "number"} - omitted, it's guessed the same
                        way /api/extract's preview is
        title           optional - defaults to "Review of <filename>"
        template         optional - omitted entirely (the default), the new
                        narrated analysis runs: the document's real text is
                        read and analyzed by a model whose every numeric
                        claim is independently verified against the source
                        (analystos.l2.analyze - see specs/slice-26/spec.md).
                        Given explicitly as "income_statement" (the only
                        named template that exists), the original schema/
                        table-driven path runs instead, unchanged.
        currency_unit   optional - "actual" (default) / "thousands" / "millions"
                        - see analystos.l4.export for why this matters
        pdf_confirmed   only meaningful with an explicit `template` and a
                        .pdf source - "true" once a person has seen
                        /api/extract's preview of it; see analystos.pipeline
                        for the confirm-before-cite gate this satisfies

Nothing from a request is written to persistent storage. The upload is saved
to a private temp directory for the life of the request only, and that
directory is deleted before the response is returned - on success *or*
failure.

Response: ``{"section": "...", "html": "...", "source_hash": "..."}`` on
success (200), or ``{"error": "..."}`` on a bad request (400), a missing or
wrong access code (401), a misconfigured server (500), or an unexpected
pipeline failure (400, using ``ValueError``'s own message) - nothing about
the server internals leaks.
"""

import hmac
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request

# api/analyze.py sits next to, not inside, the analystos package - make sure
# the repo root is importable regardless of what working directory the
# hosting platform runs this file from.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analystos.l1.detect import SUPPORTED_EXTENSIONS, extract_any  # noqa: E402
from analystos.l4.export import render_html  # noqa: E402
from analystos.pipeline import build_report  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB - generous for a table

_ACCESS_CODE_ENV_VAR = "ANALYSTOS_ACCESS_CODE"
_PREVIEW_ROW_LIMIT = 200  # a preview, not the whole table - keeps the response small
_PDF_WARNING = (
    "This table was extracted from a PDF, which has no real table object - "
    "extraction infers column boundaries from the page's layout and can "
    "occasionally misread it. Check the preview below before generating."
)

# Slice 41 - per-IP rate limiting, defense in depth on top of the shared
# access code (Slice 22 explicitly deferred this). In-memory, per-process:
# an accepted tradeoff for a small preview deployment, not a guarantee
# across multiple serverless instances - see specs/slice-41/spec.md.
_RATE_LIMIT_MAX_ENV_VAR = "ANALYSTOS_RATE_LIMIT_MAX"
_RATE_LIMIT_WINDOW_ENV_VAR = "ANALYSTOS_RATE_LIMIT_WINDOW_SECONDS"
_DEFAULT_RATE_LIMIT_MAX = 30
_DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
_rate_limit_lock = Lock()
_rate_limit_buckets = {}  # client key -> (window_start, count in this window)


def _rate_limit_config():
    """(max_requests, window_seconds), falling back to the default for a
    missing or unparseable env var - a throttle must never be the reason
    the whole service goes down."""
    def _int_env(name, default):
        try:
            return int(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

    return (
        _int_env(_RATE_LIMIT_MAX_ENV_VAR, _DEFAULT_RATE_LIMIT_MAX),
        _int_env(_RATE_LIMIT_WINDOW_ENV_VAR, _DEFAULT_RATE_LIMIT_WINDOW_SECONDS),
    )


def _client_key():
    """The client's IP: the first hop of ``X-Forwarded-For`` (the real
    client behind Vercel's proxy) if present, else the direct connection's
    address."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _rate_limit_denied():
    """Return a ``429`` response if this request's client has exceeded its
    budget for the current fixed window; ``None`` if not. Records this
    request against the budget either way, including a request that will
    go on to fail the access-code check - a wrong-code guess must count
    toward the same limit, or the limiter does nothing against the one
    thing it exists to slow down (brute-forcing the shared code).
    """
    max_requests, window_seconds = _rate_limit_config()
    key = _client_key()
    now = time.time()
    with _rate_limit_lock:
        window_start, count = _rate_limit_buckets.get(key, (now, 0))
        if now - window_start >= window_seconds:
            window_start, count = now, 0
        count += 1
        _rate_limit_buckets[key] = (window_start, count)
        over_limit = count > max_requests
    if over_limit:
        return jsonify(error="too many requests - please slow down and try again shortly"), 429
    return None


def _access_denied():
    """Return an error response if the request's access code is missing or
    wrong; ``None`` if it's fine. Shared by both routes below."""
    configured_code = os.environ.get(_ACCESS_CODE_ENV_VAR)
    if not configured_code:
        # Fail closed: an unset env var must never mean "open to everyone."
        return jsonify(error="access gating is not configured on this server"), 500

    supplied_code = request.headers.get("X-Access-Code", "")
    if not hmac.compare_digest(supplied_code, configured_code):
        return jsonify(error="missing or invalid access code"), 401
    return None


def _require_upload():
    """Return ``(upload, None)`` or ``(None, error_response)``."""
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return None, (jsonify(error="no file uploaded (form field name must be 'file')"), 400)

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return None, (
            jsonify(
                error=f"unsupported file type {suffix!r}; "
                f"expected one of {sorted(SUPPORTED_EXTENSIONS)}"
            ),
            400,
        )
    return upload, None


@app.post("/api/extract")
def extract():
    limited = _rate_limit_denied()
    if limited:
        return limited
    denied = _access_denied()
    if denied:
        return denied

    upload, error = _require_upload()
    if error:
        return error

    tmp_dir = Path(tempfile.mkdtemp(prefix="analystos-"))
    try:
        tmp_path = tmp_dir / upload.filename
        upload.save(tmp_path)
        schema, rows = extract_any(tmp_path)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)  # never keep the upload

    preview = [
        {"row": row_num, "cells": row} for row_num, row in zip(rows.row_nums, rows)
    ][:_PREVIEW_ROW_LIMIT]
    warning = _PDF_WARNING if Path(upload.filename).suffix.lower() == ".pdf" else None
    return jsonify(schema=schema, preview=preview, warning=warning)


@app.post("/api/analyze")
def analyze():
    limited = _rate_limit_denied()
    if limited:
        return limited
    denied = _access_denied()
    if denied:
        return denied

    upload, error = _require_upload()
    if error:
        return error

    schema_raw = request.form.get("schema")
    schema = None
    if schema_raw:
        try:
            schema = json.loads(schema_raw)
            if not isinstance(schema, dict):
                raise ValueError("schema must be a JSON object")
        except (json.JSONDecodeError, ValueError):
            return jsonify(error="'schema' form field must be a JSON object"), 400

    title = request.form.get("title") or f"Review of {upload.filename}"
    # Omitted entirely -> the new narrated-analysis default (build_report
    # runs analystos.l2.analyze on the document's real text). Given
    # explicitly (still just "income_statement" - the only one that
    # exists) -> the original schema/table-driven path, unchanged.
    template = request.form.get("template") or None
    currency_unit = request.form.get("currency_unit", "actual")
    pdf_confirmed = request.form.get("pdf_confirmed", "").strip().lower() in (
        "1", "true", "yes", "on",
    )

    tmp_dir = Path(tempfile.mkdtemp(prefix="analystos-"))
    try:
        tmp_path = tmp_dir / upload.filename
        upload.save(tmp_path)

        section = build_report(
            tmp_path,
            schema,
            title,
            template=template,
            currency_unit=currency_unit,
            evidence_dir=tmp_dir / "evidence",
            extract_options={"pdf_confirmed": pdf_confirmed},
        )
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)  # never keep the upload

    return jsonify(section=section, html=render_html(section))
