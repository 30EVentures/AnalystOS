"""``python3 -m analystos.api_v1 newkey <name>``, ``... measures [audit.jsonl]`` and
``... verify-audit <audit.jsonl> [--public-key B64URL] [--expect-head HASH]``
(exit 0 no check failed, 1 a check failed, 2 unreadable input)."""

import json
import sys
from pathlib import Path

from analystos.api_v1 import auth, store as store_mod
from analystos.api_v1.audit import measures
from analystos.api_v1.audit_chain import verify_audit_log


def main(argv=None, stdout=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    if len(argv) == 2 and argv[0] == "newkey":
        try:
            raw, entry = auth.new_key(argv[1])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        stdout.write(f"API key (shown once, give it to the caller): {raw}\n")
        stdout.write(f"Add to {auth.KEYS_ENV} (comma-separated): {entry}\n")
        return 0
    if argv[:1] == ["measures"] and len(argv) <= 2:
        if len(argv) == 2:
            path = Path(argv[1])
            try:
                events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            except (OSError, ValueError) as exc:
                print(f"could not read {path}: {exc}", file=sys.stderr)
                return 2
        else:
            store = store_mod.FileStore.from_env()
            if store is None:
                print(f"give an audit.jsonl path, or set {store_mod.STORE_ENV}", file=sys.stderr)
                return 2
            events = store.read_audit()
        stdout.write(json.dumps(measures(events), indent=2) + "\n")
        return 0
    if argv[:1] == ["verify-audit"]:
        path = public_key = expected_head = None
        try:
            i = 1
            while i < len(argv):
                if argv[i] == "--public-key":
                    public_key, i = argv[i + 1], i + 2
                elif argv[i] == "--expect-head":
                    expected_head, i = argv[i + 1], i + 2
                elif path is None and not argv[i].startswith("--"):
                    path, i = argv[i], i + 1
                else:
                    raise ValueError(f"unexpected argument {argv[i]!r}")
            if path is None:
                raise ValueError("give the audit.jsonl path")
            outcome = verify_audit_log(path, public_key=public_key, expected_head=expected_head)
        except (OSError, ValueError, IndexError) as exc:
            stdout.write(json.dumps({"error": str(exc) or "usage: verify-audit <audit.jsonl> [--public-key B64URL] [--expect-head HASH]"}) + "\n")
            return 2
        stdout.write(json.dumps(outcome, indent=2) + "\n")
        return 0 if outcome["ok"] else 1
    print("usage: python3 -m analystos.api_v1 newkey <name> | measures [audit.jsonl] | verify-audit <audit.jsonl> [--public-key B64URL] [--expect-head HASH]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
