"""Slice 8 glue - run L0 -> L1 -> L2 -> L4 for one job, end to end.

A *job* is a directory holding:

    job.json        title, source filename, schema, and a list of asks
    <source>.csv    the table

Each ask is ``{"text": "... {answer} ...", "where": [column, value],
"select": column}``.

``run_job`` reads the job, stores the source (L0), extracts the table (L1),
answers each ask with a citation (L2), and renders one section (L4). It
returns the section as a string.
"""

import json
import sys
from pathlib import Path

from analystos.l0.store import store
from analystos.l1.extract import extract_table
from analystos.l2.answer import answer_lookup
from analystos.l4.export import render_section


def run_job(job_dir, evidence_dir=None):
    """Run the full pipeline for the job in ``job_dir``; return the section text."""
    job_dir = Path(job_dir)
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))

    source_path = job_dir / job["source"]
    source_hash = store(source_path, evidence_dir)          # L0
    rows = extract_table(source_path, job["schema"])        # L1

    findings = []
    for ask in job["asks"]:
        result = answer_lookup(                             # L2
            rows,
            source=source_hash,
            where=tuple(ask["where"]),
            select=ask["select"],
        )
        findings.append({"text": ask["text"], **result})

    return render_section(job["title"], findings)           # L4


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("usage: python3 -m analystos <job-dir>", file=sys.stderr)
        return 2
    print(run_job(argv[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
