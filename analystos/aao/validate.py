"""Check an AAO charter against the published AAO 0.1 schema. Pure Python,
no network, no npm. Slice 58.

Three layers, each reported with a stable ``aao.*`` code:

1. The published JSON Schema (``aao.schema.json``, a pinned copy of
   https://flashyos.com/aao.schema.json), checked by a small validator that
   implements only the keywords that schema uses.
2. The cross-field rules the schema's own description documents (duplicate
   role names, ``worksIn`` naming an undeclared repository, ``escalation``
   naming a missing role, more than one default repository, a repository no
   role owns).
3. The documented role-naming rules that can be checked without a denylist
   we do not have (at most three words; a partial vendor list; placeholders),
   and the ``you@example.com`` template placeholder.

What this is not: FlashyOS's official ``@flashyos/aao`` validator. It does
not know their codename denylist, and its codes are ours (their aao/0.1
conformance corpus is not public), so agreement with the official tool is
something to measure, not assume. See ``docs/aao.md``.
"""

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("aao.schema.json")
SCHEMA_SOURCE = "https://flashyos.com/aao.schema.json"
SCHEMA_RETRIEVED = "2026-09-25"
SCHEMA_SHA256 = "99f520bb9244e83a7ef7eb5e505ad4f3b999b7a3fd9d0519a54e8274c748df69"

ERROR = "error"
WARNING = "warning"

# Every keyword the published schema uses. A test fails if a future copy of
# the schema uses one that is not listed here, rather than silently ignoring it.
SUPPORTED_KEYWORDS = frozenset({
    "$schema", "$id", "title", "description", "type", "const", "enum", "pattern",
    "minLength", "maxLength", "minItems", "required", "properties",
    "patternProperties", "additionalProperties", "items", "$ref", "$defs",
})

_VENDOR_WORDS = frozenset({"claude", "gpt", "openai", "anthropic", "gemini", "llama", "bard"})
_PLACEHOLDER_NAMES = frozenset({"todo", "tbd", "test", "test-agent", "placeholder", "changeme", "agent"})
_TEMPLATE_EMAIL = "you@example.com"
_PY_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}


@dataclass(frozen=True)
class Problem:
    code: str
    level: str
    path: str
    message: str

    def to_dict(self):
        return asdict(self)

    def __str__(self):
        return f"{self.path or '/'}: {self.message}"


def load_schema():
    """The pinned schema; refuses a file that no longer matches its hash."""
    raw = SCHEMA_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SCHEMA_SHA256:
        raise RuntimeError(
            f"{SCHEMA_PATH.name} has sha256 {digest}, expected {SCHEMA_SHA256} - "
            "it is a pinned copy of the published schema; update SCHEMA_SHA256 "
            "and SCHEMA_RETRIEVED together, deliberately"
        )
    return json.loads(raw)


def schema_keywords(node):
    """Every schema keyword used anywhere in ``node`` (for the guard test)."""
    found = set()

    def walk(n):
        if isinstance(n, dict):
            for key, value in n.items():
                if key in ("properties", "patternProperties", "$defs"):
                    found.add(key)
                    for sub in value.values():
                        walk(sub)
                else:
                    found.add(key)
                    walk(value)
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(node)
    return found


def _resolve(schema, ref):
    node = schema
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def _pointer(path):
    return "".join("/" + str(p) for p in path)


def _schema_problems(doc, node, schema, path):
    if "$ref" in node:
        merged = dict(_resolve(schema, node["$ref"]))
        merged.update({k: v for k, v in node.items() if k != "$ref"})
        return _schema_problems(doc, merged, schema, path)
    where = _pointer(path)
    out = []

    def add(code, message):
        out.append(Problem(f"aao.schema.{code}", ERROR, where, message))

    expected = node.get("type")
    if expected and (not isinstance(doc, _PY_TYPES[expected]) or (expected != "boolean" and isinstance(doc, bool))):
        add("type", f"must be a {expected}, got {type(doc).__name__}")
        return out
    if "const" in node and doc != node["const"]:
        add("const", f"must be {node['const']!r}, got {doc!r}")
    if "enum" in node and doc not in node["enum"]:
        add("enum", f"must be one of {node['enum']}; got {doc!r}")
    if isinstance(doc, str):
        if "pattern" in node and not re.search(node["pattern"], doc):
            add("pattern", f"{doc!r} does not match /{node['pattern']}/")
        if "minLength" in node and len(doc) < node["minLength"]:
            add("length", f"shorter than {node['minLength']} characters")
        if "maxLength" in node and len(doc) > node["maxLength"]:
            add("length", f"longer than {node['maxLength']} characters")
    if isinstance(doc, list):
        if "minItems" in node and len(doc) < node["minItems"]:
            add("min_items", f"needs at least {node['minItems']} item(s)")
        if "items" in node:
            for i, item in enumerate(doc):
                out += _schema_problems(item, node["items"], schema, path + [i])
    if isinstance(doc, dict):
        for name in node.get("required", []):
            if name not in doc:
                add("required", f"missing required key {name!r}")
        props = node.get("properties", {})
        patterns = node.get("patternProperties", {})
        for key, value in doc.items():
            if key in props:
                out += _schema_problems(value, props[key], schema, path + [key])
            elif any(re.search(p, key) for p in patterns):
                continue
            elif node.get("additionalProperties") is False:
                out.append(Problem(
                    "aao.schema.unknown_key", ERROR, _pointer(path + [key]),
                    f"unknown key {key!r} (only x- prefixed extensions are allowed)",
                ))
    return out


