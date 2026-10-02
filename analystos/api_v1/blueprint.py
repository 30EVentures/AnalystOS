"""The ``/api/v1`` routes (Slice 61). See ``specs/slice-61/spec.md`` and
``docs/api.md``. Registered on the one shared Flask app by
``api/analyze.py``; each route also has a one-line door file in ``api/v1/``
because Vercel routes one file to one path."""

import base64
import json
import os
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

from analystos.api_v1 import auth, links, store as store_mod
from analystos.api_v1.openapi import build_openapi
from analystos.l1.detect import SUPPORTED_EXTENSIONS
from analystos.l4.export import render_html
from analystos.l4.seal import build_bundle, code_version, load_signing_key
from analystos.l4.seal_verify import canonical_bytes, sha256_hex, verify_bundle
from analystos.pipeline import build_report

BASE_URL_ENV = "ANALYSTOS_PUBLIC_BASE_URL"
VERSION = "1"

bp = Blueprint("analystos_v1", __name__, url_prefix="/api/v1")
_rate_limit = None  # set by register()

_REPORT_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src data:; sandbox"
    ),
}


def register(app, rate_limit=None):
    """Attach the blueprint. ``rate_limit`` is a zero-argument callable that
    returns an error response or ``None`` (the shared per-IP limiter)."""
    global _rate_limit
    _rate_limit = rate_limit
    if "analystos_v1" not in app.blueprints:
        app.register_blueprint(bp)


def _err(status, code, message):
    return jsonify(error={"code": code, "message": message}), status


def _limited():
    return _rate_limit() if _rate_limit else None


def _store():
    return store_mod.FileStore.from_env()


def _base_url():
    configured = (os.environ.get(BASE_URL_ENV) or "").strip().rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("X-Forwarded-Proto") or request.scheme
    host = request.headers.get("X-Forwarded-Host") or request.host
    return f"{proto}://{host}"


def _caller():
    """``(caller, None)`` or ``(None, error_response)``. Fails closed."""
    keys = auth.load_keys()
    if not keys:
        return None, _err(503, "unavailable", "no API keys are configured on this server")
    caller = auth.authenticate(request.headers.get("Authorization"), keys)
    if caller is None:
        return None, _err(401, "unauthorized", "missing or invalid API key (send 'Authorization: Bearer <key>')")
    return caller, None


def _paths(digest):
    root = f"/api/v1/reports/{digest}"
    return {"report": root, "pdf": f"{root}?format=pdf", "seal": f"{root}?format=seal", "verify": f"/api/v1/verify/{digest}"}


@bp.get("")
def index():
    limited = _limited()
    if limited:
        return limited
    return jsonify({
        "name": "AnalystOS",
        "api_version": VERSION,
        "description": "Reads a source document and returns a report whose every figure is a verified quote or a recomputed calculation, sealed so it can be re-verified offline.",
        "openapi": "/api/v1/openapi.json",
        "docs": "https://analystos.dev/docs/api.md",
        "endpoints": [
            {"method": "POST", "path": "/api/v1/analyses", "auth": "bearer", "summary": "Analyze one uploaded document"},
            {"method": "POST", "path": "/api/v1/jobs", "auth": "bearer", "summary": "Submit one document for async analysis (returns a pending job id)"},
            {"method": "POST", "path": "/api/v1/jobs/{id}/run", "auth": "bearer", "summary": "Run a pending job's analysis (idempotent once no longer pending)"},
            {"method": "GET", "path": "/api/v1/jobs/{id}", "auth": "bearer", "summary": "Poll a job's status"},
            {"method": "GET", "path": "/api/v1/reports/{id}", "auth": "bearer or signed link", "summary": "Fetch a stored report (?format=html|pdf|seal)"},
            {"method": "POST", "path": "/api/v1/reports/{id}/review", "auth": "bearer", "summary": "Record that a human reviewed this report ({\"approved\"?: bool})"},
            {"method": "POST", "path": "/api/v1/links", "auth": "bearer", "summary": "Issue an expiring signed link to a report"},
            {"method": "GET", "path": "/api/v1/verify/{id}", "auth": "none", "summary": "Seal metadata for a stored report"},
            {"method": "POST", "path": "/api/v1/verify", "auth": "none", "summary": "Verify a seal bundle"},
        ],
        "seal_spec": "https://analystos.dev/docs/seal.md",
        "limits": {"max_upload_bytes": 10 * 1024 * 1024, "supported_extensions": sorted(SUPPORTED_EXTENSIONS)},
    })


