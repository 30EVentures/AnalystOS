# Slice 93 - audit lines are strict JSON, and the conformance corpus covers non-finite numbers

## Goal

Two gaps recorded in `docs/decisions.md` (2026-10-07, Slice 87 follow-up) as expected failures, plus the corpus cases
the overnight hardening run proposed.

1. **A line's meaning must not depend on the parser.** `verify_entries` read an audit line with Python's `json.loads`,
   which keeps the last of two equal keys and accepts the literals `NaN`, `Infinity` and `-Infinity`. A parser in
   another language may keep the first key, fail, or read a different number, so the chain was not portable. The
   verifier now refuses all of these, and the writer refuses the same input, so a log cannot fail its own verifier.
2. **Corpus cases for non-finite numbers.** A sealed `inf` / `nan` and a 400-digit citation were fixed in code
   (overnight round 4) but not pinned in the corpus a stranger runs.

## Done when

1. `audit_chain.strict_loads` refuses, at any depth: a duplicate key (even with identical values), the literals
   `NaN`, `Infinity`, `-Infinity`, and a float that overflows to infinity (`1e999`). Ordinary JSON loads unchanged.
2. `verify_entries` reports a line that fails `strict_loads` as a `chain` failure that says it is not strict JSON.
3. `FileStore.append_audit` never writes a non-JSON literal: an event holding a non-finite number is replaced by an
   `audit_event_refused` line (original type, fixed reason), the chain keeps growing, and the log verifies.
4. The two `known_gap` annotations (`audit/duplicate-key-in-a-line`, `audit/non-finite-number-literal`) are removed
   and those cases agree. New corpus cases agree: five audit cases (identical-value duplicate key, nested duplicate
   key, `Infinity`, `-Infinity`, `1e999`) and four seal-content cases (sealed `inf`, `nan`, `-inf`, and a finite
   value citing a 400-digit number).
5. The audit cases fail on the unfixed code; what the seal-content cases do and do not catch is recorded in
   `docs/decisions.md`. The full suite reports OK, also reversed.

## Not in this slice

- Any change to the seal format or to how sealed numbers are written (they are already strings).
- Telling FlashyLabs, or publishing the corpus anywhere: the corpus is ours; this changes only the file in the repo.
- Hardening `FileStore.read_audit` and `last_chained`, which still read leniently so a damaged log can still be
  appended to; the verifier is the gate.
