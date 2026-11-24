# Decisions

Dated log, newest first. One entry per real choice, with the reason.

## 2026-11-23 — Slice 111: the homepage's test figure says what it counts

A fresh-context review of Slice 108 found two wrong figures on the homepage.
First, it called the discovered test count "passing", although 14 of those
tests are `skipUnless` tests that skip on a machine without Node.js or the npm
installs. Second, its hero still said "49 written specs" while the evidence
card said 102.

For the tests, the wording changed, not the number. The other option was to
count tests that actually pass. That count depends on the machine, so the
page's figure and `site_counts.py --check` would flip depending on who ran
them. It would also mean running the whole suite from a tool that the suite
calls itself. The discovered count is deterministic and offline. The page now
says "automated tests in the suite", drops the "N / N" pass ratio, and says
that tests needing Node.js are skipped without it.
`site_counts.PASSING_CLAIM` refuses all five old wordings, and `--check`
reports any that come back.

No generator owned the hero's spec figure. It had been typed by hand and was
frozen since about Slice 49. It now has its own `site_counts.py` pattern,
generated from the same `count_specs()` as the evidence card.

## 2026-11-23 — Slice 120: the release review of PR #100 failed it; close it before the second paid test

The owner merged PR #100 (Slice 119) before its fresh-context release review
finished, and the review then failed it: six ways the normaliser could make a
wrong deck pass (narrowing cut "a third of" off "420 seats"; "$12.2" quoted out
of "$12.2 Million" printed as $12.20; recomputing hid reversed inputs; unit
matching ignored the kind of number; bare digits 0-12 beside tags; "90 days"
rewritten anywhere). Slice 119's entry below and its PR said the normaliser
"cannot change the delivered numbers" and that normalising "never makes a wrong
number acceptable": both were false, because its own tests covered only friendly
cases. Fixed in Slice 120 (see specs/slice-120). A second fresh review of the fix
failed it again on two partly closed blockers (a quote cut across "40% of our
850", written in digits; "$12.2-million" and "$12.2 millions") and one new hole
("of" taken as a time word), and those are fixed too. What the normaliser now
does to numbers, stated exactly: it never fills or recomputes a computed
figure's value; it never cuts or changes a client quote, and never rescales or fills
in a value: the one value it changes is a percent stored as a fraction (0.07
with a quote saying "7%" becomes 7). A fifth review found the rescaling turned
"12 million-dollar contracts" (value 12) into 12,000,000; it fills a unit only when none is given
and maps aliases ("%", "USD"); and on a computed figure it sets the unit to the
only one its operation allows and turns a "ratio" declared as a percent into
percent_of_total (the value is still checked). Cutting a two-number quote down
to one number was removed after four reviews in a row each found a phrasing
where the cut misled ("340 out of our 850", "3 times the $1,200", "a 25% discount
to the $1,200", "$1,200 every 3 months"): such a quote is now refused with
guidance and fixed by the model on the repair request. The cost: slips it used to fix
(a drifted calculation, "90 days", a missing value) now go to the one repair
request; that path is tested only with a replayed correct second answer, so
whether the live model fixes them is unmeasured. Lesson, again: no merge
before the review.

## 2026-11-23 — Slice 119: survive the live model's natural writing (the first paid test failed)

The one paid test of Management Consulting Analyst (owner's consent, at most
about $0.21) failed: the live model's content failed verification twice, 40
problems, and nothing was delivered - the safeguard worked, the role did not.
The visible problems were quotes holding two numbers and an unexpected field;
the API cut the rest at 300 characters. Every worked example had been written
knowing the rules; the live model writes the natural way ("7% [F2]").

Fix, without loosening what a reader is told: a deterministic normaliser runs
before verification and fixes only slips that cannot change the delivered
numbers - it removes a written number beside a tag when it states that very
figure (otherwise the verifier still refuses it), narrows a multi-number quote
verbatim to the part with the one matching number, takes client values and
units from the quote and recomputes computed values, drops fields and figures
that are never shown, and turns "within 90 days" into words. Bare whole numbers
0-12 with no unit, and years 2020-2035 after a time word, are now allowed like
the words one to twelve; label fields still allow no digits. The prompt shows a
short correct example and the common mistakes. A failed request now returns
every problem, and the hire page shows them.

The free stand-in for the live model: all 16 worked examples rewritten three
natural ways (numbers before tags, units after tags, currency before tags,
whole-sentence quotes, percents as fractions, drifted computed values, wrong
units, extra fields, an unused figure, "within 90 days") - 48 variants, each
must fail raw, pass normalised, build in one attempt, render, and pass the
independent no-new-numbers check. The stand-in found three real bugs before any
money was spent (a unit after a tag was never removed; a quote with a number
word was narrowed wrongly; a crash on a malformed id). It is still a stand-in:
the live model may write in ways it does not cover.

Also in this slice, the release review of PR #99 (which the owner merged before
the review finished): its two blockers - a quote could cut a number short of
its unit or scale ("$12.2" out of "$12.2 million" read as $12.20), and a year
from the client's text let those digits through anywhere ("we lose 2019
clinics") - are closed: a quote's number must be the client's whole number at
that spot, and a year needs a time word or a range. Tag edges are tighter (any
currency symbol, more unit words, lookalike letters, glued tags, number words),
the sources slides show exact values where the deck rounds, and 60 roles are
now labelled as checked on another role's worked example ("mock-family")
rather than implying their own.

## 2026-11-23 — Slice 118: the website - hire any role (merged as PR #99)

`site/hire.html` (linked from the homepage), `GET /api/v2/catalog` (public) and
`POST /api/v2/engagements` (the existing access code and per-IP limiter). The
owner merged PR #99 before its fresh-context release review finished; the review
then failed it on two gaps in the "every number traced" claim (a quote cut off
before its unit or scale; a year from the client's text letting digits through)
and passed everything about safety (no secrets, no unauthenticated paid call, no
crash, no XSS, the FlashyOS integration untouched). Both gaps are fixed in Slice
119. Every request past the gate is a paid model call (at most two); a retry
after a timeout is a new paid request (no idempotency key yet); the serverless
time limit is unmeasured.

## 2026-11-23 — Slice 117: all 73 roles on the verified pipeline (checked on worked examples, no paid calls)

Owner's direction: all 73 roles on the website and in the product by the end of
the day; Management Consulting Analyst gets one paid real-model test, only with
the owner's yes right before it and the exact cost stated; every other role is
proven with worked examples written and checked in the working session; price
is to be determined: no price has been set for any role (first recorded as "open
for negotiation, per engagement"; the owner changed it the same day).

One pipeline serves every role: the verified consulting pipeline, plus a brief
per role and a method brief per family (`analystos/packs/briefs.json`) in the
system prompt, and the role's boundary - a human-decides role is told to prepare
the decision, never make it, and its deck says "Prepared for your decision" and
names the decisions that stay with a qualified person; an approval-gated role's
actions are drafts for a named approver. Every number rule applies unchanged.

The catalog now says how each role was tested (`eval.method`: `mock` for worked
examples, `live` for the production model) so a mock-tested role can never be
shown as live-tested; `available` accepts `"tbd"` pricing (no price set yet); and
`delivers_today: verified-deck` says plainly that every role delivers the
verified analysis deck today, not its native work product (code, copy,
reconciliations). All 73 are `available` on a mock eval pointing at their
family's worked example: 16 examples, at least one per family, each run end to
end in tests (intake, the gate, the pipeline through ReplayClient, rendering,
the independent no-new-numbers check). Regulated roles were included at the
owner's direction; each still frames its output as preparation for a qualified
person, and the rules that apply to each have not been reviewed one by one.

## 2026-11-23 — Slice 116: code writes every number; the model only points at figures

A second fresh-context review (of Slice 115) found the claim still false:
edited "client quotes" (the L2 matcher folds away `$`, scale words and leading
signs), digit shorthand ("ARR10M"), fraction words ("a quarter of"), unit and
scale words after a number ("850 USD", "$1,200 Bn"), sign tricks, a spec that
carried its own forged client text, crashes on huge values and control
characters, chart labels formatted differently from the text, and a
no-new-numbers test that shared the detector's blind spots. Patching a detector
form by form was losing, so the design changed: the model never writes a digit.
Every number is a figure tag that code prints from the verified figure with one
formatter used everywhere (sentences, tiles, chart labels, sources), so value,
unit, sign and scale cannot be misstated. Any digit outside a tag is refused
except Q1-Q4, H1-H2, FY labels, B2B/B2C and years the client wrote; a tag may
not carry a sign, currency, bracket, unit or scale word beside it; quotes must
be the client's exact words at a word boundary, with a word and one number.
`render_deck(spec, engagement)` recomputes the client text from the engagement,
takes the role's title from the catalog, re-verifies, and reports any drawing
failure as ValueError. The no-new-numbers test is now independent of the
detector (it removes the exact formatted values a slide may show and requires
no numeric character to remain, chart text included) and checks every tile.

Stated limits, not gaps: whether a figure is used about the right thing
("revenue grew [F2]" where F2 is churn) is not checked; quantities written in
words are caught by a list, not exhaustively; counting words one to twelve are
allowed.

**Corrections to Slice 115's entry and commit.** It said the review's findings
were "all now closed" and that numbers.py "finds every quantity a reader reads
as one" - neither held (the second review reproduced misses). It said a spec
edited after verification "cannot be rendered" - a spec that forged its own
client text could. It said malformed specs raise ValueError - two crashes
remained. Its spec claimed "four recorded cases" when one was committed.

## 2026-11-23 — Slice 115: making "every number is traced" true

A fresh-context review of Slices 112-113 found the deck's central claim - every
number traced to the client's words, a recomputed calculation or a labelled
assumption, with no way for the model to slip in another - false as built.
Nothing had been pushed. What it found, all reproduced, all now closed with a
test that fails on the old code:

- Numbers that were not ASCII-style digits passed untagged: "seven percent",
  "tripled", "½", "NRR96%", ".5%", and any 1900-2099 integer read as a year.
  `analystos/packs/numbers.py` now finds them; quantities it cannot read as a
  value (words, multipliers, fractions) are refused outright, so the model must
  write digits and tag them. Exempt: Q1-Q4, H1-H2, FY labels, version strings,
  names like B2B, years after a time word, and the counting words one to twelve
  (allowed and not checked - a stated limit, not a gap).
- Figure labels and other label fields (key question, branch, option and KPI
  names, chart labels) were never scanned; they may now carry no number at all.
- Units were never verified. A client figure's unit now comes from its quote;
  a computed figure's from its operation and inputs (a difference of percents
  is points); every written number's kind must fit its figure's unit.
- A client value could be any number in its quote, within 1%; computed values
  drifted 1% per step. Quotes must state exactly one number, and verification
  replaces every value with the canonical one (the quote's number, or the exact
  recomputation from canonical inputs).
- The renderer drew any spec with the right format string. A spec now carries
  the client's text; `render_deck` re-verifies it and refuses one whose content
  or slides were edited after verification.
- The "renderer adds no numbers" test matched substrings of the whole content
  and passed with numbers injected. It is now exact, per slide, and a negative
  test injects five kinds of number and requires each to be caught. Its first
  run found numbers the renderer really does add: the roadmap's fixed column
  labels, now listed as allowed on the roadmap slide only.
- The repair-retry prompt echoed the previous output unneutralised.

**Corrections to earlier entries and commits.** Slice 112 said "7% matches
6.96, not 6.9" - the code accepted 6.5 to 7.49; matching is now "at the
precision shown and within 5%". Slice 112 said an assumption is "labelled
wherever it appears" - not on the title or issue-tree slides; those fields now
cannot carry figures. Slice 113 said the percent/points confusion was fixed -
only the fixture was; the code now enforces it. Slice 113 said every number in
the file is a figure value, reference, slide number or formula notation - the
test could not show that; it now can. Slices 112-114 quoted mutation counts
from a script outside the repo; `tools/mutation_check.py` (with mutant lists in
`tools/mutants/`) now reproduces them. Slice 112's "recorded bad-then-good
pair" was built in test code, not recorded.

Not checked, by design: qualitative claims and the direction of a change
("fell" against a rise). Those are read by a person.

## 2026-11-23 — Slice 114: charts that cannot carry a number of their own

Owner's feedback on the first deck: add some graphs and a tiny bit more text.
Each finding may now carry one bar chart, but the model only chooses which
verified figures to chart and labels the bars; each bar's height is the
figure's verified value, read by code, so a chart cannot introduce a number.
Charts are native PowerPoint charts (editable by the client), formatted by unit,
with assumption bars in grey. Each finding also gets one "so what" sentence,
under the same number rule as everything else. Kept deliberately small: one
chart type (columns), one extra sentence per finding.

Quick Look (used to preview slides in the session) does not draw chart
styling; the chart XML was read directly to confirm the number formats, colours
and hidden value axis are in the file. How PowerPoint itself draws them was not
checked here.

## 2026-11-23 — Slice 113: the deck renderer, and a renderer that adds no claims

`analystos/l4/deck.py` lays out a verified deck spec as a 16:9 PowerPoint deck:
action titles, figure references beside numbers, a footer naming each slide's
figures and flagging assumptions, big-number tiles drawn only from figures the
slide already uses, verdict pills, and sources slides that show each figure's
basis (the client's exact words, the formula, or the assumption's rationale).

The rule held in a test: the renderer adds no numbers of its own. Every number
in the file is a figure value, a figure reference, a slide number or formula
notation. A percentage-point change got its own unit after the first preview
showed "3%" for a 3-point rise - a real misreading the layout would have
introduced. Layout was checked by previewing every slide as an image in the
working session; the spec was written after the code for that reason.

## 2026-11-23 — Slice 112: the consulting skill, proved with mocks instead of spend

Owner's decision: take one role all the way through first (Management
Consulting Analyst), in days not months, proving it with mocks in the working
session rather than paying for a model call on every try.

`analystos/packs/consulting.py` turns an accepted engagement into an
`analystos-deck-spec/1`. The model writes structured content (answer first, an
issue tree of hypotheses, figures, options, one recommendation, a 30/60/90
roadmap, KPIs, risks); code assembles the slides in a fixed storyline, so the
deck's shape is never the model's to get wrong. Code verifies every figure's
basis with the existing L2 matchers (a client figure's quote must be in the
client's own words and spell out its value; a computed figure must recompute;
an assumption needs a rationale and is labelled wherever it appears) and every
number in every sentence (it must carry a `[F#]` tag in the same sentence, and
match that figure at the precision shown). Two operations were added inside the
pack, not to L2: `product` and `percent_of`. One repair retry, then a hard
error; all calls go through `_create_message`, so the spend ceiling applies.

`ReplayClient` replays recorded responses with the real client's shape; the
first recorded case (a synthetic clinic-software churn problem) was written in
the working session, and the verifier caught a real slip in it ("fewer than 10
staff" read as a number claiming the 70% figure) before it was fixed. What
mocks prove: the pipeline, the verifier, the rendering. What they do not: that
the production model writes content this good - that needs a few live runs
before the role is marked `evaluated`.

## 2026-11-23 — Slice 110: the engagement gate recomputes, never trusts (review of Slice 109)

A fresh-context review of Slice 109 finished after it merged (PR #96). Two ways
past the acceptance gate, both reproduced against main: `accept()` trusted the
record's own question list (flip every question to optional, or swap the roles
for a family never asked about, and an unanswered engagement was accepted), and
it never validated the catalog (a role marked `available` with no evaluation and
no rate was accepted - exactly what Slice 108 forbids). Neither was exploitable,
since nothing stores engagements or takes one back from a client yet.

The rule now: the gate re-validates the catalog and the scoping templates and
recomputes which questions the requested roles require; each must be present in
the record, still required and answered. A snapshot may carry extra questions
from older templates but may not drop or soften a required one. Sealing records,
or holding them server-side, is the lasting fix and comes with storage.

Client text cleaning was not idempotent (normalising before stripping left
non-NFC text the validator then refused, wedging an engagement); it now strips,
then normalises, then trims, checked by a property test. Every Unicode
Default_Ignorable code point is removed (a payload hidden in variation selectors
used to survive), and surrogate, private-use and unassigned characters are
refused rather than silently dropped. The CLI reads stdin as strict UTF-8 and
no longer relabels `--agent ""` as a person.

**Correction.** Slice 109's commit and PR said "disabling each of the module's
42 guarded rules makes at least one test fail". That was true of the method used
(turning each `if` guard off) but read as broader than it was: the reviewer's
other mutations (changing logic rather than switching guards off) survived 10
of 24. This slice states both methods and both counts.

## 2026-11-23 — Slice 109: engagement intake, and the first code that reads the role catalog

The first piece of L3. A person or an agent states a problem and names catalog
roles; `analystos/l3/engagement.py` turns that into an `analystos-engagement/1`
record holding five common scoping questions plus each requested family's own
(`analystos/l3/scoping.json`, snapshotted into the record so later template
edits never rewrite an engagement), and the answers. The acceptance gate refuses
unless the engagement is scoped and every requested role is `available` in the
catalog - so today every engagement is refused, by design: nothing can be taken
on for a role nobody has evaluated. This is what turns Slice 108's ladder from a
file into an enforced rule.

Deliberately no model call: routing from the problem text is Slice 110, so every
rule here is deterministic and tested offline. Client text is data: cleaned of
control and invisible format characters on the way in, and refused rather than
truncated when over its cap (silently dropping part of a problem would change
what was asked). An agent is a first-class requester (`requested_by.kind`), and
`open_questions()` gives it the unanswered questions in order to work through.

## 2026-11-23 — Slice 108: one shop for 73 entry-level roles, none claimed before it is proven

Owner's decision, same day as Slice 107 and widening it: not only consulting but
a one-stop shop for entry-level white-collar work - the owner listed 73 roles,
from equity research to claims adjusting to junior software development.

Seventy-three separate products would never be finished, so each role is a
configuration of a shared engine: the roles fall into 13 families, each built on
one skill (a cited brief, a deck, a sourced workbook, a reconciliation, a case
file, code its tests verify, ...). The real cost per role is its evaluation set,
not its code.

The catalog is written down first, as data, with every role `planned`. The
validator makes `available` impossible without a recorded passing evaluation and
an integer rate in US cents per engagement hour - the same refusal-first stance
the seal and the fence take. Two limits, stated plainly: nothing reads the
catalog yet (the site and `/api/v2` must read from it, not restate it, when they
are built), and an `eval` record is a claim until evaluation runs are sealed so
a stranger can re-check a pass (Phase 4).

Each role also states a boundary. Roles that would act in a client's tools
(post, send, book an entry) are `approval-gated`, each action approved by a named
human. Roles whose decisions are licensed or regulated (claims, underwriting,
credit, audit opinions, tax and payroll filings, AML and sanctions dispositions,
hiring and pay, legal advice, actuarial sign-off) are `human-decides`: the agent
prepares the whole case and a qualified, named human makes the listed decisions.
Waves are defined by what blocks the build, not by who decides: four wave-1
roles (credit, equity research ratings, model validation, actuarial) leave a
decision to a human but need nothing new to build; wave 4 is the roles whose
core output is itself a regulated decision. A fresh-context review caught the
first version conflating the two, moved AML/KYC into the financial-crime
family, made investor-facing ratings human-decides and kept payment approval
with the client's authorised approver.
Which rules apply where is general knowledge, not checked rule by rule; each
wave-4 role gets a real review of its rules before it is built.

## 2026-11-23 — Slice 107: rebuild into a consulting product, with the Flashy integration fenced

Owner's decision: rebuild AnalystOS so a person or an agent enters a business
problem and gets a consulting-grade deck back (every figure cited to a source
or labelled an assumption, sealed), with specialist agents hireable by the
hour - and leave the FlashyOS integration exactly where it is. The rebuild
fills layers the architecture already names and never built (L3 workspace,
L5 distribution) rather than replacing L0-L2/L4.

The constraint became a check before any product code: `tools/flashy_freeze.py`
pins the integration in `flashy-freeze.json` and the suite fails on any drift.
It is deliberately not a `tools/refresh.py` step (a fence that regenerates
itself protects nothing); moving it needs `--update --reason`, and each move
is logged with exactly what it re-pinned. Product routes go in a new API
version, never `/api/v1`. A fresh-context review of the first version found
the fence too literal in places (exact-string `vercel.json` matching,
untracked files invisible, fenced code importing unfenced code, set-only
append checks, an unprotected log); each was fixed in the same pull request
with a test. Not done: pinning the integration's own test files, since
`tests/` grows every slice; the fence's own tests are the guard instead.

"Hired per hour" means **engagement hours** (owner's choice, 2026-11-23): an
hour buys a fixed, published budget of agent work (model calls and tokens),
priced per specialist in integer cents, bought as a budget that only narrows,
with a hard stop that delivers what is finished, marked partial, and a sealed
receipt. Not wall-clock time (agents finish most tasks in minutes) and not
per deliverable. Declaring a consulting offer on the FlashyOS mesh stays a
separate decision for the owner.

## 2026-11-22 — Slice 106: the public devlog, with a real privacy leak found and closed before it shipped

Owner's decision: flip `.shiplog/config.json`'s `visibility` to `public` and
actually serve the record - not leave it parked in `drafts/` indefinitely.
Flipped the config, re-ran `node vendor-shiplog.mjs emit --rederive` (every
entry re-derived against the new setting, not just new ones appended with
the old stamp - 94 entries total), and moved the served projection from
`drafts/devlog.fragment.json` to a real path, `site/.well-known/devlog.fragment.json`,
with the same headers every other `.well-known/*` file gets in `vercel.json`.

Running this for real - not a dry run, the actual published tool against
this repository's actual git history - surfaced a genuine privacy leak
before anything deployed. Two different problems, found by the test suite
itself failing the moment the suite ran after the flip:

1. Old merge-commit titles from when this repository lived under the
   owner's personal GitHub fork carry the raw username verbatim
   (`"Merge pull request #66 from CalebSolway/site-new-homepage"`) - GitHub
   bakes the fork name into the merge message itself, and the vendored tool
   correctly reproduces it, since that is what the commit actually says.
2. This session's own commit trailers (`Co-Authored-By: ... <noreply@anthropic.com>`,
   `Claude-Session: https://claude.ai/code/session_...`) ride inside the
   free-text `detail` field, since that field is the commit message body.

Both conflict with the standing rule (public identity is 30E Ventures only).
Owner's decision on remedy: exclude the affected entries rather than
redact them in place - there is no version of a personal-name entry safe to
publish. `tools/redact_served_devlog.py` does that, and only that, for
problem 1 (66 of 94 entries, all from the pre-org-migration era, dropped
entirely); for problem 2 it does something different and less destructive -
truncates `detail` at the trailer, keeping the real written summary, since
every commit this session made carries that trailer and dropping all of
them too would have gutted the public record for no privacy gain. Proven in
`tests/test_redact_served_devlog.py` and caught on any regression by the
existing, generic `tests/test_site_identity.py` scan over every served file
- not duplicated.

Root `shiplog.fragment.json`/`devlog.fragment.json` are untouched - they stay
the full, private source exactly as Slice 99 designed; only the served copy
is filtered. Still open, and separate from "make it public": handing the
served URL to Flashy's fan-in, an outward/contact decision on its own.

## 2026-11-22 — Slice 105: the coordination role's accept/assign/schedule/escalate, honestly

The live seven-role charter's `coordination` role has claimed four
capabilities since Slice 103 - `accept`, `assign`, `schedule`, `escalate` -
and a measure with no code behind either. This slice makes them real, scoped
to what the codebase can actually do: one worker role (`analysis`), not an
invented dispatcher.

`POST /api/v1/jobs` takes an optional `agreed_by` (ISO date; malformed is
`400`, never silently dropped). Every job's `assigned_role` is always
`"analysis"` - a constant, not a free-text field, because that is the only
role with real code. At delivery, the existing `analysis` audit event gains
`agreed_by` and `on_time` (`None` when there was nothing to score against -
never a guessed `True`). `audit.measures()` gains a `coordination` entry
computed from exactly those two event types, matching the charter's own
measure text word for word.

`POST /api/v1/jobs/{id}/escalate` moves a **pending** job to `escalated`.
This is a real, if narrow, enforcement: `run_job`'s existing "only a pending
job runs" guard means an escalated job is genuinely blocked, not just
logged - but there is no review dashboard or notification behind it, stated
plainly rather than implied to exist. Idempotent once escalated; `409` from
any other status.

Explicitly not done here: declaring `coordination`'s `x-capability`
(`engagement-coordination`) in the live handshake. `docs/mesh-identity.md`'s
rule still applies - a discovery slug waits for the endpoint to be deployed
and smoke-tested, not merely merged to `main`. Also not done: the other
three new roles' endpoints (research, synthesis, client-delivery), or any
review surface for an escalated job - both much bigger, separate slices.

## 2026-11-22 — Slice 104: token rotation resolved without a script, decision records confirmed and prepared

Picks up where Slice 102 (`ops/README.md`) left off: neither token rotation nor
decision records had a confirmed endpoint in anything available to this
session, so nothing was built against a guess. Both are resolved now, from the
real `@flashyos/agent` package rather than from asking Flashy first.

**Token rotation needed no script.** The package's own README states plainly:
agent names are unique per org, and re-minting rotates - running
`npx @flashyos/agent init` again with the same agent name replaces that agent's
token, and the old one stops working immediately. Done for real the same day:
`analystos-agent`'s original never-expiring token (minted 2026-09-28, the thing
Flashy's register read as "not revocable") no longer exists.

**Decision records.** Read `@flashyos/agent@0.21.0`'s own published source (the
npm tarball's `dist/chunk-NL5JM7HU.mjs`, unpacked and read directly - not the
README's prose alone, and not guessed): `requestApproval()`/`decide()` both
call `POST /api/v1/orgs/{orgId}/decisions`, body
`{orgId, token, agentName, summary, impact}`, impact one of `LOW` (auto-approves),
`MEDIUM`, `HIGH`, `CRITICAL`. `ops/flashy_decide.py` mirrors this exactly in
Python, including the same `STATUS_TO_STATE` response mapping
(`AUTO_APPROVED`→`auto`, `PENDING`→`pending`, `APPROVED`/`REJECTED`→`reviewed`),
so a caller reading its output gets the same shape the SDK's own
`requestApproval()` would return.

Same safety shape as `flashy_declare.py` (Slice 102): dry run by default,
`send_request()` is the only network-touching function and no test calls it,
`--execute`'s path to it is proven in-process with that function mocked. The
package's own docs are explicit that this only *records* a decision - v1 is
visibility and an audit trail, nothing here blocks AnalystOS's own code from
doing the thing being logged, and enforcement is still on the upstream
package's roadmap, not something assumed here. Calling this against any real
action is a separate, per-use outward decision under CLAUDE.md's rule
regardless of how confirmed the endpoint now is - nothing in this repository
calls it automatically.

## 2026-11-21 — "decision-grade output" renamed to "action-ready output" (owner's decision)

The 2026-11-21 trademark check (recorded separately, same date, below) found a live
USPTO filing on DECISION-GRADE in AnalystOS's own services class, plus Beroe Inc.'s
existing "Decision Grade Intelligence" branding in an adjacent category - stronger
risk than a plain web search for "no trademark found" would suggest. Owner's
decision: drop the term rather than wait on counsel, since nothing public depended
on it yet.

`drafts/defined-analystos.json`'s entry renamed: id `defined/analystos/decision-grade-output`
-> `defined/analystos/action-ready-output`, term "Decision-grade output" -> "Action-ready
output", same definition and dates. `deliverable-acceptance-criteria`'s `seeAlso`
reference updated to match. `tests/test_defined_fragment.py` updated (the two tests
asserting the old term's exact string); `drafts/README.md` and `ROADMAP.md` updated.
Nothing in `shiplog.fragment.json`/`devlog.fragment.json` was touched - those are a
hash-chained historical record of the trademark check itself being run, not a live
assertion of the term, and rewriting a committed shiplog entry would break its own
verification.

## 2026-11-21 — seven-role charter switched live (owner's decision, builds on Slice 95)

Owner's decision on the ROADMAP item carried since Slice 95: serve the seven-role
team charter (coordination, research, analysis, verification, synthesis, evidence,
client-delivery) rather than keep the original three. `drafts/flashyos-charter.team.json`
(validated zero-errors against the real `@flashyos/aao@0.4.2`, level 2 under
`auditProperty`) is now copied byte-identical to `site/.well-known/flashyos-charter.json`
and `site/flashyos.roles.json`; `tools/build_flashyos_handshake.py` regenerated
`flashyos.json`'s `capabilities` to all seven role names.

What this does **not** do, by design (drafts/README.md's former "why it is not the
live charter" risks #2 and #3, now moved to ROADMAP.md's Blocked list): no agent was
minted for the four new roles, and none of their `x-capability` discovery slugs
(`engagement-coordination`, `source-research`, `cross-document-synthesis`,
`analyst-briefing`) were declared anywhere - the handshake derives only role *names*
(Slice 94's already-established rule: a role name restates a governance fact the
charter already publishes; a discovery slug claims something is callable). Minting
the agents needs the re-minted join-grant token; declaring the slugs needs four
endpoints that do not exist in this codebase yet.

Two tests had to change to stay honest rather than to make this pass by weakening a
real check: `tests/test_mesh_identity.py::CharterTest::test_no_role_claims_a_capability_the_product_lacks`
now asserts the original three roles' capabilities are unchanged *and* names exactly
the new roles' declared (not yet code-backed) capabilities, instead of silently
accepting whatever the charter says. `tests/test_api_v1.py::MeasuresTest::test_measure_text_matches_the_published_charter`
now checks `measures()`'s output is a subset of the charter's roles with matching
text, not an exact match - `measures()` (Slice 61/96) was already honest about
computing a share only for roles with a real audit-log event type, and the exact-match
version of the test would have forced either a fabricated number for the four new
roles or a weaker `measures()`; neither was the right fix.

## 2026-11-21 — Slice 103: a bare scaled-table number is stored at its real size, not as-is

Owner's decision on the PROPOSALS item carried since the 2026-10-14 overnight run
(slice-33): **scale it**, not "fix the docstring to admit the bug." The old
`_value_matches_text` tried the bare candidate before the scaled one and
returned the first match, so a model that left a table cell unscaled (document
"in millions", cell "1,842.0", model proposes 1842.0) got that figure stored and
rendered at the wrong, 1,000,000x-too-small size - even though its own docstring
already claimed the opposite.

Fixed by making "has its own scale word" (`$1.2 million`) a precondition for
`doc_scale` *not* applying, and `doc_scale` the only candidate tried for a bare
citation when one is declared: `_value_matches_text(1_842.0, "1,842.0", 1_000_000)`
now returns `None`, not `1842.0`. With no declared scale (`doc_scale == 1`)
nothing changes.

`analystos/l4/seal_verify.py::value_supported` carries its own, independent
re-implementation of this match for the offline verifier - by design, so a
stranger re-checking a seal is not trusting the same code that sealed it. Fixed
the same way there (`_has_own_scale_word` added, `doc_scale` applied only to a
bare citation), confirmed by the differential test
(`tests/test_l4_seal_values.py::DifferentialAgainstTheAnalyzerTest`) that the two
independent implementations still agree.

Two existing tests encoded the old, now-rejected behaviour as their stated goal
and were rewritten rather than deleted: `test_value_matches_text_accepts_the_declared_scale`
now asserts the bare-vs-bare case is refused, and
`test_growth_on_scaled_table_operands_verifies_even_if_left_unscaled` is split into
`..._verifies_when_scaled` (passes) and `..._is_dropped_if_left_unscaled` (now
correctly raises, proving the fix - a model that leaves a figure unscaled gets
nothing stored for it, rather than something wrong).

Not in this slice (documented as a known limitation in `_has_own_scale_word`'s
docstring, not solved): a quoted string citing several numbers where some carry
their own scale word and some are bare in the same string. Treated as a property
of the whole string; the conservative choice never double-scales, at the cost of
not perfectly handling that rare mixed case.

## 2026-10-11 - pin the key out of band, never see the seed, never mistake "no check failed" for "authentic" (Slice 90)

A review of the seal-key rollout found three places where the safe path was easy to get wrong, all in code that already
existed, none changing what a seal contains (so the conformance corpus and every existing seal stay valid).

(1) The runbook had the operator type the signing seed on a command line (`ANALYSTOS_SEAL_KEY=<seed> python3 tools/seal_key_file.py
--from-env`), which leaves it in shell history. `tools/seal_key_file.py --from-prompt` reads it with a hidden `getpass` prompt instead
and refuses without a real terminal rather than read a pipe. It cannot tell the seed from the public key (both are 32 bytes), so
pasting the wrong half silently derives a different public key; rather than pretend otherwise the runbook says to compare the printed
`public_key` with the line `keygen` labelled "public key", and `smoke.py --seal` would catch it after deploy anyway.

(2) `seal_verify` exits 0 when no check failed, which is not "authentic": an unsigned seal, a seal with no pinned key, and a run without
the `cryptography` package all exit 0 with `authentic` false. Changing the default exit status would break existing callers (and the
conformance adapter's expectations), so `--require-authentic` is opt-in, changes only the exit status (the JSON is byte-identical), and
the docs and the module docstring now say which to use.

(3) `--key-file` trusted whatever the file listed, which is only as trustworthy as the connection that fetched it. `--expect-key-id ID`
adds the pin a relying party recorded out of band. It compares against the seal's own `key_id`, which is not signed, so naming the
pinned id proves nothing; that is safe because the key the file lists under that id must then verify the signature, and `validate_key_file`
already forces `key_id = sha256(public key)[:16]`, so a file cannot list a different key under the pinned id. Tests cover a forged seal that
names the pinned id, a rotated two-key file, and an id the file does not list. The docs ask for the id to be taken from at least two
channels that do not share a host.

Not done: generating or publishing any key; separate keys for seals and the audit log; a revocation date in the key file; `--expect-key-id`
on `smoke.py`. Revocation is still removal, which makes the removed key's old seals non-authentic; that trade-off is the owner's to accept.

## 2026-10-07 - `smoke.py --deployed`: are the live bytes the repository's bytes? (Slice 89)

Flashy-integration item J3. The existing smoke checks prove a deployment serves the advertised surface with the right content
types, not that it serves *our* files, so a stale CDN copy or a deploy that missed a file looks healthy. `--deployed` GETs the live
URL of the 16 machine-readable files (every `.well-known` file, root files, the served docs, the two pages; `index.old.html` is left
out) and compares bytes. Choices: (1) four states that are never merged, because "the server said no" (REFUSED), "we heard nothing"
(UNREACHABLE) and "it answered with other bytes" (DIFFERS) call for different action; a truncated body is UNREACHABLE, not DIFFERS or SAME;
(2) a 404 is REFUSED, not DIFFERS: the file is missing, which is not the same as stale; (3) only same-scheme, same-host redirects are
followed, so a hijacked or misconfigured redirect cannot make another origin's bytes pass as ours; (4) `Accept-Encoding: identity` and a
refusal of any encoding we did not ask for, so compression never produces a false DIFFERS or a false SAME; (5) zero files checked is a
failure. **Result against the real site** (read-only GETs to analystos.dev; run with `SSL_CERT_FILE=/etc/ssl/cert.pem`, the script's own
documented remedy for this machine's Python): `site/` at d346660 against live: **16 SAME, 0 DIFFERS, 0 UNREACHABLE, 0 REFUSED**. This branch's
`site/` against live: 12 SAME, 4 DIFFERS (`/robots.txt`, `/docs/seal.md`, `/llms-full.txt`, `/`), which is exactly this branch's unmerged
changes (the robots fix, the seal doc paragraph and its copy in llms-full, the regenerated homepage counts), so the check does what it should.

## 2026-10-07 - robots.txt no longer contradicts what the site advertises; a test for that class of fault (Slice 88)

Flashy-integration item J2. The audit confirmed `Disallow: /api/` in `robots.txt` against a sitemap, `llms.txt` and
API catalog that advertise `/api/v1` and `/api/v1/openapi.json`. `tests/test_site_consistency.py` now checks, from the files
as served, that nothing advertised is disallowed for `*`, that every advertised same-site path and every OpenAPI path is a file,
a `vercel.json` rewrite or an `api/` function, that in-page anchors and doc links resolve, and that every `.well-known` file has a
Content-Type/CORS header rule. It failed on exactly the known contradiction before the fix, and only that. Decision: keep
`Disallow: /api/` (the API is not crawlable content and each call costs money or work) and add **more specific Allow lines for the
two advertised GET entry points**, `Allow: /api/v1$` and `Allow: /api/v1/openapi.json$`, because robots matching is longest-rule-wins
and `$` stops `/api/v1` from opening everything beneath it. The alternative, deleting the Disallow, would have invited
crawlers onto POST-only and key-gated routes. Made in the generator (`tools/build_site_machine.py`) and regenerated. A crawler that
ignores `$` still treats `/api/v1` as blocked, as before. Judgement call: `POST /api/v1/verify` is advertised in `llms.txt`
as an instruction to agents, not a link, so it stays under the Disallow and the test checks only that it is routed. **Noted, not changed:** the audit also reported a 405-versus-404 inconsistency for POST-only API routes (not reproduced in this slice); `vercel.json` routing is deliberately untouched here, so that item stays open.

## 2026-10-07 - what the conformance corpus found, and what was fixed (Slice 87 follow-up)

The corpus's first run against the real code gave eight gaps. **Fixed** in `seal_verify.verify_bundle` (six cases,
regression tests in `tests/test_seal_verify_hostile.py`, which fail on the old code): (1) a bundle with zero facts, a null
root and `entries: 0` **verified** (a vacuous pass; `build_bundle` refuses to make one), now a `structure` failure; (2) a
fact `key` that is a number, list or object raised `TypeError`; (3) a `signature` that is a string, list or number raised
`AttributeError`; (4) a fact `record` that is not an object raised `AttributeError` once text was supplied. (2) to (4) are
reachable by anyone through the public, unauthenticated `POST /api/v1/verify`, which would have returned a 500 instead of a
verdict; it now answers `ok: false`. No security bypass beyond (1): the crashes failed closed by exception, but a verifier that
dies on hostile input is not one a stranger can run against it. A falsy non-object signature (`""`, `[]`) used to count as
unsigned and now fails `structure`; `null`/absent is still unsigned and `{}` still counts as unsigned (integrity only, never
authentic). **Not fixed, recorded as expected failures** (the cases stay strict and carry `known_gap`): (5) an audit-log line with a
**duplicate JSON key** is read as last-wins, so two implementations can disagree about what the line says; (6) a **`NaN` literal**
in an audit line is accepted though it is not JSON, so a strict parser elsewhere cannot read the chain. Both want
`verify_entries` to parse strictly, but the writer (`FileStore.append_audit`, `json.dumps` with default `allow_nan`) would then
need to refuse the same input or a log could fail its own verifier; that is a change to the tested audit kernel and the store
together, so it is left for a deliberate slice. Separately noted, not a bug: dropping the tail of an audit log is invisible
without a pinned `expected_head` (documented in the module); the corpus has a case that states that limit.
Re-run of the external kit after the fixes: see the report for this slice.

## 2026-10-07 - a refusal-first conformance corpus for the seal and the audit log (Slice 87)

Flashy-integration item J1. Added `conformance/seal-1.json` (generated by `tools/build_conformance_corpus.py`),
the adapter `python -m analystos.conformance` and an in-process runner in the suite. Choices: (1) the corpus is
**ours**, with the line protocol of Flashy's conformance-kit borrowed and none of its code or format name copied
(the `contract` is `analystos-conformance/1`); (2) expectations are hand-written in the generator, never computed by
the verifier under test, because a corpus derived from the code agrees with it by construction; (3) refusals are the
substance, about four in five cases; (4) a verifier **crash is "unanswered"**, not a verdict, because a crash on a
hostile bundle is a different finding from a wrong answer and the public `POST /api/v1/verify` endpoint is exactly where
a stranger sends one; (5) the strict set is separate from the lenient: `seal` is "internally consistent", `seal-authentic`
needs a key you pinned, `seal-content` needs the text, so the corpus cannot let `ok` stand in for `authentic`; (6) a
case the code gets wrong is never weakened: it carries a `known_gap` and the suite requires it to keep failing until the
annotation goes with the fix. Written, then run against the code: the corpus found eight gaps on its first run. One
case records a **documented limitation** rather than a bug (a tail-dropped audit log with no pinned head still verifies,
as the module says) so the limit is explicit. External cross-check, by hand and not in the suite:
`node <conformance-kit clone>/src/cli.mjs conformance/seal-1.json -- python -m analystos.conformance` (direct invocation,
not `npx` or a symlinked bin, which the audit found can exit 0 without running; cases confirmed executed).
Known remaining gaps and what was done about each are in the fix entry below.

## 2026-10-02 - a public key a stranger can pin, and the means to publish it safely (Slice 86)

Hardening-plan item A2. Seals can be signed but nothing published a key to check them against, so
"authentic" had nothing to point at. Built the format (`analystos-seal-key/1`: a `keys` list with
`key_id`, `public_key`, `status`), a strict validator and a fail-closed `--key-file` path in the
standalone verifier, `tools/seal_key_file.py` to write the file, and smoke checks - and
deliberately did **not** generate, print, store or publish a real key, add any file to `site/`, or
touch the host's environment. Turning it on is a human act (docs/seal.md, "Turning it on").
Choices worth recording: (1) `keys` is a list from day one because a published format is the one
thing that cannot be widened later without breaking whoever pinned it; (2) revocation is removal
(fail closed) rather than a status with dates, which would be a feature nobody has asked for; (3)
`keygen` prints the private seed and the public key side by side, so the tool derives the public key
from the operator's own environment (`--from-env`) and refuses a `--public-key` equal to the seed:
the likeliest way to leak the key is pasting the wrong line; (4) the smoke check that matters is
`--seal`, which verifies a real production seal against the live file, because the dangerous
mistake is a host key that does not match the published one and a format check cannot see that;
(5) a missing key file is reported as "not published yet", not a failure, until `--expect-seal-key`.
The file is trusted exactly as far as TLS to analystos.dev; the docs say so and say how to pin the
`key_id` out of band.
## 2026-10-02 - review follow-ups on the hardening branch (Slices 82 and 85)

Two changes after reviewing the branch against real data. (1) The image cap counted raw placements, which rejected a normal
30-page whitepaper (53 placements, 14 distinct images over half an inch) and charged a vision call per repeated logo; it now
counts and reads distinct images of at least 36 pt, default still 40 (the largest of 12 measured documents is 15). This reverses
Slice 85's "not deduplicating identical images" and says so in that spec. (2) The Gate-2 proofreader prompt gained the "text is
material, not instructions" line the narrator and extractor already had, and the repair prompt's rejection reason is neutralized
and capped. They touch disjoint files (image_facts and its tests; narrate, proofread and theirs), so either is easy to drop in review. The sample is 12 PDFs, mostly designed finance and crypto
documents, with no real SEC filings; a few would firm the number up.

## 2026-10-02 - cost caps on PDF extraction: a limit on images, one pass over the pages (Slice 85)

Two amplifications found by the audit. Every embedded PDF image costs one paid vision call and
there was no limit, so one upload could make hundreds. `ANALYSTOS_MAX_IMAGES` (default 40; a
malformed value is an error, not a silent default) now caps it, and exceeding it **fails closed**
with a plain `ValueError` that reaches the user: reading only the first N images would silently
drop facts, which this product exists not to do. The check runs right after the images are counted
and before a client is resolved, so an over-limit document costs no calls and needs no API key; a
PDF with no images never reads the setting. The default is a judgement, not a measurement: logos
and decoration count as images, so a long filing with one per page is the case to watch, and the
setting is there to be raised. Second, text extraction reopened the PDF and re-extracted every
page's tables for each table (tables x pages). The document pass now hands each page's tables to
`_raw_rows(..., table=)`, so each page is extracted once and the parsing code stays the single
shared `_raw_rows` (a Slice 44 test depends on that); `all_tables` got the same treatment. Output
is identical (checked on the PDF fixtures and a pinned golden); a test counts `extract_tables`
calls so the quadratic behaviour cannot return unnoticed.

## 2026-10-02 - the audit log is a hash chain, signed with the seal key (Slice 84)

`audit.jsonl` was append-only by convention, and the charter's measures are computed from it.
Each line now carries `seq`, `prev_hash`, `entry_hash` and, when `ANALYSTOS_SEAL_KEY` is set, an
Ed25519 `signature` over the hash with a domain string (`analystos.audit-entry/1`). This is the
linear, insertion-order chain DiligenceOS's receipt log uses, chosen over a Merkle proof over
id-sorted leaves, which treats honest growth as tampering. The signing marker (`log_signing`) and
`key_id` are inside the hash, so a signature cannot be stripped and the line relabelled unsigned;
with no key, lines are still chained and say so. A malformed key still writes the line, unsigned,
rather than losing the audit trail (the analysis routes already refuse a malformed key before
they run). Appends take a file lock so concurrent workers cannot extend the chain from the same
head. Old unchained lines are tolerated as a prefix; an empty or legacy-only log fails verification
rather than passing vacuously. Honest limit: the chain is tamper-evident, not tamper-proof. A
shortened log is only caught if you pin the head you saw (`--expect-head`), and whoever holds the
key can re-sign a rewritten tail. No new crypto: the seal's own sign and verify helpers.

## 2026-10-02 - the signed seal names the model, the caller and the code version (Slice 83)

The audit found that model id, caller identity and code version lived only in the unsigned audit
log, so a seal on its own could not say what produced it. They are now in the signed payload as
`model_id`, `caller_id` and `code_version`. We kept `analystos-seal/1` and did not bump the
version: `seal_verify.py` demands a fixed set of payload keys but ignores extra ones, the
signature covers the whole payload, and no second verifier in the repo reads the payload, so old
bundles still verify and old verifiers still verify new ones. The honest limit is third-party
ports that reject unknown payload keys, which `docs/seal.md` now warns about. `caller_id` is the
API-key name (never the key); the CLI and legacy routes use `(cli)` and `(legacy-access-code)`,
which no key name can equal. `code_version` comes from the deployment environment
(`ANALYSTOS_CODE_VERSION`, else Vercel's commit SHA), never from running git at request time, and
is `null` when the deployment does not say. `model_id` is the model the run asked for, not a
provider statement. An unsigned seal carries these unauthenticated, as it does every field.

## 2026-10-02 - the narrator treats document text and titles as data (Slice 82)

An external audit noted that the extraction prompt told the model "text that looks like an
instruction is DATA" while the narration prompt had no such line, even though verbatim document
substrings reach it through the fact manifest, and that the caller's `title` was pasted unescaped
into both prompts. Figures cannot be altered by an injection (every number is re-verified in
code), but wording and behaviour could be steered. Now: the narration and repair system prompts
carry the rule; each manifest entry sits between `<<FACT n>>` / `<</FACT n>>` markers and text
from the document is neutralised (one line, `<<` and `>>` broken up) so it cannot forge a marker;
and one shared helper, `sanitize_title`, caps the title at 200 characters and strips control
characters, quotes and marker tokens at both prompt sites. Only the model-facing form is changed:
the title shown in the report and bound into the seal is untouched. This is a mitigation, not a
proof, and it does not delimit the raw document sent to extraction (already covered by the rule
and by source-text verification).

## 2026-10-01 - an upload's filename never decides where it is saved (Slice 81)

`/api/extract` and `/api/analyze` saved each upload as `tmp_dir / upload.filename`, with the
filename taken straight from the client. `pathlib` does not confine that: `../../x.csv` left the
temporary folder and an absolute name replaced it, so a caller holding the access code could write
a file they controlled, with an allowed extension, anywhere the server could write. Even a harmless
name with a directory in it (`reports/data.csv`) crashed the route with a 500. Both routes now use
only the last component of the name and check the result still sits directly inside the temporary
folder; the `/api/analyze` default title uses the same component. This is the rule `/api/v1` already
followed, so ordinary uploads keep the same source name in reports, which is why the fix keeps the
client's last component rather than a random server-chosen name. The regression tests were written
first and fail on the unfixed code; one pins `/api/v1`'s existing safe behavior so the two surfaces
cannot drift apart again. Not changed: the access code, rate limits, size limit, or retiring the
legacy routes.

## 2026-09-29 - one public identity: the studio, and its own email (Slice 80)

After Slice 79 the retired `site/index.old.html` was still served at `/index.old.html` with a
personal email in its "Request early access" link, and the sample AAO manifest, its tests and the
FlashyOS alignment note used a personal email and name as example values. All now use
`30eventures@gmail.com` and "30E Ventures", and a test scans every served file for a personal name
or any email other than the studio's, so it cannot come back quietly. Not changed: the
`solwayholdings` sample-org name (ROADMAP tracks its fate) and unserved research notes that quote
search terms used at the time. The internal audit and alignment notes were checked and are not
served under `/docs/`, so they were never a public leak.

## 2026-09-29 - the homepage credits the studio, not a person (Slice 79)

The page named its maintainer three times ("Built solo by ...", a first-person "Who built
it", "Built solo, early stage"). With Slice 78 the site says it is a 30E Ventures product, so
the copy now says "Built by 30E Ventures" and speaks as "we". Every factual claim in "Who
built it" is kept (a spec before the code, every real bug recorded with its root cause,
candour about being early); only the attribution changed. "Solo" was dropped rather than
carried over, because it was a claim about team size that the studio framing no longer makes.
Internal documents that mention the maintainer are out of scope for this slice.

## 2026-09-29 - the studio bar is generated static markup, not a script include or a copied snippet (Slice 78)

analystos.dev now carries a 30E Ventures bar and a footer line so it visibly belongs to the
studio's other sites. The markup lives once, in `tools/studio_chrome.py`, and is written
between marker comments into each page, with `tools/refresh.py --check` and a test failing
if a page drifts. Rejected: a shared `<script>` include (an agent that does not run scripts
would see no studio identity, and it adds an external request and a failure mode to a page
whose point is that nothing is taken on trust); hand-copying the snippet into each page (it
would drift the first time a link changed). The bar keeps the studio's own near-black colours
in both themes, so it reads as the studio's strip rather than restyling AnalystOS. It claims
only the studio's name, Toronto, and that AnalystOS is one of its products.

## 2026-09-27 - the evidence store announces the public development key (Slice 72)

Audit finding 4: with no `ANALYSTOS_EVIDENCE_KEY` the store encrypts with a key derived from a
constant in the source. Kept as the zero-configuration default (never plaintext, existing
stores stay readable) but it now prints one stderr line per process the first time it is used,
naming the variable to set. Refusing to run without a key was rejected: it would break the
command-line tool out of the box for a protection its typical user does not need, and the
hosted path deletes the upload anyway.

## 2026-09-27 - cleanup pass (Slice 71)

Removed three unused imports and one dead function; added `tools/refresh.py` (one command,
right order, `--check` mode) for the three generated artifacts that had each cost a
stale-test failure this session; and a hygiene test so unused imports and unreferenced
module-level functions cannot creep back. `solwayholdings.aao.json` (a Slice 7 sample whose
description claims an org that does not exist) was left alone and logged for the owner: it is
only a test fixture, and deleting a checked-in root file is not the loop's call.

## 2026-09-27 - one model setting, recorded per run (Slice 70)

The model name was a constant in four modules. It is now `ANALYSTOS_MODEL` through
`analystos/models.py`, read at call time, validated, and recorded in the pipeline trace
and the API audit event so an audited report can be tied to the model that wrote it. The
default is unchanged. Deliberately not done: a model per stage or per API caller, and any
claim that another model is *good* (only the live suite can say). The live suite's price
table still refuses an unpriced model, which is the guard that keeps a model switch from
defeating the $1.00 ceiling.

## 2026-09-27 - the homepage's counts are generated (Slice 69)

The homepage's test and spec counts were typed by hand in seven places and were 158 tests
stale within a day. `tools/site_counts.py` now counts by discovering the suite and the spec
folders and rewrites the figures through explicit patterns; a pattern that stops matching
exactly once is an error, so rewording the page cannot quietly freeze a number. A test fails
when the page is wrong. The cost is one command after adding tests (`python3
tools/site_counts.py`), accepted deliberately: the alternative is a public number that is
wrong.

## 2026-09-27 - deployment smoke script (Slice 68)

The checks that mattered on deploy day were run by hand with curl. `tools/smoke.py`
runs them as one command against any deployment: every advertised URL and content type,
the mesh identity files (charter valid, both paths identical, handshake slug matches),
every link in `llms.txt` and the sitemap, the API index/OpenAPI agreement, the rewritten
routes failing closed, an unauthenticated analysis refused, and a junk seal answered
`ok:false`. It is tested against a local server that emulates Vercel's file-per-route rule
and `vercel.json`'s rewrites and headers in front of the real Flask app, including
deliberately broken deployments. That emulation is my model of Vercel, verified against
the one real deployment we have; the smoke script run against analystos.dev is the
real check. Sends no document, key or secret.

## 2026-09-27 - live-suite PASS now means the report was good (Slice 67)

The live suite printed PASS whenever the pipeline did not raise, including when a
written report failed both gates and quietly fell back to a template. A run that
degraded looked the same as one that did not, which defeats the suite's purpose.
Runs are now graded from the pipeline's trace into PASS (expected tier, minimum
verified facts, and a seal that fully verifies), DEGRADED (worked, but at a lower
tier) and FAIL. DEGRADED is not a failure by default, because the model is
non-deterministic and a fallback is designed behaviour, but it is visible, counted
and fails the run under `--strict`. The minimum-fact thresholds are starting guesses
to be tuned from the first real run, said so in `live_tests/README.md`. No paid run
was made; the grading is proved with synthetic traces.

## 2026-09-27 - the standalone verifier checks values against citations (Slice 66)

The seal's biggest stated limit closed: with the extracted text, the verifier now checks
that each quote's number and each calculation operand equals a number its own citation
spells (as printed or times the document's declared scale), so a real quote paired with a
wrong value - with every hash rebuilt - no longer passes. It is a second implementation of
the analyzer's number reading, differentially tested against it. Deliberately exact on the
stored canonical value (the analyzer accepts within 1% when *accepting* a fact; what it
stores is exact). Events and prose carry no numeric value and stay uncovered, stated in
`docs/seal.md`.

## 2026-09-27 - displayed figures round half up (Slice 64)

A source figure of `$1.95B` displayed as `$1.9B` (audit finding 11) because Python
rounds the float's binary value, not the decimal the reader sees. Displayed figures
(compact usd, percent, number, donut shares) now round the shortest decimal form half
away from zero. One existing test had encoded the old behaviour (1,250,000 shown as
$1.2M) and was corrected. The homepage's sample brief still shows "$1.9B" for the Orion
guidance; that sample is a hand-condensed run and was left alone rather than guessed at.

## 2026-09-26 - deployed; FlashyOS Level 2 passes (verification of Slices 55-63)

Merged and deployed. Checked the live site with read-only requests: every new file
serves with the intended content type, `.well-known` and the rewrites work on
Vercel, the API is closed without keys, and the live charter passes our checker and
FlashyOS's own. Before running `@flashyos/conformance` I read the published code of it
and its two dependencies (no install scripts, GET-only requests, no local reads for
the check, no shell or eval) and ran it with install scripts disabled: Level 1 and 2
pass. Limits stated: the source repo is private so only the shipped JavaScript was
read; the mark (Level 3) needs a running agent on the network and is not claimed.

## 2026-09-26 - no server-side reports by default; results go to the reader's Downloads (Slice 63)

30E Ventures decided reports should land in people's Downloads. That answers the
open storage question from Slice 61: AnalystOS keeps nothing by default. The
hosted endpoint now returns the PDF and the seal alongside the HTML, and the
upload page saves report, PDF and seal through the browser. Consequences accepted:
(1) no durable report URL, so a mesh task's `evidenceUrl` points at the
requester's own storage (a seal verifies anywhere, which is why this works);
(2) no server-side audit trail of viewing, since nothing is viewed on the server;
(3) the privacy story gets simpler and stronger (only the transient upload and
Anthropic's API ever see the text). `FileStore` and signed links remain for a
deployment that wants them. Also recorded: the owner states 30E Ventures owns the
`analystos` org and `30eventures@gmail.com` is the accountable email; not
independently verifiable from the public directory.

## 2026-09-25 - machine-facing files are generated from one source (Slice 62)

Added `llms.txt`, `llms-full.txt`, an RFC 9727 API catalog, a sitemap, robots and
the guides as markdown under `/docs/`, so an agent can find what this is, how to
call it and how to check it without scraping the homepage. All are generated by
`tools/build_site_machine.py` from `docs/`, and a test fails if any is stale, so
the published copy cannot drift from the source (the failure the audit found in
the README, architecture page and roadmap). Chose markdown over rendering HTML
docs: a converter would be a new dependency for no benefit to the readers this is
for. The homepage's test and spec counts were updated by hand and will drift again
at the next slice; they are the one number still maintained manually.

## 2026-09-25 - an agent-callable API, honest about storage (Slice 61)

Added `/api/v1` (analyses, reports, links, verify, index, OpenAPI) so another
agent can hand over a document and get back a sealed report with an https URL
for the mesh's `evidenceUrl`. Choices: per-caller hashed API keys instead of the
shared access code; a signed expiring link per report and format instead of
public URLs (FlashyOS says never to put document contents on the mesh, so the
URL is access-controlled and short-lived); a public stateless verify endpoint
because checking must not require an account; the audit log records counts and
tiers but never text or filenames, and the charter's three measures are computed
from it. Storage is a plain file store, **not durable on Vercel**; that is
stated in the API docs and the spec rather than papered over with an unverified
"works in production". Every secret (API keys, link secret, seal key) fails
closed with no built-in default. Also: seal payloads gained a random nonce so two
analyses in the same second cannot share an id.

## 2026-09-25 - reports are sealed; the verifier is standalone (Slice 60)

The charter's `evidence` role promised that a stranger can re-verify a report
offline. Built as a bundle (every fact hashed under a Merkle root, plus the
report structure, the source/text hashes and the tier, all under one Ed25519
signature). Choices: the construction matches Flashy's published provenance
code so their tooling style can read it; every number in a sealed record is a
string so no verifier depends on float formatting; the verifier is one
stdlib-only file that imports nothing from AnalystOS, and is differentially
tested against the analyzer's own folding and arithmetic; and there is **no
default signing key** - an unsigned seal says it is integrity-only, because the
evidence store's public fallback key (audit finding 4) is the mistake not to
repeat. The three trust levels (`ok`, `authentic`, `content_checked`) are
reported separately rather than as one "verified" flag. Deliberately left out:
checking a quote's value against its citation in the standalone verifier (a
second, larger implementation of the number parser), storage of bundles, a
chain across reports.

## 2026-09-25 - mesh identity files added, deploy gated on the org question (Slice 59)

Published a `flashyos/1` handshake and an AAO 0.1 charter for `analystos` in
the repository (not deployed by the slice). Decisions: the handshake declares
no capabilities until something is callable; the charter's three measures are
each computable from the API audit log so nothing is published that cannot be
measured; no front door and no directory fragment, because each needs
something that does not exist (a monitored endpoint; an owner's assertions).
The `analystos` org already exists on the network with an unknown owner, so
the branch should not be merged and deployed until that is settled - serving
the handshake would read as a claim to it.

## 2026-09-25 - the AAO checker now follows the published schema (Slice 58)

`analystos/aao/validate.py` was a stand-in written before the published
schema was read: it invented a tier (`NONE`), rejected the real `CRITICAL`,
required two optional fields, refused the `x-` extension convention, and
disagreed with the schema on 15 of 21 probes. Replaced by a pinned copy of
`https://flashyos.com/aao.schema.json` (sha256 in code and test), a
keyword-limited JSON Schema checker (no new dependency; a test fails if the
schema starts using a keyword it lacks), the schema's documented cross-field
rules, and the documented naming rules. Problems now carry `aao.*` codes so the
checker can speak the conformance-kit line protocol. The codes are ours
because FlashyOS's aao/0.1 corpus is not public; that is stated in
`docs/aao.md` rather than implied. Rejected: adding `jsonschema` as a
dependency - the keyword subset is small and a dependency would add a
second thing to keep in step with the pinned schema.

## 2026-09-25 - public claims corrected to match the code (Slice 57)

The audit found the homepage describing the local command line ("stays on
your machine", "encrypted at rest") on a page whose main call to action is
the hosted upload, and promising more than the code checks ("never lost",
tags "wherever a figure appears", "real documents", "a retrospective in every
spec"). Copy corrected; `tests/test_site_claims.py` keeps the retired phrases
from coming back. Chosen over hiding the detail: the mesh outreach points at
the homepage Trust section, so it has to be the honest version.

## 2026-09-25 - one definition of a figure's basis, shown on every surface (Slice 56)

Audit findings 5-6: GAAP/guidance tags were shown in body paragraphs but not
on KPI tiles or chart bars, and the `source: "image"` marker from Slice 50
was stored and never drawn. `analystos/l4/basis.py` is now the single
definition (forward horizon, non-GAAP, from image) used by the HTML and PDF
body text, KPI tiles and chart notes, plus an image note in footnotes.
Chart basis is a note under the chart naming the tagged points, not a mark
per bar - four chart types times two renderers would have meant touching
every drawing routine for a marginal gain. Still not enforced: that the
model's `horizon`/`gaap_status` labels are right (the audit lists that; the
homepage wording in Slice 57 says so).

## 2026-09-25 - Gate 1 now checks relationships and spelled-out quantities (Slice 55)

The code-verified audit (`docs/audit-2026-09-25.md`, findings 1-2) showed that
"every number is proven" was true but weaker than it sounds. A real run passed
both gates with "Gross margin moved (4.7%) points to 54.2% from 55.8%": three
individually-correct figures joined by a wrong relationship (55.8 -> 54.2 is
1.6 points; 4.7 is the four-quarter change). Separately, "grew twenty percent",
"roughly doubled" and "about two-thirds" got through because only digits were
banned.

Two deterministic checks were added to `_validate_paragraph` (no model call,
no dependency): a change fact's named endpoints must be its own two operands,
and spelled-out amounts, fractions and multipliers are refused outside a
placeholder. Deliberately narrow (explicit "from"/"to" wording only; two-operand
`growth_percent`/`difference` only) so a false positive costs one repair call,
not a lost report. Not claimed: that all wrong relationships are now caught.

## 2026-09-12 — the deterministic floor didn't recognize "Q3 FY2026" (Slice 54)

A newly-generated test document ("Orion Industrial Group") hit Gate 1/
Gate 2 failure on a live run (a different, non-deterministic outcome
than an earlier run of the same document) and fell to Slice 52's
deterministic floor - which then produced a visibly broken result: a
KPI strip listing "Revenue" five times across five different quarters,
a jumbled chart mixing unrelated facts, and no trend sentence despite
five consecutive quarters of real growth in the data.

Root cause: the model labelled quarters "Q2 FY2027" (quarter + "FY" +
year combined) - a real, common fiscal-quarter convention this
codebase's period-detection regex only half-recognized, matching just
the trailing "FY2027" and silently losing the quarter number. That one
lost token broke three things that all depend on it: metric-key
deduplication (every quarter of "Revenue" looked like a different
metric), chronological sort order, and time-series/trend grouping. The
identical gap existed in `rich_export._PERIOD_LABEL_RE` (Slice 47's
chart-type detector) too, not only the deterministic tier - fixed in
both places, since a model-declared chart using this same label
convention would have hit the identical misclassification on the
best-case rich-narrative path.

Confirmed by reconstructing the exact real segment set visible in the
captured Test #10 output and running it through the fixed code
directly - no second live API call needed, since the real data was
already fully visible in what the user had already captured.

## 2026-09-12 — root cause found: a fake, non-numeric placeholder (Slice 53)

The actual reason Test #4/#8 fell back to the flat renderer, deliberately
left unresolved through Slice 52's own floor (that floor guarantees a
*good* output; it doesn't explain or fix why the *best* output failed).
A real, captured live run showed the model writing `{{5.0M}}` - not a
real `{{N}}` manifest index, a literal value dressed up to look like
one - for a real, source-stated figure ("...projected to decline to
approximately $5.0 million...") that had no verified segment behind it
to cite. `_PLACEHOLDER_RE` correctly never matches a non-digit token
like this, so its digits were already caught by the generic
"digit outside any {{N}} placeholder" check - but that message doesn't
say *why*, and 3 single-paragraph repair attempts plus 2 full retries
all failed, each producing a new variation of the same underlying
mistake, because nothing told the writer or the repair pass what
actually went wrong.

Added `_fake_placeholder_problem` - a specific, named check for this
exact failure class, distinct from the generic digit check - plus
explicit prompt guidance in both `_SYSTEM_PROMPT` and
`_REPAIR_SYSTEM_PROMPT`: a placeholder is always a bare manifest index,
never a value or unit; a number with no matching fact must be dropped
or described qualitatively, never approximated inside fake braces. The
repair prompt's prior guidance for this exact situation was scoped only
to a digit from an event's date/status/next_step text - generalized to
any missing fact, since the real failure here was an ordinary quote/
computed fact that simply wasn't extracted, not an event digit.

Deliberately not attempted: making extraction guarantee it never misses
a real number in the source text. Not achievable with certainty for an
LLM-driven extraction step, and not the actual point of failure -
Gate 1's job is refusing an uncited number through, not guaranteeing
every real number gets extracted; the fix belongs in how the writer/
repair handle a genuinely missing fact, not in trying to make extraction
perfect.

Confirmed via a mocked reproduction of the exact captured failure text,
not a second live API call - the user's explicit requirement going in
was not needing to run this more than once to get it fixed.

## 2026-09-12 — a mandatory, deterministic "advanced" floor (Slice 52)

Gate 1/Gate 2 rejecting the model's narrative previously meant a bare,
chart-less, KPI-less text fallback - the safety behavior was right (never
show a narrative that couldn't be verified) but what it fell back *to*
had no charts and no KPI strip at all, because those were entirely the
model's own narrative JSON to produce. Added
`analystos/l4/deterministic_report.py` - a second, zero-model-call tier
between the rich narrative and true bare text: a KPI strip, at least one
chart, and analytical sentences (benchmarking, trend, relationship,
disclosure-gap) assembled entirely from already-verified segments, using
a fixed-template approach rather than a bounded model call - reasoned
through explicitly before building: none of the four sentence types
require *discovering* a relationship (that's already done by extraction
or the existing chart-shape detector), only *phrasing* one already
known, which templates handle without needing any generative step that
could itself need a quality gate.

Produces the *exact* report-dict shape `write_narrative` already
returns, so `render_rich_report`/`render_rich_pdf` render it completely
unchanged - no new rendering code, no visual "degraded" signal, by
construction rather than convention.

One correction made before building, not after: the task's framing
assumed disclosure-gap detection was "already code-driven, reusable" -
it wasn't. `disclosure_gaps` was, until this slice, content the *model*
wrote inside `write_narrative`'s own response; nothing detected a gap
independently of that. Built a genuinely new, fixed checklist detector
instead (EPS, cash flow, gross margin, etc., keyword-matched) rather
than silently assuming code that didn't exist.

Two real bugs surfaced only by running an actual document through this
tier (not by any hand-built fixture) - both instructive, both now
covered by regression tests built directly from the failure:

1. Determining which of a computed fact's two cited quotes was the
   "current" one by *citation position* seemed reasonable but wasn't -
   `analyze.py`'s own `growth_percent` verification already tries
   operands in either order and accepts whichever matches, proving a
   model is never actually constrained to one order. A real document
   produced "Net Income Q3 2025 was $22.4M, a change of $-2.8M" -
   attached to the older quarter. Fixed by determining "current" from
   each quote's own period token (chronology), never from position.
2. `_select_bridge` treated any 2-citation `difference`/`remainder` as
   a bridge, producing a nonsensical "moved from X to Y" sentence for
   an ordinary two-point YoY comparison with no named component at all.
   Fixed by requiring 3+ citations - a genuine start/components/end
   bridge, never a plain two-point difference.

Confirmed via the pattern already established this session: engineered-
failure automated tests (a permanently broken `write_narrative` mock
still yields a full rich-rendered report with all four sentence types,
zero model dependency) *and* a real live run against the actual Meridian
document behind Test #8/#9, read directly, not asserted to work.

## 2026-09-11 — a deliberate, real-money live-test suite (Slice 51)

The 458 tests in `tests/` are entirely mocked - valuable and permanently
free, but structurally blind to anything only a genuine model response
can surface (found directly this session: a report that looked correct
against every mock but produced an uncitable number live). Added
`live_tests/` - outside `tests/` on purpose, so it is never collected by
`unittest discover -s tests` and never runs without being explicitly
invoked - a small, fixed set of 4 structurally different documents (the
schema/template path, the narrated path over plain prose, over Slice
50's column-aware extraction, and over Slice 50's image-fact
extraction), run against a real, non-mocked `anthropic.Anthropic()`
client.

Cost tracking is real, not a proxy: `CostTrackingClient` wraps the real
client so every actual `response.usage` becomes a real dollar figure via
a price table sourced from Anthropic's own published pricing
(`claude.com/pricing`, checked 2026-09-11 - $2/MTok in, $10/MTok out for
Sonnet 5), logged per call and per document. A **$1.00 hard ceiling**
(your call - conservative against an expected real cost of a few cents
to a few tens of cents for the whole run) is checked before every
dispatch; once reached, every further call is refused before it's ever
sent, and the run stops rather than continuing to spend. One honest,
disclosed limit: a call's cost isn't known until its response completes,
so the ceiling can only be checked against *completed* calls - total
spend can overshoot by at most one call's own bounded cost, never
unbounded, and this is stated plainly in `live_tests/README.md` rather
than glossed over.

The runner's own logic (price table, cost accumulation, the ceiling
correctly refusing and never dispatching the call that would exceed it)
is proven by 7 ordinary mocked tests in `tests/` - this codebase's usual
discipline of proving logic before it ever touches a real key - fully
separate from the live run itself, which is the actual, human-triggered
proof this slice exists to produce.

## 2026-09-11 — multi-column PDF reading order + image-derived facts (Slice 50)

Two audit-flagged gaps: PDF text extraction read pages in `pdfplumber`'s
default order, which - confirmed by direct experiment - interleaves a
genuine two-column layout line by line rather than reading one column
fully before the next; and an embedded image/chart was completely
invisible to the system, no OCR, no vision call, anywhere.

**Column detection** (`analystos/l1/pdf_columns.py`) works from words'
own bounding boxes: the largest empty horizontal gap on the page,
requiring it span a real minimum fraction of the page width and split a
real minimum number of words on each side, is treated as a column
gutter. No such gap -> falls back to the exact pre-Slice-50 behavior, so
every existing single-column document (the overwhelming majority) is
provably unaffected - tested directly against the same fixtures used
before this slice.

**Image-derived facts** (`analystos/l1/image_facts.py`): `tesseract`
isn't installed on this machine and a system-level binary is a bigger
ask than any dependency this repo has taken on - vision via the
existing `anthropic` client needed nothing new. The model's only job is
a literal, verbatim transcription (never "extract the revenue figure")
- that transcript is then treated as ordinary document text and flows
through `analyze_document` *completely unmodified*: a fact "from" an
image is verified exactly as rigorously as any other quote, an exact
substring of something real, here a transcript instead of digitally-
extracted text. The one honest, disclosed gap - a transcript is a model
output, not a byte-exact extraction - is why every such segment gets a
new, purely additive `source: "image"` tag, applied *after*
verification, never folded into or weakening it.

A document with zero embedded images never resolves an Anthropic
client at all, proven directly (with the API key cleared) - a plain
PDF costs nothing extra and needs no key just because this code now
sits on the extraction path.

`Pillow` is now pinned explicitly in `requirements.txt` (it was already
an implicit transitive dependency of `pdfplumber`/`reportlab`; this
slice's tests import it directly to build embedded-image fixtures).

## 2026-09-11 — Gate 2's full prose-quality rubric (Slice 49)

Gate 2 (`analystos.l2.proofread`) previously judged language mechanics
only - spelling, grammar, duplication, leftover artifacts. Raised its
bar to three further criteria (no filler, genuine cross-section
synthesis clearly labeled, plain-language disclosure gaps), each
grounded in a worked example in the system prompt the same way every
other rule in this codebase's prompts already is - a bare adjective
("check for filler") produces inconsistent model judgment; a concrete
good/bad example doesn't.

One check moved out of the LLM's hands entirely: whether
`executive_insight`/`outlook_interpretation` cites at least two distinct
`{{N}}` facts is mechanically verifiable, so it's now a deterministic
Gate-1-style check in `analystos.l2.narrate` (`_synthesis_problem`),
not asked of the model at all - this codebase's established preference
wherever a rule can be checked in code instead of only judged. Gate 2
still separately judges whether an insight that *does* cite two facts
actually connects them into a real judgment (a mechanical count can't
tell "margin fell and guidance held, together suggesting X" from
"margin fell. guidance held." - both cite two facts) - the two checks
catch different failure modes of the same instruction, deliberately not
redundant.

`_TOOL`'s schema gained `has_filler`/`has_synthesized_insight`/
`disclosure_gaps_clear` (booleans) so a specific criterion's outcome is
directly inspectable rather than inferred by string-matching `problem`
text. These are logged for auditability only - `passed` stays the
single, sole signal for whether a report ships, deliberately never
combined with the new booleans into a second, competing pass/fail path;
a test proves this holds even when the two would disagree (a mocked
`passed=True` response with `has_filler=True` still ships).

Live-tested (not offline-simulated) per the task's own before/after
requirement: same underlying facts run through a real `proofread_report`
call twice. The "before" version - a generic-sentiment filler sentence,
two facts stated side by side with no connecting judgment, and a vague
disclosure gap - failed with exactly those three reasons, verbatim from
the model. The "after" version, same facts rewritten to state a specific
gap and read the two facts together into one judgment, passed cleanly.
Full transcript in `specs/slice-49/spec.md`'s "Built" section.

## 2026-09-11 — a real server-side PDF for the rich report (Slice 48)

The rich (v4) report had no server-generated PDF, only the browser's own
`window.print()`; the flat report's `render_pdf` (Slice 24) only knows
the flat title/paragraphs/footnotes shape and has no concept of a KPI
grid, a chart, or a boxed interpretation block. Added
`analystos/l4/rich_pdf.py` (`render_rich_pdf`), a parallel PDF renderer
built on `reportlab` (already pinned - no new dependency) that consumes
the exact same `(report, segments, source_hash, currency_unit)` inputs
as `render_rich_report`, so nothing is re-derived or re-parsed from the
HTML.

Two real choices, made up front rather than discovered mid-build:

- **Bundled real IBM Plex font files** (OFL-licensed, redistributable)
  rather than `reportlab`'s base-14 fonts. "Matching visual fidelity"
  was the task's own stated goal; a Helvetica/Times stand-in would not
  meet it. Six TTFs (Sans/Serif/Mono x Regular/SemiBold) live in
  `analystos/l4/fonts/`, registered at import time.
- **Charts are redrawn, not reused.** `reportlab` has no SVG renderer,
  so the existing inline-SVG chart strings (`analystos.l4.charts`)
  can't be reused directly. A parallel PDF-native drawer
  (`reportlab.graphics.shapes`) mirrors the same layout logic, but both
  renderers call the *same* `_detect_chart_type` (Slice 47) on the same
  resolved `(labels, values)` - so HTML and PDF can never disagree on
  what shape a chart is, only how it's drawn. The waterfall tie-out
  safety check (Slice 47) is reimplemented independently on the PDF
  path too, and proven independent the same way: forcing the detector
  to lie and confirming the chart still gets refused.
- **Pipeline integration is opt-in, not a contract change.**
  `build_report` gained `want_pdf=False`; every existing caller and
  test still gets a bare string back unchanged. Passing
  `want_pdf=True` runs the pipeline exactly once and returns
  `(text, pdf_bytes)` for every path (rich, plain-fallback, and the
  schema/template path alike). Considered instead making
  `build_report` always return a pair, or wiring PDF generation only
  into `main()`/`api/analyze.py` with pipeline logic duplicated there -
  both were more disruptive for no real benefit. `main()` now always
  passes `want_pdf=True`, so the CLI writes a real `section.pdf` next
  to `section.html` for the rich path too, closing a gap where only the
  flat path ever got one.

Pagination (`reportlab.platypus.KeepTogether` around every chart and
boxed block) is proven, not assumed: a test builds a report dense
enough to force a real page break near a chart and confirms via
`pdfplumber`'s own rect-per-page reading that the chart's bars are
wholly on one page, never split.

## 2026-09-11 — code, not the model, decides chart type (Slice 47, Task 2)

The writer model previously declared `chart.type` directly; `_chart_html`
now derives it itself from the resolved, verified `(labels, values)` and
ignores whatever the model put in that field. A start -> components ->
end bridge (the exact tie-out property the existing waterfall check
already required) is a waterfall; three or more period-labelled points
are a line; anything else is a bar.

This changed one existing test's expected behavior, on purpose:
`test_a_waterfall_that_does_not_tie_out_is_dropped` previously asserted
that breaking a declared waterfall's bridge made the whole chart vanish.
Under auto-detection, that data is simply never classified as a
waterfall in the first place - it renders as an honest bar comparison of
the same real numbers instead. No chart lost, and no misleading bridge
shown either - arguably safer than the old behavior, not a regression.
Added a new, separate test proving the existing tie-out check is still a
genuinely independent safety layer: mocked the detector to force
"waterfall" onto purpose-broken bridge data, confirmed the untouched
check still refused to render it.

Donut ("parts of a stated whole") is not auto-detected - deliberately
out of scope, not silently dropped. Nothing available to the detector (a
plain resolved value list, no associated "total") reliably distinguishes
that shape from an ordinary categorical comparison without a new signal;
falls back to bar, a safe default, until that signal is designed.

## 2026-09-11 — "remainder": organic-vs-inorganic as a real operation (Slice 47, Task 1)

The Meridian Data Services bridge (total growth, minus Halyard's stated
contribution, equals organic growth) was previously only ever produced
ad hoc through the model's own `"difference"` usage. Added `"remainder"`
as its own named operation - identical arithmetic to `"difference"`
(operands[0] minus the sum of the rest), but kept separate so this
specific "total change minus a named, disclosed component" pattern is
recognizable downstream rather than just another generic magnitude.
Verified the same way every operation is: independently recomputed from
already-checked operand values, dropped if the claimed result doesn't
match - proven directly, not asserted (a wrong claimed remainder, and an
operand not actually in the source, both correctly fail).

Given the same cautious treatment `"difference"` already has in the
direction-word gate: nothing verifies operand[0] genuinely is "the
total" rather than just the first number listed, so its sign is exactly
as unreliable, and a directional word next to a `remainder` fact is
refused the same way.

## 2026-09-11 — legal boilerplate exclusion, not a keyword blocklist (Slice 46)

A forward-looking-statements/safe-harbor disclaimer is dense with words
("forward-looking," "risk," "future") that also appear constantly in
ordinary, substantive business prose - a single-keyword filter would
either miss real disclaimers phrased slightly differently or wrongly
strip legitimate content that happens to use one of those words once.
Built `analystos/l1/boilerplate.py` around two structurally different
signals instead: a canonical section heading (this genre's heading
phrasing is a genuine, standardized legal-drafting convention, not
something that varies freely) OR a *density* of specific statutory
phrase patterns (citing the actual securities-law sections, the "actual
results...differ materially" formulation, "undertake no obligation to
update") - several must co-occur before content-only detection fires.
Verified directly: a document using "forward-looking" or "risk" once in
an ordinary sentence is left untouched; a real disclaimer, headed or not,
is fully removed.

Wired into `analystos.pipeline.build_report` between
`extract_document_text` and `analyze_document` - the narrated-default
path only. The old schema/template path never reads prose at all, so
there is nothing for this to act on there.

Also closed a proof gap in Slice 45 (GAAP/non-GAAP): that slice's own
tests used hand-typed prose fixtures, never a real table. Built
`tests/test_l1_l2_gaap_table_integration.py` - a genuine `.docx`
reconciliation table, run through the real unified extraction path
(spied to confirm `extract_docx._raw_rows` actually parsed it), proving
both figures verify against the real table text and are linked by a
verified reconciling gap, with a fabricated third figure correctly
failing verification. No production code changed for this part - Slice
45's mechanism was already correct; this proved it against the harder,
realistic case instead of only the fixture that was convenient to type.

## 2026-09-11 — detect and label GAAP vs. non-GAAP figures (Slice 45)

SEC Reg G requires a filer to label a non-GAAP figure as such wherever it
appears - a genuinely detectable signal already in the source text, not
something to infer from a number's size or direction. Added `gaap_status`
("gaap"/"non_gaap"/"n/a") alongside the existing `horizon` field on every
segment, verified the same way: trusted only when the source's own
wording states it, defaulting safely to "n/a" (not "gaap") on anything
missing or malformed - unlike `horizon`, where the safe default
("reported") is what most segments genuinely are, defaulting a malformed
gaap_status to "gaap" would risk silently presenting an unlabelled
adjusted figure as the audited one, exactly what this slice exists to
prevent.

Planned a new Gate 1 validator (a non-GAAP fact cited without its tag
gets rejected) before building it, then found it unnecessary during
implementation: the tag is attached by `rich_export.py`'s renderer
straight from the segment's `gaap_status`, the identical mechanism
`⟦guidance⟧`/`⟦projected⟧` already use - reusing `_TAG_RE`'s existing
generic rendering branch and the already-generic `.horizon-tag` CSS
class needed no new styling either. The model cannot omit the tag any
more than it can omit a guidance marker; a validator would have only
checked something already structurally guaranteed. Dropped the checker,
kept the guarantee - a stronger property than the originally-scoped
plan, found by building it rather than assumed going in.

## 2026-09-11 — one real table-parsing standard + real footnote detection (Slice 44)

Foundation work for GAAP/non-GAAP detection, which needs real typed table
structure and real footnoted adjustments to reason about - neither existed
on the narrated-default path before this. `document_text.py` maintained
its own separate, weaker table flattening (raw cell text joined directly)
instead of the real, type-aware `_raw_rows` every format module already
had for the schema-driven path. Unified: every `_text_from_*` function now
calls that same `_raw_rows` directly. Proved genuine, not just asserted -
stashed this slice's changes, reran the five unification tests, watched
all five fail (each for "the real parsing function was never called"),
restored the fix, watched them pass.

One real bug this fixes, not just a refactor: Excel stores a percentage-
formatted cell as its fraction (`0.571` for what displays as "57.1%").
The schema-driven path already rescaled this correctly; the old narrated-
path flattening showed the raw fraction verbatim - a person reading the
narrated text would see a number 100x too small. Fixed by construction,
not a special case, once both paths go through the same function.

Footnote detection: built real, structural marker-to-content linking for
`.docx` only. Word's OOXML format has a genuine structural relationship
(a footnote reference element with an `id`, linked to real content in a
separate `footnotes.xml` part) - the same kind of unambiguous link a
table's real cell/row structure has. Checked every other supported format
against the same bar before building anything, not after: PDF has no
reliable structural footnote concept through `pdfplumber` (or through most
real-world PDFs, which aren't tagged) - only a font-size/position
heuristic is possible, and that's guesswork, not structural detection, so
it's deliberately not built as part of this. PPTX has no footnote
mechanism at all. XLSX's closest analog (cell comments) is a different
relationship entirely (attached to a cell, not a marker in running body
text). CSV is flat data with no markup. `python-docx` itself exposes no
public API for footnotes, so the reader parses `word/document.xml` and
`word/footnotes.xml` directly - and the test fixture needed a real
footnote built by hand (`lxml`-level XML injection into a python-docx
document plus a hand-assembled `footnotes.xml`/relationship/content-type),
since neither a committed fixture nor `python-docx`'s API could produce
one.

## 2026-09-11 — evidence encryption at rest + a retention window (Slice 43)

`evidence/` has held plain, unencrypted copies of every uploaded source
since Slice 2, kept indefinitely. Both gaps closed together: `store` now
writes `Fernet(key).encrypt(...)` to disk instead of raw bytes, and
`purge_expired_evidence` deletes anything past a configurable retention
window. `hash_of` deliberately still hashes the *plaintext*, before
encryption - Fernet's fresh random nonce means the same source would file
under a different address every time otherwise, breaking the whole
"same bytes -> same name" point of a content-addressed store.

Added `cryptography` as a direct, pinned dependency
(`requirements.txt`) - it was already present transitively (via `anthropic`
and/or `flask`'s dependency tree), so this makes an existing implicit
dependency explicit rather than adding real new surface. `Fernet`
specifically: the standard, well-audited choice in this library for
"encrypt a blob with one symmetric key," no need to hand-roll AES modes or
authentication.

Key source: `ANALYSTOS_EVIDENCE_KEY` if set - a real per-deployment secret,
the same pattern as `ANALYSTOS_ACCESS_CODE` (Slice 22). If unset, a stable,
repo-known fallback derived from a fixed local constant, so the store is
never plaintext-by-default in a dev environment - but this fallback is
explicitly *not* a secret (anyone with this source can derive it) and must
never be relied on where real data matters. This differs from Slice 22's
access code, which fails *closed* (500) when unconfigured - encryption
fails *soft* to a known-weak default instead, because the alternative
(refusing to store anything without a real key configured) would silently
break every existing caller and test that has never needed to think about
this. Documented, not hidden - anyone auditing this file sees exactly
where the weaker default is.

Retention: `ANALYSTOS_EVIDENCE_RETENTION_DAYS` unset means no expiry
enforced - the same opt-in pattern Slices 41/42 already use for their own
ceilings, not a surprise auto-deletion policy. Deletion, not archiving, for
simplicity (the task's own framing allowed either). `store()` runs the
cleanup pass itself on every call (best-effort - never lets a cleanup
problem break the store it's riding along with), so retention is actually
enforced over time with no external cron job needed, while
`purge_expired_evidence` stays independently callable for a script or a
test.

Not migrated: any evidence already on disk from before this change, stored
under the old plaintext format. `evidence/` is git-ignored dev/test data at
this stage, and `retrieve()` (the only thing that would ever try to
decrypt an old file) isn't currently called anywhere in the live pipeline -
confirmed by inspection, not assumption - so this has no live-behavior
impact today.

## 2026-09-11 — an in-code spend hard-stop, second layer over the account cap (Slice 42)

The only spend safety net before this was external to the repo entirely: a
monthly cap set on the Anthropic account itself (see the 2026-09-05 entry
below). Real, but this repo's code can't see, configure, or test it.
Added a second layer inside `_create_message` - the one choke point every
Anthropic call in the codebase already goes through - checked *before*
dispatching a call, so a runaway loop hits an internal stop before (or
even without) ever touching the account-level cap.

Tracks **call count, not dollar cost**. Considered token-usage-based
tracking (the SDK response does carry `usage.input_tokens`/
`output_tokens`), but that means embedding a per-model price table in this
repo that goes silently stale the moment Anthropic's pricing changes -
exactly the kind of drift a safety net shouldn't have. Call count degrades
safely instead: worst case the ceiling trips a bit earlier or later than a
dollar-exact one would, never silently and never wrong-currency.

`ANALYSTOS_MAX_API_CALLS` unset means **no internal ceiling** - this is a
second layer on top of the account-level cap, not a replacement forced on
every deployment by default. Set it, and it's enforced with the same
clean `ValueError` a real `anthropic.APIError` already produces, so a
caller can't tell "hit the account cap" from "hit the internal one"
without reading server logs.

## 2026-09-11 — per-IP rate limiting on the access-code endpoints (Slice 41)

Slice 22 explicitly deferred this ("an accepted, disclosed tradeoff for
this stage, not an oversight"). Added as defense in depth, not a redesign
of auth: the shared-code, no-accounts model is unchanged. In-memory,
per-process fixed-window counter keyed by client IP
(`X-Forwarded-For`'s first hop, else `request.remote_addr`), checked
*before* the access-code comparison so a wrong-code guess still counts
against the budget - the actual point of rate-limiting this endpoint is
slowing down someone trying to brute-force the shared code, not just
capping legitimate traffic. Configurable via `ANALYSTOS_RATE_LIMIT_MAX`
(default 30) and `ANALYSTOS_RATE_LIMIT_WINDOW_SECONDS` (default 60); an
unset or unparseable value falls back to the default rather than raising -
a throttle must never be the reason the whole service goes down.

In-memory per-process, not a shared store (Redis, etc.): correct for a
single Vercel function instance, not guaranteed across many concurrent
instances under real distributed load. Accepted for this stage - the same
category of tradeoff Slice 22 already made for the access code itself
(good enough to keep this off casual abuse, not hardened against a
determined distributed attacker). A real shared-store limiter is future
work if the threat model changes.

## 2026-09-11 — repair the one flagged piece, not a full regenerate (Slice 40)

Live-tested Slice 39's fix twice more, back to back, and both runs still
fell back to the plain renderer with zero trace of why -
`analystos.pipeline`'s except clause swallowed the fallback reason
entirely. Fixed the logging gap first (now every Gate 1/Gate 2 fallback
reason prints to stderr), which is what made the rest of this diagnosable
live at all.

What the logs then showed, repeatedly: `write_narrative` throws away the
*entire* report on any rejection and asks the model to regenerate
everything from scratch. A report this size (exec summary + 3-5 sections +
KPIs + outlook) has enough sentences that a full reroll is a fresh chance
to break a *different* rule anywhere else in the document, even while
correctly fixing the one that was actually reported - watched happen live,
several times in a row, on the same test document. Replaced "reject and
reroll the whole document" with "repair just the one flagged paragraph in
place" for both gates: `write_narrative` now tries a scoped, small repair
call first (chasing a second problem the first repair's fix exposes,
within a bounded budget) before falling back to a full regenerate; Gate 2
(language quality) gets the same treatment instead of an instant,
unconditional fallback on any wording issue.

A repair is only ever kept if it still satisfies Gate 1's own paragraph
validator - a wording fix must never quietly reintroduce a correctness
violation. And a Gate 2 issue's flagged location is only patched if it
matches exactly one field in the report; an ambiguous match (a short,
generic quote that could be more than one sentence) is left alone rather
than risking a patch to the wrong one - safer to leave an issue unfixed
than to guess and rewrite something that wasn't actually broken.

Also closed three specific validator/prompt gaps the live diagnosis
surfaced along the way, each a real, separately-found live bug, not
speculative hardening: a missing rule (an "N consecutive quarters" claim
needs N+1 citations - now stated in the prompt itself, not just checked
after the fact); a false positive in the direction-word check (a
direction word separated from a "difference" fact by another placeholder
was wrongly flagged as describing that fact instead of the comparison it
actually modified); and a new check for a placeholder followed by a
spelled-out unit ("million," "percent") - always wrong, since a rendered
value already carries its own unit, and for a non-numeric fact (an event)
it was silently being used as though it had a value at all. The last of
these traced back one layer further, to L2's extraction prompt: an
event's `status`/`next_step` text can legitimately contain a real,
material figure (an acquisition's integration-cost peak and step-down)
that the model could see but had no `{{N}}` to cite - now asked to also
surface such a figure as its own separate citable fact.

## 2026-09-11 — growth_percent operand order made order-independent (Slice 39)

Live-tested Slice 38 immediately after merge: a report that should have
been rich fell all the way back to plain text. The log showed the real
cause - every `growth_percent` computed segment in that run failed
verification, e.g. `recomputed growth_percent = -8.63 does not match the
model's result 9.45`. Checked both orderings of the same two operands by
hand: `(498-455)/455 = 9.45` - the model's math was correct; it had just
listed the operands as `[current, prior]` instead of the `[prior,
current]` `_recompute` assumed. With no citable growth fact left, the
narrator wrote a raw, uncited dollar figure instead, which tripped the
existing digit check and took the whole report down to the flat fallback.

Root cause is Slice 38 itself: the new "use growth_percent for every
directional claim" prompt rule (replacing "difference," which has no
reliable sign) made the model attempt `growth_percent` far more often -
so an operand-order mixup that used to surface occasionally now hit on
every attempt in one run. Fixing the sign-word bug amplified a different,
pre-existing one.

**Fixed at the verification layer, not the prompt** - a prompt
clarification was added too, but a prompt instruction had already failed
4 times in this exact run and shouldn't be trusted alone.
`_verify_computed` now tries both operand orderings for `growth_percent`
and accepts whichever one matches the model's own claimed result. Both
operands are already independently verified real numbers at that point,
so this stays entirely inside the guarantee - it is still the real
percent change between the same two real numbers, computed the other
legitimate way, never a third or fabricated value. `difference` is left
order-sensitive (unchanged) since Slice 38 already bans a direction word
next to it regardless of sign.

## 2026-09-11 — Two mandatory quality gates: correctness and language, independent (Slice 38)

A real PDF from the live site (`Downloads/Test #5 to download pdf.pdf`)
had four distinct defects even though every number in it individually
traced to a real source: a net-income decline described as "rose... up
$2.8M"; an event's full composed timeline leaking verbatim into prose
6+ times, "next:" artifact and all; a footnote whose displayed operand
("$1.9B") didn't actually support its own displayed result ("$565.0M");
and a fragile, unchecked class of "N consecutive quarters" claims. All
four are root-caused and fixed in `analystos/l2/narrate.py` and
`analystos/l4/{export,rich_export}.py` - see the Slice 38 commit for the
full breakdown per bug.

**Gate 1 (correctness)** is enforced inside `write_narrative`'s existing
validation (`_validate_paragraph`), so a violation gets the same
retry-then-fallback treatment a stray digit already did - never a special
code path. **Gate 2 (language quality)** is a new, separate, independent
model call (`analystos/l2/proofread.py`) that sees only the assembled
prose - never segments, citations, or values - so it cannot be swayed by
whether the facts are right, and can never be quietly satisfied just
because Gate 1 already passed. Wired into `pipeline.py` to run after Gate
1, before rendering; either gate failing takes the identical fallback
path to the plain renderer.

This is a third model call per narrated report (real added latency and
cost, on top of `analyze_document` and `write_narrative`) - a deliberate
trade explicitly asked for over a general-purpose grammar library, which
is a poor fit for a Vercel serverless function (most need a JVM or a
native binary neither of which reliably run there).

Each of the four checks has a dedicated test reproducing the live defect
and confirming the fix catches it (not just "the code changed"). The
exact Meridian figures behind the broken PDF were also rebuilt as
verified segments and run through the real `write_narrative` +
`proofread_report` + `render_rich_report` end to end (mocked client) -
both gates pass, and the corrected output was converted to a real PDF
via headless Chrome for a direct before/after comparison. Whether a
*real* model reliably produces content this clean, and whether Gate 2
actually catches a real model's language slips, is the still-open,
unverifiable-without-the-API question - same caveat as every model-facing
change this session.

Also true but out of scope here, and deferred to a follow-up per the
request's own ordering: chart-type diversity and table formatting.

## 2026-09-09 — The output-token ceiling on a dense document (Slice 34)

Slice 33 fixed how verification matches; the realistic earnings release
still returned "no verifiable content survived" once deployed. The tell:
that request ran **1m38s** on Vercel - a single Sonnet call on an
8.5k-char document should take 20-40s. 98s is the signature of hitting
the output ceiling. `max_tokens` was 4096; a dense filing (four tables)
makes the model emit 20+ segments in the verbose all-required schema, it
overruns 4096, and the tool call is truncated mid-JSON - the segment
list comes back short or with a half-written last entry, and little or
nothing verifies. Meridian (5 paragraphs, ~7 segments) never came close.

- **`_MAX_TOKENS` 4096 -> 8192** in `analyze_document` and
  `write_narrative` (a rich report over a dense document can also
  outgrow 4096). Direct fix.
- **`stop_reason == "max_tokens"` is now logged** to stderr, and the
  "no verifiable content" log flags `(RESPONSE WAS TRUNCATED at
  max_tokens)` - the failure that had no fingerprint now has an obvious
  one.
- **Prompt caps output at 20 segments** and says not to transcribe
  tables - prefer a computed comparison or a prose point tying figures
  together. Keeps the response in budget and makes a better report.
- **Schema shape left alone.** Slimming the all-required per-segment
  schema (the reason each segment is verbose) risks re-triggering
  Slice 26's "400 Schema is too complex"; the token bump plus the cap
  solve it without that risk. Revisit only if 8192 + a 20-cap still
  truncates.

## 2026-09-09 — Verification that survives a real filing's tables and scale (Slice 33)

A realistic fictional earnings release, uploaded to the live site,
returned **"no verifiable content survived"** — every segment the model
returned was dropped. `analyze_document`'s checks were tuned to Meridian
(five prose paragraphs, every figure spelled out "$498.0 million"); a real
condensed income statement is a pipe-delimited table headed "In millions
of U.S. dollars", and against that the checks reject everything.

- **Byte-exact substring citation was the wrong bar.** A model reasons
  about a figure and re-expresses it — `1,842.0` in the table becomes
  `$1,842.0 million` / `$1,842` / `1842.0` — and an exact `in` check drops
  each. Fixed with `_match_key` (folds case, dashes, `$`, the `|` our L1
  rendering inserts, and thousands separators — never the digits) plus a
  trailing-scale-word fallback in `_really_in_document`. A model that
  prepends a row label to a *non-leading* cell still fails, on purpose:
  tying a label to a distant number by proximity risks accepting a
  *mislabelled* one, and a false "verified" is the one thing this must
  never do.
- **No notion of a table's declared scale.** `_detect_scale` reads "in
  millions" / "in thousands" once; `_value_matches_text` now accepts the
  model's `value` at face value *or* times the declared scale, and returns
  whichever matched (canonical value) — so a figure the model scaled to
  its real magnitude verifies and is stored/rendered correctly, and one
  left unscaled still verifies (no regression). Sign preserved, so the
  Slice 29 sign-flip guard holds. The user message also states the
  detected scale and that per-share amounts, percentages and share counts
  are not scaled.
- **The failure logged nothing about *why*** — the same "no clue why"
  hole Slice 27 closed for the narrative pass. `_verify_*` now return
  `(segment, None)` or `(None, reason)`; a total failure logs the first
  several reasons to stderr (Vercel logs), never the client response.
- Verified beyond the suite: the real L1 extraction of the document that
  failed live, fed a hand-authored model response mimicking real
  table-citation behaviour — 8 of 10 segments verified (was 0), dollar
  cells stored at real magnitude, per-share values untouched, a
  fabricated figure and wrong arithmetic dropped with logged reasons.
  Meridian and every prior fixture unaffected (a document declaring no
  unit has `doc_scale == 1` and the new checks collapse to the old ones).
- Not fixed here, its own slice: column-aware L1 extraction (keep a cell
  tied to its row label / column header) so a "RowLabel Cell" citation of
  any column verifies. This slice makes that citation fail *safely and
  visibly*, not silently.

## 2026-09-08 — Dated events as a verified, structured fact (Slice 32)

The system was rigorous with numbers and weak with events - an
acquisition or a regulatory step could be mentioned as a plain quote, but
nothing captured *when*, *where it stands*, and *what's next*, so the
report said "an acquisition closed during the quarter." This adds an
`event` segment type to `analyze_document` - the last piece of the
diagnosis's Mechanism 4.

- **`event` is a fourth segment type** (`quote` / `computed` / `event` /
  `prose`), carrying no numeric value. Its four parts - `what` / `date` /
  `status` / `next_step` - sit in a nested `event` object on the tool
  schema, every field required (Slice 26 all-required rule; nesting was
  never the problem, optionality was - Slice 30's nested chart schema
  already proves it).
- **The model copies, never composes.** `what` must be a verbatim
  substring and is required; `date` / `status` / `next_step` are each
  either `""` or a verbatim substring. `_verify_event` drops the whole
  event if `what` isn't real, or if any *supplied* part isn't - a
  half-verified timeline is worse than none.
- **The model never types an event's date into prose either.** The
  narrator references an event with `{{N}}` like any citable fact; L4's
  new `event_line` composes the verified parts into a timeline string
  (`what (date) — status — next: next_step`, omitting absent parts). Every
  digit on an event line is a verified substring. This extends the "model
  never writes a number" guarantee to "model never writes a date." Slice
  27's calendar carve-out still lets the model write "into 2027" as
  connective prose; the *event's own* dates come through the verified
  channel.
- **Slice 31's `horizon` marker applies** - a `projected` event (a
  planned/expected one) renders its line with the `(projected)` /
  `PROJECTED` marker unchanged. Charts are untouched: an event has no
  `value`, so `_resolve_chart` already excludes it.
- `coverage_summary` gains an `events` count.
- `rich_export.py` needed **no change** - `_substitute` already routes
  through `display_value`, which now knows `event`.
- 280 tests, mocked client only. Hand-authored end-to-end run: two events
  (one reported, one projected) verified, the reported one rendered as a
  full dated timeline, the projected one with `— next: …` and the Slice
  31 marker, `coverage_summary` reporting `events: 2`. Real-model
  behaviour is the still-owed live Vercel smoke test.
- **Not in this slice:** numeric reasoning about a deal (size, %
  accretion) stays a `quote`/`computed`; multi-event chronology ordering;
  and the long-standing carve-outs (mix-vs-rate bridge, share-of-total
  shift, peer benchmarks, a real `.pdf` of the rich layout).

## 2026-09-08 — Horizon made visible in the rendered report (Slice 31)

Slice 29 tags every fact `reported` / `guidance` / `projected`; Slice 30
surfaces that to the narrator and asks it to keep forward material in the
outlook. This slice makes it *enforced in the output*: a `guidance` or
`projected` figure is visibly marked wherever it appears - executive
summary, any section, the outlook - so it can't be read as a verified
historical result regardless of where the model put it.

- **Mark, don't police.** A hard "reject a guidance fact used outside the
  outlook" rule was rejected: the Slice 30 prompt legitimately allows a
  forward fact in a clearly-forward-marked part of a section, so a hard
  rule would cause needless fallbacks. Marking at the point of
  substitution is strictly safer - the fact is always flagged, the report
  is never lost, and there is no model call in the slice at all.
- **Two-pass, matching the existing pattern.** `rich_export._substitute`
  runs before `html.escape` (Slice 28's double-escape bug), so it emits a
  plain-text sentinel `⟦guidance⟧` / `⟦projected⟧` (U+27E6/27E7 - never in
  financial prose, pass through `html.escape` untouched) and `_para_html`
  converts it to `<span class="horizon-tag">` in the same escape-then-
  convert pass that already handles `[n]`.
- **The plain fallback marks it too.** `render_narrated_section` appends a
  literal ` (guidance)` / ` (projected)` - plain text, flows through
  `render_html` / `render_pdf` untouched. The degraded path must not
  mislead any more than the rich one.
- **`horizon` absent → no marker.** Purely additive; every pre-existing
  test segment (no `horizon` key) renders unchanged.
- Verified beyond the suite: the Slice 30 hand-authored end-to-end run,
  re-checked - `$15.0B` (guidance) and `$4.5B` (the implied-remaining
  `difference`, also guidance) carry the marker in both the executive
  summary and the outlook; the reported quarterly figures do not; the
  sentinel never leaks as literal text.
- **Dated-event structure is explicitly NOT here.** `date` / `what` /
  `status` / `next_step` as a quote-verified segment shape in
  `analyze.py`, so an acquisition or regulatory step can be narrated as a
  real timeline, is the other half of the diagnosis's Mechanism 4. It is
  a genuine `analyze.py` + `narrate.py` change and gets its own slice
  (proposed Slice 32) - not part of the pre-approved 29-31 run. Slice 30
  already broadened discipline 4 in the prompt; until 32, events are
  narrated from `quote` / `prose` segments.

## 2026-09-08 — Structured narrator, wired end to end (Slice 30)

Slice 28 built `analystos/l4/rich_export.py` (executive summary, sections,
per-section charts, a distinct outlook block) and wired it to nothing.
Slice 29 made `analyze_document` guarantee the comparison set and tag each
fact's `horizon`. This slice closes the loop: `write_narrative` returns
the structured report shape and `pipeline.build_report`'s default path
renders it through `render_rich_report`. From here, the default output of
AnalystOS is the rich report, for any document, verification contract
untouched.

- **`write_narrative` returns a `report` dict, not a `paragraphs` list** —
  `executive_summary`, `sections` (each with an optional `chart`),
  `outlook` — exactly what `render_rich_report` consumes. It validates,
  then normalizes (`has_chart` folded away, `chart` → `None` when false or
  invalid, empty `outlook` → `None`).
- **Schema stays all-required, zero optional properties** — the exact
  pattern that fixed Slice 26's `400 Schema is too complex`. "Not
  applicable" is the `has_chart` boolean plus placeholder values, never an
  absent key. Nesting (report → section → chart → series) is fine; it was
  *optional*-property combinatorics that broke the grammar compiler, and
  there are none.
- **A malformed chart is the one non-fatal case.** Every paragraph
  failure (bad `{{N}}`, stray digit) and every structural failure (empty
  summary/sections, a section with no heading or body) raises → the
  pipeline falls back to Slice 26's plain rendering, no partial
  acceptance. A bad chart is just dropped (`chart` → `None`), matching
  `rich_export._resolve_chart`'s existing "a bad chart is left out, the
  report is never lost" rule — that check stays as defence in depth,
  `write_narrative` now also runs it up front.
- **Prompt extends the five disciplines, doesn't replace them.**
  Discipline 4 broadened from "legal/regulatory content" to *any* dated or
  sequential event (a deal, a launch, a leadership change, a financing) —
  the user's ask was explicitly wider than the reference pieces that
  seeded the original wording. Discipline 5 got a worked example of
  co-stating trigger and consequence in one sentence. New structural
  instruction (exec summary / 3-5 sections / outlook), chart guidance
  (only 2+ cited facts, only when the shape carries information), and a
  `horizon` instruction (forward-looking facts belong in the outlook —
  Slice 31 *enforces* it). `coverage_summary` from Slice 29 is passed into
  the prompt so a genuinely thin document is described as thin rather than
  dressed up.
- **`build_report`'s default path now returns a full HTML document**,
  where the table/`template` path still returns section markdown.
  Contained by two small guards, no contract rewrite: `render_html` is
  idempotent on an already-complete document (so `api/analyze.py` needs no
  change — the live frontend only reads `data.html` anyway), and
  `pipeline.main()` writes `section.html` directly for an HTML section and
  skips the `.md`/`.pdf` writes for it. A real `.pdf` of the
  sectioned/charted layout (extending Slice 24's `reportlab` renderer) is
  its own follow-up.
- **`render_narrative_section`** (the flat narrative renderer) stays in
  `export.py` for its own tests but leaves the pipeline path — rich or the
  Slice 26 plain fallback, nothing in between.
- Tested against a mocked client only. A hand-authored structured response
  for the Slice 29 multi-period mock document, run through the real
  `write_narrative` + `render_rich_report`, produced the target shape:
  executive summary, sections, a line chart drawn only from cited
  quarterly facts, a distinct outlook, one shared 8-footnote sequence,
  guidance and implied-remaining figures rendered from verified `computed`
  segments. Whether a *real* model produces this well from a real
  document is the post-merge Vercel smoke test, flagged before any paid
  call.

## 2026-09-08 — L2 extraction contract: guarantee the comparisons, tag the horizon (Slice 29)

`analystos/l2/narrate.py`'s prompt already instructs all five
executive-writing disciplines (benchmark, name the mechanism, sequence
past from future, narrate events, co-state cause and effect). The gap the
`mock_rich_report_v3.html` diagnosis surfaced
(`docs/rich-report-diagnosis.md`) is upstream of the writing: the
narrator can only write from what `analyze_document` extracted, and that
stage returned "the important facts" with benchmarking left to the
model's per-run discretion. No prompt on the narrator conjures a
comparison that was never computed. This slice is `analyze.py` only.

- **`difference` is now a supported operation.** Subtraction was excluded
  through Slice 26 because a model could smuggle a sign flip (the
  `sum([1240, -1050])` "net additions" case). That hole was closed
  separately by `_value_matches_text`, which checks each operand's value
  against the number its own `exact_text` spells out, sign included. With
  that check in place `operands[0] - sum(rest)` is safe — and it is the
  operation an absolute period-over-period change, a margin move in
  points, and "stated target minus the actuals so far" all need, none of
  which the five prior operations could express. A dedicated test retries
  the old sign-flip exploit under `difference` and confirms it still
  fails.
- **Every segment carries a `horizon`:** `reported` (default),
  `guidance`, or `projected`, verified by the same substring + value-match
  checks as any quote. Nothing in L4 consumes it yet — Slice 31 wires the
  outlook block from it and enforces "no projected figure unmarked in a
  history section." Produced now so that wiring has something to read.
- **The prompt's "what to report" section is now a completeness
  contract:** for every figure featured, surface *every* comparison the
  source's own numbers support (prior value + `growth_percent` +
  `difference`; each period of a 3-plus-period trend as its own quote;
  `percent_of_total` of a stated total; target-vs-actuals where a target
  is stated). The honesty rule is unchanged and explicit: if the source
  doesn't contain a comparison, leave the figure without one — never
  invent one. The bar is on which *citable* comparisons must be computed
  when available, not on inventing them.
- **Return type stays `list[segment]`.** The spec floated returning a
  dict with a coverage summary; threading that through `pipeline.py` and
  ~20 tests was more churn than value for a signal that's derivable from
  the segments. Instead `coverage_summary(segments)` is a module helper —
  comparison count, reported-figure count, horizon breakdown — for the
  Slice 30 narrator to flag a thin document, and for tests. Verified
  segments also now carry `operation` (previously dropped after
  verification) so the helper, and later the narrator, can tell a
  comparison from an aggregate.
- **Schema stays all-required.** `horizon` is one more required enum on an
  object whose every property is already required — no optional-property
  combinatorics, so no repeat of the `400 Schema is too complex` failure
  (that was caused by *optional* properties).
- **Peer / sector / index benchmarks remain out of scope.** The system
  sees one document; the verification guarantee forbids a comparison it
  can't cite. A boundary, not a bug — revisit only if a second (peer)
  source is supplied.
- Tested against a mocked client only (no `ANTHROPIC_API_KEY` in the
  build env). Whether a *real* model produces the full comparison set
  from a real document, unprompted per run, is the post-merge Vercel
  smoke test in the agreed proof plan — flagged before any paid call.

## 2026-09-06 — Rich rendering: charts, real section structure, a distinct outlook block (Slice 28)

Slice 27 fixed how the words read; this fixes what the report looks
like. Explicit bar: a Fortune 10 executive should see something their
own strategy/IR team would produce - charts where data supports them, a
real executive-summary-first section structure, forward-looking
"outlook" content visually impossible to mistake for a verified fact.

**Scope drawn deliberately narrow, and stated up front:** this slice
builds the *rendering capability* - new `analystos/l4/charts.py` and
`analystos/l4/rich_export.py` - proven by hand-authoring the structured
input a future L2 stage would produce and running it through the real
render code, not by writing throwaway HTML. It does not build that L2
stage (a model actually deciding section structure/chart placement/
outlook content from a real document) - that's a new prompt, schema, and
tool-use design in its own right, and it needs its own live test before
it's trusted, same as every other model-facing change today. Drawing
this line let the rendering side get reviewed and merged on its own
strength, independent of a not-yet-built model-decision layer.

**Charting approach**: checked `requirements.txt` first, per the
instruction to use what's already available before reaching for
something new. Nothing exists yet. Chose plain inline SVG (zero new
dependency - a browser renders it natively with no JavaScript) over
`matplotlib`, which would add real weight to Vercel's serverless
functions for something a few hundred lines of string-built markup
already does. `reportlab` (already a dependency) has
`reportlab.graphics.charts` for a PDF equivalent - explicitly deferred,
not part of this round's ask (an HTML draft specifically).

**A chart data point inherits Slice 26's verification by construction,
not a new check.** A chart spec's `fact_index` can only point into
`segments`, which is already 100% verified by the time anything reaches
L4 - exactly how `{{N}}` already works in prose. `_resolve_chart` does
its own defensive bounds/type check (in range, quantitative, not
`prose`) because no L2 stage produces or validates chart specs yet - the
same structural check `_validate_paragraph` already does for text
placeholders, just not inherited from anywhere since this is new. A bad
point is dropped; a chart left with fewer than two points is dropped
entirely rather than rendered as something misleading.

**A real bug caught by the new test suite, not by review**: the first
draft inserted real `<sup><a>` HTML during placeholder substitution, then
ran the whole paragraph through `html.escape()` afterward - double-
escaping the markup into literal `&lt;sup&gt;` text. Fixed by matching
the existing codebase's own pattern (`export.py`'s `_para_html`): escape
first, then convert plain `[n]` markers into real HTML - two passes, not
one, so nothing inserted mid-pipeline gets re-escaped downstream.

Verified with a hand-authored mock (a clearly-labeled DRAFT/TEMPLATE
earnings report for a fictional company, not a real client's data), run
through the real `render_rich_report` - 4 embedded charts, a shared
footnote sequence across the executive summary/4 sections/outlook, cross-
section synthesis (margin compression and segment-mix shift connected
explicitly as one story, not two). Honestly scoped: this fictional
source has no legal/regulatory content and no market-reaction event
either, so two of Slice 27's five writing disciplines still aren't
exercised by any mock built so far - even a *real* earnings report
wouldn't naturally contain those, since a company's own report doesn't
cover its own stock's reaction to itself. Proving those two needs a
source that's actually news coverage, not a financial report.

## 2026-09-06 — Five mechanical writing disciplines, grounded in four real reference pieces

The prior prompt rewrite (Pyramid Principle/SCQA) fixed structure but was
still too abstract to mechanically prevent a flat fact-list - "say what's
notable" doesn't tell a model *how*. Given four real, fully-read reference
pieces (a McKesson equity-research note, a Zacks research digest, a
Courthouse News DOJ/Google appeal story, and CNBC's UnitedHealth DOJ
investigation coverage) and asked to extract the actual mechanical
patterns that separate them from a fact sheet - not another round of
stylistic guessing.

Five disciplines, each traced to a specific thing the reference pieces do
and now written into `_SYSTEM_PROMPT` in `analystos/l2/narrate.py`:

1. **Benchmark every number, stacking comparisons when the source
   supports more than one** - the McKesson piece never reports a return
   alone; it layers one-year vs. S&P 500, then YTD-only, then a
   sector ETF, because each comparison told a different part of the
   story.
2. **Name the specific mechanism behind any tension, never a category
   word** - McKesson names actual drivers (oncology, GLP-1 demand vs. a
   named primary-care mix shift), never "headwinds."
3. **Sequence past from future; never blend them in one sentence** - both
   financial pieces fully resolve current performance before turning to
   forward-looking material (ratings, targets, catalysts) as a distinct,
   later block.
4. **Legal/regulatory content narrated as a dated, unfolding process** -
   the Courthouse News piece names the specific remedy being appealed and
   gives a concrete filing date, never a generic "legal risk" label.
5. **State a triggering event and its reaction together** - the
   UnitedHealth coverage states the stock-drop magnitude and its specific
   cause in the same breath, and represents the company's own stated
   defense faithfully rather than asserting a verdict.

Explicitly scoped as conditional: not every document has legal or
market-reaction content, and the prompt says so - apply each discipline
only where the source actually supports it, never force one that
doesn't fit. The verification contract is untouched (same `{{N}}`
mechanism, same `_validate_paragraph`, same schema).

Rebuilt the mechanically-real mock (hand-written paragraphs through the
actual `_validate_paragraph`/`render_narrative_section` code) against the
new prompt, and was honest about its limits: the Solstice source has no
legal or market-reaction content, so disciplines 4 and 5 aren't
exercised by this mock at all - only a live test on a document that
actually contains that kind of material can confirm those two work.
Also deliberately did *not* invent a mechanism for a cost-growth figure
the source doesn't explain, rather than force discipline 2 where it
isn't supported - flagged in the mock's own text instead.

## 2026-09-06 — Rewrote the narrative prompt against real executive-writing patterns

Every live test so far (even before any of them succeeded end to end)
carried the same underlying flaw: `write_narrative`'s prompt asked for
"structure however best serves an executive reader" - vague enough that
one fact per paragraph, in extraction order with a bolded label, trivially
satisfies it. That's a fact sheet, not analysis, and it was never going to
change on its own no matter how many bug fixes landed. Explicit ask: fix
this *before* spending more on a live test, not after, since a working
bug fix paired with a still-flat writing style would waste the test on a
known-insufficient output shape.

Researched how real executive/analyst writing is actually structured
rather than defaulting to a generic "sound smart" instruction:

- The **Minto Pyramid Principle** (Barbara Minto, McKinsey) - lead with
  the single governing answer, then MECE-grouped support ordered by
  importance. "You think from the bottom up, but you present from the top
  down" - the standard taught at McKinsey/BCG/Bain.
- **SCQA** (Situation-Complication-Question-Answer), the same Minto
  framework applied to how an opening frames "why this matters" before
  the supporting detail.
- **Equity research practice**: "numbers by themselves do not usually
  convince anybody of anything" - reports connect figures to a story,
  usually built around two or three things that actually matter, with
  qualitative context explaining *why* a number is moving, not just that
  it is.

Rewrote `_SYSTEM_PROMPT` in `analystos/l2/narrate.py` around these:
open with a 2-3 sentence bottom-line takeaway; 3-5 substantive paragraphs
each built around one analytical point (not one number) with facts woven
in as evidence; explicitly call out tension/anomalies/comparisons rather
than flat restatement; a closing risk/outlook note. Explicit anti-pattern
named directly in the prompt: "never produce a paragraph that is just
'Label: sentence with one number in it,' repeated fact after fact."

The verification contract is completely unchanged - still `{{N}}`
placeholders only, still the same `_validate_paragraph` checks, still no
schema change (kept to the same single required `text` property, given
Slice 26's `400 Schema is too complex` history). This is purely a change
to what the model is asked to do with already-verified facts, never to
how those facts are checked.

Before spending on a live test, produced a mechanically-real mock (not
just typed-up prose): hand-wrote paragraphs in the new style using the
already-verified Solstice facts from Test #2/#3, ran them through the
actual `_validate_paragraph` and `render_narrative_section` code (not a
model call), and confirmed the shape renders correctly. Also surfaced a
real, expected side effect of the earlier verification-gap fix: a fake
"operating income" figure (previously only reachable via the negated-
operand exploit) is gone for good, since subtraction still isn't one of
the five supported operations - the mock instead uses a legitimate `sum`
of cost of revenue + opex (both real, correctly-signed quoted operands).

## 2026-09-06 — A follow-up commit landed after its PR had already merged

Test #3's continued fallback-shaped output looked like the value-matching
and calendar fixes below hadn't worked. They hadn't been *deployed at
all*: they were pushed as a second commit to the `slice-27-narrative-pass`
branch after PR #39 (which only covered the branch's first commit) had
already been merged - `git log`/`git branch --contains` confirmed the
merge commit only covers up through the "Add PR #39 reference" commit,
and the fix commit existed only on the now-orphaned branch, never on
`main`. Reported it as "pushed to PR #39" without re-checking the PR was
still open at that moment - it wasn't. The "190" exploit's absence in
Test #3 was the model choosing different phrasing that run, unrelated to
any fix actually running. Recovered by cherry-picking that commit's real
changes onto a fresh branch off current `main`, rather than assuming a
push reached wherever it was aimed - and by actually diffing the merge
commit against the fix commit to confirm, not just asking for another
retest and guessing again from the result.

## 2026-09-06 — write_narrative's remaining failure paths were unlogged

A precaution taken alongside the recovery above, before any of this had
actually reached a live test: the per-paragraph validation-rejection path
had logging (added earlier today), but `write_narrative`'s other two
failure points - the model's response having no `tool_use` block at all,
and the model returning an empty `paragraphs` list - did not. Either
could produce a silent fallback with zero log evidence, exactly like the
gap that motivated adding logging in the first place. Added logging to
both remaining raise points, plus a success line (`narrative accepted: N
paragraphs`) so a clean run is also visible, not just inferred from the
absence of a rejection - the next live check is conclusive either way.

## 2026-09-06 — Closed a real verification gap found on the first Slice 27 live test

The first live test of Slice 27 (two real Anthropic calls, both `200 OK`
per Vercel's logs) still rendered Slice 26's plain fallback, and the
output contained "Net customer additions were 190" - correct
arithmetically (1,240 − 1,050 = 190), but subtraction isn't one of the
five operations `_recompute` supports (`sum`/`average`/`ratio`/
`growth_percent`/`percent_of_total`). The only way to land on exactly 190
is `sum([1240, -1050])` - the model quoted the real substring `"1,050"`
but paired it with `value: -1050.0`. `_verify_computed` only checked that
`"1,050"` really appears in the document; it never checked that the
*number* paired with it (`-1050` vs `1050`) is what the text actually
says. Same root cause explained a `$7.6M` operating-income figure computed
via a three-way signed `sum` faking `revenue − cogs − opex`. Both landed
on the *true* number this time - the finding is that nothing stops the
same mechanism from landing on a false one, which is the entire premise
this project is built to prevent.

Fixed in `analystos/l2/analyze.py`: `_parse_number`/`_value_matches_text`
parse the actual number a piece of quoted text spells out (handling `$`,
commas, `%`, accounting-parens negatives, and `K`/`M`/`B`/`thousand`/
`million`/`billion` scale words, with a lookahead so "142 members" isn't
misread as 142 million) and reject a quote or computed operand whose
claimed `value` doesn't match. Applied to `_verify_quote`, every operand
in `_verify_computed`, and `percent_of_total`'s `total_value`. New tests
reproduce the exact live exploit (confirmed they fail without the fix,
pass with it) plus the abbreviated-figure and false-positive-word cases
the stricter parsing has to get right to avoid new false rejections.

## 2026-09-06 — Calendar references don't need a citation

Also found on that same live test, from the Vercel log's two `200 OK`
Anthropic calls: the narrative pass got a real, successful model response
and my own validation code rejected it anyway - `write_narrative` had no
logging on that path, only on an `anthropic.APIError`, so this was
invisible until reproduced manually. Root cause: `_verify_prose` (Slice
26) and `write_narrative`'s paragraph check (Slice 27) both ban any digit
outside a citation - but ordinary analyst writing constantly mentions a
quarter or year ("heading into Q4 2026"), so the ban was rejecting almost
any real connective prose, not just genuine unverified figures.

Added `_CALENDAR_RE` in `analyze.py` (quarters, halves, `FY`-prefixed
years, bare `19xx`/`20xx` years) and strip it before the digit check in
both `_verify_prose` and `narrate._validate_paragraph`, so a calendar
reference is allowed while an actual number still isn't - it was never a
claim that needed a source quote in the first place. Also added logging
to `write_narrative`'s own validation-rejection path (previously silent),
matching the logging `analyze_document` already had for API failures -
this exact gap is why the live failure had to be reproduced manually
instead of read straight from the logs.

## 2026-09-06 — Backend-first roadmap toward Fortune 10 exec-quality reports

Slice 26 proved the core loop works on a real live document, but its
output is a fact list, not writing - one paragraph per verified fact, in
extraction order, with no real structure. Discussed the end goal directly:
any document, any size, any format, a report worthy of a Fortune 10
executive, the user choosing the output shape (one-pager/slide deck/memo)
and giving feedback on a generated report to have it improve. Agreed
backend work comes before frontend polish, in this order:

1. Split verification from writing so writing quality can be pushed hard
   without ever reopening the door to a fabricated number (Slice 27,
   below).
2. Write down a concrete rubric for "Fortune 10 exec-worthy," not vibes.
3. Handle documents too large for one model call (chunk, verify per
   chunk, synthesize once over the combined verified facts).
4. Harden extraction for messier real-world files.
5. Add an output-shape selector on the backend (one-pager/memo/slide
   deck), API-first, before any UI exists to choose it.
6. Add the feedback/revision loop - re-run the writing pass with a
   person's critique, but always re-verify before showing anything.
7. Move off "one HTTP request does everything" once chunking/feedback
   both need multi-step state.
8. Build a real eval set graded against the rubric from step 2.
9. Iterate against that eval set - the same live-testing discipline as
   every slice so far, systematized instead of one document at a time.
10. Frontend controls for shape choice and feedback, last.

## 2026-09-06 — Split verification from writing (Slice 27)

Step 1 of the roadmap above. `analystos/l2/analyze.py`'s extraction and
verification logic is completely untouched by this slice - it's the
safety net every later step still depends on, so it stays frozen while
writing quality gets pushed on separately.

Added `analystos/l2/narrate.py`: a second, narrower model call
(`write_narrative`) that takes only the already-verified `segments` from
`analyze_document` - never the raw document - and returns an ordered list
of paragraphs. A paragraph is free prose that may reference a citable
fact via a `{{N}}` placeholder (`N` = that fact's index); it can group
several facts into one sentence, add a transition, or skip a fact
entirely - real structural choices Slice 26's one-paragraph-per-fact
rendering couldn't make. It cannot write a number itself: every
placeholder is substituted afterward, in `analystos/l4/export.py`'s new
`render_narrative_section`, with the exact value Slice 26 already
verified - a fact referenced twice reuses one footnote number, by first
appearance. A stray digit outside a placeholder, or a placeholder
pointing at an out-of-range index or a `prose` segment (nothing to cite),
rejects the whole narrative.

Two design choices worth recording:

- **Fail to the known-good path, not to an error.** `pipeline.build_report`
  tries `write_narrative` + `render_narrative_section`; any `ValueError`
  (bad model output, a validation failure, an `anthropic.APIError`) falls
  back to Slice 26's `render_narrated_section` unchanged. A worse-structured
  report is an acceptable cost of a quality experiment; losing the report
  entirely is not.
- **`{{N}}` parsed from the text itself, no separate `refs` field.** A
  redundant field that could disagree with the text it's describing is a
  bug waiting to happen; parsing keeps one source of truth. Also kept the
  tool schema to exactly one property (`paragraphs: [{text}]`, fully
  required) - deliberately, after Slice 26's schema already produced a
  real `400 Schema is too complex` once (see 2026-09-05).

Refactored `analyze_document`'s inline client-resolution and error-
handling into shared `_resolve_client`/`_create_message` helpers in
`analyze.py`, since there are now two real call sites (`analyze_document`
and `write_narrative`) that must not reimplement or drift from the same
missing-key check and `APIError`→clean-`ValueError` conversion. Also
renamed `analystos.l4.export._format_number` to `format_number` and
factored a new `display_value` helper there, both now genuinely shared
across L2 and L4 rather than L4-private.

Doubles the per-report Anthropic cost (a second real model call) - not
deployed or live-tested with a real API key yet; built and tested
entirely against mocked clients per the standing rule on real spend.

## 2026-09-05 — The narrated path always uses "actual" currency scale

Found on the first successful real report: every dollar figure came back
1000x too large ($18.4B instead of $18.4M for a real "$18,400,000" quoted
directly from the source memo) - all math was verified correct
independently (confirmed by hand: 29.6% growth, 59.8% share, 5.2%
non-renewal rate, $8.7M profit all check out), so this was a display bug,
not a verification bug. Cause: the upload page's "Currency scale" dropdown
was set to "Data is in thousands," and `build_report` passed that straight
through to the narrated path's renderer, multiplying an already-real
number by 1,000.

That control only ever made sense for the old table-driven path, where a
CSV/Excel table's own header can say "figures in thousands" - a real,
if old-fashioned, accounting convention. It has no meaning for the
narrated path: `analyze_document`'s quoted `value`s are always the literal
number as it's written in the source text, never something pre-scaled by
a stated convention. Fixed in `analystos/pipeline.py` by hardcoding
`"actual"` for `render_narrated_section` regardless of what's passed in -
the parameter is accepted but ignored on this path, matching how the
narrated default already ignores `schema`. Also moved the "Currency scale"
control in `site/upload.html` behind the same "this file is a table"
checkbox as the rest of the old-path-only UI, so it's not visible (and
can't be mis-set) for a narrated upload at all.

## 2026-09-05 — Every segment field is required, not just "type" (real live 400)

The first real, paid call to `write_report` - after `ANTHROPIC_API_KEY` was
finally working and the previous logging fix let the real error surface -
came back `400 Bad Request: "Schema is too complex."` from Anthropic
itself, not from any bug this codebase's own error handling could catch.
The original `_TOOL["input_schema"]` required only `"type"` on each
segment, leaving twelve properties genuinely optional (`display`, `label`,
`value`, `operands`, `total_exact_text`, ...). Strict-mode tool use
compiles the schema into a grammar, and a schema with that many optional
properties on one object forces the compiler to represent every possible
combination of which ones are present - exactly the kind of blowup real
users have hit and reported upstream (this is a known, if under-documented,
strict/structured-output limitation, not unique to this schema).

No mocked test could have caught this - every test in
`tests/test_l2_analyze.py` patches `client.messages.create` directly, so
the real schema is never sent to Anthropic's real validator. This is the
first defect only a genuine, paid API call could surface.

Fixed by making every property required and replacing "is this key present"
with explicit `has_value`/`has_total` booleans - a segment that doesn't use
a field still supplies a placeholder (`""`, `0`, `[]`, `"none"`) and the
flag says whether to look at it. This removes the combinatorial optionality
entirely (every segment object now has exactly one shape) at the cost of a
longer system prompt and a few more required keys. `_verify_quote` and
`_verify_computed` in `analystos/l2/analyze.py` now branch on the explicit
flags instead of key absence; existing tests updated to set them. Added
dedicated positive/negative tests for `has_total` specifically, since that
branch (`percent_of_total`) had no direct test coverage before.

## 2026-09-05 — Log the real Anthropic failure server-side, not just a generic message

Found immediately after the previous fix went live: the client-facing
message ("analysis is temporarily unavailable") is deliberately generic -
it has to be, since `anthropic.APIError`'s own text can carry account/
request detail that shouldn't reach a client response. But that means a
bad key, missing billing, a rate limit, a wrong model name, and a real
Anthropic-side outage are now genuinely indistinguishable from the outside
- including to me, debugging this from outside Vercel's dashboard. Nothing
printed the real exception anywhere, so a handled `ValueError` left no
trace at all in the function logs.

Fixed by printing the real `anthropic.APIError` (`repr(exc)` - the SDK's
own error text, which does include the useful part like an HTTP status
code) to stderr before converting it, right where it's caught in
`analystos/l2/analyze.py`. Server logs only, never the response body -
that boundary is unchanged. Vercel's function logs are the actual next
diagnostic step for the real live-test failure this follows.

## 2026-09-05 — A missing API key must fail clean too, not just a bad call

Found via a real live test: the first Anthropic error-handling fix only
caught `anthropic.APIError` around `client.messages.create(...)`, on the
assumption that any auth problem would come back from Anthropic's server as
an API-shaped error (`AuthenticationError`, a subclass of `APIError`). A
completely missing or empty `ANTHROPIC_API_KEY` doesn't reach the server at
all - the SDK can't build an authenticated request and raises a plain
`TypeError` ("Could not resolve authentication method") from inside that
same call, which the `except anthropic.APIError` clause never sees. That
crashed as a raw, unhandled Flask 500 instead of the intended clean 400.

Fixed in `analystos/l2/analyze.py` by checking the constructed client's
`api_key` *before* the call, only on the production path (`client=None`,
where a real `anthropic.Anthropic()` is built) - tests that patch in a
bare stand-in client have no `api_key` attribute at all, so
`getattr(client, "api_key", "present")` leaves them alone and this doesn't
change any existing test's behavior. Confirmed the exact `TypeError`
reproduces with the fix reverted and the new test in place, and that it's
gone with the fix applied.

## 2026-09-05 — Upload page: narrated analysis is now the default, not just the API's

Found while preparing a real live test: `site/upload.html` had a hardcoded
`<input type="hidden" name="template" value="income_statement">`, sent on
every submit regardless of the schema field's contents. `api/analyze.py`
already treats an omitted `template` as the new Slice 26 narrated-analysis
default, but the live page could never actually omit it - every upload,
table-shaped or not, was silently forced through the old column-by-column
path. A non-tabular document (a memo, a slide deck) would fail there since
there's no table to extract, which is exactly the case the new default
exists to handle.

Fixed by removing the hardcoded field. The page now defaults to the
narrated path (no `template`, no `schema` sent) and only sends
`template=income_statement` when a new "this file is a table shaped like an
income statement" checkbox is explicitly checked - which is also the only
case that shows the Detect columns/schema UI at all. `tests/test_upload_page.py`
updated to match: it no longer asserts a static `name="template"` attribute
exists (there isn't one any more) and instead asserts the checkbox and the
JS that conditionally sets `template` are both present.

## 2026-09-05 — Anthropic API failures fail clean, not with a raw 500

Follow-up to Slice 26, prompted by setting up the real `ANTHROPIC_API_KEY`
and a monthly spend cap: `analyze_document` only wrapped verification
failures in `ValueError`, which is what `api/analyze.py` converts to a
clean `400`. A failure in the API call itself - a hit spend limit, a bad or
revoked key, a rate limit, an Anthropic-side outage - raises some
`anthropic.APIError` subclass instead, which would have passed through
uncaught and surfaced as a raw, unhandled `500`. Fixed by catching
`anthropic.APIError` (the common base for every SDK-raised failure - status
errors and connection errors alike) around the one API call and re-raising
as a `ValueError` with a generic message ("analysis is temporarily
unavailable") - never the raw exception, which can carry account or request
detail that shouldn't reach a client response. Means hitting your own spend
cap now fails the same clean way every other pipeline error already does,
instead of looking like the site is broken.

## 2026-09-05 — Narrated analysis: read any document, verify every number (Slice 26)

Prompted directly by a live gap: the only template (`income_statement`)
requires a period-like column, so a file that's genuinely tabular but isn't
shaped like an income statement (a company/revenue/employee list, say)
failed cleanly rather than producing a report. Working through what "no
restrictions" should actually mean landed on a real architecture change,
not an addition - `docs/architecture.md`'s L2 was already described as
"retrieval + analysis... every claim points back into L0"; what shipped
through Slice 25 was a deliberately thin first slice of that, not its
ceiling.

**What changed, and why, in the order the design actually evolved during
building:**

- **Not forced into a table.** `analystos/l1/document_text.py` reads a
  document's real text content - paragraphs, bullet points, table cells
  rendered as readable text - the same way for all five supported formats.
  A memo or a slide deck with no table at all now reads the same as a
  spreadsheet; nothing requires row/column structure to exist.
- **A model reads the whole thing and decides what matters; it never
  supplies a number.** `analystos/l2/analyze.py` sends the real document
  text to Claude and gets back a structured list of segments (via strict
  tool use, not free text) - each a quote, a computed value, or plain
  connective prose. A quote gives `exact_text` the model claims is verbatim
  in the source; this code checks that with an actual substring match
  against the real text - not "the model says so." A computed value (a
  sum, a ratio, a growth rate, a share of total) gives its own raw operands
  the same way, *plus* the operation and the model's claimed result - and
  this code *independently recomputes* that arithmetic and checks it
  matches. This second check is the reason a citation alone isn't enough:
  it proves a quote is real, but says nothing about whether math performed
  on top of it is correct - a real gap surfaced explicitly while designing
  this, not caught by accident. Prose is scanned for stray digits and
  rejected if any appear - no number ever reaches the report without going
  through one of the two checks above. A segment that fails verification is
  dropped, not shown, not retried; a report where *nothing* survives is a
  real `ValueError`, never a silent partial success.
- **A number renders as a number when that's the point.** Each segment
  carries its own `"display"`: `"stat"` for a standalone labeled figure,
  `"inline"` for a sentence with context. The model chooses per figure,
  not a global setting.
- **Model: Claude Sonnet 5, not Opus 5** - overriding Anthropic's own
  default-to-Opus guidance for one disclosed, concrete reason:
  `api/analyze.py` runs as a Vercel function with a real 10-second
  wall-clock ceiling. Opus 5's always-on extended thinking makes that a
  real timeout risk for a bounded, structured-output task like this one;
  Sonnet 5 reliably finishes well inside it. A one-line change to revisit
  if the Vercel plan changes or quality disappoints.
- **A new required secret, `ANTHROPIC_API_KEY`, on Vercel** - separate from
  anything used to build this code - and a new, real, small, ongoing
  per-report dollar cost that didn't exist before this slice.
- **This is the new default, not a replacement.** `build_report` now runs
  this path when *neither* `asks` nor `template` is given at all - the
  original schema/table-driven path (explicit `asks`, or
  `template="income_statement"`) is completely unchanged and still costs
  nothing extra to run; this only fires when nothing else was specified,
  which is the new default for the live API/site.
- **Disclosed, accepted residual risk:** a text value from the source
  (e.g. a company name) still reaches the model as data it can quote or
  reason about, with an explicit system-prompt instruction that all such
  values are data, never instructions - a standard, imperfect mitigation.
  Verification catches every fabricated *number*; it cannot catch
  manipulated *wording* smuggled in through a text field the model quotes
  or paraphrases around.
- **Tested entirely against a mocked Anthropic client** - this session had
  no `ANTHROPIC_API_KEY` and no way to reach the real API, so the test
  suite verifies the logic (a fabricated quote is rejected, fabricated math
  is rejected even with real cited numbers, prose with a stray digit is
  rejected) deterministically, with no cost and no network dependency. Real
  output quality - whether Claude actually produces good, well-chosen
  analysis in practice - can only be confirmed once a real key is set and
  a real request is made.

## 2026-09-05 — Real production bug: /api/extract 404'd on Vercel

Confirmed live, right after `ANALYSTOS_ACCESS_CODE` was finally set on the
Vercel project (the one open item from Slice 22): `/api/extract` (Slice 25)
returned Vercel's own 404 page ("The page could not be found"), never
reaching our code at all - while every local test for it passed.

Root cause: exactly the file-based routing model researched and recorded
here for Slice 20 - one `.py` file in `api/` maps to one route matching
*its own path* (`api/analyze.py` -> `/api/analyze`), regardless of what
routes a file's Flask app defines internally. `/api/extract` was added to
the same shared app inside `api/analyze.py` instead of its own file, so
Vercel had no file to map that path to. Flask's test client bypasses this
entirely - it calls the app object directly - so nothing in the test suite
could have caught it; this was exactly the "only confirmable once deployed"
residual risk Slice 20's own entry already flagged, now realized for real.

Fix: `api/extract.py`, a one-line file that just re-exports the same shared
`app` object from `api/analyze.py`. Gives Vercel a matching file for
`/api/extract` while keeping exactly one implementation of every route -
two file-based doors into the identical app, not a second app or duplicated
logic. A regression test (`tests/test_api_vercel_routing.py`) checks both
files resolve to the identical app object with both routes registered, so
this can't silently regress if a third route gets added the same way.

## 2026-09-04 — Universal upload: auto-detected schema, PDF's constraint
generalized instead of special-cased (Slice 25)

Prompted directly by feedback that an analyst shouldn't have to know which
of 4 extensions were accepted or hand-type an exact JSON schema before the
system would touch their file - and that's correct once a table is
extracted, format has never mattered to L0/L2/L4. Two real changes:

- **Schema auto-detection, not elimination.** `analystos.l1.schema.guess_schema`
  guesses `"number"` vs `"text"` per column using the exact same
  `_clean_number_token` cleaning `apply_schema` already applies when typing
  a value - so a guessed schema and a hand-typed one behave identically once
  resolved. An explicit schema is still honored exactly as before; nothing
  is guessed when one is given. `analystos/scaffold.py`'s own CSV-only
  guessing heuristic (duplicated since Slice 9) was replaced by this shared
  one - a real behavior improvement in passing, since scaffold's own
  `float(value)` check missed `$`/comma/`%`/paren-formatted numbers that
  the shared cleaner already handled correctly.
- **PDF's real constraint (a table inferred from layout, not read from a
  real object, so it can be misread) doesn't go away - it becomes universal
  instead of PDF-only.** Every format now gets a preview step
  (`POST /api/extract`) before a report is generated, not just PDF; PDF's
  preview additionally carries a warning. This is what actually let PDF
  join `api/analyze.py`/`site/upload.html` for the first time - the
  "PDF needs its own review-step UI" gap Slices 20/21/23 all flagged is
  closed by this same mechanism, since every format already needed one.
  The confirm-before-cite gate itself (Slice 23) is unchanged in behavior;
  it's satisfied via a `pdf_confirmed` form field once the browser has
  shown the preview, the same way Slice 23's CLI job.json flag always did.

Found and fixed a real bug while building this: `guess_schema` originally
scanned its `numbered_raw_rows` argument once per header, silently starving
every header after the first when called with a one-shot generator
(`scaffold.py` passed `enumerate(rows, ...)` directly) - only the first
column ever got real data, everything else guessed "text". Fixed by
materializing the argument inside `guess_schema` itself, so no caller has
to know it's scanned more than once; a regression test
(`test_a_one_shot_iterator_still_works_for_every_header`) locks this in.

## 2026-09-04 — PDF output: reportlab put to its actual use (Slice 24)

`reportlab`, pinned since Slice 23 for test fixtures only, is now used for
its actual intended purpose: `analystos.l4.export.render_pdf` builds a real
generated `.pdf` from a rendered section - a title, one paragraph per
finding, a rule, then footnotes - mirroring `render_html`'s layout via a
shared `_parse_section` helper so there is exactly one place that parses a
section string, not two. Verified directly before finalizing this design:
built a real `reportlab` document with a superscript marker and a bold
footnote number, then read the exact expected text back out with
`pdfplumber` - title, body sentence, and footnote citation all present.

Scoped to L4/CLI only, matching Slice 23's own discipline: `api/analyze.py`
and `site/upload.html` are untouched. A real PDF *download* on the live
site is a genuine, separate product decision (a new API response shape, a
UI affordance) worth its own scoped slice, not a rider on this one - until
then the live MVP's only path to a PDF is still the browser's own Print.
`[n]` footnote markers render as plain superscripts in the PDF, not
clickable links like the HTML version's same-page anchors - a PDF has no
equivalent low-effort mechanism, a disclosed gap, not an oversight.

## 2026-09-04 — PDF input: pdfplumber, and pulling reportlab forward (Slice 23)

`pdfplumber==0.11.10` for table extraction — verified directly before
writing the extractor, not just read about: a real bordered table built with
`reportlab` and read back with `pdfplumber.page.extract_tables()` came back
as exactly the right rows. Installs with no system dependencies — its own
deps (`pdfminer.six`, `Pillow`, `pypdfium2`) all ship self-contained wheels,
no Poppler/Ghostscript/Java needed - the same Vercel-serverless-friendly
reasoning already used to pick `reportlab` over `weasyprint` for output.
Rejected `camelot` (needs Ghostscript) and `tabula-py` (needs Java) for that
same reason.

Also added `reportlab==5.0.1` now, a slice early — but for tests only. Every
other format extractor's tests build their own fixture file at test time
with that format's own writer library (`openpyxl` for `.xlsx`, etc.); a real
PDF table `pdfplumber` can reliably detect needs actual ruling lines, so
*something* has to write a real PDF for `tests/test_l1_extract_pdf.py`.
Using the PDF-writing library already decided on for Slice 24 beat inventing
a second, throwaway one just for tests. Slice 24 is still the slice that
wires `reportlab` into `analystos/l4/export.py` for real report output.

Because a PDF table is inferred from visual layout, not a real structured
object, `analystos.pipeline.build_report` refuses to build a report from a
`.pdf` source until the job explicitly says `"pdf_confirmed": true` - a
non-interactive flag, not a terminal prompt, since the CLI's execution model
has no `input()` anywhere and shouldn't gain one just for this. The error
raised without that flag includes the actual extracted table, so the
"confirm" step is real: whoever runs it sees exactly what needs reviewing
before they can flip the flag and re-run. Correcting a misread value isn't
supported yet - accept-as-extracted-or-don't-use-it - and `.pdf` stays
unsupported by `api/analyze.py`/`site/upload.html`, since a stateless HTTP
request has no natural place for this kind of human-in-the-loop gate without
a real review UI (already named in `ROADMAP.md` as the reason PDF was pushed
after the MVP).

## 2026-09-04 — Access gating: one shared code, not accounts (Slice 22)

`api/analyze.py` and `site/upload.html` went live in Slices 20-21 with no
access control at all, deliberately deferred to this slice. The gate: a
single shared secret, read from the `ANALYSTOS_ACCESS_CODE` environment
variable and required as an `X-Access-Code` header on every request,
compared with `hmac.compare_digest` and **fail-closed** (a `500`, not open
access) if the variable is ever unset.

- Real per-analyst accounts are out of scope here on purpose - this is a
  small, hands-on preview with a handful of real analysts (`ROADMAP.md`'s
  NOW milestone), not a public product. Accounts are R1/R2 work, once there's
  an actual cohort to manage identity for.
- No rate limiting on the code itself - accepted, disclosed tradeoff. The
  point is keeping this off search engines and drive-by visitors, not
  standing up to a targeted attacker who's decided to guess it.
- One manual step this repo's code can't do for itself: `ANALYSTOS_ACCESS_CODE`
  has to actually be set on the live Vercel project (dashboard -> Settings ->
  Environment Variables) before the deployed endpoint is gated for real -
  same category of "only confirmable post-deploy" residual risk Slices 20-21
  already flagged.

## 2026-09-04 — How Python actually deploys on Vercel (researched before Slice 20)

Checked Vercel's own docs rather than guessing, since the Root Directory
picker earlier already showed guessing wrong costs a real deploy cycle.
Findings, current as of this date:

- Vercel supports file-based Python functions in an `/api` directory:
  each `.py` file there becomes its own route (`api/analyze.py` ->
  `/api/analyze`). The file must define a top-level `app` (WSGI/ASGI) or
  `application` (WSGI) object, or a `handler` class extending
  `BaseHTTPRequestHandler`. Flask's `app` object satisfies this directly.
- **Caveat found in the same docs**: if Vercel detects a Python "framework
  preset" for the project (from a matching dependency in `requirements.txt`),
  the framework takes over *all* routing, and `/api/*.py` stops being
  treated as file-based functions. Our project was already configured as a
  static site (Output Directory override to `site/`, from the earlier
  Root Directory workaround) before `flask` was ever added to
  `requirements.txt` - the working assumption is that an already-configured
  project keeps its existing routing rather than being silently
  reclassified, since Vercel's own docs describe the file-based `/api` model
  specifically as being for "existing projects." **This is not confirmed by
  an actual deploy** - only verifiable once it's live.
- Added `vercel.json` with an explicit `functions` config for `api/*.py`
  (the exact pattern shown in Vercel's docs) rather than relying purely on
  auto-detection, to make the intent unambiguous.
- Chose the file-based `app.py`-style entrypoint (Flask, WSGI) specifically
  because it means requests are parsed through Flask's own `request.files`
  API - the same code path whether running via `flask run` locally or
  wrapped by Vercel's Python runtime - rather than hand-parsing multipart
  form data against a raw `BaseHTTPRequestHandler`, which would be Vercel
  runtime-specific and much easier to get subtly wrong.

## 2026-09-04 — Known risk: nothing verifies a "format" matches the data's real scale

Found while demoing Slice 17: an ask can declare `"format": "usd_millions"`
on a column whose values are actually raw dollars (or vice versa), and
nothing catches it. The result isn't an error - it's a confidently wrong
number (a $150,000 loss rendered as "($150.0B)"). This is exactly the
failure mode the whole hardening effort is meant to prevent, and it isn't
fixed yet. Candidate for the report-template slice (renumbered to 19 - moved
earlier when PDF was pushed after the MVP): a template that generates the
asks could also know - or sanity-check - the expected scale, rather than
leaving it to whoever writes `job.json` to get right by hand.

**Update, same day, demoing Slice 18:** hit the identical mistake again -
`usd_millions` on raw-dollar PowerPoint figures produced "$4,200.0B" instead
of "$4.2M", no error either time. Two for two. This is not a one-off typo
risk, it is a genuinely easy mistake, which raises the priority of fixing it
in Slice 19 rather than just documenting it.

## 2026-09-04 — First third-party dependencies: a live MVP, multi-format input

Ending the stdlib-only period from Slice 1. Reason: a live, browser-based MVP
("upload a document, get a report") needs things the standard library
genuinely doesn't do well — reading Excel/Word/PowerPoint/PDF files, and
running a web server.

- **Hosting: Python + Vercel**, not a separate always-on server (Render/Fly).
  Keeps everything on one host the studio already uses. Consequence: Vercel's
  Python functions are WSGI, so the web layer will be **Flask**, not FastAPI.
  Free-tier functions time out at 10s — fine for CSV/Excel/Word/PowerPoint
  (sub-second), a real constraint once PDF extraction is in the request path;
  revisit hosting then if it becomes an issue.
- **Input formats, in order: Excel → Word → PowerPoint → PDF.** The first
  three are structured data (a cell/table object, not an inferred layout) —
  same reliability guarantee as CSV, no review step needed. **PDF is
  different**: table extraction infers column boundaries from a page's visual
  layout and can be wrong. Because the product's entire premise is "every
  number is defensible," a PDF-extracted table is never cited directly — it's
  shown to a person to confirm or correct first. Scanned/image PDFs (which
  need OCR) are explicitly out of scope: OCR is slow and would blow the
  10-second Vercel limit, and it's a different, heavier problem.
- **Output: a real generated `.pdf`**, not "open the HTML and print." Chosen
  library: **`reportlab`**, not `weasyprint` — weasyprint needs system
  graphics libraries (Cairo/Pango) that don't reliably install on Vercel's
  serverless functions; reportlab is pure Python with no system dependencies,
  so it won't work locally and silently fail in production.
- Each dependency is added in the slice that needs it, pinned exactly in
  `requirements.txt`, with the reason recorded here - not all at once.

## 2026-09-03 — Build in Python

Chosen over TypeScript / Node for the first slices.

- Python 3.14 and pip are already installed on the build machine; no setup cost.
- The hard parts of AnalystOS — document extraction (L1) and reasoning (L2) —
  have their strongest libraries in Python.
- Trade-off accepted: the FlashyOS mesh CLIs (`@flashyos/aao`, `@flashyos/agent`)
  are npm packages, so Node will be added later as its own slice when the
  manifest work (Slice 7) needs it.

## 2026-09-03 — Standard library only, for now

No third-party packages and no virtual environment until a slice explicitly
needs one (expected at Slice 4, document parsing). Keeps the skeleton trivial
to run and to review.

## 2026-10-13 — Slice 91: the homepage's machine links are absolute

The homepage is also proxied at `https://www.30eventures.com/analystos/`. Its root-relative `rel="api-catalog"`
and `llms.txt` links resolved to the studio's own site there: the catalog was a 404 and `/llms.txt` was the
studio's file, not AnalystOS's. Both are now `https://analystos.dev/...`. Chosen over publishing a
`/.well-known/api-catalog` on the studio domain, which would claim AnalystOS's catalog as the studio's.
Effect only after deploy; the proxy serves the page from analystos.dev, so no change is needed on the studio side.

## 2026-11-17 — Slice 92: a size cap before the paid call, no upload text in the audit log, a logged verifier fault

Three gaps the overnight hardening run found and left. (1) `analyze_document` refuses over 600,000 characters
before resolving the client or calling the model: the API would refuse such a request after a paid call, and the
empty-result retry would resend it. 600,000 is an estimate (about 150k tokens at 4 characters a token), not a
measured limit of any one model; the refusal names the count and the limit, never text. (2) A job that fails on the
document no longer writes `str(exc)` to the audit log, because an extractor error can quote a cell and the log has
no expiry; the line carries a fixed sentence and the exception class. The job record and response keep the message
(the caller's own upload; purged with the job). `title` is capped at 200 characters (the length the model already
sees) and refused with 400 above it, rather than silently truncated. (3) `verify_bundle`'s catch-all still fails
closed and returns the same verdict, but writes one stderr line naming the exception class (never the message).
Not done, still the owner's call: the unscaled-table-number rule, audit-line duplicate-key and `NaN` handling, and
new conformance-corpus cases for a sealed `inf`/`nan`.

## 2026-11-18 — Slice 93: audit lines are strict JSON; corpus cases for non-finite numbers

Closes the two gaps Slice 87 recorded as `known_gap` (above) and that you told the overnight run to leave until a deliberate
slice. `verify_entries` now parses with `audit_chain.strict_loads`, which refuses a duplicate key at any depth (even two
equal values: Python keeps the last, another parser the first or fails), the literals `NaN`, `Infinity` and `-Infinity`,
and a float that overflows to infinity (`1e999`, which is valid JSON text but reads as a different number in a double).
The writer changed in the same slice, as the 2026-10-07 entry required: `FileStore.append_audit` checks the event with
`allow_nan=False` and, if it holds a non-finite number, writes an `audit_event_refused` line (original type, fixed reason)
and a stderr line instead, so the chain keeps growing and a log cannot fail its own verifier. Chosen over raising, which
would have turned a bad counter into a 500 on a request. `FileStore.read_audit` and `last_chained` still read leniently on
purpose: a damaged log can still be appended to, and the verifier is the gate. Dedicated tests are in
`tests/test_slice_93_strict_audit.py`.

Corpus (`conformance/seal-1.json`, 143 to 152 cases): both annotations removed; five new audit cases and four new
seal-content cases (sealed `inf`, `nan`, `-inf`, and a finite value citing a 400-digit number). Measured: on the code from
before this slice the seven audit cases (the two old ones and five new) disagree. The seal-content cases pass on today's
code and are regression pins, and a mutation run showed how much they pin: with the citation parser's finite check and
`seal_verify._num`'s removed, only the sealed-`inf` / 400-digit case disagrees; with either removed alone, none does (the two
guards back each other up), and the `nan` and `-inf` cases never disagree under those mutations because other logic
refuses them. The file changes what a strict runner of this corpus sees; it was not sent to anyone.

## 2026-11-21 — Slice 94: the handshake declares the charter's role names

Resolves an open question from Slice 59 (`docs/mesh-identity.md`), using the Flashy
estate's own 21 Nov 2026 reply to the owner's integration plan as the authority rather
than guessing: their `auditProperty` grades a handshake with no `capabilities` at
level 1 ("declares nothing it can do"), and their reply distinguishes a role name
(restates the charter, claims nothing callable) from a discovery slug (claims an
endpoint). `tools/build_flashyos_handshake.py` now derives `flashyos.json`'s
`capabilities` from the charter's role names only, wired into `tools/refresh.py`.

Checked against the real packages, not a local guess at their rules: added
`tools/flashyos-check/` (a pinned `@flashyos/aao@0.4.2` + `@flashyos/conformance@0.2.3`
install, gitignored `node_modules/`, like the Python venv). `tests/test_build_flashyos_handshake.py`
runs `validateCharterDocument` (zero errors) and `auditProperty` (`{ok: true, issues: [],
level: 2}`) against the served files, and separately proves that removing `capabilities`
drops the real validator's verdict back to level 1 - the exact finding Flashy's reply
described, reproduced here rather than taken on their word. Those two tests skip
themselves with a clear instruction when `node_modules` is absent (CI without the npm
step, or no network at setup time); they do not fail the suite silently.

The discovery slugs (`document-analysis`, `figure-verification`, `sealed-report`) are
still not declared - that claim needs a deployed endpoint and a minted token, per
`docs/mesh-identity.md`'s existing rule, which this slice does not touch.

Not done, not attempted here, both the owner's or Flashy's call: declaring capabilities
and offers on the *live* FlashyOS org (needs the re-minted join-grant token, Flashy's
side as of 2026-11-21); switching the live charter from three roles to the seven-role
team draft (`site/.well-known/flashyos-charter.team.json`, also validated level 2, not
served - see `ROADMAP.md`); domain verification (explicitly Flashy's, not started).

## 2026-11-21 — Slice 95: a draft seven-role team charter, kept out of site/

Drafted `drafts/flashyos-charter.team.json` (coordination, research, analysis,
verification, synthesis, evidence, client-delivery) from Flashy's 18/21 Nov
integration documents and validated it for real against `@flashyos/aao@0.4.2` and
`@flashyos/conformance@0.2.3`: zero validator errors, all five static conformance
checks pass, and `auditProperty` returns level 2 with zero issues when every role
name and discovery slug is declared.

Put it in `drafts/`, not `site/.well-known/`, on purpose: a file under `site/` is
served the moment a deploy ships it, whether or not anything links to it, so an
ordinary merge-and-deploy could not accidentally publish a charter nobody decided to
publish. `tests/test_seven_role_charter.py::DraftLocationTest` holds that boundary.

Not switched live, and not something a loop should decide on its own: a served
charter is a public governance claim, and declaring four new roles with no agent
behind them and four discovery slugs with no endpoint behind them would be exactly
the gamed metric `docs/mesh-identity.md` exists to refuse. `drafts/README.md` records
what switching would actually need. Recorded as an owner decision in `ROADMAP.md`.

## 2026-11-21 — Slice 96: measures/1, an envelope around the existing audit.measures()

Flashy's 21 Nov reply committed to *pull* a measures document from AnalystOS rather
than have it push one, and named neither the path nor the format. First draft of
this slice duplicated the arithmetic as a new `analystos/api_v1/measures.py` before
noticing `analystos.api_v1.audit.measures()` (Slice 61) already computes exactly
these three numbers from the audit log - `tier == "written"` for the `analysis`
role, `dropped`/`proposed` for `verification`, `seal_ok` for `evidence` - and is
already called by `python3 -m analystos.api_v1 measures`, already tested
(`tests/test_api_v1.py::MeasuresTest`). The duplicate file was deleted; what this
slice actually adds is the envelope that function never had: a stated window
(never derived from the clock at read time), the charter's own measure sentence
copied in rather than retyped a second time, and a path. `tools/build_measures.py`
calls `audit.measures()` directly - see its module docstring.

`tests/test_measures.py` tests only what is new (the envelope, the CLI, honest
handling of a role `audit.measures()` does not know about) and a belt-and-braces
check that the envelope's numbers agree with that function called directly on the
same log; the arithmetic itself keeps its existing coverage in `test_api_v1.py`
rather than being re-tested under a different name. `tools/build_measures.py --check`
replays the same window and store and compares the result, rather than diffing
against a moving "now" (which could never pass twice by construction).

In `drafts/`, not `site/.well-known/`, for the same reason as the Slice 95 charter
draft: Flashy has not confirmed a path or format, so this is a proposal. Unlike the
charter draft, nothing here could assert something false if served as-is today - a
live production run would correctly show every value as `null`, because Slice 84
recorded the audit log as dormant until a persistent volume exists. Publishing it is
still left as a decision, not because the content is risky, but because the path
itself is not yet agreed with Flashy.

## 2026-11-21 — Slice 97: a playbook for document-analysis, acceptance as a check

The Engageable Workforce document's two remaining asks for the purchase layer -
a `playbook/1` per sellable engagement, and acceptance criteria written as a test -
both exist now, built on code this repo already has.

`@flashyos/playbook@0.2.0` turned out to be richer than the integration documents'
description suggested: a closed, 13-key catalogue of inter-organisation
collaboration *types* (data-pilot, joint-research, integration, ...), each with
roles, steps, dependencies (`after`) and one of four evidence kinds (`url`,
`sealed`, `endpoint`, `attested`), plus `checkClaim`/`verifyEvidence` functions a
caller supplies real verifiers to. A hand-authored document outside that catalogue
still validates (`isPlaybook`/`validate` do not require a known key), so
`drafts/playbook-document-analysis.json` maps AnalystOS's one real offer onto the
real shape: `coordination` accepts scope, `research` gathers sources (closing on
the client's attestation, never a published URL - the same reasoning the built-in
`data-pilot` playbook states for its own step), `analysis` and `verification` both
close against the real, unauthenticated `POST /api/v1/verify` endpoint (one checks
it answers at all, the other checks its body actually says `content_checked`),
`evidence` closes on `sealed` evidence (a future shipped/1 entry; honestly
`unverified` today, since Track C does not exist yet - checked for real with
`verifyEvidence` and no verifier supplied, not merely asserted), and
`client-delivery` closes on the real signed-link URL shape.

`analystos/l4/acceptance.py::document_analysis_acceptance` is the acceptance check:
built entirely on `verify_bundle`, requires the source text (treats its absence as
a failure - a client holds its own document and should supply it, and accepting a
check that was never run would be the exact gamed metric this is meant to prevent),
and never raises on a hostile bundle. Its `CRITERIA` constant is the same text used
in the playbook's `seal-the-report` step brief, so the two documents cannot
silently disagree about what "accepted" means.

Both the playbook and the acceptance check are proven against this repo's own
running Flask app and real seal verifier (`tests/test_playbook.py`), not only
validated as shapes - including a negative case (self-attestation refused) proving
the real validator's checks are not vacuous.

## 2026-11-21 — Slice 98: a defined/1 fragment for AnalystOS's own terms

Drafted `drafts/defined-analystos.json` for the three terms the 18 Nov integration
document found AnalystOS can own outright - analyst agent, decision-grade output,
deliverable acceptance criteria - none used anywhere in the estate's term map or
AUTHORITY register. `deliverable-acceptance-criteria` links `decision-grade-output`
via `seeAlso` rather than restating it, matching the estate's own one-owner-per-term
rule even though nothing here enforces it.

`@flashyos/defined` is not on the npm registry (404, checked 2026-11-21) and has no
publicly readable source, unlike every other format checked in `tools/flashyos-check/`.
`tools/defined_proxy_validator.py` checks the *documented* rules instead - says so
plainly in its own module docstring, so nobody mistakes a pass here for the real
checker's verdict. Every rule (definition length, expiry-not-derived, https basis,
the fourteen forbidden entry keys, the seven forbidden citation keys) is proven to
actually fire against a constructed violation in `tests/test_defined_fragment.py`,
not only asserted against the one real fragment.

Known gap, checked for rather than assumed away: the fragment's `basis` URLs point
at `/defined/<slug>` pages that do not exist in `site/` yet - exactly the mistake
the 18 Nov document named (mlgblockchain's six dead `/defined/<slug>` links) as "the
mistake not to repeat". `tests/test_defined_fragment.py` fails if a page under that
path is ever added without updating the test, so the gap cannot be silently closed
by accident. `ROADMAP.md` records it as open: write the three basis pages, or decide
to publish with 404 links and say why, before serving this fragment anywhere.

## 2026-11-21 — trademark check on "decision-grade" (no new slice; a finding)

Checked before anything using this term is published, per the 18 Nov integration
document's own instruction. Web search found two things worth more than "no
trademark found": USPTO serial 87896620 is a live application (status suspended,
not dead or abandoned) filed 2018 for the standard-character mark DECISION-GRADE
in Class 042 (analytics services - AnalystOS's own category); its owner is not
confirmed from public search snippets, and this session has no USPTO TESS/TSDR
access to confirm further. Separately, Beroe Inc. uses "Decision Grade Intelligence"
as core, heavy branding (homepage headline, product copy, a 2026 article title) in
procurement analytics - an adjacent category, not AnalystOS's own.

Recorded as an owner decision in `ROADMAP.md`, not acted on unilaterally: nothing
using "decision-grade" is served anywhere (`drafts/defined-analystos.json` is the
only place it appears, and it is in `drafts/`, unserved). Get real trademark advice
before publishing it or using it anywhere public, including in a pitch or a page.

## 2026-11-21 — Slice 99: shipped/1 and devlog/1, adopted for real

Of every record plane drafted this session, this is the one Flashy's own 21 Nov
reply said is real and already large (25,014 leaves, 23 sources) and pays off at
N=1 - it needs no counterparty. Unlike the charter, measures, playbook and defined
drafts, "adopt it now" is itself correct, because the tool's first-run default is
`visibility: "private"`: adopting publishes nothing.

Deepened the checkout (it had been cloned shallow at depth 1) to get real git
history, then ran the actual `@flashyos/shiplog@0.2.0` CLI: `flashy-shiplog adopt`
(writing `.shiplog/config.json` and `vendor-shiplog.mjs`, `--no-workflow` so it
does not add a CI job on its own authority) and `node vendor-shiplog.mjs emit`
(producing `shiplog.fragment.json`, `devlog.fragment.json`, and the served public
projection at `drafts/devlog.fragment.json`, kept in `drafts/` per every other
draft's rule rather than `site/`). `flashy-shiplog check` reports every seal
recomputed, and is shown to actually refuse a tampered copy in
`tests/test_shiplog.py`, not merely asserted to.

The tool correctly auto-detected a real `prBase` from this repository's GitHub
remote, avoiding the opaque-ref silent failure the 18 Nov document warned about.

Privacy note: the real run reported two unmapped commit-author emails, one of them
the repository owner's personal address. Neither is written into any committed
file - both already fall back to the safe `defaultAuthor` node id, which is the
correct behaviour and needed no change; adding an explicit mapping would only have
meant typing a personal email into a tracked file for no behavioural gain, so this
was deliberately not done. `tests/test_shiplog.py` proves no email appears in any
entry's `by` field or in `.shiplog/config.json`.

Not done, the owner's call: flipping `visibility` to `"public"`, and handing the
served URL to Flashy's fan-in (one commit on their side once there is a real URL -
there is not yet, since nothing here is deployed). Recorded in `ROADMAP.md`.

## 2026-11-21 — Slice 100: AnalystOS's own MCP server, with fenced untrusted text

Flashy's 21 Nov reply answered this directly: build your own server rather than
route through `@flashyos/mcp`, which was still 0.6.0 (the F-01 fence unpublished)
when checked, and importing a third party's unfixed injection surface into a
document-analysis product's own tools would be the wrong trade regardless.

`mcp-server/server.mjs` runs on the real, published `@modelcontextprotocol/sdk@1.32.2`
and exposes two tools, `verify_report` and `check_acceptance`, both thin wrappers
over `mcp-server/analystos_bridge.py`, which calls the real, already-tested
`verify_bundle` and `document_analysis_acceptance` - no verification logic is
duplicated in JavaScript, continuing the rule this session already learned the hard
way in Slice 96.

`mcp-server/untrusted.mjs::fence()` mirrors Flashy's own F-01 fix rather than
inventing a different approach: any caller-supplied free text is wrapped in
delimiters keyed to a fresh random nonce per call, so a forged closing marker
inside the untrusted text cannot close the fence early. `mcp-server/test.mjs`
proves this for real, over actual stdio with the official SDK's `Client` and
`StdioServerTransport` (not a mock): a genuine prompt-injection string asking the
server to report `ok: true` regardless of the real result is sent as
`counterparty_note`, shown to change nothing about the structured verdict, and
shown to still be returned verbatim inside its fence - a human or a model reading
the response can see exactly what was said without executing it. `tests/test_mcp_server.py`
wires the real Node suite into `python3 -m unittest discover`.

## 2026-11-21 — Slice 101: a findings-register schema, without real finding content

Both the owner's 18 Nov plan and Flashy's 21 Nov reply agreed on one discipline:
30E Ventures publishes each finding at a stable URL with a discovery date before
Flashy's fix cites it, so a stranger can check the order held. Built the
machinery - `findings/schema.json`, `findings/validate.py` (hand-rolled, this
repo's own convention for a schema this small - see Slice 76/77), `findings/build_findings.py`
- without inventing the 24 real findings' content, which lives in the owner's
local `flashy-audit` material and was not reachable from this session. A
plausible-sounding security finding that was never actually verified would be
worse than publishing nothing.

`registry.json` holds exactly one entry, `F-00`, explicitly `status: "template"`.
`tests/test_findings.py::RegistryContentTest` fails the moment any entry's status
is not `"template"` - a deliberate tripwire so a real finding cannot be added
without the person doing it reading `findings/README.md`'s publishing section
first.

Caught in review before committing: the generator's first draft ran every field
through `html.escape()`, which is correct for HTML output and wrong for the
Markdown this actually produces - it left literal `&lt;` in rendered pages
instead of `<`. Fixed, and a regression test (`test_a_page_never_html_escapes_markdown_content`)
pins it so it cannot silently return; table cells still neutralise a bare `|` or
newline, since those really would break a markdown table row.

Output lands in `findings/pages/`, not `site/`, for the same structural reason as
every other draft this session built. Not added to `tools/refresh.py`'s automatic
chain, which assumes every step lives directly under `tools/` - changing that
assumption for one still-template-only directory was judged not worth the risk;
run `python3 findings/build_findings.py --check` by hand.

## 2026-11-21 — Slice 102: prepared live-API scripts, never executed

Three ROADMAP items need a credential this session does not have and are
outward actions regardless: declaring capabilities and offers, rotating the
never-expiring agent token, auditable decision records. Prepared what can
honestly be prepared without presenting a guess at an unconfirmed API surface
as fact.

`ops/flashy_declare.py` builds the exact, confirmed request from Flashy's 21
Nov reply for the capabilities endpoint, prints it, and stops - `--execute`
is required to actually send it, and even then there is no real token to send.
The token is never printed; `build_request()` only ever carries a redacted
placeholder. The `offers` variant is clearly labelled as this script's own
guess at the path (Flashy named the scope, never the endpoint), with the
warning printed before the request is even built.

Token rotation and decision records got a written runbook (`ops/README.md`),
deliberately not a script: neither document gave a confirmed endpoint for
either, and a confidently wrong request looks identical to a correct one until
it runs. The runbook says exactly what to find out first, including the real
open question of whether "decision records" is AnalystOS's own API's job
(the existing audit log in `analystos/api_v1/store` being the natural place).

Testing discipline carried over from every other slice this session: no test
makes a real call to `api.flashyos.com`. `tests/test_flashy_declare.py` proves
`--execute` reaches the network-touching function with that function mocked,
in-process (`unittest.mock.patch`), never a live request.
