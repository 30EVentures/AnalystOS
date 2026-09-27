# Slice 70 - the model is one setting, and every report says which one made it (roadmap Q7)

## Goal

R2 lists "model-swap". The model name was hard-coded in four modules (`analyze`,
`narrate`, `proofread`, `image_facts`), so trying another model, or responding to
a deprecation, meant editing four files and hoping none was missed.

- `analystos/models.py` - `model_name()` returns `ANALYSTOS_MODEL` if set, else
  the current default (`claude-sonnet-5`). Read at call time so a deployment can
  change it without a code change. A value that is not a plausible model id is
  an error, not silently ignored.
- All four call sites use it. Nothing else changes; the default is unchanged.
- The pipeline's trace and the API's audit log record the model used, so a sealed
  or audited report can be tied to the model that wrote it. (The seal payload is
  unchanged.)
- The live suite's price table stays keyed by model and still refuses an unpriced
  model, so switching models cannot silently defeat the $1.00 ceiling. `docs/api.md`
  and the live-tests README say so.

## Not in this slice

- Choosing a different model per stage, or per-request model selection by API callers.
- Verifying that a different model is *good* - only the live suite can say that.

## Done when

1. Unset, all four call sites request the default model.
2. With `ANALYSTOS_MODEL` set, all four request that model (checked through the real
   functions with a recording client).
3. An invalid value is refused with a clear error.
4. The trace and the audit event carry the model.
5. The live suite refuses an unpriced model.
6. Full suite OK.
