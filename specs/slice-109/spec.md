# Slice 109 - engagement intake: a problem in, a scoped engagement out

## Goal

First piece of L3 (the workspace layer, never built until now). A person or an
agent states a business problem and names the catalog roles they want; this
slice turns that into an **engagement record** (`analystos-engagement/1`) that
asks the right scoping questions, records the answers, and decides - by reading
the role catalog - whether the engagement may be accepted.

No model is called in this slice. Choosing roles from the problem text (a model
proposes, code checks against the catalog) is Slice 110; doing the work is
later. Keeping this slice deterministic means every rule below is testable
offline.

## The record

- `id` (32 lowercase hex), `created` (UTC ISO-8601, supplied by the caller: no
  clock inside the module), `requested_by` (`{"kind": "person" | "agent",
  "ref": "..."}` - an agent is a first-class caller, not an afterthought).
- `problem`: the client's own words, at most 8,000 characters.
- `roles`: 1 to 7 distinct role ids, each present in the catalog.
- `questions`: the scoping questions, **snapshotted at creation** so a later
  change to the templates never rewrites an existing engagement. Five common
  questions (the decision to be made, the deadline, the audience, the material
  available, what is out of scope) plus each requested role family's own.
- `answers`: question id to text, at most 4,000 characters each.
- `state`: `scoping` until every required question is answered, then `scoped`;
  `accepted` only through the acceptance gate.

## Client text is data

`problem` and every answer come from outside - possibly from another agent.
They are stored as data and never treated as instructions. On the way in, text
is NFC-normalised and stripped of control and invisible format characters
(zero-width, bidirectional overrides), keeping ordinary newlines and tabs; text
over its cap is **refused, not truncated** (silently dropping part of a
client's problem would change what was asked). When a later slice puts this
text into a model prompt, it goes through the existing delimiting in
`analystos/l2/prompt_safety.py`.

## The acceptance gate - the first code that reads the catalog's ladder

`accept(engagement, catalog)` refuses, with a reason per problem, unless the
engagement is `scoped` and every requested role is `available` in the catalog.
Today all 73 roles are `planned`, so every engagement is refused at the gate,
by design: AnalystOS cannot take on work no role has been evaluated for. This
is what turns Slice 108's ladder from a file into an enforced rule.

## Done when

1. `analystos/l3/scoping.json` holds the five common questions and at least
   one question for every catalog family; its validator refuses a missing
   family, a duplicate or malformed question id, or an empty question.
2. `new_engagement()` builds a valid record and refuses (ValueError naming the
   field) an unknown, duplicate or missing role, more than 7 roles, an empty or
   over-long problem, a bad id, timestamp or `requested_by`.
3. `answer()` returns a new record (the input is never mutated), refuses an
   unknown question, an over-long or empty answer, and any change once
   accepted; the state moves to `scoped` exactly when the last required
   question is answered. `open_questions()` lists what is still unanswered, in
   order, so an agent can work through them.
4. `accept()` refuses unless `scoped` and every role is `available`; it accepts
   when they are (proved against a test catalog with an available role).
5. `validate_engagement()` never raises on any JSON value and catches a record
   whose state disagrees with its answers, an answer to a question it never
   asked, or a role the catalog does not list.
6. `python3 -m analystos.l3 new` builds an engagement from the command line
   (problem on stdin) and prints it as JSON, with its open questions.
7. The full suite is `OK`, `tools/refresh.py --check` is clean and
   `tools/flashy_freeze.py --check` holds.

## Not in this slice

- Any model call, routing from the problem text (Slice 110), or doing the work.
- Storing engagements or serving them (`/api/v2` comes with the front door).
- Budgets and engagement hours (Phase 5).
