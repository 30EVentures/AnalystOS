"""Smoke test: proves the test runner is wired up.

Replace with real tests as slices land. Keep at least one test passing at all
times, so `python3 -m unittest` always has something to report.
"""

import unittest


class SmokeTest(unittest.TestCase):
    def test_arithmetic_still_works(self):
        self.assertEqual(1 + 1, 2)


if __name__ == "__main__":
    unittest.main()
