"""Glue - run L0 -> L1 -> L2 -> L4 for one job, end to end.

A *job* is a directory holding:

    job.json        title, source filename, schema, and asks (or a template)
    <source file>   the table - .csv, .xlsx, .docx, or .pptx

Each ask is ``{"text": "... {answer} ...", "where": [column, value],
"select": column}`` (or a "growth"/"ratio" kind - see analystos.l2.answer).
Instead of ``"asks"``, a job may give ``"template": "income_statement"`` to
generate the standard asks from whatever line items are recognized in the
source - see analystos.templates.

``run_job`` reads the job, stores the source (L0), extracts its table with
the extractor matching the source file's extension (L1), answers each ask
with a citation (L2), and renders one section (L4). It returns the section
as a string.
"""

import json
import subprocess
import sys
from pathlib import Path

from analystos.l0.store import store
from analystos.l1.extract import extract_table
from analystos.l1.extract_docx import extract_table_docx
from analystos.l1.extract_pptx import extract_table_pptx
from analystos.l1.extract_xlsx import extract_table_xlsx
from analystos.l2.answer import answer_growth, answer_lookup, answer_ratio
from analystos.l4.export import render_html, render_section
from analystos.templates import build_asks


def _extract_rows(source_path, schema, job):
    """Dispatch to the extractor matching ``source_path``'s file extension."""
    suffix = source_path.suffix.lower()
    if suffix == ".csv":
        return extract_table(source_path, schema)
    if suffix == ".xlsx":
        return extract_table_xlsx(source_path, schema, sheet=job.get("sheet"))
    if suffix == ".docx":
        return extract_table_docx(source_path, schema, table_index=job.get("table_index", 0))
    if suffix == ".pptx":
        return extract_table_pptx(
            source_path,
            schema,
            slide_index=job.get("slide_index"),
            table_index=job.get("table_index", 0),
        )
    raise ValueError(
        f"unsupported source file type {suffix!r}; expected .csv, .xlsx, .docx, or .pptx"
    )


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
    source_hash = store(source_path, evidence_dir)                    # L0
    rows = _extract_rows(source_path, job["schema"], job)             # L1

    if "asks" in job:
        asks = job["asks"]
    elif "template" in job:
        asks = build_asks(job["template"], rows)
    else:
        raise ValueError("job.json needs either \"asks\" or \"template\"")

    findings = []
    for ask in asks:
        result = _run_ask(rows, source_hash, ask)                     # L2
        findings.append({"text": ask["text"], "format": ask.get("format"), **result})

    currency_unit = job.get("currency_unit", "actual")
    return render_section(job["title"], findings, currency_unit)      # L4


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("usage: python3 -m analystos <job-dir>", file=sys.stderr)
        return 2
    job_dir = Path(argv[0])
    section = run_job(job_dir)
    md_path = job_dir / "section.md"
    html_path = job_dir / "section.html"
    md_path.write_text(section, encoding="utf-8")
    html_path.write_text(render_html(section), encoding="utf-8")
    print(section)
    print(f"\n(written to {md_path} and {html_path})", file=sys.stderr)
    # Open the page for the person running it; never during tests (no terminal).
    if sys.platform == "darwin" and sys.stdout.isatty():
        subprocess.run(["open", str(html_path)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
