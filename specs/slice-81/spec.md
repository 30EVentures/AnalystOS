# Slice 81 - an upload's filename never decides where it is saved

## Goal

`POST /api/extract` and `POST /api/analyze` (both in `api/analyze.py`) save the
uploaded file into a fresh temporary folder, using the filename the client
sent: `tmp_dir / upload.filename`. The client controls that string, and
`pathlib` does not confine it. A name such as `../../x.csv` leaves the temporary
folder, and an absolute name such as `/tmp/x.csv` replaces the folder entirely.
The only check on the name is its extension, so a caller who holds the access
code can write a file whose contents they control, with an allowed extension,
anywhere the server process may write. (The request handler deletes the temporary
folder afterwards, but not whatever escaped it.)

The fix is the rule `/api/v1` already follows: use only the last component of
the client's filename (`Path(name).name`), and check that the resulting path
still sits directly inside the temporary folder.

## Included

- `api/analyze.py` - one helper, `_upload_path(upload, tmp_dir)`, used by both
  routes; and the `/api/analyze` default title built from the same last
  component, so a directory the client sent never appears in a report.
- `tests/test_api_upload_filename.py` - regression tests, written first and
  confirmed to fail on the unfixed code.
- `docs/decisions.md` - the choice and the reason.

## Done when

- [ ] On both routes, uploads named `../x.csv`, `../../x.csv`, `a/../../x.csv`
      and an absolute path leave no file anywhere outside the temporary folder.
- [ ] Those same requests are still processed normally (HTTP 200): the safe
      name is the last component, so the report is the same as for `x.csv`.
- [ ] The `/api/analyze` report title and body never contain the directory part
      of a client filename.
- [ ] The tests above fail on `main` before the change (checked, not assumed).
- [ ] A normal filename (`data.csv`) behaves exactly as before: all existing
      tests are unchanged and pass.
- [ ] `/api/v1` is untouched; its filename handling is covered by a test that
      pins the existing safe behavior.
- [ ] `docs/decisions.md` records the change, and the full suite reports `OK`.

## Not in this slice

- **A random server-chosen name.** It would also be safe, but it would change
  the source name shown in reports for ordinary uploads. Using the client's
  last component keeps today's output byte-for-byte.
- **Changing the access code, rate limits or file-size limit** on the legacy
  routes, or retiring them in favour of `/api/v1`.
- **Anything in `analystos/`.** The job store keeps the client filename only as
  file contents under a fixed name, and the job-run step already uses the last
  component; both were checked and need no change.
