"""Slice 117 - every role on the verified pipeline. Each family has at least one
worked example (written in the working session; no model call), and every example
goes end to end on the real catalog: intake, the acceptance gate, the pipeline
through ReplayClient, verification, rendering, and the independent
no-new-numbers check."""

import io
import json
import unittest
from pathlib import Path

from pptx import Presentation

from analystos.catalog import load_catalog
from analystos.l3 import engagement as eng
from analystos.l4 import deck
from analystos.packs import consulting as c
from analystos.packs.replay import ReplayClient
from tests.test_deck_render import slide_text, unexplained_numbers

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog()
ROLES = {r["id"]: r for r in CATALOG["roles"]}
BRIEFS = c.load_briefs()
EXAMPLES = sorted([d for d in (ROOT / "fixtures" / "consulting").iterdir() if d.is_dir()]
                  + [d for d in (ROOT / "fixtures" / "roles").iterdir() if d.is_dir()])


def run_example(directory):
    client = json.loads((directory / "client.json").read_text())
    response = json.loads((directory / "response.json").read_text())
    record = eng.new_engagement(engagement_id="a" * 32, created="2026-11-23T18:00:00Z",
                                requested_by=client["requested_by"], problem=client["problem"],
                                roles=client["roles"], catalog=CATALOG)
    for qid, text in client["answers"].items():
        record = eng.answer(record, qid, text)
    record, problems = eng.accept(record, CATALOG)
    assert not problems, problems
    replay = ReplayClient([response])
    spec = c.build_deck_spec(record, CATALOG, client=replay)
    data = deck.render_deck(spec, record, CATALOG)
    return record, spec, Presentation(io.BytesIO(data)), replay


class BriefsTest(unittest.TestCase):
    def test_every_role_and_family_has_a_brief(self):
        self.assertEqual(set(BRIEFS["roles"]), set(ROLES))
        self.assertEqual(set(BRIEFS["families"]), {f["id"] for f in CATALOG["families"]})
        for text in list(BRIEFS["roles"].values()) + list(BRIEFS["families"].values()):
            self.assertTrue(isinstance(text, str) and len(text.split()) >= 6, text)

    def test_the_prompt_carries_the_role_and_its_boundary(self):
        claims = ROLES["claims-adjuster"]
        prompt = c.system_prompt(claims)
        self.assertIn("Role: Claims Adjuster.", prompt)
        self.assertIn(BRIEFS["roles"]["claims-adjuster"], prompt)
        self.assertIn(BRIEFS["families"]["insurance"], prompt)
        self.assertIn("you never make it", prompt)
        self.assertIn(claims["human_decides"][0], prompt)
        sdr = c.system_prompt(ROLES["sales-development-representative-sdr"])
        self.assertIn("draft for a named approver", sdr)
        self.assertIn(ROLES["sales-development-representative-sdr"]["gated_actions"][0], sdr)
        advisory = c.system_prompt(ROLES["management-consulting-analyst"])
        self.assertNotIn("you never make it", advisory)
        self.assertNotIn("named approver", advisory)


class WorkedExamplesTest(unittest.TestCase):
    def test_every_family_has_a_worked_example(self):
        families = set()
        for directory in EXAMPLES:
            role = json.loads((directory / "client.json").read_text())["roles"][0]
            families.add(ROLES[role]["family"])
        self.assertEqual(families, {f["id"] for f in CATALOG["families"]})

    def test_every_example_runs_end_to_end_and_adds_no_numbers(self):
        self.assertGreaterEqual(len(EXAMPLES), 16)
        for directory in EXAMPLES:
            with self.subTest(example=f"{directory.parent.name}/{directory.name}"):
                record, spec, prs, replay = run_example(directory)
                role = ROLES[spec["role"]]
                self.assertEqual(spec["role"], record["roles"][0])
                self.assertIn(f"Role: {role['title']}.", replay.requests[0]["system"])
                self.assertEqual(unexplained_numbers(prs, spec), [])
                title_slide = slide_text(list(prs.slides)[0])
                self.assertIn(role["title"], title_slide)
                text = "\n".join(slide_text(s) for s in prs.slides)
                if role["boundary"] == "human-decides":
                    self.assertIn("PREPARED FOR YOUR DECISION", text)
                    self.assertIn("Decisions that stay with a qualified person:", text)
                elif role["boundary"] == "approval-gated":
                    self.assertIn("WE RECOMMEND", text)
                    self.assertIn("Drafts for your approval before anything happens:", text)
                else:
                    self.assertIn("WE RECOMMEND", text)
                    self.assertNotIn("PREPARED FOR YOUR DECISION", text)


if __name__ == "__main__":
    unittest.main()
