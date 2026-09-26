# Slice 63 - reports go to the reader's own Downloads, not to a server

## Goal

Decision from 30E Ventures, 2026-09-26: reports should land in people's
Downloads folder. That settles the open storage question from the Slice 61
retrospective: **AnalystOS keeps no reports on a server by default.** The
upload is processed and deleted (already true); now the result is handed to the
person as files they save themselves.

- `POST /api/analyze` (the hosted page's endpoint) additionally returns
  `pdf_base64` (the real generated PDF the audit found the API never exposed)
  and, for narrated runs, `seal` (Slice 60). Additive: `section` and `html` are
  unchanged.
- `site/upload.html` gets three real downloads - report (`.html`), PDF, and
  seal (`.json`) - saved by the browser to its Downloads folder. The old
  print-dialog button stays as a fallback when no PDF came back.
- `POST /api/v1/analyses` accepts `include_pdf=true` and then returns
  `pdf_base64`. Server-side storage (`ANALYSTOS_STORE_DIR`) stays available but
  is off by default and no longer on the critical path.
- Docs: the stateless mode is the documented default; for the mesh, whoever
  receives a seal hosts it themselves (a seal verifies anywhere; nothing about it
  depends on our server), so a mesh task's `evidenceUrl` can point at the
  requester's own storage.
- Records that 30E Ventures owns the `analystos` org and that
  `30eventures@gmail.com` is the accountable email (both stated by the owner;
  ownership is not independently verifiable from the public directory).

## Not in this slice

- A filename picker or a "choose where to save" dialog (the browser's own
  setting decides whether it asks).
- Saving reports to anything but the reader's machine.
- Changing the retention/link features of Slice 61 (still there if a deployment
  sets a store).

## Done when

1. `/api/analyze` returns a real PDF and a seal that verifies (narrated path),
   and neither for the table path where there is no seal; existing tests still
   pass unchanged.
2. The upload page has the three download controls wired to the response
   fields, using a `download` attribute so the browser saves to Downloads.
3. `include_pdf` returns a PDF that starts with `%PDF`; without it the response
   has none.
4. Docs and decision log state the stateless default and the mesh consequence.
5. Full suite OK.
