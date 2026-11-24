# Slice 126 - role-written work products (phase 2), framework

## Goal

The owner: "loop through phase 2 for every single role". 40 of the 73 roles list
a native output the analysis formats do not cover: draft (15 roles), register
(11), case file (10), reconciliation (6), plan (3) and code (2). This slice
builds the framework once; later slices loop family by family (tracker:
`specs/slice-126/LOOP.md`). The other 33 roles list only report, memo, brief,
workbook or deck, which phase 1 already delivers.

## Work products (content field `work`, a list)

Each item has a `kind` and only that kind's fields:

- **draft**: title, for (audience or channel), body (1-8 paragraphs). Copy,
  emails, job posts, policy text, outreach.
- **register**: title, rows of {item, rating low/medium/high, owner, status
  open/in progress/closed, action}.
- **case_file**: subject, facts, evidence, open_questions, for_decision. The case
  file ends in a question for a person; it never decides.
- **reconciliation**: title, side_a and side_b {label, figure_id}, items
  {label, figure_id, effect add_to_a/subtract_from_a/add_to_b/subtract_from_b},
  entries {debit, credit, figure_id, memo}.
- **plan**: title, steps {when, task, owner, done_when}.
- **code**: language, purpose, code.

## Rules (the same verifier, extended)

1. Every prose field is checked like the rest of the content: numbers only as
   figure tags; names, owners, accounts and titles carry no digits.
2. A reconciliation balances on the verified figures: side A adjusted by its
   items equals side B adjusted by its items; journal entries are amounts that
   are figures, presented as proposals for approval.
3. A case file's for_decision is a question; no work product decides what the
   role's boundary leaves to a person.
4. Code is a draft: shown in a fixed-width block labelled "not run or
   reviewed"; numbers inside code are not figures and are not checked.
5. A role must deliver at least one item of each kind its catalog deliverables
   name; nothing else is required of it. A renderer refuses a spec whose work
   kinds are not the role's.
6. Work renders inside the role's format: a memo section, workbook sheets (a
   reconciliation's adjusted balances as live formulas over the Inputs cells),
   deck slides.

## Done when (framework)

1. For each of the 40 roles, a test builds valid work of its kinds on a worked
   example, verifies it, and renders it in the role's format with no number of
   its own; missing a required kind is refused.
2. Each rule above has a refusal test (unbalanced reconciliation, a decided case
   file, digits in prose, a kind the role does not do).
3. Full suite OK; refresh check clean; Flashy fence holds; no paid call.
