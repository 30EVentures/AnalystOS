# Slice 34 — the output-token ceiling on a dense document

## Goal

Slice 33 fixed *how* verification matches; a realistic earnings release
(`Calderon_Grid_Q3_2026`, four tables, dozens of figures) still returned
"no verifiable content survived" after it deployed. The tell was in the
earlier Vercel log: that request ran **1 minute 38 seconds** — a single
Sonnet call on an 8.5k-char document should take 20–40s. 98s is the
signature of hitting the output ceiling: `max_tokens` was 4096, the model
tries to emit 20+ segments in the all-required schema (each verbose with
placeholder fields), overruns 4096, and the tool call is **truncated
mid-JSON**. The segment list comes back short or with a half-written last
entry, and little or nothing verifies. Meridian never hit this (5
paragraphs → ~7 segments → well under the ceiling).

## Design decisions

- **`_MAX_TOKENS` 4096 → 8192**, in both `analyze_document` and
  `write_narrative` (a rich report over a dense document can also
  outgrow 4096). Sonnet handles 8192 comfortably; this is the direct fix
  for the truncation.
- **Truncation is never silent again.** After the call, if
  `response.stop_reason == "max_tokens"`, log it to stderr (Vercel
  function logs, not the client response — same rule as Slice 27/33). The
  "no verifiable content" log line also flags `(RESPONSE WAS TRUNCATED at
  max_tokens)` when that happened, so this exact failure is one glance to
  diagnose.
- **Cap the segment count in the prompt.** `_SYSTEM_PROMPT` now says
  "Return AT MOST 20 segments … do not transcribe the tables … prefer a
  computed comparison or a prose point that ties several figures together
  over restating cells one by one." Fewer, better segments keep the
  response inside budget *and* make for a better report - a dense filing
  doesn't need every cell echoed back.
- **Not touched:** the schema shape. Slimming the all-required per-segment
  schema (it is the reason each segment is verbose) risks re-triggering
  the "400 Schema is too complex" from Slice 26; the token bump plus the
  segment cap solve the immediate problem without that risk. Revisit only
  if 8192 + a 20-segment cap still truncates.

## Included

- `analystos/l2/analyze.py` — `_MAX_TOKENS = 8192`; `stop_reason ==
  "max_tokens"` detected and logged; truncation flagged in the
  no-content log; `_SYSTEM_PROMPT` segment cap + "don't transcribe
  tables" guidance.
- `analystos/l2/narrate.py` — `_MAX_TOKENS = 8192`; same `stop_reason`
  log.
- `docs/decisions.md` — dated entry.
- `tests/test_l2_analyze.py` — `_fake_client` grows a `stop_reason`
  arg; a truncated response with a valid segment still verifies and logs
  "hit max_tokens"; a truncation that leaves nothing verifiable logs
  "TRUNCATED" and still raises. Every existing test unchanged
  (`stop_reason` defaults to "tool_use").

## Done when

1. `analyze_document` and `write_narrative` request 8192 output tokens.
2. A response with `stop_reason == "max_tokens"` logs a clear truncation
   line to stderr; if nothing survives, the failure log says the response
   was truncated.
3. The prompt caps output at 20 segments and steers away from
   cell-by-cell transcription.
4. `python3 -m unittest discover -s tests -v` passes, mocked client only.

## Not in this slice

- **Slimming the per-segment schema** — see design note (Slice 26 risk).
- **Column-aware L1 extraction** — still its own slice (from Slice 33).
- **A live paid model run** — the confirmation is re-running
  `Calderon_Grid_Q3_2026` on Vercel after merge. If it still fails, the
  new log line names the cause (truncation, or the per-segment reasons
  Slice 33 already logs).

## Verified beyond the test suite

Local suite covers the truncation logging deterministically. The real
confirmation is the post-merge live re-test of the document that has
failed twice - and, whichever way it goes, the function log now states
plainly whether the response was truncated or which segments failed and
why.
