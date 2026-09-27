# Slice 66 - the standalone verifier checks each quote's value against its citation (roadmap Q3)

## Goal

`docs/seal.md` listed this as the biggest limit: the verifier proved a
citation was in the text and a calculation recomputed, but not that the number a
fact *claims* is the number its citation *spells*. A sealer could pair a real
quote ("$498.0 million") with a wrong value and rebuild every hash; the
verifier would not notice.

With the extracted text supplied, `verify_bundle` now also runs
`values_match_citations`:

- every `quote` fact with a numeric `value` must equal a number its citation
  spells, as printed or times the document's declared scale ("in millions");
- every `computed` fact's operands (and total) must equal the numbers their own
  citations spell (`citation[i]` is operand `i`; a `percent_of_total` total is
  the last citation);
- sign is preserved, so `-1,050` never matches `1,050`.

It is a second implementation (regexes and scale detection re-written in
`seal_verify.py`, stdlib only) and is differential-tested against the analyzer's
own `_parse_numbers`, `_detect_scale` and `_value_matches_text`. It joins
`calculations` and `citations_in_text` as required for `content_checked`.

## Not in this slice

- Event facts (dates, milestones) and prose: they carry no numeric value.
- Anything without the extracted text (the check is `skipped`, as the others are).

## Done when

1. A bundle rebuilt around a wrong quote value (all hashes valid) passes
   integrity and fails `values_match_citations`; so does a sign flip, a wrong
   operand, and a wrong total.
2. Values that legitimately match pass: as printed, with a scale word, bare with
   a declared document scale, and picked out of a whole table row.
3. Differential test: the verifier agrees with the analyzer on parsing, scale
   detection and the match decision across a sample and random inputs.
4. `docs/seal.md` and the generated site copies say what is now checked.
5. Full suite OK.
