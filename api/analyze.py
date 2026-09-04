"""The live MVP's one HTTP endpoint: upload a document, get a cited report.

    POST /api/analyze
    header:
        X-Access-Code   required - must match the ANALYSTOS_ACCESS_CODE
                        environment variable (see Slice 22's spec) - this is
                        a single shared code for the whole preview cohort,
                        not per-user auth
    multipart/form-data:
        file            required - the document (.csv, .xlsx, .docx, .pptx)
        schema          required - a JSON object, e.g.
                        {"period": "text", "revenue": "number"}
        title           optional - defaults to "Review of <filename>"
        template         optional - defaults to "income_statement" (the only
                        one that exists yet - see analystos.templates)
        currency_unit   optional - "actual" (default) / "thousands" / "millions"
                        - see analystos.l4.export for why this matters

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
from pathlib import Path

from flask import Flask, jsonify, request

# api/analyze.py sits next to, not inside, the analystos package - make sure
# the repo root is importable regardless of what working directory the
# hosting platform runs this file from.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analystos.l4.export import render_html  # noqa: E402
from analystos.pipeline import build_report  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB - generous for a table

_ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".docx", ".pptx"}

_ACCESS_CODE_ENV_VAR = "ANALYSTOS_ACCESS_CODE"


@app.post("/api/analyze")
def analyze():
    configured_code = os.environ.get(_ACCESS_CODE_ENV_VAR)
    if not configured_code:
        # Fail closed: an unset env var must never mean "open to everyone."
        return jsonify(error="access gating is not configured on this server"), 500

    supplied_code = request.headers.get("X-Access-Code", "")
    if not hmac.compare_digest(supplied_code, configured_code):
        return jsonify(error="missing or invalid access code"), 401

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify(error="no file uploaded (form field name must be 'file')"), 400

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        return (
            jsonify(
                error=f"unsupported file type {suffix!r}; "
                f"expected one of {sorted(_ALLOWED_EXTENSIONS)}"
            ),
            400,
        )

    schema_raw = request.form.get("schema")
    if not schema_raw:
        return jsonify(error="'schema' form field is required, e.g. "
                              '{"period":"text","revenue":"number"}'), 400
    try:
        schema = json.loads(schema_raw)
        if not isinstance(schema, dict):
            raise ValueError("schema must be a JSON object")
    except (json.JSONDecodeError, ValueError):
        return jsonify(error="'schema' form field must be a JSON object"), 400

    title = request.form.get("title") or f"Review of {upload.filename}"
    template = request.form.get("template", "income_statement")
    currency_unit = request.form.get("currency_unit", "actual")

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
        )
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)  # never keep the upload

    return jsonify(section=section, html=render_html(section))
