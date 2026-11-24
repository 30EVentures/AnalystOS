# Slice 128 - per-role samples in the homepage role explorer

## Goal

The owner: "make per-role samples, show me mocks first". Until now every role in a
family showed its family's one sample. 23 roles now have a worked example of their
own (13 family examples plus the 10 in `fixtures/work/`, Slice 127).

## What changes

- `tools/build_samples.py` also builds one file per role with its own example,
  served at `site/samples/roles/<role id>.<docx|xlsx|pptx>`, in the role's format.
- `samples.json` (format `analystos-samples/2`) lists every role in each family
  (the family example's role first) with `own_sample`, its boundary and its
  "delivers today" line, plus a `roles` map of the role samples.
- Every sample's preview gains up to two "The role's own work" pages drawing its
  work product (draft, register, case file, reconciliation, plan, code), every
  number a verified figure value.
- The explorer lists every role in the family as a button. A role with its own
  example shows it; any other role shows the family's and says so: "No sample of
  its own yet: this is the family's example, written for the <role>."
- The "delivers today" line counts delivered work as delivered ("with its draft
  and reconciliation inside"), never as "Also planned" (a stale claim since
  Slice 126).

## Done when

- [x] Every role appears once, in its own family; `own_sample` is true for
      exactly the 23 roles with an example.
- [x] Each role sample is its own file, in its role's format, with a work page.
- [x] Every number shown, including on work pages, is the verified value.
- [x] Delivered work is never called planned.
- [x] The page builds everything with textContent; no HTML is parsed from data.
- [x] Local mock shown to the owner before any push; no horizontal scroll at phone width.
- [x] Full suite OK, `refresh.py --check`, `build_samples.py --check`, Flashy fence holds.