@bp.get("/openapi")  # the path a Vercel rewrite of /openapi.json lands on
@bp.get("/openapi.json")
def openapi():
    limited = _limited()
    if limited:
        return limited
    return jsonify(build_openapi())


@bp.post("/analyses")
def create_analysis():
    limited = _limited()
    if limited:
        return limited
    caller, denied = _caller()
    if denied:
        return denied

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return _err(400, "bad_request", "no file uploaded (multipart field name must be 'file')")
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return _err(415, "unsupported_media", f"unsupported file type {suffix!r}; expected one of {sorted(SUPPORTED_EXTENSIONS)}")
    try:
        signing_key = load_signing_key()
        code_version()  # a malformed ANALYSTOS_CODE_VERSION fails here (503), before any model call
    except ValueError as exc:
        return _err(503, "unavailable", str(exc))
    store = _store()
    if store is not None:
        store.purge_expired()

    title = request.form.get("title") or f"Review of {Path(upload.filename).name}"
    trace = {}
    tmp_dir = Path(tempfile.mkdtemp(prefix="analystos-"))
    try:
        tmp_path = tmp_dir / Path(upload.filename).name
        upload.save(tmp_path)
        section, pdf = build_report(
            tmp_path, None, title, evidence_dir=tmp_dir / "evidence", want_pdf=True, trace=trace,
        )
    except ValueError as exc:
        return _err(422, "unprocessable", str(exc))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)  # never keep the upload

    html = section if section.lstrip().lower().startswith("<!doctype html") else render_html(section)
    try:
        bundle = build_bundle(trace, signing_key=signing_key, caller_id=caller)
    except ValueError as exc:
        return _err(422, "unprocessable", str(exc))
    digest = sha256_hex(canonical_bytes(bundle["payload"]))
    seal_ok = verify_bundle(bundle, source_text=trace["document_text"])["content_checked"]
    now = time.time()
    ttl = store_mod.ttl_days() * 86400
    analysis = trace.get("analysis") or {}
    store_mod.emit_audit(store, {
        "type": "analysis", "caller": caller, "id": digest, "tier": trace["tier"],
        "fallback_reason": trace.get("fallback_reason"), "proposed": analysis.get("proposed", 0),
        "verified": analysis.get("verified", 0), "dropped": analysis.get("dropped", 0),
        "signed": bundle["signature"] is not None, "seal_ok": seal_ok, "extension": suffix,
        "model": trace.get("model"),
    })
    body = {
        "id": digest, "tier": trace["tier"], "created": bundle["payload"]["created"],
        "counts": {"proposed": analysis.get("proposed", 0), "verified": analysis.get("verified", 0),
                   "dropped": analysis.get("dropped", 0)},
        "signed": bundle["signature"] is not None, "seal": bundle, "html": html,
        "stored": store is not None, "links": None, "expires": None,
    }
    response_headers = {}
    if store is not None:
        store.put(digest, {"caller": caller, "created": bundle["payload"]["created"], "tier": trace["tier"],
                           "expires_ts": now + ttl, "expires": store_mod.iso(now + ttl)}, html, pdf, bundle)
        body["links"] = _paths(digest)
        body["expires"] = store_mod.iso(now + ttl)
        response_headers["Location"] = body["links"]["report"]
    if request.form.get("include_pdf", "").strip().lower() in ("1", "true", "yes", "on"):
        body["pdf_base64"] = base64.b64encode(pdf).decode("ascii") if pdf else None
    response = jsonify(body)
    response.status_code = 201
    response.headers.update(response_headers)
    return response


def _job_body(job_id, meta):
    body = {"id": job_id, "status": meta["status"], "created": meta["created"]}
    if meta["status"] == "done":
        body["report_id"] = meta["report_id"]
        body["links"] = _paths(meta["report_id"])
    elif meta["status"] == "failed":
        body["error"] = meta.get("error")
    return body


