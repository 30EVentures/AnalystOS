# Slice 131 - correct the record once, then serve it where Flashy reads it

Phase 0 of the AnalystOS x Flashy two-sided plan (2026-11-25), items C-ID-1,
C-REC-2, C-REC-1, C-REC-3, C-REC-4. Owner's decision, 2026-11-26: the person
id is `person/30e-founder` (no personal name).

## Goal

Flashy's plan found three things wrong with the record AnalystOS serves, and
this session found the cause of the third and a fourth:

1. 27 of 28 served entries are sealed with the placeholder author
   `person/accountable-human`.
2. The record is a `shipped/1` document served at the `devlog/1` path, so
   Flashy's fan-in would fold 0 of its 28 entries as the kind the URL implies.
3. One seal (`ship/analystos/572370f44a16`) does not recompute. Cause, found
   here: Slice 106's `tools/redact_served_devlog.py` strips commit trailers
   from `detail` *after* the emitter sealed the entry. Every entry with a
   trailer in its body breaks; only one such entry survived the name filter.
4. The full, unredacted record (`shiplog.fragment.json`,
   `devlog.fragment.json`, `DEVLOG.md`) is committed to a public repository,
   with 66 entries each naming the owner personally. Slice 106 cleaned only
   the served copy. The site does not serve these files (404), but GitHub
   does.

The fix is one rule: **privacy happens before sealing, never after.** A seal
must cover exactly the bytes that are served.

The log Flashy is about to register never forgets a leaf, and a re-derive
after the first fold doubles the record for good. So this is the one
correction, done before anything is registered.

## Done when

1. `tools/emit_record.mjs` wraps the vendored, unmodified
   `vendor-shiplog.mjs` (published `@flashyos/shiplog@0.2.0`, byte-equal):
   it reads git history, **drops** every commit whose subject or body names
   the owner personally, **strips** `Co-Authored-By` / `Claude-Session`
   trailers from the body (co-author attribution is parsed first, so
   `agent/claude` is still credited), and only then derives and seals.
2. Authors: `30eventures@gmail.com` and any unmapped address resolve to
   `person/30e-founder`; `noreply@anthropic.com` to `agent/claude`. No
   personal email is written to any file. No entry names
   `person/accountable-human`.
3. Served at the right paths, on the apex host:
   - `site/.well-known/shiplog.json`: `shipped/1`, every seal recomputes
     (`node vendor-shiplog.mjs verify` prints `ok`).
   - `site/.well-known/devlog.fragment.json`: a real `devlog/1` document.
   - `site/.well-known/checkpoint.json`: a `checkpoint/1` head over the
     served shiplog (`vendor-checkpoint.mjs`, published 0.2.0, byte-equal),
     `size` equal to the entry count, `verify` prints `ok`.
   Each gets the JSON/CORS/cache headers in `vercel.json`.
4. The full unredacted files leave the repository: `shiplog.fragment.json`
   and `devlog.fragment.json` are removed and ignored. State for append-only
   emits is the served public file itself. `DEVLOG.md` is regenerated from
   the cleaned entries. (Git history still holds the old copies; rewriting a
   public repository's history is a separate owner decision.)
5. A second plain emit changes nothing (append-only holds). A plain emit on a
   branch other than `main` is refused (it would seal the branch's own commits
   into a log that never forgets; `--rev origin/main` derives the trunk), and so
   is a plain emit when a served file is missing (that would silently re-derive
   every digest; `--rederive` is the stated act).
6. `tools/redact_served_devlog.py --check` reports already clean, and stays
   as a guard over both served records (it never rewrites the sealed one). `tests/test_site_identity.py` passes over every served file.
7. The Flashy freeze moves with a stated reason (`tools/flashy_freeze.py
   --update`), and the full suite reports OK.

## Not in this slice

- Registering the record with Flashy (F-REC-1). That waits for this to merge
  and deploy, and for the owner's yes.
- CI wiring of the emitters (C-REC-9).
- Rewriting git history to remove the old unredacted copies.
- Any change to the handshake, charter or seal key.
