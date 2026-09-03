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
from analystos.l2.answer import answer_growth, answer_lookup, answer_ratio
from analystos.l4.export import render_section


def _run_ask(rows, source, ask):
    """Dispatch one ask by its ``kind`` (default ``"lookup"``)."""
    kind = ask.get("kind", "lookup")
    if kind == "lookup":
        return answer_lookup(
            rows, source=source, where=tuple(ask["where"]), select=ask["select"]
        )
    if kind == "growth":
        return answer_growth(
            rows,
            source=source,
            key_column=ask["key_column"],
            from_key=ask["from"],
            to_key=ask["to"],
            value_column=ask["value_column"],
        )
    if kind == "ratio":
        return answer_ratio(
            rows,
            source=source,
            key_column=ask["key_column"],
            key=ask["key"],
            numerator=ask["numerator"],
            denominator=ask["denominator"],
        )
    raise ValueError(f"unknown ask kind: {kind!r}")


def run_job(job_dir, evidence_dir=None):
    """Run the full pipeline for the job in ``job_dir``; return the section text."""
    job_dir = Path(job_dir)
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))

    source_path = job_dir / job["source"]
    source_hash = store(source_path, evidence_dir)          # L0
    rows = extract_table(source_path, job["schema"])        # L1

    findings = []
    for ask in job["asks"]:
        result = _run_ask(rows, source_hash, ask)           # L2
        findings.append({"text": ask["text"], **result})

    return render_section(job["title"], findings)           # L4


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("usage: python3 -m analystos <job-dir>", file=sys.stderr)
        return 2
    job_dir = Path(argv[0])
    section = run_job(job_dir)
    out_path = job_dir / "section.md"
    out_path.write_text(section, encoding="utf-8")
    print(section)
    print(f"\n(written to {out_path})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