def _create_job():
    limited = _limited()
    if limited:
        return limited
    caller, denied = _caller()
    if denied:
        return denied
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return _err(400, "bad_request", "no file uploaded (multipart field name must be 'file')")
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return _err(415, "unsupported_media", f"unsupported file type {suffix!r}; expected one of {sorted(SUPPORTED_EXTENSIONS)}")
    store = _store()
    if store is None:
        return _err(503, "store_not_configured", "job storage is not configured on this server (set ANALYSTOS_STORE_DIR)")
    store.purge_expired()
    job_id = secrets.token_hex(16)
    title = request.form.get("title") or f"Review of {Path(upload.filename).name}"
    meta = {"caller": caller, "status": "pending", "created": store_mod.iso(time.time()), "title": title}
    store.create_job(job_id, meta, upload.filename, upload.read())
    store_mod.emit_audit(store, {"type": "job_created", "id": job_id, "caller": caller})
    return jsonify(_job_body(job_id, meta)), 202


def _get_job(job_id):
    limited = _limited()
    if limited:
        return limited
    if not store_mod.JOB_ID_RE.match(job_id or ""):
        return _err(404, "not_found", "no such job")
    store = _store()
    if store is None:
        return _err(503, "store_not_configured", "job storage is not configured on this server")
    caller, denied = _caller()
    if denied:
        return denied
    meta = store.job_meta(job_id)
    if meta is not None and meta.get("caller") != caller:
        meta = None  # someone else's job looks exactly like a missing one
    if meta is None:
        return _err(404, "not_found", "no such job")
    return jsonify(_job_body(job_id, meta))


def _fail_job(store, job_id, caller, exc):
    meta = store.update_job(job_id, status="failed", error=str(exc))
    store.delete_job_upload(job_id)
    store_mod.emit_audit(store, {"type": "job_failed", "id": job_id, "caller": caller, "error": str(exc)})
    return jsonify(_job_body(job_id, meta))


def _run_job(job_id):
    """Runs the same, unmodified pipeline ``/analyses`` uses - see
    specs/slice-74/spec.md for why this is one bounded call, same ceiling as
    a synchronous analysis, not a background worker."""
    limited = _limited()
    if limited:
        return limited
    if not store_mod.JOB_ID_RE.match(job_id or ""):
        return _err(404, "not_found", "no such job")
    store = _store()
    if store is None:
        return _err(503, "store_not_configured", "job storage is not configured on this server")
    caller, denied = _caller()
    if denied:
        return denied
    meta = store.job_meta(job_id)
    if meta is not None and meta.get("caller") != caller:
        meta = None  # someone else's job looks exactly like a missing one
    if meta is None:
        return _err(404, "not_found", "no such job")
    if meta["status"] != "pending":
        return jsonify(_job_body(job_id, meta))  # idempotent: never re-runs

    try:
        signing_key = load_signing_key()
        code_version()  # a malformed ANALYSTOS_CODE_VERSION fails here (503), before any model call
    except ValueError as exc:
        return _fail_job(store, job_id, caller, exc)
    upload = store.job_upload(job_id)
    if upload is None:
        return _err(409, "conflict", "this job's upload is missing")
    filename, data = upload
    store.update_job(job_id, status="running")

    trace = {}
    tmp_dir = Path(tempfile.mkdtemp(prefix="analystos-job-"))
    try:
        tmp_path = tmp_dir / Path(filename).name
        tmp_path.write_bytes(data)
        section, pdf = build_report(
            tmp_path, None, meta.get("title"), evidence_dir=tmp_dir / "evidence", want_pdf=True, trace=trace,
        )
    except ValueError as exc:
        return _fail_job(store, job_id, caller, exc)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)  # never keep the upload

    html = section if section.lstrip().lower().startswith("<!doctype html") else render_html(section)
    try:
        bundle = build_bundle(trace, signing_key=signing_key, caller_id=caller)
    except ValueError as exc:
        return _fail_job(store, job_id, caller, exc)
    digest = sha256_hex(canonical_bytes(bundle["payload"]))
    seal_ok = verify_bundle(bundle, source_text=trace["document_text"])["content_checked"]
    now = time.time()
    ttl = store_mod.ttl_days() * 86400
    analysis = trace.get("analysis") or {}
    store.put(digest, {"caller": caller, "created": bundle["payload"]["created"], "tier": trace["tier"],
                       "expires_ts": now + ttl, "expires": store_mod.iso(now + ttl)}, html, pdf, bundle)
    store_mod.emit_audit(store, {
        "type": "analysis", "caller": caller, "id": digest, "tier": trace["tier"],
        "fallback_reason": trace.get("fallback_reason"), "proposed": analysis.get("proposed", 0),
        "verified": analysis.get("verified", 0), "dropped": analysis.get("dropped", 0),
        "signed": bundle["signature"] is not None, "seal_ok": seal_ok, "extension": Path(filename).suffix.lower(),
        "model": trace.get("model"), "via": "job",
    })
    meta = store.update_job(job_id, status="done", report_id=digest)
    store.delete_job_upload(job_id)
    return jsonify(_job_body(job_id, meta))


