#!/usr/bin/env python3
"""Build the homepage's samples and the data its role explorer draws (Slices 122, 124).

    python3 tools/build_samples.py          # write site/samples/<family>.<pptx|docx|xlsx> and samples.json
    python3 tools/build_samples.py --check  # exit 1 if anything served is not this build

One worked example per role family (fixtures/roles/<family>, and the churn example for
consulting): a synthetic client run through the real pipeline with a replayed answer -
build_deck_spec verifies every figure, render_deck draws the deck. No model call is made.

samples.json carries only what the page shows, taken from the verified spec: every number
is the figure's value as format_value prints it in the deck, kept as a separate segment
({"v": "7%", "ref": "F2"}) so the page builds it with textContent and never parses HTML.
--check compares each deck's spec digest (a .pptx is a zip with timestamps) and the JSON.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from docx import Document  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from pptx import Presentation  # noqa: E402

from analystos.catalog import load_catalog  # noqa: E402
from analystos.l3 import engagement as eng  # noqa: E402
from analystos.l4 import deck, formats  # noqa: E402
from analystos.packs import consulting  # noqa: E402
from analystos.packs.replay import ReplayClient  # noqa: E402

OUT = ROOT / "site" / "samples"
TAG = re.compile(r"\[(F[1-9][0-9]{0,2})\]")
BOUNDARY = {"human-decides": "Prepares the decision; a qualified person decides.",
            "approval-gated": "Drafts only; you approve before anything happens.",
            "deliverable-only": "Delivers analysis; acts on nothing."}


def examples():
    """{family id: example directory}, one per family."""
    found = {"consulting": ROOT / "fixtures" / "consulting" / "churn-clinics"}
    for directory in sorted((ROOT / "fixtures" / "roles").iterdir()):
        if directory.is_dir():
            found[directory.name] = directory
    return found


def build_one(directory, catalog):
    client = json.loads((directory / "client.json").read_text())
    record = eng.new_engagement(engagement_id="5a" * 16, created="2026-11-23T00:00:00Z",
                                requested_by=client["requested_by"], problem=client["problem"],
                                roles=client["roles"], catalog=catalog)
    for qid, text in client["answers"].items():
        record = eng.answer(record, qid, text)
    record, problems = eng.accept(record, catalog)
    if problems:
        raise SystemExit(f"{directory.name}: the sample engagement is not accepted: " + "; ".join(problems))
    response = json.loads((directory / "response.json").read_text())
    spec = consulting.build_deck_spec(record, catalog, client=ReplayClient([response]))
    data, fmt = formats.render(spec, record, catalog)  # the role's own format (Slice 124)
    return client, spec, data, fmt


def segments(text, figures):
    """``text`` as [{"t": words} | {"v": value, "ref": "F2"}], each tag printed as the deck prints it."""
    out, pos = [], 0
    for m in TAG.finditer(text):
        if m.start() > pos:
            out.append({"t": text[pos:m.start()]})
        out.append({"v": deck.format_value(figures[m.group(1)]), "ref": m.group(1)})
        pos = m.end()
    if pos < len(text):
        out.append({"t": text[pos:]})
    return out


def tile(fig):
    basis = {"client": "client data", "computed": "calculated", "assumption": "assumption"}[fig["basis"]]
    return {"v": deck.format_value(fig), "ref": fig["id"], "label": fig["label"], "basis": basis}


def short(text, limit=240):
    """The client's problem in at most two sentences, cut at a word if longer than ``limit``."""
    first_two = " ".join(re.split(r"(?<=[.!?])\s+", text.strip())[:2])
    if len(first_two) <= limit:
        return first_two
    return first_two[:limit].rsplit(" ", 1)[0] + "…"


