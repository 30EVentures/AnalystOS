"""Regression test for a real production bug: Vercel's file-based Python
routing maps one file to one route by path (api/analyze.py -> /api/analyze),
regardless of what a file's Flask app defines internally - so /api/extract,
defined on the same shared app, needs its own matching file
(api/extract.py) or it 404s on Vercel even though every local test (which
talks to the app object directly, bypassing Vercel's routing) passes.
"""

import unittest


class ApiExtractFileExistsTest(unittest.TestCase):
    def test_api_extract_module_exists_and_exposes_the_shared_app(self):
        from api.analyze import app as app_via_analyze
        from api.extract import app as app_via_extract

        self.assertIs(app_via_extract, app_via_analyze)

    def test_both_routes_are_registered_on_the_shared_app(self):
        from api.extract import app

        rules = {str(r) for r in app.url_map.iter_rules()}
        self.assertIn("/api/analyze", rules)
        self.assertIn("/api/extract", rules)


if __name__ == "__main__":
    unittest.main()
