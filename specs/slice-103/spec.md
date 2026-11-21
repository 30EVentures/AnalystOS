# Slice 103 - a bare scaled-table number is stored at its real size, not as-is

## Goal

Owner's decision on the PROPOSALS item carried since the 2026-10-14 overnight run:
scale it. `docs/decisions.md`/slice-33 recorded "stored as-is" as intended, but
`_value_matches_text`'s own docstring already claimed the opposite ("a figure the
model left unscaled is still stored - and rendered - at its real size"), which was
false whenever the model's own proposed value was also unscaled: `_value_matches_text`
tried the bare candidate first and returned it the moment it matched, never reaching
the scaled candidate. A document that says "in millions" and prints a table cell
"1,842.0" must report $1.8B, never $1.8K.

## Done when

1. When `exact_text` is a **bare** number (no scale word of its own) and the
   document declares a scale (`doc_scale != 1`), the only canonical value
   `_value_matches_text` will match against is the **scaled** one - the bare
   literal is refused, forcing the real magnitude to be the one that is proven,
   recomputed and rendered.
2. When `exact_text` carries its **own** scale word ("$1.2 million"), `doc_scale`
   is never applied on top of it - `_parse_numbers` already returned the real
   size for that number, and multiplying it again would be a second, wrong scale.
3. With no document-wide scale declared (`doc_scale == 1`), behaviour is
   unchanged: the bare literal is exactly the real size.
4. The docstring now says what the code does, not what an earlier version of the
   code almost did.
5. A differential/regression test proves the exact scenario the overnight run
   found live: a document declaring "in millions", a table cell "1,842.0", a
   model proposing the bare (wrong) value 1842.0 - now refused as unprovable
   (`None`), matching only when the model proposes the real, scaled value.

## Not in this slice

- A mixed `exact_text` string that cites several numbers, some with their own
  scale word and some bare, in the one quote (e.g. `"$1.2 million and (3,400)"`).
  This fix treats "has its own scale word" as a property of the whole quoted
  text, not of each number within it individually - a conservative choice that
  never double-scales, at the cost of not perfectly handling that rare mixed
  case. Documented as a known limitation in the code, not solved here.
