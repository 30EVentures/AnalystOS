"""The OpenAPI 3.1 description of ``/api/v1`` (Slice 61). Written by hand and
kept honest by a test: every route the blueprint serves must appear here."""

from analystos.l4.seal_schema import SEAL_FACT_SCHEMA

_ERROR_REF = {"$ref": "#/components/schemas/Error"}


def _err(description):
    return {"description": description, "content": {"application/json": {"schema": _ERROR_REF}}}


_DIGEST = {"name": "id", "in": "path", "required": True, "description": "The 64-hex report id (SHA-256 of the sealed payload).",
           "schema": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}
_JOB_ID = {"name": "id", "in": "path", "required": True, "description": "The 32-hex job id.",
           "schema": {"type": "string", "pattern": "^[0-9a-f]{32}$"}}
_FORMAT = {"name": "format", "in": "query", "required": False, "schema": {"type": "string", "enum": ["html", "pdf", "seal"], "default": "html"}}
_BEARER = [{"bearerAuth": []}]


def build_openapi():
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "AnalystOS API",
            "version": "1",
            "description": "Analyze a document into a report whose every figure is a verified quote or a recomputed calculation, sealed so anyone can re-verify it offline (see https://analystos.dev/docs/seal.md).",
        },
        "servers": [{"url": "https://analystos.dev"}],
        "paths": {
            "/api/v1": {"get": {
                "operationId": "index", "summary": "Machine-readable index", "security": [],
                "responses": {"200": {"description": "The index", "content": {"application/json": {"schema": {"type": "object"}}}}},
            }},
            "/api/v1/openapi.json": {"get": {
                "operationId": "openapi", "summary": "This document", "security": [],
                "responses": {"200": {"description": "OpenAPI 3.1", "content": {"application/json": {"schema": {"type": "object"}}}}},
            }},
            "/api/v1/analyses": {"post": {
                "operationId": "createAnalysis", "summary": "Analyze one uploaded document", "security": _BEARER,
                "description": "Synchronous: runs the whole pipeline, bounded by the platform's function time limit. The upload is deleted when the request ends. Document text is sent to Anthropic's API.",
                "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                    "type": "object", "required": ["file"],
                    "properties": {"file": {"type": "string", "format": "binary", "description": "csv, xlsx, docx, pptx or pdf; at most 10 MB"},
                                   "title": {"type": "string"},
                                   "include_pdf": {"type": "boolean", "description": "also return the generated PDF as pdf_base64"}}}}}},
                "responses": {
                    "201": {"description": "Analyzed", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Analysis"}}}},
                    "400": _err("no file"), "401": _err("missing or invalid API key"), "415": _err("unsupported file type"),
                    "422": _err("the document could not be analyzed"), "429": _err("rate limited"),
                    "503": _err("no API keys configured, or the seal key is malformed"),
                },
            }},
            "/api/v1/jobs": {"post": {
                "operationId": "createJob", "summary": "Submit one document for async analysis", "security": _BEARER,
                "description": "Returns immediately with a pending job id; no model calls yet. Call POST /jobs/{id}/run to actually run it, then GET /jobs/{id} (or poll it directly) for the result. See https://analystos.dev/docs/api.md#async-jobs for why this is not a background worker.",
                "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                    "type": "object", "required": ["file"],
                    "properties": {"file": {"type": "string", "format": "binary", "description": "csv, xlsx, docx, pptx or pdf; at most 10 MB"},
                                   "title": {"type": "string"}}}}}},
                "responses": {
                    "202": {"description": "Pending", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Job"}}}},
                    "400": _err("no file"), "401": _err("missing or invalid API key"), "415": _err("unsupported file type"),
                    "429": _err("rate limited"), "503": _err("no API keys or no job storage configured"),
                },
            }},
            "/api/v1/jobs/{id}/run": {"post": {
                "operationId": "runJob", "summary": "Run a pending job (idempotent once no longer pending)", "security": _BEARER,
                "description": "One bounded call, same time ceiling as POST /analyses - not a background worker (see docs/api.md#async-jobs). Calling this again on a running/done/failed job just returns its current status.",
                "parameters": [_JOB_ID],
                "responses": {
                    "200": {"description": "The job's status once this call returns", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Job"}}}},
                    "401": _err("missing or invalid API key"), "404": _err("not found"), "409": _err("the job's upload is missing"),
                    "429": _err("rate limited"), "503": _err("no job storage, or the seal key is malformed"),
                },
            }},
            "/api/v1/jobs/{id}": {"get": {
                "operationId": "getJob", "summary": "Poll a job's status (never executes anything)", "security": _BEARER,
                "parameters": [_JOB_ID],
                "responses": {
                    "200": {"description": "The job's status", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Job"}}}},
                    "401": _err("missing or invalid API key"), "404": _err("not found"), "503": _err("storage not configured"),
                },
            }},
            "/api/v1/reports/{id}": {"get": {
                "operationId": "getReport", "summary": "Fetch a stored report, its PDF or its seal",
                "description": "Bearer key of the caller who created it, or a signed link (?exp=&sig=&format=). Somebody else's report is indistinguishable from a missing one.",
                "security": _BEARER + [{}], "parameters": [_DIGEST, _FORMAT,
                    {"name": "exp", "in": "query", "required": False, "schema": {"type": "integer"}},
                    {"name": "sig", "in": "query", "required": False, "schema": {"type": "string"}}],
                "responses": {
                    "200": {"description": "The report", "content": {"text/html": {"schema": {"type": "string"}},
                            "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                            "application/json": {"schema": {"$ref": "#/components/schemas/SealBundle"}}}},
                    "401": _err("missing or invalid API key"), "403": _err("invalid link"), "404": _err("not found"),
                    "410": _err("expired"), "503": _err("storage not configured"),
                },
            }},
            "/api/v1/reports/{id}/review": {"post": {
                "operationId": "reviewReport", "summary": "Record that a human reviewed a delivered report", "security": _BEARER,
                "description": "Same ownership rule as GET /reports/{id}: only the key that created the report may review it. Idempotent - reviewing again overwrites who/when/approved.",
                "parameters": [_DIGEST],
                "requestBody": {"required": False, "content": {"application/json": {"schema": {
                    "type": "object", "properties": {"approved": {"type": ["boolean", "null"]}}}}}},
                "responses": {
                    "200": {"description": "Recorded", "content": {"application/json": {"schema": {
                        "type": "object", "properties": {"id": {"type": "string"}, "reviewed": {"$ref": "#/components/schemas/Review"}}}}}},
                    "400": _err("approved must be a boolean"), "401": _err("missing or invalid API key"),
                    "404": _err("not found"), "410": _err("expired"), "503": _err("storage not configured"),
                },
            }},
            "/api/v1/links": {"post": {
                "operationId": "createLink", "summary": "Issue an expiring signed link to one report and one format",
                "security": _BEARER,
                "requestBody": {"required": True, "content": {"application/json": {"schema": {
                    "type": "object", "required": ["id"],
                    "properties": {"id": {"type": "string"}, "format": {"type": "string", "enum": ["html", "pdf", "seal"]},
                                   "ttl_seconds": {"type": "integer", "minimum": 60, "maximum": 604800}}}}}},
                "responses": {
                    "201": {"description": "The link", "content": {"application/json": {"schema": {
                        "type": "object", "properties": {"id": {"type": "string"}, "format": {"type": "string"},
                                                          "expires": {"type": "string", "format": "date-time"}, "url": {"type": "string"}}}}}},
                    "400": _err("bad request"), "401": _err("unauthorized"), "404": _err("not found"),
                    "410": _err("expired"), "503": _err("storage or link secret not configured"),
                },
            }},
            "/api/v1/verify/{id}": {"get": {
                "operationId": "getSealMetadata", "summary": "Seal metadata for a stored report (never the report)", "security": [],
                "parameters": [_DIGEST],
                "responses": {"200": {"description": "Payload, signature info and review state", "content": {"application/json": {"schema": {"type": "object"}}}},
                              "404": _err("not found"), "410": _err("expired"), "503": _err("storage not configured")},
            }},
            "/api/v1/verify": {"post": {
                "operationId": "verifySeal", "summary": "Verify a seal bundle (stateless)", "security": [],
                "requestBody": {"required": True, "content": {"application/json": {"schema": {
                    "type": "object", "required": ["bundle"],
                    "properties": {"bundle": {"$ref": "#/components/schemas/SealBundle"},
                                   "public_key": {"type": "string", "description": "base64url Ed25519 key you trust; without it the result is never `authentic`"},
                                   "text": {"type": "string", "description": "the extracted text, to check content"}}}}}},
                "responses": {"200": {"description": "Verification result", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Verification"}}}},
                              "400": _err("bad request")},
            }},
        },
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "description": "Per-caller API key (aos_...)"}},
            "schemas": {
                "Error": {"type": "object", "required": ["error"], "properties": {"error": {
                    "type": "object", "required": ["code", "message"],
                    "properties": {"code": {"type": "string"}, "message": {"type": "string"}}}}},
                "SealBundle": {"type": "object", "description": "analystos-seal/1; specified in https://analystos.dev/docs/seal.md",
                               "required": ["format", "payload", "facts"], "properties": {
                                   "format": {"const": "analystos-seal/1"}, "payload": {"type": "object"},
                                   "facts": {"type": "array", "items": {"$ref": "#/components/schemas/SealFact"}}, "report": {"type": ["object", "null"]},
                                   "signature": {"type": ["object", "null"]}}},
                "SealFact": SEAL_FACT_SCHEMA,
                "Verification": {"type": "object", "required": ["ok", "authentic", "content_checked", "checks"], "properties": {
                    "ok": {"type": "boolean"}, "authentic": {"type": "boolean"}, "content_checked": {"type": "boolean"},
                    "checks": {"type": "array", "items": {"type": "object", "required": ["name", "status", "detail"],
                                                          "properties": {"name": {"type": "string"},
                                                                         "status": {"enum": ["pass", "fail", "skipped"]},
                                                                         "detail": {"type": "string"}}}}}},
                "Review": {"type": ["object", "null"], "description": "null until reviewed", "properties": {
                    "caller": {"type": "string"}, "at": {"type": "string", "format": "date-time"},
                    "approved": {"type": ["boolean", "null"]}}},
                "Job": {"type": "object", "required": ["id", "status", "created"], "properties": {
                    "id": {"type": "string"}, "status": {"enum": ["pending", "running", "done", "failed"]},
                    "created": {"type": "string", "format": "date-time"},
                    "report_id": {"type": "string", "description": "present once status is done"},
                    "links": {"type": ["object", "null"], "description": "present once status is done"},
                    "error": {"type": "string", "description": "present once status is failed"}}},
                "Analysis": {"type": "object", "required": ["id", "tier", "created", "counts", "signed", "seal", "html", "stored"], "properties": {
                    "id": {"type": "string"}, "tier": {"enum": ["written", "deterministic", "plain"]},
                    "created": {"type": "string"}, "signed": {"type": "boolean"}, "stored": {"type": "boolean"},
                    "counts": {"type": "object", "properties": {"proposed": {"type": "integer"}, "verified": {"type": "integer"}, "dropped": {"type": "integer"}}},
                    "seal": {"$ref": "#/components/schemas/SealBundle"}, "html": {"type": "string"},
                    "links": {"type": ["object", "null"]}, "expires": {"type": ["string", "null"]},
                    "pdf_base64": {"type": ["string", "null"], "description": "present only when include_pdf was set"}}},
            },
        },
    }
