# Slice 26 — narrated analysis: any table shape, still 100% cited

## Goal

`income_statement` is the only template that exists, and it only works on
data shaped like an income statement (a period-like column, recognized line
items). Anything else - the Company/Estimated-Revenue/Estimated-Employees
file that surfaced this gap live - fails cleanly today, which is honest but
not useful. This slice makes AnalystOS work on *any* table shape, and write
about it the way a real analyst would - while keeping the one rule that
doesn't bend: every number shown still has to be a real, computed, cited
value. Nothing is ever invented by the model; it chooses what to say and
how to phrase it, never what number to show.

This is not a detour from the architecture - `docs/architecture.md` already
describes L2 as "Retrieval + analysis over the evidence graph. Every claim
points back into L0." What's shipped so far (lookup/growth/ratio, one
template) is a deliberately thin first slice of that layer. This is the
fuller version of the same layer, bound by the same rule.

## Design decisions

- **Deterministic facts, then a model narrates - never the reverse.**
  `analystos/l2/facts.py` computes a bounded set of real, cell-cited facts
  from *any* schema (see "Included") with zero model involvement. Only
  those facts - not the raw file - are ever shown to the model. This is a
  real security boundary, not just an architecture preference: an
  adversarial or just-weird value in the uploaded file (a company name
  engineered to look like an instruction, say) can't reach the model as
  free text it might act on, only as one labeled data point inside a fact.
- **The model picks and phrases; it never supplies the number.** For each
  fact it chooses to feature, the model writes a sentence template with one
  `{answer}` placeholder - the exact same contract `render_section` already
  uses. The real fact's value is substituted in afterward, by code, exactly
  like every template ask today. The model's own sentence text is then
  scanned for stray digit sequences outside that placeholder; any found and
  that sentence is rejected outright, not shown. Two independent layers -
  the model structurally cannot control what number appears, and anything
  that looks like it tried to sneak one in gets caught. A report entirely
  refused by verification is a real `ValueError`, same as any other
  pipeline failure - never a silent partial success.
