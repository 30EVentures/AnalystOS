"""``/api/v2``: the catalog, and hiring a role for one engagement (Slice 118).

- ``GET  /api/v2/catalog``     public. Every role: its family, boundary, how it was
  tested (``eval.method``), pricing, what it delivers today, and the scoping
  questions it will ask. People and agents read the same document.
- ``POST /api/v2/engagements/preflight`` public, free: the same checks as a hire, no
  model call; says whether the hire would be taken on and what it would use at most
  (Slice 135).
- ``POST /api/v2/engagements`` access code required (``X-Access-Code``). JSON body
  ``{"role", "problem", "answers": {question id: text}, "requested_by": {"kind", "ref"},
  "budget"?: {"max_model_calls", "max_output_tokens_per_call"}}``.
  Runs intake, the acceptance gate, the verified pipeline (one model call, at most
  one repair retry, under the existing spend ceiling; a budget may only narrow these)
  and the renderer, and returns the role's file - or, with ``?format=json``, the
  verified spec and the file as base64. Every engagement taken on gets
  an ``analystos-receipt/1`` (Slice 133; ``docs/hiring-api.md``), failures included.

Every request that passes the gate is a paid model call on the operator's account;
the access code is what limits who can make one. Price: to be determined - no price
has been set for any role, and nothing is charged here.
"""

import base64
import json
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from analystos.api_v2 import receipt as receipts
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


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _failed(status, code, message, record, budget, meter, **extra):
    """An error after the model was reached: the receipt says what was spent."""
    outcome = "unavailable" if status == 503 else "not_verified"
    receipt = receipts.build(record, outcome, budget, meter, _now())
    return _err(status, code, message, receipt=receipt, receipt_sha256=receipts.digest(receipt), **extra)


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


def _intake(body):
    """The one intake path hiring and preflight share (Slice 135), so they cannot disagree.
    Never makes a model call. Checks run in the hire's order; a later check is skipped
    only when an earlier one leaves nothing to check."""
    out = {"bad_request": None, "budget": None, "budget_problems": [], "refused": None, "record": None,
           "accepted": None, "problems": [], "open_questions": [], "catalog": load_catalog()}
    answers = body.get("answers", {})
    if not isinstance(answers, dict):
        out["bad_request"] = "answers must be an object of question id to text"
        return out
    out["budget"], out["budget_problems"] = receipts.parse_budget(body.get("budget"))
    try:
        record = eng.new_engagement(
            engagement_id=eng.new_id(), created=_now(),
            requested_by=body.get("requested_by", {"kind": "person", "ref": "web"}),
            problem=body.get("problem"), roles=[body.get("role")], catalog=out["catalog"])
        for qid, text in answers.items():
            if isinstance(text, str) and not text.strip():
                continue
            record = eng.answer(record, qid, text)
    except ValueError as exc:
        out["refused"] = str(exc)
        return out
    out["record"] = record
    out["accepted"], out["problems"] = eng.accept(record, out["catalog"])
    if out["accepted"] is None:
        out["open_questions"] = eng.open_questions(record)
    return out


