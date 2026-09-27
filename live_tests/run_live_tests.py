"""Slice 51 - the deliberate, real-money live-test suite.

NOT part of `python3 -m unittest discover -s tests` - this whole
directory lives outside `tests/` specifically so it is never collected
there and never runs without being explicitly invoked. Every call this
script makes is real: a real ``anthropic.Anthropic()`` client (built
from ``ANTHROPIC_API_KEY`` in your own shell - this script never sees or
stores the key beyond what the SDK itself reads from the environment),
real tokens, real dollars. See specs/slice-51/spec.md and README.md in
this directory.

Run from the repo root, with the venv active and a real
ANTHROPIC_API_KEY exported in your own shell:

    python3 live_tests/run_live_tests.py [--ceiling 1.00] [--log-file path]

The four fixed documents (``live_tests/fixtures/``, built by
``build_fixtures.py``) each exercise a genuinely different path: the
schema/template path (no model narrative at all), the narrated-default
path over a plain single-column DOCX, the narrated-default path over a
two-column PDF (Slice 50's column-aware extraction), and the
narrated-default path over a PDF with an embedded image (Slice 50's
image-fact path).

Each run is graded PASS, DEGRADED or FAIL (``evaluate``; Slice 67): PASS means
the expected tier with enough verified facts and a seal that fully verifies,
not merely that nothing raised.

Hard-stops the instant the running total would cross the ceiling - the
call that would have crossed it is never dispatched, and the run exits
non-zero.
"""

import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `import analystos`

from analystos.l4.seal import build_bundle  # noqa: E402
from analystos.l4.seal_verify import verify_bundle  # noqa: E402
from analystos.pipeline import build_report  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_DEFAULT_CEILING = 1.00

# Sourced from https://claude.com/pricing, checked 2026-09-11 - $2/MTok
# input, $10/MTok output for Sonnet 5. Update this table (and the date
# above) if pricing changes: a stale price here would silently defeat
# the entire point of a *real* dollar ceiling.
_PRICE_PER_MTOK = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
}

DOCUMENTS = [
    {
        "name": "csv-schema-template-path",
        "path": FIXTURES_DIR / "income_statement.csv",
        "path_kind": "schema/template",
        "kwargs": {"template": "income_statement", "title": "Live test - CSV/schema path"},
        "expect": {"tier": "table", "min_verified": 0},
    },
    {
        "name": "docx-narrated-single-column",
        "path": FIXTURES_DIR / "quarterly_review.docx",
        "path_kind": "narrated-default",
        "kwargs": {"title": "Live test - DOCX narrated path"},
        "expect": {"tier": "written", "min_verified": 3},
    },
    {
        "name": "pdf-two-column",
        "path": FIXTURES_DIR / "two_column_review.pdf",
        "path_kind": "narrated-default (column-aware extraction)",
        "kwargs": {"title": "Live test - two-column PDF"},
        "expect": {"tier": "written", "min_verified": 3},
    },
    {
        "name": "pdf-embedded-image",
        "path": FIXTURES_DIR / "chart_exhibit.pdf",
        "path_kind": "narrated-default (image-fact extraction)",
        "kwargs": {"title": "Live test - embedded-image PDF"},
        "expect": {"tier": "written", "min_verified": 1},
    },
]


PASS, DEGRADED, FAIL = "PASS", "DEGRADED", "FAIL"
_TIER_RANK = {"table": 3, "written": 3, "deterministic": 2, "plain": 1}


def evaluate(expect, trace):
    """Grade one finished run (Slice 67). Pure and offline.

    ``expect`` is ``{"tier": ..., "min_verified": n}``; ``trace`` is what
    ``build_report(..., trace=...)`` recorded. Returns ``(outcome, detail)``
    with outcome PASS, DEGRADED or FAIL - see specs/slice-67/spec.md.
    """
    tier = trace.get("tier")
    if tier is None:
        return FAIL, "the run recorded no trace"
    if expect["tier"] == "table":
        return (PASS, "table path completed") if tier == "table" else (FAIL, f"expected the table path, got tier {tier!r}")
    verified = (trace.get("analysis") or {}).get("verified", 0)
    if verified < expect["min_verified"]:
        return FAIL, f"only {verified} verified fact(s); expected at least {expect['min_verified']}"
    try:
        bundle = build_bundle(trace)
    except ValueError as exc:
        return FAIL, f"could not seal the run: {exc}"
    check = verify_bundle(bundle, source_text=trace.get("document_text") or "")
    if not check["content_checked"]:
        failed = [c["name"] for c in check["checks"] if c["status"] != "pass" and c["name"] != "signature"]
        return FAIL, f"the seal does not fully verify (not passing: {failed})"
    if _TIER_RANK.get(tier, 0) < _TIER_RANK[expect["tier"]]:
        return DEGRADED, f"fell back to the {tier} tier ({trace.get('fallback_reason') or 'no reason recorded'}); {verified} verified facts"
    return PASS, f"{tier} tier, {verified} verified facts, seal verifies"


class BudgetExceeded(RuntimeError):
    """Raised instead of dispatching a call that would cross the ceiling."""


