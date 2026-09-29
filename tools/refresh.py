"""Regenerate everything that is generated, in the right order (Slice 71).

    python3 tools/refresh.py           # regenerate
    python3 tools/refresh.py --check   # exit 1 if anything is stale, change nothing

Order matters: the docs copy and machine files first, then the spec index, then the
homepage counts (which count the specs and discover the tests). The suite fails when
any of these is stale; this is the one command that fixes them.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = ["build_site_machine.py", "build_specs_index.py", "site_counts.py", "studio_chrome.py"]


def main(argv=None):
    check = "--check" in (sys.argv[1:] if argv is None else argv)
    status = 0
    for step in STEPS:
        command = [sys.executable, str(ROOT / "tools" / step)] + (["--check"] if check else [])
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        print(f"{step}: {done.stdout.strip() or done.stderr.strip()}")
        status = status or done.returncode
    return status


if __name__ == "__main__":
    sys.exit(main())