@bp.post("/engagements/preflight")
def preflight_engagement():
    """Everything a hire checks, with no model call, no reservation and no access code."""
    if _rate_limit and (limited := _rate_limit()):
        return limited
    if (request.content_length or 0) > MAX_BODY_BYTES:
        return _err(413, "too_large", f"request body over {MAX_BODY_BYTES} bytes")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _err(400, "bad_request", "send a JSON object")
    intake = _intake(body)
    if intake["bad_request"]:
        return _err(400, "bad_request", intake["bad_request"])
    cat, budget, accepted = intake["catalog"], intake["budget"], intake["accepted"]
    problems = list(intake["budget_problems"])
    if intake["refused"]:
        problems.append(intake["refused"])
    elif accepted is None:
        problems += intake["problems"]
    role = next((r for r in cat["roles"] if r["id"] == body.get("role")), None)
    fmt = formats.format_of(role) if role else None
    ready = not problems and accepted is not None
    first_call = None
    if ready:
        work = consulting.work_role(accepted, cat)
        first_call = {"system_characters": len(consulting.system_prompt(work)),
                      "message_characters": len(consulting.build_prompt(accepted)),
                      "tool_definition_characters": len(json.dumps(consulting.TOOL, ensure_ascii=False,
                                                                  separators=(",", ":")))}
    return jsonify({
        "format": "analystos-preflight/1",
        "ready": ready,
        "role": role["id"] if role else None,
        "problems": problems,
        "open_questions": intake["open_questions"],
        "budget": budget,
        "limits": receipts.LIMITS,
        "worst_case": None if budget is None else {
            "model_calls": budget["max_model_calls"],
            "output_tokens": budget["max_model_calls"] * budget["max_output_tokens_per_call"]},
        "deliverable": None if fmt is None else {"format": fmt["name"], "media_type": fmt["media_type"],
                                                 "extension": fmt["extension"]},
        "first_call": first_call,
        "pricing": "tbd",
        "model_calls_made": 0,
        "note": "A preflight makes no model call and reserves nothing. The hire repeats every check, "
                "and needs the access code.",
    })


@bp.post("/engagements")
def create_engagement():
    if request.args.get("preflight") == "true":  # Vercel rewrites /engagements/preflight here (vercel.json)
        return preflight_engagement()
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
    intake = _intake(body)
    if intake["bad_request"]:
        return _err(400, "bad_request", intake["bad_request"])
    if intake["budget_problems"]:
        return _err(422, "bad_budget", "the budget was refused before any model call",
                    problems=intake["budget_problems"], limits=receipts.LIMITS)
    if intake["refused"]:
        return _err(422, "refused", intake["refused"])
    if intake["accepted"] is None:
        return _err(422, "not_accepted", "the engagement cannot be taken on yet", problems=intake["problems"],
                    open_questions=intake["open_questions"])
    cat, budget, accepted = intake["catalog"], intake["budget"], intake["accepted"]

    meter = []
    try:
        client = client_factory() if client_factory else None
        spec = consulting.build_deck_spec(accepted, cat, client=client, meter=meter,
                                          max_model_calls=budget["max_model_calls"],
                                          max_tokens=budget["max_output_tokens_per_call"])
        data, fmt = formats.render(spec, accepted, cat)
    except consulting.VerificationFailed as exc:
        return _failed(502, "not_verified", f"the work could not be verified, so nothing was delivered "
                       f"({len(exc.problems)} problems)", accepted, budget, meter, problems=exc.problems[:100])
    except ValueError as exc:
        message = str(exc)
        if "temporarily unavailable" in message:
            return _failed(503, "unavailable", message, accepted, budget, meter)
        return _failed(502, "not_verified", "the work could not be verified, so nothing was delivered: "
                       + message[:300], accepted, budget, meter)

    digest = spec_digest(spec)
    receipt = receipts.build(accepted, "delivered", budget, meter, _now(), spec_sha256=digest, output=data, fmt=fmt)
    filename = f'analystos-{spec["role"]}-{accepted["id"][:8]}.{fmt["extension"]}'
    if request.args.get("format") == "json":
        body = {"engagement": accepted, "spec": spec, "spec_sha256": digest,
                "output": {"format": fmt["name"], "media_type": fmt["media_type"], "filename": filename,
                           "base64": base64.b64encode(data).decode("ascii")},
                "receipt": receipt, "receipt_sha256": receipts.digest(receipt)}
        if fmt["name"] == "deck":
            body["deck_base64"] = body["output"]["base64"]  # kept for clients written before Slice 124
        return jsonify(body)
    response = Response(data, mimetype=fmt["media_type"])
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["X-AnalystOS-Format"] = fmt["name"]
    response.headers["X-AnalystOS-Engagement"] = accepted["id"]
    response.headers["X-AnalystOS-Spec-Sha256"] = digest
    response.headers["X-AnalystOS-Receipt"] = receipts.header_value(receipt)
    response.headers["X-AnalystOS-Receipt-Sha256"] = receipts.digest(receipt)
    return response
