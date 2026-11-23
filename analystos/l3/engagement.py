"""Engagement intake (Slice 109): a problem in, a scoped engagement record out.

The first piece of L3. A person or an agent states a problem and names catalog
roles; the record asks the scoping questions for those roles' families, holds
the answers, and may be accepted only when every requested role is available in
the role catalog - the first code that reads Slice 108's status ladder.

Pure functions over plain JSON-shaped dicts: no clock, no randomness (except
``new_id``), no I/O except loading the scoping templates. Builders raise
``ValueError`` naming the bad field; validators return a list of problems and
never raise. Client text (``problem``, answers) is data, never instructions; it
is cleaned on the way in and refused, not truncated, when too long.
"""

import copy
import json
import re
import secrets
import unicodedata
from datetime import datetime
from pathlib import Path

FORMAT = "analystos-engagement/1"
SCOPING_FORMAT = "analystos-scoping/1"
SCOPING_PATH = Path(__file__).resolve().parent / "scoping.json"

STATES = ("scoping", "scoped", "accepted")
REQUESTER_KINDS = ("person", "agent")
MAX_PROBLEM_CHARS = 8000
MAX_ANSWER_CHARS = 4000
MAX_REF_CHARS = 200
MAX_ROLES = 7

_ID_RE = re.compile(r"[0-9a-f]{32}")
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_QID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*")
_RECORD_KEYS = {"format", "id", "created", "requested_by", "problem", "roles", "questions", "answers", "state"}
_QUESTION_KEYS = {"id", "text", "required"}
_KEEP = {"\n", "\t"}


# --- client text ------------------------------------------------------------

