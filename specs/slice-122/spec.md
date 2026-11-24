# Slice 122 - a short homepage: specialist work, ready when you need it

## Goal

The owner wants the homepage to have less text and fewer sections, and to lead
with output that is ready when it is needed. The old page had 16 sections and 12
menu links about the document-to-report product. Of three local mocks he chose A
("Ready when you need it") and the word "specialist" over "analyst" ("expert"
was rejected: the roles are entry-level and licensed work stays with a qualified
person).

## What changes

1. `site/index.html` becomes mock A: one hero (headline, role names, one
   sentence, two buttons, a preview of the sample deck's summary slide), three
   steps, the 13 role families, one call to action, a short footer. Menu: Roles,
   How it works, Full details, For agents.
2. The old page moves unchanged to `site/details.html` ("Full details: how it
   works, privacy and known limits"), with its disclosures intact; its counts
   generator, studio chrome and tests follow it; `llms.txt` points its trust
   link there; the sitemap lists it.
3. `site/samples/sample-consulting-deck.pptx`: the churn worked example (a
   synthetic client) run through the real pipeline with a replayed answer, no
   model call; built by `tools/build_sample_deck.py`, `--check` compares the
   deck's spec digest.
4. Agent-native: the head keeps the api-catalog and llms.txt links; the footer
   links llms.txt and the role catalog JSON.

## Done when

1. The homepage's role and family counts equal the catalog's; its slide preview
   shows exactly the sample deck's verified figures; the sample deck is current;
   every link it carries is served; it says "Price: to be determined." and makes
   no other pricing claim (`tests/test_homepage.py`).
2. Every disclosure test that guarded the old homepage passes on `details.html`.
3. Full suite OK; `tools/refresh.py --check` clean; Flashy fence holds; the
   owner sees the page locally before anything is pushed.
