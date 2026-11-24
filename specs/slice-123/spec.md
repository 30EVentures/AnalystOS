# Slice 123 - role-specific output formats, phase 1: memo and workbook

## Goal

The owner, seeing the homepage samples: "the example deck is the same for all
roles". Today all 73 roles deliver the same verified analysis deck. Phase 1 gives
roles a format that fits their work, built from the same verified content, with
no change to the model call or its checks:

- **Memo** (.docx) for legal, research, audit, HR, insurance and financial crime:
  question, short answer, background, findings, options, recommendation, next
  steps, measures, risks, sources.
- **Workbook** (.xlsx) for finance, accounting and data: an Inputs sheet with
  every client figure and its quote, every calculated figure as a live Excel
  formula over the cells it uses, then Findings, Plan and Risks sheets.
- **Deck** (.pptx) stays for consulting, content, sales and software until phase
  2 gives them role-written content (drafts, job posts, journal entries, plans).

## Rules (the same as the deck)

1. Each renderer refuses anything it cannot re-verify: the one shared guard
   re-verifies the content, recomputes the client text from the accepted
   engagement, and takes the role from the catalog.
2. Every number in the document is a figure's value printed by `format_value`,
   with its reference; nothing else carries a digit except labels the deck also
   allows (references, quotes on the sources table, formulas).
3. In the workbook, each calculated figure's formula, evaluated over its input
   cells, equals the verified value; inputs are the client's values exactly.
4. The human-decides or approval-gated boundary is stated at the top.

## Done when

1. All 16 worked examples render as a memo and as a workbook.
2. An independent no-new-numbers check passes on every memo and on every
   workbook's text; every workbook formula evaluates to its figure's value.
3. Each renderer refuses an edited spec, a forged client text, a role the
   engagement did not ask for, and an unaccepted engagement.
4. Full suite OK; refresh check clean; Flashy fence holds; no paid call.
5. The owner sees sample memos and workbooks before they are wired into hiring
   or the homepage.
