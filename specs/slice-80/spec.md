# Slice 80 - one public identity: 30E Ventures, and its own email

## Goal

Slices 78 and 79 made the public pages credit 30E Ventures. Two leftovers
remain: the retired `site/index.old.html` is still served at
`/index.old.html` and carries a personal email address in its "Request early
access" link, and the sample AAO manifest, its tests and the FlashyOS alignment
note still use a personal email and a personal name as example values. The rule
going forward: the repository names the studio, never an individual, and the
only contact address is `30eventures@gmail.com`.

- Every `mailto:` in `site/` points at `30eventures@gmail.com`.
- `solwayholdings.aao.json` is accountable to `30eventures@gmail.com`.
- The tests' and the alignment note's example values use "30E Ventures" and
  `30eventures@gmail.com`, and the note still describes the file truthfully.
- A test scans every file under `site/` (the served surface, including the
  generated docs copies) and fails if a personal name or email appears.

## Done when

- [ ] No file under `site/` contains a personal name or a personal email.
- [ ] Every real email address under `site/` is `30eventures@gmail.com` (reserved
      `@example.com` placeholders in the docs are allowed).
- [ ] `solwayholdings.aao.json` still passes `analystos.aao.validate` and its
      `accountableTo` is `30eventures@gmail.com`.
- [ ] `docs/decisions.md` records the change.
- [ ] `tools/refresh.py --check` is clean and the full suite reports `OK`.

## Not in this slice

- **The `solwayholdings` organisation name and slug.** They name a sample org
  that does not exist; ROADMAP already tracks its fate. Renaming it is a
  decision about that org, not about who is credited.
- **Historical research notes** (`docs/flashyos-spec-notes-2026-09-25.md`), which
  quote search terms used at the time, and a local filesystem path in a code
  sample. They are not served and are records of what was done.
- **Deleting `site/index.old.html`.** It is retired but linked from nowhere; only
  its address changes here.
