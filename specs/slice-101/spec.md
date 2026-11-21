# Slice 101 - the findings-register schema, validator and generator

## Goal

Both the owner's 18 Nov plan and Flashy's 21 Nov reply agreed on one discipline:
30E Ventures publishes each finding at a stable URL with a discovery date, before
Flashy's fix cites it, so a stranger can check the order. Build the machinery for
that - schema, validator, page generator - without inventing finding content this
session cannot verify. The 24 real findings live in the owner's local
`flashy-audit` material, not reachable from here.

## Done when

1. `findings/schema.json` documents the shape of one entry: a stable `F-NN` id,
   title, discovery date, status, 30E's own severity rating, the affected package
   and exact version, a summary with no exploit detail, whether a reproducer
   exists (without publishing it), and a fix-commit URL once one exists and cites
   the id.
2. `findings/validate.py` enforces every rule in the schema by hand (this repo's
   own convention for a schema small enough that a dependency is the wrong
   trade - see `tests/test_l4_seal_schema.py`), including the specific
   cross-field rules: `published` cannot precede `discovered`; `status: fixed`
   needs a `fix_commit_url`.
3. `findings/build_findings.py` renders `registry.json` into one markdown page
   per finding plus an index, refuses to write anything if the registry does not
   validate, and never HTML-escapes markdown content (caught in review - an
   earlier draft did, and left literal `&lt;` in rendered pages; pinned by a
   regression test).
4. `findings/registry.json` holds exactly one entry, `F-00`, explicitly marked
   `status: "template"`, with its summary explaining it is not a real finding.
   `tests/test_findings.py::RegistryContentTest` fails the moment anyone adds an
   entry without a `template` status, which is deliberate: it forces whoever adds
   a real finding to go through `findings/README.md`'s publishing section rather
   than slipping one in silently.
5. Every validator rule and the generator's own correctness are tested against
   synthetic fixtures in the test file - never by relying on real finding
   content that does not exist in this repository.

## Not in this slice

- Any of the 24 real findings' actual content. Fabricating a plausible-sounding
  security finding that was never verified would be worse than publishing
  nothing - see `findings/README.md`.
- Publishing anything findings/build_findings.py generates. Output lands in
  `findings/pages/`, not `site/`, the same rule every draft in this session
  follows, and for the same structural reason (a deploy cannot publish by
  accident what was never put under the served directory).
- Wiring `findings/build_findings.py --check` into `tools/refresh.py`'s automatic
  chain. That script assumes every step lives under `tools/`; changing that
  assumption for one new, still-template-only directory was not judged worth the
  risk this session. Run it by hand, per `findings/README.md`.
