"""Expiring signed report links (Slice 61). HMAC-SHA256 over
``id.format.expiry`` with ``ANALYSTOS_LINK_SECRET``; there is no default
secret, so without one no link can be issued or honoured."""

import hashlib
import hmac
import os
import time

SECRET_ENV = "ANALYSTOS_LINK_SECRET"
MIN_TTL = 60
MAX_TTL = 7 * 24 * 3600
FORMATS = ("html", "pdf", "seal")


def secret(environ=None):
    return ((environ if environ is not None else os.environ).get(SECRET_ENV) or "").strip() or None


def _mac(key, digest, fmt, exp):
    return hmac.new(key.encode("utf-8"), f"{digest}.{fmt}.{exp}".encode("utf-8"), hashlib.sha256).hexdigest()


def sign(key, digest, fmt, ttl_seconds, now=None):
    """``(exp, sig)``. ``ttl_seconds`` outside 60 s..7 d is a ``ValueError``."""
    if fmt not in FORMATS:
        raise ValueError(f"format must be one of {list(FORMATS)}")
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not MIN_TTL <= ttl_seconds <= MAX_TTL:
        raise ValueError(f"ttl_seconds must be an integer from {MIN_TTL} to {MAX_TTL}")
    exp = int((time.time() if now is None else now)) + ttl_seconds
    return exp, _mac(key, digest, fmt, exp)


def check(key, digest, fmt, exp, sig, now=None):
    """``"ok"``, ``"expired"`` or ``"invalid"``. Signature first, so an
    attacker cannot probe expiry of a link they could not have forged."""
    try:
        exp = int(exp)
    except (TypeError, ValueError):
        return "invalid"
    if not isinstance(sig, str) or not hmac.compare_digest(sig, _mac(key, digest, fmt, exp)):
        return "invalid"
    return "expired" if (time.time() if now is None else now) >= exp else "ok"
