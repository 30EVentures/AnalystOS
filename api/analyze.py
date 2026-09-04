"""The live MVP's one HTTP endpoint: upload a document, get a cited report.

    POST /api/analyze
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
failure. There is no access control yet (Slice 22); do not share this URL
widely until there is.

Response: ``{"section": "...", "html": "...", "source_hash": "..."}`` on
success (200), or ``{"error": "..."}`` on a bad request (400) or an
unexpected failure (500) - the message is never more detail than what
``ValueError`` already gives; nothing about the server internals leaks.
"""

import json
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


@app.post("/api/analyze")
def analyze():
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
