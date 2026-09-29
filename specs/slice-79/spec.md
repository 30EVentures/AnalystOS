# Slice 79 - the homepage credits 30E Ventures, not an individual

## Goal

analystos.dev is a 30E Ventures product (Slice 78 says so in the studio bar).
Its own copy still credits one person by name and in the first person: "Built
solo by ...", "I'm ... I built AnalystOS on my own", "Built solo, early stage".
This slice makes the page credit the studio consistently.

- The hero byline reads "Built by 30E Ventures."
- The "Who built it" section is written in the studio's voice ("we"), keeps
  every factual claim it made (a spec before every piece of code, every real
  bug recorded with its root cause, a report should never contain a number
  nobody can defend) and keeps its candour about being early.
- The status paragraph reads "Built by 30E Ventures, early stage."
- "Solo" is dropped: it described a team size, which is no longer the claim.

## Done when

- [ ] None of the public pages (`site/index.html`, `site/upload.html`) names an
      individual.
- [ ] `site/index.html` credits "30E Ventures" in the byline, in "Who built it"
      and in the status paragraph, and no longer says "solo" or "on my own".
- [ ] The factual claims in "Who built it" are unchanged in substance.
- [ ] Homepage counts still true after the new spec (`tools/refresh.py --check`).
- [ ] `docs/decisions.md` records the change.
- [ ] The full suite reports `OK`.

## Not in this slice

- **Internal documents** that mention the maintainer (`docs/` audit and
  alignment notes, the sample `solwayholdings.aao.json` manifest, its tests,
  `ROADMAP.md`, the retired `site/index.old.html`). Some of these are served
  publicly under `/docs/`; whether they should be is a separate decision.
- **The sealed-report, API and mesh files:** unchanged.
- **Any claim about the studio's size or funding.**
