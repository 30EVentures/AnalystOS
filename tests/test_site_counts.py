"""Slice 69 - the homepage's test and spec counts are true and cannot silently
freeze. See specs/slice-69/spec.md. Slice 111 - the test count is described as
what it is (tests in the suite, some skipped without Node.js), never as a count of
passing tests, and the hero's spec figure is generated too. See
specs/slice-111/spec.md."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import site_counts  # noqa: E402

PAGE = (ROOT / "site" / "details.html").read_text(encoding="utf-8")  # counts live on the full page (Slice 122)


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

    def test_the_page_never_calls_the_test_count_a_pass_count(self):
        # The count includes tests skipped on a machine without Node.js.
        self.assertEqual(site_counts.passing_claims(PAGE), [])

    def test_both_spec_figures_come_from_the_same_count(self):
        specs = site_counts.count_specs()
        self.assertIn(f"<strong>{specs}</strong><span>written specs behind the build", PAGE)
        self.assertIn(f">{specs} specs</b>", PAGE)
        self.assertNotIn("<strong>49</strong><span>written specs", PAGE)


class RewriteTest(unittest.TestCase):
    SAMPLE = (
        '<strong>1</strong><span>automated tests in the suite</span> 2 automated tests with mocked calls '
        '<b>3 automated tests</b><p class="note" style="x">in the suite, run in under a minute</p> 4 specs</b> '
        "5 automated tests, a live suite backed by 6 automated tests meas:'7 mocked tests in the suite "
        "<strong>8</strong><span>written specs behind the build</span>"
    )

    def test_it_rewrites_all_eight_figures(self):
        new, problems = site_counts.rewrite(self.SAMPLE, 800, 70)
        self.assertEqual(problems, [])
        self.assertEqual(new.count("800"), 6)
        self.assertEqual(new.count(">70<") + new.count("70 specs"), 2)
        for old in ("<strong>1<", "2 automated", ">3 automated", "4 specs", "5 automated",
                    "by 6 automated", "'7 mocked", "<strong>8<"):
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
        self.assertEqual(len(stale), 8)
        fresh, _ = site_counts.rewrite(self.SAMPLE, 800, 70)
        self.assertEqual(site_counts.stale_figures(fresh, 800, 70), [])

    def test_a_stale_hero_spec_figure_is_caught(self):
        fresh, _ = site_counts.rewrite(self.SAMPLE, 800, 70)
        broken = fresh.replace("<strong>70</strong><span>written specs", "<strong>49</strong><span>written specs")
        self.assertEqual(site_counts.stale_figures(broken, 800, 70), ["hero specs: page says 49, actual 70"])


class PassingClaimTest(unittest.TestCase):
    """Every wording the page used before Slice 111 is refused; the new wording is not."""

    OLD = (
        '<strong>1352</strong><span>automated tests passing</span>',
        "1352 automated tests with mocked calls: no network, no cost, passing in under a minute.",
        '<b style="x">1352 / 1352</b>',
        "a live upload page work, with 1352 automated tests passing.",
        "meas:'1352 mocked tests passing, plus a live suite",
    )

    def test_each_old_wording_is_a_passing_claim(self):
        for old in self.OLD:
            with self.subTest(old=old):
                self.assertNotEqual(site_counts.passing_claims(old), [])

    def test_the_new_wording_is_not(self):
        self.assertEqual(site_counts.passing_claims(RewriteTest.SAMPLE), [])

    def test_unrelated_numbers_and_ratios_are_left_alone(self):
        for ok in ("4 fixed test documents", "a 3 / 4 split", "12 tests. Everything passing is a later goal"):
            with self.subTest(ok=ok):
                self.assertEqual(site_counts.passing_claims(ok), [])


class CommandTest(unittest.TestCase):
    def test_check_mode_exit_codes(self):
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(site_counts.main(["--check"]), 0)
        self.assertIn("homepage counts are true", out.getvalue())


if __name__ == "__main__":
    unittest.main()
