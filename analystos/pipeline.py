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

``schema`` is optional. Given, it's used exactly as before. Omitted, it's
guessed from the source's own data (``analystos.l1.detect.extract_any``) -
so a job, or an API call, doesn't have to declare one at all. See
``specs/slice-25/spec.md``.

Neither ``asks`` nor ``template`` given at all - not even ``"auto"`` - is no
longer an error. It's the new default: the source is read as plain text,
whatever shape it actually is (``analystos.l1.document_text``, not forced
into a table), analyzed by a model that can only feature a number it can
prove is real (``analystos.l2.analyze`` - every quote checked against the
actual source text, every computed value independently recomputed, never
the model's own arithmetic taken on faith). See ``specs/slice-26/spec.md``.
This doesn't apply to a ``.pdf`` source's existing table-extraction gate
above - reading a PDF's plain text (what this path does) has none of the
column-boundary-inference risk table extraction does, so no confirmation
step is needed here.

A second, narrower model call (``analystos.l2.narrate.write_narrative``)
then decides how to write about those already-verified facts - real
structure and grouping instead of one paragraph per fact in extraction
order - but it can only reference a fact by placeholder, never state a
number itself. If that call fails for any reason, the report falls back
to the plain per-segment rendering (``render_narrated_section``) that
Slice 26 already produces - a worse-structured report, never a lost one.
See ``specs/slice-27/spec.md``.
"""

import json
import subprocess
import sys
from pathlib import Path

from analystos.l0.store import store
from analystos.l1.detect import extract_any
from analystos.l1.boilerplate import strip_forward_looking_boilerplate
from analystos.l1.document_text import extract_document_text
from analystos.l1.image_facts import tag_image_sourced_segments
from analystos.l4.seal import build_bundle, load_signing_key
from analystos.l4.deterministic_report import build_deterministic_report
from analystos.l2.analyze import analyze_document
from analystos.l2.answer import answer_growth, answer_lookup, answer_ratio
from analystos.l2.narrate import repair_language_issues, write_narrative
from analystos.l2.proofread import proofread_report
from analystos.l4.export import (
    render_html,
    render_narrated_section,
    render_pdf,
    render_section,
)
from analystos.l4.rich_export import render_rich_report
from analystos.l4.rich_pdf import render_rich_pdf
from analystos.templates import build_asks

# A Gate 2 repair is a small, targeted call per flagged issue, not a full
# regenerate - see repair_language_issues - so it gets a couple of rounds
# to converge before falling back.
_MAX_GATE2_REPAIR_ROUNDS = 2


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


def _fill_trace(trace, tier, source_hash, segments, report, document_text, analysis, reason=None):
    if trace is None:
        return
    trace.update(
        tier=tier, source_hash=source_hash, segments=segments, report=report,
        document_text=document_text, analysis=dict(analysis), fallback_reason=reason,
    )


def build_report(
    source_path,
    schema=None,
    title=None,
    *,
    asks=None,
    template=None,
    currency_unit="actual",
    evidence_dir=None,
    extract_options=None,
    llm_client=None,
    want_pdf=False,
    trace=None,
):
    """Run L0 -> L1 -> L2 -> L4 for one source file; return the section text.

    Giving neither ``asks`` nor ``template`` runs the new default: a
    document-text read plus a verified, model-assisted analysis - see the
    module docstring. Giving exactly one of them runs the original,
    schema/table-driven path unchanged. Giving both is still an error.
    ``schema`` is optional there too - omitted, it's guessed from the
    source's own data (see the module docstring). ``extract_options`` is
    passed through to the L1 extractor for format-specific choices
    (``sheet``, ``table_index``, ``slide_index``, ``page``) and also
    carries ``pdf_confirmed`` for the PDF confirm-before-cite gate.
    ``llm_client`` is passed through to both ``analyze_document`` and
    ``write_narrative`` - tests supply a mock there; production leaves it
    unset and a real client is built per call.

    ``want_pdf=True`` is opt-in (Slice 48): the default single-string
    return contract is unchanged for every existing caller. Asking for a
    PDF makes this return a ``(section_text, pdf_bytes)`` pair instead -
    ``render_rich_pdf`` for the rich (v4) report, ``render_pdf`` (the
    existing flat renderer) for the plain-fallback or schema/template
    path - so one call produces both without re-running the pipeline.

    ``trace``, when a dict is passed, is filled with what the run did, for a
    caller that must seal or log it (Slice 60): ``tier`` ("written",
    "deterministic", "plain" or "table"), ``source_hash``, ``segments`` and
    ``report`` (the structure that was rendered; ``None`` for plain/table),
    ``document_text``, ``analysis`` (proposed/verified/dropped counts) and
    ``fallback_reason``. It never changes what is returned.
    """
    if asks is not None and template is not None:
        raise ValueError('exactly one of "asks" or "template" is required')

    extract_options = extract_options or {}
    source_path = Path(source_path)
    title = title or f"Review of {source_path.name}"
    source_hash = store(source_path, evidence_dir)                          # L0

    if asks is None and template is None:
        document_text = extract_document_text(source_path, client=llm_client)  # L1 (text)
        document_text = strip_forward_looking_boilerplate(document_text)    # L1 (legal boilerplate out)
        analysis_stats = {}
        segments = analyze_document(document_text, title, client=llm_client, stats=analysis_stats)  # L2 (verified)
        segments = tag_image_sourced_segments(segments, document_text)       # L1 (image provenance)
        # currency_unit ("thousands"/"millions") means "the source data is
        # pre-scaled by this factor" - true of a CSV/Excel table whose
        # header says "figures in thousands," never of a quoted number
        # copied verbatim from prose (it's already the real, actual value).
        # Applying it here would silently inflate every dollar figure.
        try:
            # A second, narrower call decides how to *structure and write*
            # the report about the already-verified facts above - an
            # executive summary, sections, charts drawn only from cited
            # facts, a distinct outlook block (Slice 27 + 30). It cannot
            # state a number itself; any failure here (a bad reference, a
            # stray digit, a malformed structure, a wrong direction word,
            # an API error) falls back to the plain per-segment rendering
            # below rather than losing the report over a writing-quality
            # improvement. See specs/slice-27/spec.md, slice-30, slice-38.
            report = write_narrative(segments, title, client=llm_client)  # L2 (structure + writing) - Gate 1
            # Gate 2, run separately and blind to the facts: language
            # quality only (spelling, grammar, duplicated text, leftover
            # artifacts). Both gates are mandatory - a report that fails
            # either one is never shown. Unlike a raw fallback, a Gate 2
            # rejection gets the same "repair the one flagged piece,
            # don't regenerate everything" treatment Gate 1 already has -
            # found live 2026-09-11: a report can pass Gate 1 (every
            # number correctly cited) and still fail Gate 2 on pure
            # wording (redundant phrasing, inconsistent terminology),
            # which a full regenerate would just as likely trade for a
            # different wording nit as actually fix. See
            # specs/slice-38/spec.md and specs/slice-40/spec.md.
            passed, issues = proofread_report(report, client=llm_client)
            for _ in range(_MAX_GATE2_REPAIR_ROUNDS):
                if passed:
                    break
                print(
                    f"[analystos.pipeline] Gate 2 failed ({len(issues)} issue(s)) - repairing",
                    file=sys.stderr,
                )
                for issue in issues:
                    print(
                        f"[analystos.pipeline] Gate 2 issue at "
                        f"{issue.get('location') or '(unlocated)'}: {issue.get('problem')}",
                        file=sys.stderr,
                    )
                report = repair_language_issues(report, issues, segments, client=llm_client)
                passed, issues = proofread_report(report, client=llm_client)
            if not passed:
                for issue in issues:
                    print(
                        f"[analystos.pipeline] Gate 2 issue at "
                        f"{issue.get('location') or '(unlocated)'}: {issue.get('problem')}",
                        file=sys.stderr,
                    )
                raise ValueError(f"Gate 2 (language quality) did not pass after repair ({len(issues)} issue(s))")
            html = render_rich_report(report, segments, source_hash, "actual")  # L4 (rich HTML)
            _fill_trace(trace, "written", source_hash, segments, report, document_text, analysis_stats)
            if want_pdf:
                return html, render_rich_pdf(report, segments, source_hash, "actual")
            return html
        except ValueError as exc:
            reason = str(exc)
            print(f"[analystos.pipeline] rich report fell back: {exc}", file=sys.stderr)
            # Slice 52 - a mandatory, deterministic floor: zero model
            # calls, so it cannot fail Gate 1/Gate 2 the way the
            # narrative that just failed did. Renders through the exact
            # same render_rich_report/render_rich_pdf as the best case -
            # no visual "degraded" signal, ever. Only None (fewer than 2
            # numeric facts anywhere) falls through to the true last
            # resort below.
            deterministic = build_deterministic_report(segments, title)
            if deterministic is not None:
                html = render_rich_report(deterministic, segments, source_hash, "actual")
                _fill_trace(trace, "deterministic", source_hash, segments, deterministic, document_text,
                            analysis_stats, reason)
                if want_pdf:
                    return html, render_rich_pdf(deterministic, segments, source_hash, "actual")
                return html
            print(
                "[analystos.pipeline] deterministic floor also had too few "
                "numeric facts - falling through to the plain renderer",
                file=sys.stderr,
            )
            plain = render_narrated_section(title, source_hash, segments, "actual")  # L4 (plain fallback)
            _fill_trace(trace, "plain", source_hash, segments, None, document_text, analysis_stats, reason)
            if want_pdf:
                return plain, render_pdf(plain)
            return plain

    schema, rows = extract_any(source_path, schema, extract_options)        # L1 (table)

    if source_path.suffix.lower() == ".pdf" and not extract_options.get("pdf_confirmed"):
        raise ValueError(
            "PDF-extracted tables must be confirmed by a person before use - "
            "a PDF has no real table object, so extraction can misread it in "
            "ways the other formats can't. Review the table below; if it's "
            "correct, resubmit with the PDF confirmed - job.json's "
            '"pdf_confirmed": true for the CLI, or the "Detect columns" '
            "step for the live site - AnalystOS never edits or guesses a "
            "PDF-derived value itself:\n\n"
            f"{_pdf_preview(rows)}"
        )

    if template:
        asks = build_asks(template, rows)

    findings = []
    for ask in asks:
        result = _run_ask(rows, source_hash, ask)                          # L2
        findings.append({"text": ask["text"], "format": ask.get("format"), **result})

    section = render_section(title, findings, currency_unit)                # L4
    _fill_trace(trace, "table", source_hash, [], None, None, {})
    if want_pdf:
        return section, render_pdf(section)
    return section


def run_job(job_dir, evidence_dir=None, want_pdf=False, trace=None):
    """Run the job in ``job_dir`` (reads job.json); return the section text.

    ``build_report`` raises only if job.json has *both* "asks" and
    "template" - having neither now runs the new document-analysis default
    (see ``build_report``'s docstring). "schema" and "title" are optional
    in job.json too. ``want_pdf`` is passed straight through - see
    ``build_report``'s docstring.
    """
    job_dir = Path(job_dir)
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))

    return build_report(
        job_dir / job["source"],
        job.get("schema"),
        job.get("title"),
        asks=job.get("asks"),
        template=job.get("template"),
        currency_unit=job.get("currency_unit", "actual"),
        evidence_dir=evidence_dir,
        extract_options=job,
        want_pdf=want_pdf,
        trace=trace,
    )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("usage: python3 -m analystos <job-dir>", file=sys.stderr)
        return 2
    job_dir = Path(argv[0])
    trace = {}
    section, pdf_bytes = run_job(job_dir, want_pdf=True, trace=trace)
    html_path = job_dir / "section.html"
    pdf_path = job_dir / "section.pdf"

    # The narrated default path returns a finished HTML document
    # (analystos.l4.rich_export); the schema/table path returns section
    # markdown that render_html turns into a page. Either way, want_pdf=True
    # above already produced the matching PDF (render_rich_pdf for the rich
    # report, render_pdf for the flat one) - see specs/slice-48/spec.md.
    if section.lstrip().lower().startswith("<!doctype html"):
        html_path.write_text(section, encoding="utf-8")
        pdf_path.write_bytes(pdf_bytes)
        print(f"(written to {html_path} and {pdf_path})", file=sys.stderr)
        # Slice 60: a narrated report is sealed next to its HTML. Signed only
        # when ANALYSTOS_SEAL_KEY is set; otherwise integrity-only.
        if trace.get("segments"):
            seal_path = job_dir / "section.seal.json"
            bundle = build_bundle(trace, signing_key=load_signing_key())
            seal_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            signed = "signed" if bundle["signature"] else "unsigned"
            print(f"(sealed, {signed}: {seal_path})", file=sys.stderr)
    else:
        md_path = job_dir / "section.md"
        md_path.write_text(section, encoding="utf-8")
        html_path.write_text(render_html(section), encoding="utf-8")
        pdf_path.write_bytes(pdf_bytes)
        print(section)
        print(f"\n(written to {md_path}, {html_path}, and {pdf_path})", file=sys.stderr)

    # Open the page for the person running it; never during tests (no terminal).
    if sys.platform == "darwin" and sys.stdout.isatty():
        subprocess.run(["open", str(html_path)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