@bp.post("/jobs")
def create_job_or_run_by_query():
    if request.args.get("run"):
        return _run_job(request.args.get("id", ""))
    return _create_job()


@bp.post("/jobs/<job>/run")
def run_job(job):
    return _run_job(job)


@bp.get("/jobs/<job>")
def get_job(job):
    return _get_job(job)


@bp.get("/jobs")
def get_job_by_query():
    return _get_job(request.args.get("id", ""))


def _serve(digest, fmt, via, caller_name=None):
    store = _store()
    meta = store.meta(digest) if store else None
    if meta is None:
        return _err(404, "not_found", "no such report")
    if meta.get("expires_ts", 0) <= time.time():
        return _err(410, "expired", "this report has expired and been removed")
    payload = store.read(digest, {"html": "html", "pdf": "pdf", "seal": "seal"}[fmt])
    if payload is None:
        return _err(404, "not_found", f"no {fmt} stored for this report")
    store_mod.emit_audit(store, {"type": "view", "id": digest, "format": fmt, "via": via, "caller": caller_name})
    mime = {"html": "text/html; charset=utf-8", "pdf": "application/pdf", "seal": "application/json"}[fmt]
    return Response(payload, mimetype=mime.split(";")[0], headers={"Content-Type": mime, **_REPORT_HEADERS})


def _report_request(digest):
    limited = _limited()
    if limited:
        return limited
    if not store_mod.DIGEST_RE.match(digest or ""):
        return _err(404, "not_found", "no such report")
    if _store() is None:
        return _err(503, "store_not_configured", "report storage is not configured on this server")
    fmt = request.args.get("format", "html")
    if fmt not in links.FORMATS:
        return _err(400, "bad_request", f"format must be one of {list(links.FORMATS)}")
    if request.args.get("sig") is not None or request.args.get("exp") is not None:
        key = links.secret()
        if key is None:
            return _err(503, "unavailable", "signed links are not configured on this server")
        outcome = links.check(key, digest, fmt, request.args.get("exp"), request.args.get("sig"))
        if outcome == "invalid":
            return _err(403, "link_invalid", "this link is not valid for this report and format")
        if outcome == "expired":
            return _err(410, "link_expired", "this link has expired")
        return _serve(digest, fmt, "link")
    caller, denied = _caller()
    if denied:
        return denied
    meta = _store().meta(digest)
    if meta is not None and meta.get("caller") != caller:
        meta = None  # someone else's report looks exactly like a missing one
    if meta is None:
        return _err(404, "not_found", "no such report")
    return _serve(digest, fmt, "key", caller)


@bp.get("/reports/<digest>")
def get_report(digest):
    return _report_request(digest)


@bp.get("/reports")
def get_report_by_query():
    return _report_request(request.args.get("digest", ""))


