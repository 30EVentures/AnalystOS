# Phase 2 loop tracker (role-written work products)

Framework: Slice 126 (2026-11-23) - all six kinds, checks, prompt, rendering in
memo, workbook and deck; every one of the 40 roles tested with work of its kinds
(tests/test_work.py). Then one family per step: realistic worked examples for
each kind the family's roles deliver. Update this file as each step finishes.

Realistic worked examples (fixtures/roles/<family>/response.json "work"):

| Family | Roles needing work | Kinds in the family | Realistic examples | Still to write |
|---|---|---|---|---|
| accounting-operations | 6 | reconciliation, draft, case_file | reconciliation (bookkeeper); draft and reconciliation (AP/AR clerk); case_file and reconciliation (trade support) | - |
| risk-audit-controls | 6 | register, case_file | register (operational risk); case_file (cybersecurity) | - |
| financial-crime | 5 | case_file, register | case_file (fraud); register and case_file (AML / KYC) | - |
| content-communications | 5 | draft | two drafts (copywriter) | - |
| legal-contracts-procurement | 4 | draft, register | register (contract analyst); draft and register (paralegal) | - |
| people-hr | 3 | draft, plan | plan and draft (L&D) | - |
| software-it | 3 | code, draft, case_file | code (junior developer); case_file and draft (help desk) | - |
| sales-customer-coordination | 3 | draft, plan | draft (SDR); plan (project coordinator) | - |
| consulting | 2 | register | register (risk advisory) | - |
| insurance | 2 | case_file | case_file (claims adjuster) | - |
| research-reporting | 1 | register | register (regulatory change) | - |

Done (Slice 127, 2026-11-24): every one of the 20 (family, kind) pairs has at least one
realistic example - the family examples in fixtures/roles/ plus 10 role examples in
fixtures/work/<role id>/. tests/test_work_examples.py fails if any pair loses its example.
Loop complete; next is a paid live check of a memo role and a workbook role (owner's yes first).
