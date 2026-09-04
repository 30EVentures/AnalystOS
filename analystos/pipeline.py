"""Glue - run L0 -> L1 -> L2 -> L4 for one job, end to end.

A *job* is a directory holding:

    job.json        title, source filename, schema, and asks (or a template)
    <source file>   the table - .csv, .xlsx, .docx, .pptx, or .pdf

Each ask is ``{"text": "... {answer} ...", "where": [column, value],
"select": column}`` (or a "growth"/"ratio" kind - see analystos.l2.answer).
Instead of ``"asks"``, a job may give ``"template": "income_statement"`` to
generate the standard asks from whatever line items are recognized in the
source - see analystos.templates.

``build_report`` is the actual pipeline: given a source file, a schema, and
either ``asks`` or a ``template``, it stores the source (L0), extracts its
table with the extractor matching the file's extension (L1), answers each
ask with a citation (L2), and renders one section (L4). ``run_job`` is a thin
wrapper that reads those arguments from a job.json file; the HTTP API
(api/analyze.py) calls ``build_report`` directly from an uploaded file
instead - both drive the identical pipeline, so there is exactly one
implementation of "how a report gets built," not two.

A ``.pdf`` source is different: pdfplumber *infers* a table's shape from the
page's visual layout rather than reading a real table object, so it can be
wrong in ways the other formats can't be. ``build_report`` refuses to go past
L1 for a PDF source unless the job says ``"pdf_confirmed": true`` - a person
has to have looked at the actual extracted table (the error raised without
that flag shows it) before it can be cited. See ``specs/slice-23/spec.md``.
"""

import json
import subprocess
import sys
from pathlib import Path

from analystos.l0.store import store
from analystos.l1.extract import extract_table
from analystos.l1.extract_docx import extract_table_docx
from analystos.l1.extract_pdf import extract_table_pdf
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
    if suffix == ".pdf":
        return extract_table_pdf(
            source_path,
            schema,
            page=job.get("page"),
            table_index=job.get("table_index", 0),
        )
    raise ValueError(
        f"unsupported source file type {suffix!r}; "
        "expected .csv, .xlsx, .docx, .pptx, or .pdf"
    )


def _pdf_preview(rows):
    """Render extracted PDF rows as plain text for the confirm-before-cite error."""
    if not rows:
        return "(no rows)"
    headers = list(rows[0].keys())
    lines = ["  |  ".join(headers)]
    for row_num, row in zip(rows.row_nums, rows):
        lines.append(f"[row {row_num}]  " + "  |  ".join(str(row[h]) for h in headers))
    return "\n".join(lines)


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


def build_report(
    source_path,
    schema,
    title,
    *,
    asks=None,
    template=None,
    currency_unit="actual",
    evidence_dir=None,
    extract_options=None,
):
    """Run L0 -> L1 -> L2 -> L4 for one source file; return the section text.

    Exactly one of ``asks`` or ``template`` is required. ``extract_options``
    is passed through to the L1 extractor for format-specific choices
    (``sheet``, ``table_index``, ``slide_index``, ``page``) - see the
    individual extractors in ``analystos.l1`` - and also carries
    ``pdf_confirmed`` for the PDF confirm-before-cite gate below.
    """
    if (asks is None) == (template is None):
        raise ValueError('exactly one of "asks" or "template" is required')

    extract_options = extract_options or {}
    source_path = Path(source_path)
    source_hash = store(source_path, evidence_dir)                          # L0
    rows = _extract_rows(source_path, schema, extract_options)              # L1

    if source_path.suffix.lower() == ".pdf" and not extract_options.get("pdf_confirmed"):
        raise ValueError(
            "PDF-extracted tables must be confirmed by a person before use - "
            "a PDF has no real table object, so extraction can misread it in "
            "ways the other formats can't. Review the table below; if it's "
            'correct, add "pdf_confirmed": true to job.json and re-run '
            "(AnalystOS never edits or guesses a PDF-derived value itself):\n\n"
            f"{_pdf_preview(rows)}"
        )

    if template:
        asks = build_asks(template, rows)

    findings = []
    for ask in asks:
        result = _run_ask(rows, source_hash, ask)                          # L2
        findings.append({"text": ask["text"], "format": ask.get("format"), **result})

    return render_section(title, findings, currency_unit)                   # L4


def run_job(job_dir, evidence_dir=None):
    """Run the job in ``job_dir`` (reads job.json); return the section text.

    ``build_report`` raises if job.json has neither "asks" nor "template"
    (or both) - see there for the exact message.
    """
    job_dir = Path(job_dir)
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))

    return build_report(
        job_dir / job["source"],
        job["schema"],
        job["title"],
        asks=job.get("asks"),
        template=job.get("template"),
        currency_unit=job.get("currency_unit", "actual"),
        evidence_dir=evidence_dir,
        extract_options=job,
    )


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