def clean_text(value, field, cap):
    """``value`` as stored client text, or ValueError naming ``field``.

    NFC-normalised; line endings unified; control characters and invisible
    format characters (zero-width, bidi overrides) removed, keeping newlines
    and tabs; surrounding whitespace trimmed. Empty or over ``cap`` is refused."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    text = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        ch for ch in text
        if ch in _KEEP or unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp")
    ).strip()
    if not text:
        raise ValueError(f"{field} is empty")
    if len(text) > cap:
        raise ValueError(f"{field} is {len(text)} characters; the limit is {cap} (refused, not truncated)")
    return text


def _is_clean(value, cap):
    try:
        return clean_text(value, "x", cap) == value
    except ValueError:
        return False


def _valid_timestamp(value):
    if not isinstance(value, str) or not _TS_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def new_id():
    return secrets.token_hex(16)


# --- scoping templates --------------------------------------------------------

def load_scoping(path=SCOPING_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _question_problems(where, question):
    if not isinstance(question, dict) or set(question) != _QUESTION_KEYS:
        return [f"{where}: a question has exactly the fields {sorted(_QUESTION_KEYS)}"]
    problems = []
    if not (isinstance(question["id"], str) and _QID_RE.fullmatch(question["id"])):
        problems.append(f"{where}: question id must look like 'family.slug'")
    if not (isinstance(question["text"], str) and question["text"].strip()):
        problems.append(f"{where}: question text must be non-empty")
    if not isinstance(question["required"], bool):
        problems.append(f"{where}: required must be true or false")
    return problems


def validate_scoping(doc, catalog):
    """Problems with the scoping templates; every catalog family must have questions."""
    if not isinstance(doc, dict):
        return ["scoping templates must be a JSON object"]
    problems = []
    if doc.get("format") != SCOPING_FORMAT:
        problems.append(f"format must be {SCOPING_FORMAT!r}")
    seen = set()

    def check_list(where, questions, prefix):
        if not isinstance(questions, list) or not questions:
            problems.append(f"{where}: must be a non-empty list of questions")
            return
        for i, question in enumerate(questions):
            found = _question_problems(f"{where}[{i}]", question)
            problems.extend(found)
            if found:
                continue
            if not question["id"].startswith(prefix + "."):
                problems.append(f"{where}[{i}]: id must start with {prefix + '.'!r}")
            if question["id"] in seen:
                problems.append(f"{where}[{i}]: duplicate question id {question['id']!r}")
            seen.add(question["id"])

    check_list("common", doc.get("common"), "common")
    families = doc.get("families")
    if not isinstance(families, dict):
        return problems + ["families must be an object keyed by catalog family id"]
    catalog_families = {f.get("id") for f in catalog.get("families", []) if isinstance(f, dict)}
    for fid in sorted(catalog_families - set(families), key=str):
        problems.append(f"family {fid!r} has no scoping questions")
    for fid in sorted(set(families) - catalog_families, key=str):
        problems.append(f"scoping questions for {fid!r}, which is not a catalog family")
    for fid in sorted(set(families) & catalog_families, key=str):
        check_list(f"families[{fid!r}]", families[fid], fid)
    return problems


def _roles_by_id(catalog):
    roles = catalog.get("roles") if isinstance(catalog, dict) else None
    if not isinstance(roles, list):
        return {}
    return {r["id"]: r for r in roles if isinstance(r, dict) and isinstance(r.get("id"), str)}


def questions_for(role_ids, catalog, scoping):
    """The common questions, then each requested role family's own, in the order the
    families first appear among ``role_ids``. Copies, so the snapshot is independent."""
    by_id = _roles_by_id(catalog)
    questions = [copy.deepcopy(q) for q in scoping["common"]]
    seen_families = []
    for rid in role_ids:
        family = by_id[rid]["family"]
        if family not in seen_families:
            seen_families.append(family)
            questions.extend(copy.deepcopy(q) for q in scoping["families"][family])
    return questions


# --- the engagement record ----------------------------------------------------

def _state_for(questions, answers):
    required = [q["id"] for q in questions if q.get("required") is True]
    return "scoped" if all(qid in answers for qid in required) else "scoping"


def new_engagement(*, engagement_id, created, requested_by, problem, roles, catalog, scoping=None):
    """A new engagement in state ``scoping`` (or ``scoped`` if nothing is required)."""
    if not (isinstance(engagement_id, str) and _ID_RE.fullmatch(engagement_id)):
        raise ValueError("engagement_id must be 32 lowercase hex characters")
    if not _valid_timestamp(created):
        raise ValueError("created must be a UTC timestamp like 2026-11-23T18:00:00Z")
    if not isinstance(requested_by, dict) or set(requested_by) != {"kind", "ref"}:
        raise ValueError("requested_by must be {'kind': 'person' | 'agent', 'ref': '...'}")
    if requested_by["kind"] not in REQUESTER_KINDS:
        raise ValueError(f"requested_by.kind must be one of {list(REQUESTER_KINDS)}")
    ref = clean_text(requested_by["ref"], "requested_by.ref", MAX_REF_CHARS)
    problem = clean_text(problem, "problem", MAX_PROBLEM_CHARS)

    if not isinstance(roles, list) or not roles:
        raise ValueError("roles must be a non-empty list of catalog role ids")
    if len(roles) > MAX_ROLES:
        raise ValueError(f"at most {MAX_ROLES} roles per engagement")
    by_id = _roles_by_id(catalog)
    for rid in roles:
        if not isinstance(rid, str) or rid not in by_id:
            raise ValueError(f"roles: {rid!r} is not a role in the catalog")
    if len(set(roles)) != len(roles):
        raise ValueError("roles: each role may be requested once")

    scoping = scoping if scoping is not None else load_scoping()
    questions = questions_for(roles, catalog, scoping)
    record = {
        "format": FORMAT,
        "id": engagement_id,
        "created": created,
        "requested_by": {"kind": requested_by["kind"], "ref": ref},
        "problem": problem,
        "roles": list(roles),
        "questions": questions,
        "answers": {},
        "state": _state_for(questions, {}),
    }
    return record


def answer(engagement, question_id, text):
    """A copy of ``engagement`` with ``question_id`` answered (or re-answered)."""
    if (not isinstance(engagement, dict) or not isinstance(engagement.get("questions"), list)
            or not isinstance(engagement.get("answers"), dict)
            or not all(isinstance(q, dict) and "id" in q for q in engagement["questions"])):
        raise ValueError("not an engagement record")
    if engagement.get("state") == "accepted":
        raise ValueError("an accepted engagement's scope cannot change")
    ids = [q["id"] for q in engagement["questions"]]
    if question_id not in ids:
        raise ValueError(f"{question_id!r} is not a question this engagement asked")
    updated = copy.deepcopy(engagement)
    updated["answers"][question_id] = clean_text(text, f"answer to {question_id}", MAX_ANSWER_CHARS)
    updated["state"] = _state_for(updated["questions"], updated["answers"])
    return updated


def open_questions(engagement):
    """Required questions not yet answered, in the order they were asked."""
    return [q["id"] for q in engagement["questions"]
            if q.get("required") is True and q["id"] not in engagement["answers"]]


def accept(engagement, catalog):
    """``(accepted copy, [])`` when the engagement may be taken on, else ``(None, problems)``.

    It may be taken on only when it is scoped and every requested role is
    'available' in the catalog - a role nobody has evaluated is never hired."""
    problems = list(validate_engagement(engagement, catalog))
    if problems:
        return None, problems
    if engagement["state"] != "scoped":
        if engagement["state"] == "accepted":
            return None, ["already accepted"]
        problems.append("still scoping: unanswered " + ", ".join(open_questions(engagement)))
    by_id = _roles_by_id(catalog)
    for rid in engagement["roles"]:
        status = by_id[rid].get("status")
        if status != "available":
            problems.append(f"role {rid!r} is {status}, not available for hire")
    if problems:
        return None, problems
    accepted = copy.deepcopy(engagement)
    accepted["state"] = "accepted"
    return accepted, []


def validate_engagement(doc, catalog):
    """Every problem with an engagement record. Never raises on any JSON value."""
    if not isinstance(doc, dict):
        return ["engagement must be a JSON object"]
    problems = []
    if doc.get("format") != FORMAT:
        problems.append(f"format must be {FORMAT!r}")
    for key in sorted(_RECORD_KEYS - set(doc), key=str):
        problems.append(f"missing {key!r}")
    for key in sorted(set(doc) - _RECORD_KEYS, key=str):
        problems.append(f"unknown field {key!r}")
    if problems:
        return problems

    if not (isinstance(doc["id"], str) and _ID_RE.fullmatch(doc["id"])):
        problems.append("id must be 32 lowercase hex characters")
    if not _valid_timestamp(doc["created"]):
        problems.append("created must be a UTC timestamp like 2026-11-23T18:00:00Z")
    rb = doc["requested_by"]
    if (not isinstance(rb, dict) or set(rb) != {"kind", "ref"} or rb["kind"] not in REQUESTER_KINDS
            or not _is_clean(rb["ref"], MAX_REF_CHARS)):
        problems.append("requested_by must be {'kind': 'person' | 'agent', 'ref': clean text}")
    if not _is_clean(doc["problem"], MAX_PROBLEM_CHARS):
        problems.append(f"problem must be clean, non-empty text of at most {MAX_PROBLEM_CHARS} characters")

    roles = doc["roles"]
    by_id = _roles_by_id(catalog)
    if not isinstance(roles, list) or not 1 <= len(roles) <= MAX_ROLES:
        problems.append(f"roles must be a list of 1 to {MAX_ROLES} role ids")
    else:
        if not all(isinstance(r, str) for r in roles) or len(set(roles)) != len(roles):
            problems.append("roles must be distinct role ids")
        for rid in roles:
            if isinstance(rid, str) and rid not in by_id:
                problems.append(f"role {rid!r} is not in the catalog")

    questions = doc["questions"]
    question_ids = []
    if not isinstance(questions, list) or not questions:
        problems.append("questions must be a non-empty list")
        questions = []
    for i, question in enumerate(questions):
        found = _question_problems(f"questions[{i}]", question)
        problems.extend(found)
        if not found:
            if question["id"] in question_ids:
                problems.append(f"questions[{i}]: duplicate question id {question['id']!r}")
            question_ids.append(question["id"])

    answers = doc["answers"]
    if not isinstance(answers, dict):
        problems.append("answers must be an object")
        answers = {}
    for qid, text in answers.items():
        if qid not in question_ids:
            problems.append(f"answer to {qid!r}, which this engagement never asked")
        if not _is_clean(text, MAX_ANSWER_CHARS):
            problems.append(f"answer to {qid!r} must be clean, non-empty text of at most {MAX_ANSWER_CHARS} characters")

    state = doc["state"]
    if not isinstance(state, str) or state not in STATES:
        problems.append(f"state must be one of {list(STATES)}")
    elif not problems:
        expected = _state_for(questions, answers)
        if state in ("scoping", "scoped") and state != expected:
            problems.append(f"state is {state!r} but its answers make it {expected!r}")
        if state == "accepted" and expected != "scoped":
            problems.append("accepted with required questions still unanswered")
    return problems
