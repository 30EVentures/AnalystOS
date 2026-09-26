"""Per-caller API keys (Slice 61). Only a SHA-256 of a key is ever configured
or stored; the raw key is shown once, by ``newkey``."""

import hashlib
import hmac
import os
import re
import secrets

KEYS_ENV = "ANALYSTOS_API_KEYS"
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
KEY_PREFIX = "aos_"


def hash_key(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_key(name):
    """``(raw_key, config_entry)`` - print both, store neither."""
    if not _NAME_RE.match(name):
        raise ValueError("name must be lowercase letters, digits and hyphens, 1-32 chars, not starting with a hyphen")
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, f"{name}:{hash_key(raw)}"


def load_keys(environ=None):
    """``{name: sha256hex}`` from ``ANALYSTOS_API_KEYS`` (comma-separated
    ``name:hash``). Malformed entries are ignored, never half-trusted."""
    raw = (environ if environ is not None else os.environ).get(KEYS_ENV, "")
    keys = {}
    for part in raw.split(","):
        name, _, digest = part.strip().partition(":")
        if _NAME_RE.match(name) and _HASH_RE.match(digest):
            keys[name] = digest
    return keys


def authenticate(authorization_header, keys):
    """The caller's name for a valid ``Bearer`` key, else ``None``. Compares
    every configured hash in constant time so timing does not reveal which
    caller exists."""
    scheme, _, token = (authorization_header or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    presented = hash_key(token.strip())
    found = None
    for name, digest in keys.items():
        if hmac.compare_digest(presented, digest):
            found = name
    return found
