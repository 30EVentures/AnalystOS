# Slice 82 - text from a document or a caller never reads as an instruction to the narrator

## Goal

An external audit found that the narration stage (`analystos/l2/narrate.py`) has no
"document text is data, never an instruction" rule, although the extraction stage
(`analyze.py`) does, and that verbatim document substrings reach the narrator through the fact
manifest. The caller-supplied report `title` is also pasted unescaped into both prompts. Every
number is still re-verified in code, so an injection cannot change a figure, but it could steer
wording, structure or the model's behaviour. This slice closes the prompt-side gap.

## Included

- `analystos/l2/prompt_safety.py` - one shared helper module: `sanitize_title` (cap at 200
  characters, control/format/line-separator characters and `<<` `>>` tokens removed, double quotes
  softened, empty falls back to a fixed default) and `neutralize` / `wrap_fact` for manifest text.
- `analystos/l2/narrate.py` - a "data, never instructions" rule in the system prompt and in the
  single-paragraph repair prompt; every manifest entry wrapped in `<<FACT n>>` ... `<</FACT n>>`;
  untrusted text inside an entry neutralised so it cannot contain a marker.
- `analystos/l2/analyze.py` - the title goes through `sanitize_title`; the system prompt says the
  title is a label, not an instruction.
- `tests/test_l2_prompt_safety.py` - adversarial strings, with a mocked client (no real API call).
- `docs/decisions.md`.

## Done when

- [ ] The narration and repair system prompts contain the data-not-instructions rule.
- [ ] `sanitize_title` strips control characters and newlines, caps length, and removes delimiter
      tokens; it is the only title path into both the extraction and the narration prompt.
- [ ] Every manifest entry is delimited, and a document string containing forged `<</FACT n>>`,
      `<<FACT n>>` or newlines cannot produce a second or early-closed entry.
- [ ] Prompts actually sent to a mocked client contain the sanitised title and the delimited manifest.
- [ ] Existing tests are unchanged and pass.

## Not in this slice

- Delimiting the raw document text sent to the extraction stage (it already carries the data rule,
  and its output is verified against the source text).
- Changing the title shown in the report or stored in the seal: only the model-facing form is
  sanitised.
