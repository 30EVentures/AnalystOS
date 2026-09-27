"""Slice 69 - the homepage's test and spec counts are true and cannot silently
freeze. See specs/slice-69/spec.md."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import site_counts  # noqa: E402

PAGE = (ROOT / "site" / "index.html").read_text(encoding="utf-8")


class HomepageCountsAreTrueTest(unittest.TestCase):
    def test_the_page_states_the_real_test_and_spec_counts(self):
        stale = site_counts.stale_figures(PAGE, site_counts.count_tests(), site_counts.count_specs())
        self.assertEqual(stale, [], "run: python3 tools/site_counts.py")

    def test_every_pattern_still_matches_exactly_once(self):
        _, problems = site_counts.rewrite(PAGE, 1, 1)
        self.assertEqual(problems, [])

    def test_the_counts_are_plausible_and_not_the_frozen_old_ones(self):
        self.assertGreater(site_counts.count_tests(), 700)
        self.assertNotIn("<strong>503</strong>", PAGE)


class RewriteTest(unittest.TestCase):
    SAMPLE = (
        '<strong>1</strong><span>automated tests passing</span> 2 automated tests with mocked calls '
        '<b>3 / 3</b><p class="note" style="x">automated tests passing, run in about 3 seconds</p> 4 specs</b> '
        "5 automated tests, a live suite with 6 automated tests passing meas:'7 mocked tests passing"
    )

    def test_it_rewrites_all_seven_figures(self):
        new, problems = site_counts.rewrite(self.SAMPLE, 800, 70)
        self.assertEqual(problems, [])
        self.assertEqual(new.count("800"), 6 + 1)  # six single figures plus the "800 / 800" pair's second number
        self.assertIn("800 / 800", new)
        self.assertIn("70 specs", new)
        for old in ("<strong>1<", "2 automated", "3 / 3", "4 specs", "5 automated", "with 6 automated", "'7 mocked"):
            self.assertNotIn(old, new)

    def test_a_reworded_page_is_an_error_not_a_silent_skip(self):
        reworded = self.SAMPLE.replace("automated tests with mocked calls", "tests, all mocked")
        new, problems = site_counts.rewrite(reworded, 800, 70)
        self.assertEqual(len(problems), 1)
        self.assertIn("built list", problems[0])

    def test_a_duplicated_figure_is_also_an_error(self):
        _, problems = site_counts.rewrite(self.SAMPLE + " 9 specs</b>", 800, 70)
        self.assertTrue(any("specs card" in p and "2 times" in p for p in problems))

    def test_stale_detection(self):
        stale = site_counts.stale_figures(self.SAMPLE, 800, 70)
        self.assertEqual(len(stale), 7)
        fresh, _ = site_counts.rewrite(self.SAMPLE, 800, 70)
        self.assertEqual(site_counts.stale_figures(fresh, 800, 70), [])

    def test_a_pair_with_only_the_second_number_wrong_is_stale(self):
        fresh, _ = site_counts.rewrite(self.SAMPLE, 800, 70)
        broken = fresh.replace("800 / 800", "800 / 799")
        self.assertTrue(any("evidence card" in s for s in site_counts.stale_figures(broken, 800, 70)))


class CommandTest(unittest.TestCase):
    def test_check_mode_exit_codes(self):
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(site_counts.main(["--check"]), 0)
        self.assertIn("homepage counts are true", out.getvalue())


if __name__ == "__main__":
    unittest.main()
