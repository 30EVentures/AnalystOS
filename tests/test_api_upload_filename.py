"""Slice 81 - an upload's filename never decides where it is saved.
See specs/slice-81/spec.md.

The routes save each upload into a fresh temporary folder. A client controls the
filename, so it must never be joined to a path as sent: ``../../x.csv`` or an
absolute path would otherwise leave that folder. Each test makes the temporary
folder a known directory inside a throwaway parent, so a file written anywhere
else is visible, then sends hostile filenames and looks for strays.

The model is never called: ``/api/extract`` has no model step, ``/api/analyze``
is given a schema and template (the table-driven path), and ``/api/v1`` uses the
same mocked pipeline as test_api_v1.py.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.analyze import _ACCESS_CODE_ENV_VAR, app
from tests.test_api_v1 import CSV as V1_CSV, ApiTestCase

_CODE = "test-access-code"
_CSV = "period,revenue\nFY2023,26974\nFY2024,60922\n"
_SCHEMA = json.dumps({"period": "text", "revenue": "number"})
_PREFIX = "analystos-"  # what the routes pass to tempfile.mkdtemp


class Sandbox:
    """Make the route's temp folder ``<base>/work`` and expose anything written
    elsewhere under ``<base>``. Only the route's own mkdtemp call is redirected;
    every other temp-file use runs for real."""

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name).resolve()
        self.work = self.base / "work"
        real = tempfile.mkdtemp

        def fake(*args, **kwargs):
            if kwargs.get("prefix") == _PREFIX and not self.work.exists():
                self.work.mkdir()
                return str(self.work)
            return real(*args, **kwargs)

        self._patch = patch("tempfile.mkdtemp", side_effect=fake)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        self._td.cleanup()

    def stray_files(self):
        """Every file under the parent. The route deletes ``work`` itself, so
        any file listed here was written outside the temp folder."""
        return sorted(str(p.relative_to(self.base)) for p in self.base.rglob("*") if p.is_file())

    def hostile_names(self):
        return [
            "../x.csv",
            "../../x.csv",
            "a/../../x.csv",
            "./../x.csv",
            f"{self.base}/x.csv",  # absolute: replaces the temp folder entirely
        ]


class LegacyRoutesTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        os.environ[_ACCESS_CODE_ENV_VAR] = _CODE
        self.addCleanup(os.environ.pop, _ACCESS_CODE_ENV_VAR, None)

    def _post(self, path, name, **form):
        data = {"file": (io.BytesIO(_CSV.encode()), name), **form}
        return self.client.post(path, data=data, content_type="multipart/form-data", headers={"X-Access-Code": _CODE})

    def _analyze(self, name):
        return self._post("/api/analyze", name, schema=_SCHEMA, template="income_statement", currency_unit="actual")

    def _check_route(self, send):
        with Sandbox() as sb:
            for name in sb.hostile_names():
                response = send(name)
                self.assertEqual(response.status_code, 200, f"{name!r}: {response.get_data(as_text=True)[:200]}")
                self.assertEqual(sb.stray_files(), [], f"{name!r} wrote a file outside the temp folder")

    def test_extract_keeps_hostile_filenames_inside_the_temp_folder(self):
        self._check_route(lambda name: self._post("/api/extract", name))

    def test_analyze_keeps_hostile_filenames_inside_the_temp_folder(self):
        self._check_route(self._analyze)

    def test_a_directory_in_the_client_filename_never_reaches_the_report(self):
        with Sandbox():
            response = self._analyze("secretdir/data.csv")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:200])
        self.assertNotIn("secretdir", response.get_data(as_text=True))

    def test_a_plain_filename_still_works(self):
        with Sandbox() as sb:
            self.assertEqual(self._post("/api/extract", "data.csv").status_code, 200)
            self.assertEqual(self._analyze("data.csv").status_code, 200)
            self.assertEqual(sb.stray_files(), [])

    def test_the_extension_check_still_runs_first(self):
        with Sandbox() as sb:
            response = self._post("/api/extract", "../../x.exe")
            self.assertEqual(response.status_code, 400)  # the legacy routes answer 400 for an unsupported type
            self.assertIn("unsupported file type", response.get_data(as_text=True))
            self.assertEqual(sb.stray_files(), [])


class V1PinsTheSafeBehaviourTest(ApiTestCase):
    """/api/v1 already used only the last filename component. Pin it, so the
    two surfaces cannot drift apart again."""

    def test_analyses_keeps_hostile_filenames_inside_the_temp_folder(self):
        with Sandbox() as sb:
            for name in sb.hostile_names():
                with contextlib.redirect_stderr(io.StringIO()):
                    response = self.analyze(name=name, content=V1_CSV)
                self.assertEqual(response.status_code, 201, f"{name!r}: {response.get_data(as_text=True)[:200]}")
                self.assertEqual(sb.stray_files(), [], f"{name!r} wrote a file outside the temp folder")

    def test_a_job_with_a_hostile_filename_runs_inside_the_temp_folder(self):
        with Sandbox() as sb:
            data = {"file": (io.BytesIO(V1_CSV.encode()), "../../x.csv")}
            with contextlib.redirect_stderr(io.StringIO()):
                made = self.client.post("/api/v1/jobs", data=data, headers=self.h(), content_type="multipart/form-data")
                self.assertEqual(made.status_code, 202, made.get_data(as_text=True)[:200])
                run = self.client.post(f"/api/v1/jobs/{made.get_json()['id']}/run", headers=self.h())
            self.assertEqual(run.get_json()["status"], "done", run.get_data(as_text=True)[:200])
            self.assertEqual(sb.stray_files(), [])


if __name__ == "__main__":
    unittest.main()
