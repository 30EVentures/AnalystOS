"""Report storage and the append-only audit log (Slice 61).

``FileStore`` is the only implementation and is **not durable on Vercel** (its
filesystem is ephemeral): use a persistent volume, or write an adapter with
the same five methods for an object store. Everything is addressed by the
64-hex seal digest, validated before it touches a path.
"""

import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

STORE_ENV = "ANALYSTOS_STORE_DIR"
TTL_ENV = "ANALYSTOS_REPORT_TTL_DAYS"
DEFAULT_TTL_DAYS = 30
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_KINDS = {"html": "report.html", "pdf": "report.pdf", "seal": "seal.json", "meta": "meta.json"}


def ttl_days(environ=None):
    try:
        days = float((environ if environ is not None else os.environ).get(TTL_ENV, DEFAULT_TTL_DAYS))
        return days if days > 0 else DEFAULT_TTL_DAYS
    except (TypeError, ValueError):
        return DEFAULT_TTL_DAYS


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FileStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, environ=None):
        root = (environ if environ is not None else os.environ).get(STORE_ENV, "").strip()
        return cls(root) if root else None

    def _dir(self, digest):
        if not DIGEST_RE.match(digest or ""):
            raise ValueError("not a report id")
        return self.root / "reports" / digest

    def put(self, digest, meta, html, pdf, seal_bundle):
        directory = self._dir(digest)
        directory.mkdir(parents=True, exist_ok=True)
        self._write(directory / _KINDS["html"], html.encode("utf-8"))
        if pdf is not None:
            self._write(directory / _KINDS["pdf"], pdf)
        self._write(directory / _KINDS["seal"], json.dumps(seal_bundle, ensure_ascii=False).encode("utf-8"))
        self._write(directory / _KINDS["meta"], json.dumps(meta).encode("utf-8"))  # last: its presence means complete

    @staticmethod
    def _write(path, data):
        fd, tmp = tempfile.mkstemp(dir=path.parent)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)

    def meta(self, digest):
        try:
            return json.loads((self._dir(digest) / _KINDS["meta"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def read(self, digest, kind):
        try:
            return (self._dir(digest) / _KINDS[kind]).read_bytes()
        except (OSError, ValueError, KeyError):
            return None

    def purge_expired(self, now=None):
        now = time.time() if now is None else now
        removed = 0
        base = self.root / "reports"
        for directory in base.iterdir() if base.exists() else []:
            meta = self.meta(directory.name)
            if meta is not None and meta.get("expires_ts", now + 1) <= now:
                for path in directory.iterdir():
                    path.unlink()
                directory.rmdir()
                removed += 1
        return removed

    def append_audit(self, event):
        with open(self.root / "audit.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def read_audit(self):
        path = self.root / "audit.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def emit_audit(store, event):
    """Append to the store's log; with no store, one JSON line on stderr so
    the host's logs still carry it."""
    event = {"ts": iso(time.time()), **event}
    if store is not None:
        store.append_audit(event)
    else:
        print(json.dumps({"audit": event}, sort_keys=True), file=sys.stderr)
