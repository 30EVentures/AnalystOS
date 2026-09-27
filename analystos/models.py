"""Which model AnalystOS asks (Slice 70): one setting instead of four constants."""

import os
import re

MODEL_ENV = "ANALYSTOS_MODEL"
DEFAULT_MODEL = "claude-sonnet-5"
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")


def model_name(environ=None):
    """``ANALYSTOS_MODEL`` if set, else the default. Read on every call, so a
    deployment can change it without a code change. A value that does not look
    like a model id is a ``ValueError``."""
    raw = ((environ if environ is not None else os.environ).get(MODEL_ENV) or "").strip()
    if not raw:
        return DEFAULT_MODEL
    if not _MODEL_RE.match(raw):
        raise ValueError(f"{MODEL_ENV} must be a model id (letters, digits, . _ : -), got {raw!r}")
    return raw