def _review_report(digest):
    limited = _limited()
    if limited:
        return limited
    if not store_mod.DIGEST_RE.match(digest or ""):
        return _err(404, "not_found", "no such report")
    store = _store()
    if store is None:
        return _err(503, "store_not_configured", "report storage is not configured on this server")
    caller, denied = _caller()
    if denied:
        return denied
    meta = store.meta(digest)
    if meta is not None and meta.get("caller") != caller:
        meta = None  # someone else's report looks exactly like a missing one
    if meta is None:
        return _err(404, "not_found", "no such report")
    if meta.get("expires_ts", 0) <= time.time():
        return _err(410, "expired", "this report has expired and been removed")
    body = request.get_json(silent=True) or {}
    approved = body.get("approved")
    if approved is not None and not isinstance(approved, bool):
        return _err(400, "bad_request", "approved must be a boolean if given")
    review = {"caller": caller, "at": store_mod.iso(time.time()), "approved": approved}
    store.mark_reviewed(digest, review)
    store_mod.emit_audit(store, {"type": "review", "id": digest, "caller": caller, "approved": approved})
    return jsonify({"id": digest, "reviewed": review})


@bp.post("/reports/<digest>/review")
def review_report(digest):
    return _review_report(digest)


@bp.post("/reports")
def review_report_by_query():
    if not request.args.get("review"):
        return _err(404, "not_found", "no such report")
    return _review_report(request.args.get("digest", ""))


@bp.post("/links")
def create_link():
    limited = _limited()
    if limited:
        return limited
    caller, denied = _caller()
    if denied:
        return denied
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _err(400, "bad_request", "send a JSON object: {\"id\", \"format\", \"ttl_seconds\"}")
    digest, fmt, ttl = body.get("id"), body.get("format", "html"), body.get("ttl_seconds", 3600)
    store = _store()
    if store is None:
        return _err(503, "store_not_configured", "report storage is not configured on this server")
    key = links.secret()
    if key is None:
        return _err(503, "unavailable", "signed links are not configured on this server")
    meta = store.meta(digest) if isinstance(digest, str) and store_mod.DIGEST_RE.match(digest) else None
    if meta is None or meta.get("caller") != caller:
        return _err(404, "not_found", "no such report")
    if meta.get("expires_ts", 0) <= time.time():
        return _err(410, "expired", "this report has expired and been removed")
    try:
        exp, sig = links.sign(key, digest, fmt, ttl)
    except ValueError as exc:
        return _err(400, "bad_request", str(exc))
    if exp > meta["expires_ts"]:
        exp, sig = int(meta["expires_ts"]), links._mac(key, digest, fmt, int(meta["expires_ts"]))
    store_mod.emit_audit(store, {"type": "link", "id": digest, "format": fmt, "caller": caller, "exp": exp})
    return jsonify({"id": digest, "format": fmt, "expires": store_mod.iso(exp),
                    "url": f"{_base_url()}/api/v1/reports/{digest}?format={fmt}&exp={exp}&sig={sig}"}), 201


def _verify_meta(digest):
    limited = _limited()
    if limited:
        return limited
    if not store_mod.DIGEST_RE.match(digest or ""):
        return _err(404, "not_found", "no such report")
    store = _store()
    if store is None:
        return _err(503, "store_not_configured", "report storage is not configured on this server")
    meta = store.meta(digest)
    raw = store.read(digest, "seal") if meta else None
    if meta is None or raw is None:
        return _err(404, "not_found", "no such report")
    if meta.get("expires_ts", 0) <= time.time():
        return _err(410, "expired", "this report has expired and been removed")
    bundle = json.loads(raw)
    signature = bundle.get("signature")
    return jsonify({
        "id": digest, "payload": bundle["payload"],
        "signature": {k: signature[k] for k in ("alg", "key_id", "public_key")} if signature else None,
        "expires": meta.get("expires"), "reviewed": meta.get("reviewed"),
        "note": "metadata only: fetch the seal and report with credentials or a signed link",
    })


@bp.get("/verify/<digest>")
def verify_stored(digest):
    return _verify_meta(digest)


@bp.get("/verify")
def verify_stored_by_query():
    return _verify_meta(request.args.get("digest", ""))


@bp.post("/verify")
def verify_posted():
    limited = _limited()
    if limited:
        return limited
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("bundle"), dict):
        return _err(400, "bad_request", "send a JSON object: {\"bundle\": {...}, \"public_key\"?: \"...\", \"text\"?: \"...\"}")
    public_key, text = body.get("public_key"), body.get("text")
    if public_key is not None and not isinstance(public_key, str) or text is not None and not isinstance(text, str):
        return _err(400, "bad_request", "public_key and text must be strings")
    return jsonify(verify_bundle(body["bundle"], public_key=public_key, source_text=text))
