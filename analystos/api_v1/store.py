"""Report storage and the hash-chained, signed audit log (Slices 61, 84).

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
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from analystos.api_v1 import audit_chain
from analystos.l4.seal import load_signing_key

try:  # POSIX advisory lock so two processes cannot extend the chain from the same head
    import fcntl
except ImportError:  # pragma: no cover - not Windows-tested
    fcntl = None
_AUDIT_THREAD_LOCK = threading.Lock()

STORE_ENV = "ANALYSTOS_STORE_DIR"
TTL_ENV = "ANALYSTOS_REPORT_TTL_DAYS"
DEFAULT_TTL_DAYS = 30
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
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

    def mark_reviewed(self, digest, review):
        """Merge ``{"reviewed": review}`` into the stored meta. Raises
        ``ValueError`` if there is no such report (caller checks first)."""
        directory = self._dir(digest)
        meta = self.meta(digest)
        if meta is None:
            raise ValueError("no such report")
        self._write(directory / _KINDS["meta"], json.dumps({**meta, "reviewed": review}).encode("utf-8"))

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

    def _job_dir(self, job_id):
        if not JOB_ID_RE.match(job_id or ""):
            raise ValueError("not a job id")
        return self.root / "jobs" / job_id

    def create_job(self, job_id, meta, filename, data):
        """A ``pending`` job: its upload, kept only until ``run`` consumes it,
        and its meta (caller, status, title, ...)."""
        directory = self._job_dir(job_id)
        directory.mkdir(parents=True, exist_ok=True)
        self._write(directory / "upload.name", filename.encode("utf-8"))
        self._write(directory / "upload", data)
        self._write(directory / "meta.json", json.dumps(meta).encode("utf-8"))  # last: its presence means complete

    def job_meta(self, job_id):
        try:
            return json.loads((self._job_dir(job_id) / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def job_upload(self, job_id):
        """``(filename, bytes)``, or ``None`` once ``run`` has consumed it."""
        directory = self._job_dir(job_id)
        try:
            return (directory / "upload.name").read_text(encoding="utf-8"), (directory / "upload").read_bytes()
        except OSError:
            return None

    def update_job(self, job_id, **fields):
        """Merge ``fields`` into the job's meta. Raises ``ValueError`` if
        there is no such job (caller checks first)."""
        directory = self._job_dir(job_id)
        meta = self.job_meta(job_id)
        if meta is None:
            raise ValueError("no such job")
        meta = {**meta, **fields}
        self._write(directory / "meta.json", json.dumps(meta).encode("utf-8"))
        return meta

    def delete_job_upload(self, job_id):
        """Drop the uploaded bytes once a job has run - never kept longer
        than it has to be, same rule as a synchronous analysis."""
        directory = self._job_dir(job_id)
        for name in ("upload", "upload.name"):
            path = directory / name
            if path.exists():
                path.unlink()

    def append_audit(self, event):
        """Append ``event`` as the next line of a hash chain (Slice 84; see
        ``analystos.api_v1.audit_chain``). Signed with ``ANALYSTOS_SEAL_KEY``
        when it is set and well formed; otherwise still chained, marked
        ``"log_signing": "none"``. A malformed key never loses the line."""
        try:
            signing_key = load_signing_key()
        except ValueError:
            signing_key = None
        path = self.root / "audit.jsonl"
        with _AUDIT_THREAD_LOCK, open(path, "a+b") as handle:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_EX)  # released when the handle closes
            head = self._chain_head(handle)
            seq, prev = (0, audit_chain.GENESIS) if head is None else (head[0] + 1, head[1])
            line = json.dumps(audit_chain.seal_entry(event, seq, prev, signing_key), sort_keys=True) + "\n"
            handle.seek(0, os.SEEK_END)
            if handle.tell() and self._last_byte(handle) != b"\n":
                line = "\n" + line  # never glue onto a line that was cut short
            handle.write(line.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _last_byte(handle):
        handle.seek(-1, os.SEEK_END)
        return handle.read(1)

    @staticmethod
    def _chain_head(handle):
        """``(seq, entry_hash)`` of the last chained line, or ``None``. Reads
        only the tail in the normal case; scans the whole file only when the
        last line is not chained (a legacy-only log, or damage)."""
        handle.seek(0, os.SEEK_END)
        pos = handle.tell()
        buf = b""
        while pos > 0:
            step = min(65536, pos)
            pos -= step
            handle.seek(pos)
            buf = handle.read(step) + buf
            if b"\n" in buf.rstrip(b"\n"):
                break
        tail = buf.rstrip(b"\n").rsplit(b"\n", 1)[-1].decode("utf-8", "replace")
        found = audit_chain.last_chained([tail])
        if found is not None or pos == 0 and not buf.strip():
            return found
        handle.seek(0)
        return audit_chain.last_chained(handle.read().decode("utf-8", "replace").splitlines())

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
