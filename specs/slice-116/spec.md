# Slice 116 - code writes every number; the model only points at figures

## Goal

A second fresh-context review (of Slice 115) found the claim still false: the
model could get numbers into a rendered deck through edited "client quotes"
(the L2 matcher folds away `$`, scale words and leading signs), digit shorthand
("ARR10M"), fraction words ("a quarter of"), unit and scale words after a
number ("850 USD", "$1,200 Bn"), sign tricks ("minus 7%", "(7%)"), and a spec
that carried its own forged client text. Patching a number detector form by
form was losing; this slice changes the design instead.

## The design

1. **The model never writes a digit.** Every number in model-written text is a
   figure tag, `[F2]`, and code prints the value from the verified figure
   (`7%`, `$30,600`, `3 pts`) using the same formatter everywhere: sentences,
   tiles, charts and the sources slides. Unit, sign and scale come from the
   figure, so they cannot be misstated.
2. **Any digit outside a tag is refused** (ASCII or not, fractions,
   superscripts), except an allow-list: Q1-Q4, H1-H2, FY with a year, B2B, B2C,
   and a four-digit year that appears in the client's own text.
3. **Tag context.** A tag may not be preceded by a currency symbol, a sign, an
   opening parenthesis, "minus" or "negative", nor followed by a percent sign,
   a currency or a scale or unit word ("million", "USD", "bps", "x"...).
4. **Quantity words, best effort.** Number words above twelve, multipliers,
   fractions ("a quarter of", "two fifths", "one in three", "nine out of
   ten") and scale words are refused. Natural language has more ways to state
   a quantity than any list; this is a stated limit, not a guarantee.
5. **Quotes are verbatim.** A client quote must appear in the client's text
   exactly (only whitespace, dash style and Unicode normal form are folded),
   start at a word boundary, contain at least two words and exactly one number.
6. **Clean strings.** Control, format, surrogate, private-use and unassigned
   characters anywhere in the content are refused; numbers beyond +-1e15 are
   refused (no OverflowError).
7. **The renderer derives, never trusts.** `render_deck(spec, engagement)`
   recomputes the client text from the engagement, checks the engagement id,
   reads the role's title from the catalog, re-verifies, rebuilds the slides,
   and wraps any drawing error as `ValueError`. Chart data labels are written
   per bar with the same formatter as the text.
8. **An independent no-new-numbers test.** For every slide, and the text inside
   every chart, remove the exact formatted values of the figures that slide
   uses, its slide number, and (only where they are drawn) pagination, formula
   notation and roadmap column labels; no numeric character may remain. Each
   number tile is checked against its own figure.

## Stated limits

- Whether a figure is used about the right thing ("revenue grew [F2]" where F2
  is churn) is not checked; a person reads that.
- Quantities in words are caught by a list, not exhaustively.
- Counting words one to twelve are allowed.

## Done when

1. Every probe from the second review is a test that is refused (or, for the
   stated limits, a test that documents the limit).
2. All recorded examples are converted to tags-only and verify; their decks
   render and pass the independent no-new-numbers test.
3. `tools/mutation_check.py` passes for the pack and the renderer.
4. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.
