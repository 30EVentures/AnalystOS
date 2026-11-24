# Slice 124 - wire the role formats into hiring and the homepage

## Goal

The owner approved the phase-1 formats (Slice 123): "Looks right, wire it in". A
role hired on the site or through the API now gets its family's format, and the
homepage samples show and download that format.

## What changes

1. `analystos/l4/formats.py`: the three formats (deck, memo, workbook) with
   their renderer, media type and extension, and `FAMILY_FORMAT`: memo for
   legal, research, audit, HR, insurance and financial crime; workbook for
   finance, accounting and data; deck for consulting, content, sales and
   software.
2. The catalog's `delivers_today` names each role's format (`verified-deck`,
   `verified-memo`, `verified-workbook`), set by family.
3. `POST /api/v2/engagements` renders the role's format; the response carries
   its media type, a matching filename, and `X-AnalystOS-Format`. With
   `?format=json` it returns `output` {format, media_type, filename, base64};
   `deck_base64` stays for decks so earlier clients keep working.
4. The hire page names each role's format, names the download after what came
   back, and states truthfully that one role has passed a live run.
5. Homepage samples: each family's sample is its own format
   (`site/samples/<family>.<pptx|docx|xlsx>`); the explorer downloads it and
   says what it is; the page states which format each family delivers.

## Done when

1. Every role's `delivers_today` equals its family's format; every family has one.
2. Hiring a memo role returns a .docx and a workbook role a .xlsx, both from a
   replayed worked example (no paid call); JSON mode carries `output`.
3. Each homepage sample is in its role's format and is current; the statement on
   the page matches the formats.
4. Full suite OK; refresh check clean; Flashy fence holds.
