"""Slice 115 - what counts as a number. Every case the Slice 112-113 review found
slipping past the first detector is here, plus what must stay exempt."""

import unittest

from analystos.packs.numbers import find_numbers


def found(text):
    return [(t.text.strip(), t.value, t.kind) for t in find_numbers(text)]


class NumbersTest(unittest.TestCase):
    def test_quantities_in_words_and_symbols_are_numbers_with_no_value(self):
        for text in ("seven percent", "thirty thousand dollars", "tripled", "doubled", "twice as fast",
                     "half the clinics", "halved", "a tenfold rise", "one third", "fourteen stores",
                     "seventy-two", "hundreds of clinics", "a dozen", "five percent", "VII percent",
                     "½", "x²", "Ⅶ"):
            with self.subTest(text=text):
                tokens = find_numbers(text)
                self.assertTrue(tokens, text)
                self.assertTrue(all(t.value is None for t in tokens), found(text))

    def test_digits_however_written_are_numbers_with_a_value(self):
        cases = (
            ("NRR96%", ("96%", 96.0, "percent")), (".5%", (".5%", 0.5, "percent")),
            ("We will lose 2000 clinics", ("2000", 2000.0, None)), ("$30,600", ("$30,600", 30600.0, "usd")),
            ("$1.8 million", ("$1.8 million", 1800000.0, "usd")), ("3 points", ("3 points", 3.0, "points")),
            ("3pp", ("3pp", 3.0, "points")), ("-3 pp", ("-3 pp", -3.0, "points")), ("−3%", ("−3%", -3.0, "percent")),
            ("7x", ("7x", 7.0, "ratio")), ("1K", ("1K", 1000.0, None)), ("٧", ("٧", 7.0, None)),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(found(text), [expected])

    def test_a_hyphen_inside_a_range_is_not_a_sign(self):
        self.assertEqual(found("4-7%"), [("4", 4.0, None), ("7%", 7.0, "percent")])

    def test_exempt(self):
        for text in ("Q3 roadmap", "In Q3 2025 the release shipped.", "In 2025 churn rose", "since 2024",
                     "FY2025 plan", "FY 26 budget", "v1.2 broke", "[F12]", "B2B software", "two hires",
                     "fewer than ten staff", "three options", "a single owner"):
            with self.subTest(text=text):
                self.assertEqual(find_numbers(text), [])

    def test_a_year_shaped_count_after_a_non_time_word_is_a_number(self):
        self.assertEqual(found("signed 1950 clinics"), [("1950", 1950.0, None)])

    def test_not_text(self):
        self.assertEqual(find_numbers(None), [])
        self.assertEqual(find_numbers(7), [])


if __name__ == "__main__":
    unittest.main()