def _price(model, input_tokens, output_tokens):
    rates = _PRICE_PER_MTOK.get(model)
    if rates is None:
        raise ValueError(
            f"no price-table entry for model {model!r} - add one to "
            "_PRICE_PER_MTOK before running the live suite against it"
        )
    return (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]


class CostTrackingClient:
    """Wraps a real ``anthropic.Anthropic()`` client so every real call's
    actual token usage (``response.usage``) is converted into a real
    dollar cost via ``_PRICE_PER_MTOK``, and a hard ceiling is enforced
    *before* each call is dispatched - the same "check before dispatch"
    discipline ``analystos.l2.analyze._enforce_spend_ceiling`` already
    uses for its own (call-count) safety net, just in real dollars and
    scoped to this one run.

    Passed as ``llm_client`` to ``build_report``, so every internal call
    site (extraction's image transcription, analysis, narration,
    proofreading, repair) - already threaded through ``llm_client``
    end to end - is captured here without touching any of that code.
    """

    def __init__(self, real_client, ceiling_dollars):
        self._real = real_client
        self.messages = SimpleNamespace(create=self._create)
        self.ceiling_dollars = ceiling_dollars
        self.total_cost = 0.0
        self.calls = []

    def _create(self, **kwargs):
        if self.total_cost >= self.ceiling_dollars:
            raise BudgetExceeded(
                f"${self.total_cost:.4f} already spent >= ${self.ceiling_dollars:.2f} "
                "ceiling - refusing to dispatch another call"
            )
        response = self._real.messages.create(**kwargs)
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cost = _price(kwargs.get("model"), input_tokens, output_tokens)
        self.total_cost += cost
        self.calls.append({
            "model": kwargs.get("model"), "input_tokens": input_tokens,
            "output_tokens": output_tokens, "cost": cost,
        })
        return response


def _run_one(document, client, log):
    log(f"\n=== {document['name']} ({document['path_kind']}) ===")
    before_cost = client.total_cost
    before_calls = len(client.calls)
    started = time.monotonic()
    trace = {}
    try:
        build_report(
            document["path"],
            evidence_dir=FIXTURES_DIR / ".evidence",
            llm_client=client,
            trace=trace,
            **document["kwargs"],
        )
        outcome, detail = evaluate(document["expect"], trace)
    except BudgetExceeded:
        raise  # propagate - this is the hard-stop, not a per-document failure
    except ValueError as exc:
        outcome, detail = FAIL, f"pipeline error: {exc}"
    elapsed = time.monotonic() - started

    calls_made = client.calls[before_calls:]
    doc_cost = client.total_cost - before_cost
    log(f"  result: {outcome} - {detail}")
    log(f"  calls: {len(calls_made)}, elapsed: {elapsed:.1f}s")
    for c in calls_made:
        log(f"    - {c['model']}: {c['input_tokens']} in / {c['output_tokens']} out -> ${c['cost']:.4f}")
    log(f"  document cost: ${doc_cost:.4f}")
    return outcome


def exit_status(results, stopped_early, strict=False):
    """Non-zero on a budget stop or any FAIL; with ``strict``, also any DEGRADED."""
    outcomes = {r for _, r in results}
    if stopped_early or FAIL in outcomes or (strict and DEGRADED in outcomes):
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ceiling", type=float, default=_DEFAULT_CEILING,
                         help=f"hard dollar ceiling for this run (default ${_DEFAULT_CEILING:.2f})")
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--strict", action="store_true",
                        help="also exit non-zero when a document DEGRADED to a lower tier")
    args = parser.parse_args(argv)

    log_lines = []

    def log(line):
        print(line)
        log_lines.append(line)

    real_client = anthropic.Anthropic()
    client = CostTrackingClient(real_client, args.ceiling)

    log("Slice 51 live-test suite - real, non-mocked API calls")
    log(f"ceiling: ${args.ceiling:.2f}  documents: {len(DOCUMENTS)}")

    stopped_early = False
    results = []
    for document in DOCUMENTS:
        try:
            results.append((document["name"], _run_one(document, client, log)))
        except BudgetExceeded as exc:
            log(f"\n!!! BUDGET CEILING HIT - run stopped before the next call: {exc}")
            stopped_early = True
            break

    log("\n=== summary ===")
    for name, outcome in results:
        log(f"  {name}: {outcome}")
    counts = {o: sum(1 for _, r in results if r == o) for o in (PASS, DEGRADED, FAIL)}
    log(f"  outcomes: {counts[PASS]} PASS, {counts[DEGRADED]} DEGRADED, {counts[FAIL]} FAIL")
    log(f"  documents completed: {len(results)}/{len(DOCUMENTS)}")
    log(f"  total real API calls: {len(client.calls)}")
    log(f"  total real cost: ${client.total_cost:.4f}")
    log(f"  ceiling: ${args.ceiling:.2f}")
    log(f"  stopped early (budget ceiling hit): {stopped_early}")

    if args.log_file:
        args.log_file.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        print(f"\n(log written to {args.log_file})")

    return exit_status(results, stopped_early, args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
