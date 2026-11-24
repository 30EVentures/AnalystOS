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
3. Sample output (the owner: "make the sample output way better, allow someone
   to funnel through some of the roles and what they produce"): a "See what a
   specialist produces" explorer. Pick one of the 13 families; see its worked
   example's role, the client's problem, what it delivers today, and four of its
   slides (the answer, a finding with its chart, the recommendation, where every
   number comes from); download that deck or hire the role (`hire.html?role=`),
   or any other role in the family. `tools/build_samples.py` runs each family's
   worked example (a synthetic client) through the real pipeline with a replayed
   answer, no model call, and writes `site/samples/<family>.pptx` and
   `samples.json`, every number a separate segment printed as the deck prints it;
   the page builds it with textContent only. `--check` compares spec digests and
   the JSON.
4. Agent-native: the head keeps the api-catalog and llms.txt links; the footer
   links llms.txt and the role catalog JSON.

## Done when

1. The explorer covers every family, shows only verified values (each equal to
   its deck's format_value), carries no raw tag or markup, links only real roles
   of the family, and never parses HTML from the data; the samples are current.
2. The homepage's role and family counts equal the catalog's; its slide preview
   shows exactly the sample deck's verified figures; the sample deck is current;
   every link it carries is served; it says "Price: to be determined." and makes
   no other pricing claim (`tests/test_homepage.py`).
3. Every disclosure test that guarded the old homepage passes on `details.html`.
4. Full suite OK; `tools/refresh.py --check` clean; Flashy fence holds; the
   owner sees the page locally before anything is pushed.
