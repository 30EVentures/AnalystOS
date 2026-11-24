# Slice 129 - every role has a worked example and a sample of its own

## Goal

The owner, seeing five accounting roles show the bookkeeper's sample: "do both, give
every role its own sample". Slice 128 made a borrowed sample obvious; this slice
removes the borrowing. 50 roles had no example of their own; each now has one in
`fixtures/work/<role id>/`: a synthetic client and a model-shaped response, written
in session with no model call, typical of that role's job and different from the
other roles in its family. 28 of them owe no work product (analysis only); the other
22 carry exactly their role's work kinds.

## Done when

- [x] Every one of the 73 roles has exactly one worked example: the 13 family
      examples plus 60 in `fixtures/work/` (test: `test_every_role_has_a_worked_example_of_its_own`).
- [x] Each example verifies on the first attempt, renders in its role's format,
      shows every work title, and leaves no number that is not a figure.
- [x] Reconciliations (payroll, fund accountant, banking operations) balance
      through the workbook's live formulas, checked independently.
- [x] Drafts are for approval or review and never read as sent; case files ask.
- [x] Roles that owe no work carry no `work` key and get no work page.
- [x] Every catalog role's eval is "mock" with its own example as the set (73 of 73).
- [x] The homepage explorer shows 73 different client problems; no borrowed banner.
- [x] The no-stray-numbers test no longer breaks on a blank line in a code draft.
- [x] Full suite OK, `refresh.py --check`, `build_samples.py --check`, Flashy fence holds.

## Not in this slice

- No live model output for these roles; that is a paid run, owner's yes first.