- **`"auto"` tries the precise path first, falls back only when it must.**
  A new `"auto"` template - the new default for the live API/site - first
  tries `income_statement_asks` exactly as today; if that raises (no
  period-like column, the shape this file doesn't fit), *only then* does it
  fall through to the generic facts + narration path. An income-statement
  file costs nothing extra and behaves identically to today; a company list
  now gets a real report instead of an error.
- **Model choice: Claude Sonnet 5, not Opus 5 - a latency call, not a cost
  call.** Anthropic's own current guidance defaults every integration to
  Opus 5 unless told otherwise. Overridden here for one concrete, disclosed
  reason: `api/analyze.py` runs as a Vercel serverless function with a real
  10-second wall-clock ceiling (the same constraint already flagged for PDF
  extraction) - and this call has to fit inside a single request alongside
  everything else the pipeline already does. Sonnet 5 reliably finishes a
  bounded, structured-output task like this well inside that budget; Opus
  5's on-by-default extended thinking makes the 10-second ceiling a real
  risk, not a hypothetical one. This is a one-line change to flip back if
  the Vercel plan changes (a paid plan raises the function timeout) or if
  quality at Sonnet 5 turns out to disappoint - flagged explicitly, not
  buried.
- **A new required secret: `ANTHROPIC_API_KEY`, on Vercel, separate from
  anything used to build this code.** The live product needs its own key
  and its own budget - a new, real, ongoing dollar cost per report
  generated this way (Sonnet 5 pricing: $2/$10 per 1M input/output tokens;
  a single narration call is small - a handful of facts in, a few hundred
  output tokens - so cost per report is fractions of a cent, but it is
  non-zero and ongoing, unlike everything shipped before this).
- **Residual, disclosed risk: a text label can still carry manipulated
  wording into the final prose, even though it can never carry a false
  number.** A company name engineered to read as an instruction is passed
  to the model as a labeled data value, with an explicit system-prompt
  instruction that all such values are data, never instructions - a
  standard, imperfect mitigation. Verification catches every fabricated
  *number*; it does not and cannot catch manipulated *wording* smuggled in
  through a text field. Real gap, not silently ignored - see "Not in this
  slice."

## Included

- `analystos/l2/facts.py` - `build_facts(rows, schema, source_hash) ->
  list[fact]`, each fact `{"text": "...", "format": ..., "answer": ...,
  "citation": {...}}` (or a list-citation for a total/average, same shape
  `answer_growth`/`answer_ratio` already produce). Per numeric column:
  total, average, max (with its key-column label if a text column exists),
  min. No fact is ever produced without a real cell citation - a row count
  or anything else uncitable is not generated, ever.
- `analystos/l2/narrate.py` - `select_and_phrase(facts, title) ->
  list[ask-shaped dict]`: one `anthropic` SDK call (`claude-sonnet-5`,
  strict tool use for structured output - see `python/claude-api` skill
  reference), asking the model to choose a handful of the given facts and
  write one templated sentence per chosen fact. Verifies every returned
  item (valid fact reference, exactly one `{answer}` placeholder, no stray
  digits) before it becomes a finding; drops anything that fails
  verification; raises `ValueError` if nothing survives.
- `analystos/pipeline.py` - `build_report`: `template == "auto"` tries
  `income_statement_asks` first, falls back to
  `build_facts` + `select_and_phrase` only on that call's `ValueError`.
  `_run_ask` gains a `"precomputed"` kind - the facts/narration path hands
  over already-computed answers and citations, so it plugs into the exact
  same `findings` construction every other ask kind already uses; L4
  (`render_section`/`render_html`/`render_pdf`) needs no changes at all.
- `api/analyze.py` / `site/upload.html` - default `template` value changes
  from `"income_statement"` to `"auto"`.
- `requirements.txt` / `docs/decisions.md` - `anthropic` pinned, with the
  model-choice reasoning above recorded in full.
- Tests: `build_facts` against several arbitrary schemas (including the
  real Company/Revenue/Employees shape); `select_and_phrase` against a
  **mocked** Anthropic client (deterministic, no real API calls, no cost, no
  network dependency in the test suite) covering the verification logic
  directly - a fabricated extra number, a missing placeholder, an
  out-of-range fact reference, all correctly rejected; `build_report` with
  `template="auto"` on both an income-statement file (proves the
  no-fallback path) and a non-conforming file (proves the fallback fires).

## Done when

1. `build_facts` produces real, cited facts for a table with no
   income-statement-shaped columns at all - proven against the actual
   Company/Estimated-Annual-Revenue/Estimated-Employees shape that
   surfaced this gap.
2. `select_and_phrase`, given a set of facts, returns findings where every
   `{answer}` is a real substituted value from an actual fact - never
   something the model wrote directly - verified with a mocked client so
   this is checked on every test run, not just once by hand.
3. A sentence with a stray, fabricated number, or a missing/extra
   `{answer}` placeholder, is rejected before it ever reaches a rendered
   report - proven with a test that deliberately returns exactly that from
   the mocked client.
4. `template="auto"` on a real income-statement-shaped file produces byte-
   identical output to `template="income_statement"` on the same file - the
   fallback never fires when the precise path already works.
5. `template="auto"` on the real company-list file that started this
   produces a real report - the whole reason for this slice.
6. `python3 -m unittest discover -s tests -v` passes (with the venv active)
   using only the mocked client - the suite has no dependency on a real
   `ANTHROPIC_API_KEY` or network access to run clean.

## Not in this slice

- **Multi-fact, free-flowing narrative paragraphs.** Still one sentence per
  fact, exactly like every template ask before it - no connective prose
  spanning multiple numbers in one sentence. Keeps verification simple and
  airtight; real, disclosed scope limit, not the final shape of "executive
  quality."
- **Catching manipulated wording carried in through a text label** (as
  opposed to a fabricated number, which verification does catch). See
  "Design decisions" above - a real, accepted residual risk for this slice.
- **A model-generated intro paragraph, exec-summary framing, or any
  free-standing sentence that isn't tied to exactly one fact.** Everything
  shown still has to look exactly like today's cited findings.
- **New fact types beyond total/average/max/min** (ratios between rows,
  trends across a natural sequence, category breakdowns). A real, likely
  next step once this lands, not this slice.
- **Retrying or regenerating a rejected sentence.** A sentence that fails
  verification is simply dropped from the report, not retried against the
  model - keeps the verification step simple and the failure mode obvious.
- **Actually setting `ANTHROPIC_API_KEY` on the live Vercel project.** Same
  category as `ANTHROPIC_ACCESS_CODE` before it - a manual dashboard step
  outside this repo's code, for after this merges.
