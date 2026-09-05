"""Vercel's file-based Python routing maps one file to one route by path -
``api/analyze.py`` -> ``/api/analyze`` (see docs/decisions.md, 2026-09-04) -
regardless of what routes a file's WSGI app actually defines internally.

``POST /api/extract`` is defined on the same shared Flask ``app`` in
``api/analyze.py`` (both routes belong to one app on purpose - see that
module's docstring), so it needs its own matching file for Vercel to route
to. This file exists purely to give Vercel that entry point; the route
itself, and everything it does, lives in ``api/analyze.py`` - there is still
exactly one implementation, just two file-based doors into it.
"""

from api.analyze import app  # noqa: F401