def _cross_field_problems(doc):
    out = []
    roles = doc.get("roles") if isinstance(doc.get("roles"), list) else []
    role_dicts = [(i, r) for i, r in enumerate(roles) if isinstance(r, dict)]
    names = [r.get("name") for _, r in role_dicts]
    seen = set()
    for i, r in role_dicts:
        name = r.get("name")
        if isinstance(name, str) and names.count(name) > 1 and name not in seen:
            seen.add(name)
            out.append(Problem("aao.role.duplicate_name", ERROR, f"/roles/{i}/name",
                               f"duplicate role name {name!r}; role names are unique within an org"))
    repos = doc.get("repositories") if isinstance(doc.get("repositories"), list) else []
    repo_names = {r.get("name") for r in repos if isinstance(r, dict)}
    for i, r in role_dicts:
        works_in = r.get("worksIn") if isinstance(r.get("worksIn"), list) else []
        for w in works_in:
            if w not in repo_names:
                out.append(Problem("aao.role.worksin_undeclared", ERROR, f"/roles/{i}/worksIn",
                                   f"worksIn names {w!r}, which is not a declared repository"))
    escalation = doc.get("escalation")
    if isinstance(escalation, str) and escalation not in names:
        out.append(Problem("aao.escalation.unknown_role", ERROR, "/escalation",
                           f"escalation names {escalation!r}, which is not a role in this document"))
    defaults = [i for i, r in enumerate(repos) if isinstance(r, dict) and r.get("default") is True]
    if len(defaults) > 1:
        out.append(Problem("aao.repository.multiple_default", ERROR, "/repositories",
                           "more than one repository is marked default; at most one is allowed"))
    for i, r in enumerate(repos):
        if not isinstance(r, dict):
            continue
        owned = any(
            r.get("name") in (role.get("worksIn") or [])
            for _, role in role_dicts if isinstance(role.get("worksIn"), list)
        )
        if not owned:
            out.append(Problem("aao.repository.no_owner", ERROR, f"/repositories/{i}",
                               f"repository {r.get('name')!r} is not in any role's worksIn"))
    return out


def _naming_problems(doc):
    out = []
    email = doc.get("accountableTo")
    if isinstance(email, str) and email.strip().lower() == _TEMPLATE_EMAIL:
        out.append(Problem("aao.accountable.placeholder", ERROR, "/accountableTo",
                           f"{_TEMPLATE_EMAIL} is the template placeholder, not an accountable person"))
    roles = doc.get("roles") if isinstance(doc.get("roles"), list) else []
    for i, role in enumerate(roles):
        if not isinstance(role, dict):
            continue
        name = role.get("name")
        path = f"/roles/{i}/name"
        if isinstance(name, str) and name:
            words = name.split("-")
            if len(words) > 3:
                out.append(Problem("aao.role.name.too_many_words", ERROR, path,
                                   f"role name {name!r} has {len(words)} words; at most three"))
            if set(words) & _VENDOR_WORDS:
                out.append(Problem("aao.role.name.vendor", ERROR, path,
                                   f"role name {name!r} references a model vendor (partial vendor list)"))
            if name.lower() in _PLACEHOLDER_NAMES:
                out.append(Problem("aao.role.name.placeholder", ERROR, path,
                                   f"role name {name!r} is a placeholder"))
        if "measure" not in role:
            out.append(Problem("aao.role.no_measure", WARNING, f"/roles/{i}",
                               "no measure: the number this role moves is strongly encouraged"))
    return out


def validate_charter(doc):
    """Every problem with ``doc``, errors and warnings, as ``Problem`` objects.
    A document with no *error* is valid; warnings are advice, not a rule."""
    if not isinstance(doc, dict):
        return [Problem("aao.schema.type", ERROR, "", "a charter must be a JSON object")]
    schema = load_schema()
    problems = _schema_problems(doc, schema, schema, [])
    problems += _cross_field_problems(doc)
    problems += _naming_problems(doc)
    return problems


def errors(problems):
    return [p for p in problems if p.level == ERROR]


def is_valid(doc):
    return not errors(validate_charter(doc))


def load_manifest(path):
    """Load a manifest JSON file and return the dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_manifest(manifest):
    """Compatibility wrapper: the *error* messages as a list of strings
    (empty list means valid)."""
    return [str(p) for p in errors(validate_charter(manifest))]
