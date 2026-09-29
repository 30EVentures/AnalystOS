"""Slice 78 - the 30E Ventures studio bar and footer are on every public page, come from
one source, and cannot silently go stale. See specs/slice-78/spec.md."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import refresh  # noqa: E402
import studio_chrome  # noqa: E402


class PagesMatchTheSourceTest(unittest.TestCase):
    def test_every_public_page_is_in_step_with_the_source(self):
        for page in studio_chrome.PAGES:
            with self.subTest(page=page.name):
                text = page.read_text(encoding="utf-8")
                self.assertEqual(studio_chrome.stale(text), [], "run: python3 tools/studio_chrome.py")

    def test_each_page_has_exactly_one_bar_one_css_block_and_one_footer_line(self):
        for page in studio_chrome.PAGES:
            with self.subTest(page=page.name):
                text = page.read_text(encoding="utf-8")
                self.assertEqual(text.count('class="studio-bar"'), 1)
                self.assertEqual(text.count("/* studio:css:start */"), 1)
                self.assertEqual(text.count('class="studio-foot"'), 1)

    def test_the_bar_is_the_first_thing_in_the_body(self):
        for page in studio_chrome.PAGES:
            with self.subTest(page=page.name):
                text = page.read_text(encoding="utf-8")
                after_body = text.split("<body>", 1)[1].lstrip()
                self.assertTrue(after_body.startswith("<!-- studio:bar:start -->"))


class TheBlocksAreHonestAndSelfContainedTest(unittest.TestCase):
    def setUp(self):
        self.bar = studio_chrome.render_bar()
        self.foot = studio_chrome.render_footer()

    def test_every_studio_link_goes_to_the_canonical_domain(self):
        for html in (self.bar, self.foot):
            hrefs = re.findall(r'href="([^"]+)"', html)
            self.assertTrue(hrefs)
            for href in hrefs:
                self.assertTrue(href.startswith("https://30eventures.com"), href)

    def test_no_script_no_external_request_no_inline_handlers(self):
        blob = self.bar + self.foot + studio_chrome.CSS
        for banned in ("<script", "onclick", "@import", "url(", "src=", "http://"):
            self.assertNotIn(banned, blob)

    def test_it_states_only_what_is_true_today(self):
        blob = self.bar + self.foot
        self.assertIn("AnalystOS is a 30E Ventures product", blob)
        self.assertIn("Toronto", blob)
        for overreach in ("holding company", "capital markets", "Inc.", "Ltd"):
            self.assertNotIn(overreach, blob)

    def test_the_bar_is_hidden_in_print_and_collapses_on_phones(self):
        self.assertIn("@media print{.studio-bar{display:none}}", studio_chrome.CSS)
        self.assertIn("@media (max-width:640px)", studio_chrome.CSS)


class ApplyTest(unittest.TestCase):
    SAMPLE = (
        "<style>a{}\n/* studio:css:start */\nOLD\n/* studio:css:end */\n</style><body>\n"
        "<!-- studio:bar:start -->\nOLD\n<!-- studio:bar:end -->\nkeep me\n<footer><div>x"
        "<!-- studio:footer:start -->\nOLD\n<!-- studio:footer:end -->\n</div></footer>"
    )

    def test_it_replaces_only_between_markers_and_keeps_everything_else(self):
        new, problems = studio_chrome.apply(self.SAMPLE)
        self.assertEqual(problems, [])
        self.assertNotIn("OLD", new)
        self.assertIn("keep me", new)
        self.assertIn("a{}", new)
        self.assertIn("studio-bar", new)

    def test_it_is_idempotent(self):
        once, _ = studio_chrome.apply(self.SAMPLE)
        twice, _ = studio_chrome.apply(once)
        self.assertEqual(once, twice)

    def test_a_missing_marker_is_an_error_not_a_silent_skip(self):
        broken = self.SAMPLE.replace("<!-- studio:bar:end -->", "")
        _, problems = studio_chrome.apply(broken)
        self.assertTrue(any(p.startswith("bar:") for p in problems))

    def test_a_marker_pair_present_twice_is_an_error(self):
        doubled = self.SAMPLE + "<!-- studio:footer:start --><!-- studio:footer:end -->"
        _, problems = studio_chrome.apply(doubled)
        self.assertTrue(any(p.startswith("footer:") for p in problems))

    def test_a_stale_block_is_reported(self):
        self.assertTrue(studio_chrome.stale(self.SAMPLE))


class WiredIntoRefreshTest(unittest.TestCase):
    def test_refresh_runs_the_studio_step(self):
        self.assertIn("studio_chrome.py", refresh.STEPS)
        self.assertTrue((ROOT / "tools" / "studio_chrome.py").exists())


if __name__ == "__main__":
    unittest.main()
