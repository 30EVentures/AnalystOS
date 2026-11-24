"""``/api/v2``: the catalog, and hiring a role for one engagement (Slice 118).

- ``GET  /api/v2/catalog``     public. Every role: its family, boundary, how it was
  tested (``eval.method``), pricing, what it delivers today, and the scoping
  questions it will ask. People and agents read the same document.
- ``POST /api/v2/engagements`` access code required (``X-Access-Code``). JSON body
  ``{"role", "problem", "answers": {question id: text}, "requested_by": {"kind", "ref"}}``.
  Runs intake, the acceptance gate, the verified pipeline (one model call, at most
  one repair retry, under the existing spend ceiling) and the renderer, and returns
  the PowerPoint deck - or, with ``?format=json``, the verified deck spec.

Every request that passes the gate is a paid model call on the operator's account;
the access code is what limits who can make one. Price: to be determined - no price
has been set for any role, and nothing is charged here.
"""

import base64
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from analystos.catalog import load_catalog
from analystos.l3 import engagement as eng
from analystos.l4.deck import spec_digest
from analystos.l4 import formats
from analystos.packs import consulting

bp = Blueprint("analystos_v2", __name__, url_prefix="/api/v2")
_rate_limit = None
_access_denied = None
# Tests replace this with a factory that returns a ReplayClient; None means the real API client.
client_factory = None
MAX_BODY_BYTES = 64_000
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def register(app, rate_limit=None, access_denied=None):
    """Attach the blueprint. ``rate_limit`` and ``access_denied`` are zero-argument callables
    returning an error response or ``None`` (the app's shared limiter and access-code check)."""
    global _rate_limit, _access_denied
    _rate_limit, _access_denied = rate_limit, access_denied
    if "analystos_v2" not in app.blueprints:
        app.register_blueprint(bp)


def _err(status, code, message, **extra):
    return jsonify(error=dict({"code": code, "message": message}, **extra)), status


def questions_for_role(role_id, catalog, scoping):
    return eng.questions_for([role_id], catalog, scoping)


@bp.get("/catalog")
def catalog():
    if _rate_limit and (limited := _rate_limit()):
        return limited
    cat, scoping = load_catalog(), eng.load_scoping()
    roles = []
    for role in cat["roles"]:
        roles.append({
            "id": role["id"], "title": role["title"], "family": role["family"], "wave": role["wave"],
            "boundary": role["boundary"], "human_decides": role.get("human_decides", []),
            "gated_actions": role.get("gated_actions", []), "status": role["status"],
            "tested": (role.get("eval") or {}).get("method"), "pricing": role["rate_cents_per_engagement_hour"],
            "delivers_today": role.get("delivers_today"), "native_deliverables": role["deliverables"],
            "questions": questions_for_role(role["id"], cat, scoping),
        })
    return jsonify({
        "format": "analystos-v2-catalog/1",
        "pricing": "Price: to be determined. No price has been set for any role, and nothing is charged through this API.",
        "testing": "tested = 'mock': checked on a worked example written for this role, in development, with no "
                   "model call; 'mock-family': checked the same way on a worked example written for another role "
                   "in the same family; 'live': checked with the production model.",
        "families": [{"id": f["id"], "title": f["title"], "skill": f["skill"]} for f in cat["families"]],
        "roles": roles,
    })


@bp.post("/engagements")
def create_engagement():
    if _rate_limit and (limited := _rate_limit()):
        return limited
    if _access_denied is None:
        return _err(500, "not_configured", "access gating is not configured on this server")
    if (denied := _access_denied()) is not None:
        return denied
    if (request.content_length or 0) > MAX_BODY_BYTES:
        return _err(413, "too_large", f"request body over {MAX_BODY_BYTES} bytes")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _err(400, "bad_request", "send a JSON object")
    role, answers = body.get("role"), body.get("answers", {})
    requested_by = body.get("requested_by", {"kind": "person", "ref": "web"})
    if not isinstance(answers, dict):
        return _err(400, "bad_request", "answers must be an object of question id to text")

    cat = load_catalog()
    try:
        record = eng.new_engagement(
            engagement_id=eng.new_id(),
            created=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            requested_by=requested_by, problem=body.get("problem"), roles=[role], catalog=cat)
        for qid, text in answers.items():
            if isinstance(text, str) and not text.strip():
                continue
            record = eng.answer(record, qid, text)
    except ValueError as exc:
        return _err(422, "refused", str(exc))
    accepted, problems = eng.accept(record, cat)
    if accepted is None:
        return _err(422, "not_accepted", "the engagement cannot be taken on yet", problems=problems,
                    open_questions=eng.open_questions(record))

    try:
        client = client_factory() if client_factory else None
        spec = consulting.build_deck_spec(accepted, cat, client=client)
        data, fmt = formats.render(spec, accepted, cat)
    except consulting.VerificationFailed as exc:
        return _err(502, "not_verified", f"the work could not be verified, so nothing was delivered "
                    f"({len(exc.problems)} problems)", problems=exc.problems[:100])
    except ValueError as exc:
        message = str(exc)
        if "temporarily unavailable" in message:
            return _err(503, "unavailable", message)
        return _err(502, "not_verified", "the work could not be verified, so nothing was delivered: " + message[:300])

    filename = f'analystos-{spec["role"]}-{accepted["id"][:8]}.{fmt["extension"]}'
    if request.args.get("format") == "json":
        body = {"engagement": accepted, "spec": spec, "spec_sha256": spec_digest(spec),
                "output": {"format": fmt["name"], "media_type": fmt["media_type"], "filename": filename,
                           "base64": base64.b64encode(data).decode("ascii")}}
        if fmt["name"] == "deck":
            body["deck_base64"] = body["output"]["base64"]  # kept for clients written before Slice 124
        return jsonify(body)
    response = Response(data, mimetype=fmt["media_type"])
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["X-AnalystOS-Format"] = fmt["name"]
    response.headers["X-AnalystOS-Engagement"] = accepted["id"]
    response.headers["X-AnalystOS-Spec-Sha256"] = spec_digest(spec)
    return response
