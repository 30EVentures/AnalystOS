# Slice 96 - a measures/1 document, computed from the real audit log

## Goal

Flashy's 21 Nov reply committed to *pull* a measures document rather than have
AnalystOS push one, for exactly the reason this repo already applies everywhere
else: a measure a stranger can fetch is checkable; one we hand over is not. They
named neither the path nor their own format, so this slice proposes both and backs
the proposal with a real computation, not placeholder numbers.

## Done when

1. `tools/build_measures.py` wraps the existing, already-tested `analystos.api_v1.audit.measures()`
   (Slice 61) in a measures/1 envelope - it does not recompute the arithmetic itself.
   (First draft of this slice duplicated the arithmetic as a new module before this
   was noticed; see `docs/decisions.md` for the correction.)
2. An empty denominator is `null`, never 0% or 100% (already true of `audit.measures()`;
   this slice does not change that property, only wraps it).
3. The measure sentence in the output is copied from the charter, never retyped,
   so the two can never disagree.
4. The window (`since`/`until`) is always stated explicitly in the output, never
   silently derived from the clock at read time.
5. `tools/build_measures.py` builds this against a real `FileStore`, with a
   `--check` mode that replays the same window/store and compares the result -
   not a byte-for-byte diff against a moving "now", which could never pass twice.
6. A test writes real events through `FileStore.append_audit` (the same method
   production calls) and checks the measures computed from the real chained log,
   not a mocked one.
7. The output lands in `drafts/measures.json`, not `site/.well-known/`, because
   Flashy has not confirmed a path or format yet - this is a proposal to review,
   matching Slice 95's reasoning for the seven-role charter draft.

## Not in this slice

- Serving this at any public URL. That needs Flashy to confirm the path/format,
  and then the owner's decision to publish, same as every other draft here.
- New instrumentation for a role that is not yet measurable (there are none among
  the three live roles today, but the seven-role draft's four new roles have no
  entry in `audit.measures()`, and the envelope says so honestly rather than guessing).
- Wiring this against the *live* production audit log, which Slice 84 recorded as
  dormant until `ANALYSTOS_STORE_DIR` is a persistent volume - until then, a real
  run against production would honestly show every value as `null`, which this
  tool already does correctly when no store directory is given.