def page_data(family, role, client, spec, catalog, fmt):
    figures = {f["id"]: f for f in spec["content"]["figures"]}
    by_kind = {}
    for s in spec["slides"]:
        by_kind.setdefault(s["kind"], []).append(s)
    summary = by_kind["executive-summary"][0]
    finding = next(s for s in by_kind["finding"] if s.get("chart"))
    rec = by_kind["recommendation"][0]
    chart = finding["chart"]
    values = [figures[fid]["value"] for fid in chart["figure_ids"]]
    top = max(abs(v) for v in values) or 1
    slides = [
        {"kind": "summary", "heading": "The answer first", "title": segments(summary["title"], figures),
         "bullets": [segments(b, figures) for b in summary["bullets"][:3]],
         "tiles": [tile(figures[f]) for f in summary["figure_ids"][:3]]},
        {"kind": "finding", "heading": "A finding, with its chart", "title": segments(finding["title"], figures),
         "bullets": [segments(b, figures) for b in finding["bullets"][:2]],
         "chart": {"title": segments(chart["title"], figures),
                   "bars": [{"label": label, "v": deck.format_value(figures[fid]), "ref": fid,
                             "share": round(abs(figures[fid]["value"]) / top, 4),
                             "assumption": figures[fid]["basis"] == "assumption"}
                            for label, fid in zip(chart["labels"], chart["figure_ids"])]}},
        {"kind": "recommendation", "heading": "The recommendation", "title": segments(rec["title"], figures),
         "bullets": [segments(b, figures) for b in rec["bullets"][:2]]},
        {"kind": "sources", "heading": "Where every number comes from",
         "rows": [{"ref": f["id"], "label": f["label"], "v": deck.format_value(f),
                   "basis": f["basis"], "source": segments(_source(f), figures)}
                  for f in spec["content"]["figures"][:6]],
         "counts": {b: sum(1 for f in spec["content"]["figures"] if f["basis"] == b)
                    for b in ("client", "computed", "assumption")}},
    ]
    family_roles = [r for r in catalog["roles"] if r["family"] == family["id"]]
    return {
        "family": {"id": family["id"], "title": family["title"]},
        "role": {"id": role["id"], "title": role["title"], "boundary": BOUNDARY[role["boundary"]],
                 "deliverables": role["deliverables"]},
        "problem": short(client["problem"]),
        "file": f"samples/{family['id']}.{fmt['extension']}",
        "format": fmt["name"],
        "slide_count": deck.slide_count(spec),
        "figure_count": len(spec["content"]["figures"]),
        "slides": slides,
        "others": [{"id": r["id"], "title": r["title"], "deliverables": r["deliverables"]}
                   for r in family_roles if r["id"] != role["id"]],
    }


def _source(fig):
    if fig["basis"] == "client":
        return f"Client's words: “{fig['quote']}”"
    if fig["basis"] == "computed":
        return f"Calculated: {deck.formula(fig['operation'], fig['inputs'])}"
    return f"Assumption: {fig['rationale']}"


def build():
    catalog = load_catalog()
    families = {f["id"]: f for f in catalog["families"]}
    roles = {r["id"]: r for r in catalog["roles"]}
    data, decks = [], {}
    for family_id, directory in examples().items():
        client, spec, output, fmt = build_one(directory, catalog)
        role = roles[client["roles"][0]]
        if role["family"] != family_id:
            raise SystemExit(f"{directory.name}: example role {role['id']} is not in family {family_id}")
        data.append(page_data(families[family_id], role, client, spec, catalog, fmt))
        decks[family_id] = (spec, output, fmt)
    order = [f["id"] for f in catalog["families"]]
    data.sort(key=lambda d: order.index(d["family"]["id"]))
    document = {"format": "analystos-samples/1",
                "note": "Worked examples for synthetic clients, verified and drawn by AnalystOS with a replayed answer; "
                        "no model call. Values are printed exactly as in each deck.",
                "samples": data}
    return document, decks


def _keywords(path):
    """The spec digest each format records in its document properties."""
    if path.suffix == ".pptx":
        return Presentation(str(path)).core_properties.keywords or ""
    if path.suffix == ".docx":
        return Document(str(path)).core_properties.keywords or ""
    return load_workbook(str(path)).properties.keywords or ""


def render_json(document):
    return json.dumps(document, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    document, decks = build()
    text = render_json(document)
    if "--check" in argv:
        stale = []
        if not (OUT / "samples.json").is_file() or (OUT / "samples.json").read_text(encoding="utf-8") != text:
            stale.append("samples.json")
        for family_id, (spec, _, fmt) in decks.items():
            path = OUT / f"{family_id}.{fmt['extension']}"
            keywords = _keywords(path) if path.is_file() else ""
            if f"spec sha256 {deck.spec_digest(spec)}" not in (keywords or ""):
                stale.append(path.name)
        print("stale: " + ", ".join(stale) + " - run python3 tools/build_samples.py" if stale else "samples are current")
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    keep = {f"{family_id}.{fmt['extension']}" for family_id, (_, _, fmt) in decks.items()} | {"samples.json"}
    for old in OUT.iterdir():
        if old.name not in keep:
            old.unlink()  # a family whose format changed leaves no stale file behind
    for family_id, (_, output, fmt) in decks.items():
        (OUT / f"{family_id}.{fmt['extension']}").write_bytes(output)
    (OUT / "samples.json").write_text(text, encoding="utf-8")
    print(f"wrote {len(decks)} samples and samples.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
