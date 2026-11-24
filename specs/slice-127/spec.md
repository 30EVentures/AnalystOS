# Slice 127 - realistic worked examples for every work kind (phase 2 loop)

## Goal

The owner: "loop through phase 2 for every single role". Slice 126 built the
work-product framework and tested all 40 roles with synthetic work. Its tracker
(`specs/slice-126/LOOP.md`) listed 11 (family, kind) pairs still without a
realistic worked example. This slice writes them: one synthetic client and one
model-shaped response per role, in `fixtures/work/<role id>/`, written in the
session with no model call.

## The examples (10 roles, 11 pairs)

| Role | Family | Kinds | Format |
|---|---|---|---|
| Accounts payable / receivable clerk | accounting | draft, reconciliation | workbook |
| Trade support / middle office analyst | accounting | case file, reconciliation | workbook |
| Operational risk analyst | risk, audit and controls | register | memo |
| Cybersecurity analyst (junior) | risk, audit and controls | case file | memo |
| Compliance (AML / KYC) analyst | financial crime | case file, register | memo |
| Paralegal / contracts administrator | legal, contracts, procurement | draft, register | memo |
| IT help desk specialist | software and IT | case file, draft | deck |
| Project / program coordinator | sales and coordination | plan | deck |
| Risk advisory associate | consulting | register | deck |
| Regulatory change analyst | research and reporting | register | memo |

Each role's catalog entry now names its own example (`eval.method` "mock",
`eval.set` the example's folder), so 23 roles have their own example and 50
are checked on their family's.

## Done when

- [x] Every example is for a role that owes work and carries exactly its kinds.
- [x] Every example verifies on the first attempt through the real pipeline
      (ReplayClient), renders in its role's own format, shows every work title,
      and leaves no number that is not a figure.
- [x] Both new reconciliations balance through the workbook's live formulas,
      evaluated independently.
- [x] Approval-gated drafts say they are for approval and never read as sent;
      every case file ends in a question for a qualified person.
- [x] Coverage: every one of the 20 (family, kind) pairs the catalog owes has a
      realistic example (`tests/test_work_examples.py`).
- [x] Catalog, API and site counts updated by their tests and generators.
- [x] Full suite OK, `refresh.py --check`, `build_samples.py --check`, Flashy
      fence holds. No paid call.

## Not in this slice

- The homepage role explorer still shows one sample per family; per-role
  samples are a separate change.
- No work product has come from the live model yet; that needs a paid run with
  the owner's yes and exact cost.
