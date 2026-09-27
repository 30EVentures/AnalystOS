# Slice 64 - displayed figures round half up (roadmap Q1)

## Goal

Audit finding 11: a source figure of `$1.95B` displayed as `$1.9B`. Python's
`format(x, ".1f")` rounds the float's *binary* value, so a decimal that is
exactly half-way (1.95, 12.25, 0.35) rounds down or to even depending on how
the float happens to be stored. A reader of a financial report expects
half-up (1.95 -> 2.0). A rounding that quietly disagrees with the source is
exactly the kind of small untrustworthiness this product exists to remove.

- New `round_half_up(value, decimals)` in `analystos/l4/export.py`: rounds the
  value's shortest decimal representation (`repr`) half away from zero and
  returns a thousands-separated string.
- Used everywhere a *figure* is displayed: the compact `$K/$M/$B` form,
  `percent`, `number`, and the donut chart's share labels.
- Chart geometry (pixel coordinates) is not a displayed figure and is left alone.

## Not in this slice

- Changing how many decimals any figure shows.
- Rounding of the underlying verified value (unchanged; only its display).

## Done when

1. A table of half-way cases renders half-up for usd (K/M/B and plain),
   percent and number, including negatives (shown in parentheses).
2. Non-half-way cases are unchanged from before, checked against the old
   formatter over a sweep of values.
3. The donut label uses the same rounding.
4. Full suite OK.
