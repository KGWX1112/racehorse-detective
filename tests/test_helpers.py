"""Career and text helpers that the evaluators build on."""

import unittest

from horsedetective.evaluators import longest_win_streak, streak_then_loss
from horsedetective.text import normalize_country, text_matches

W, DH, L = "W", "DH", "L"


class LongestWinStreakTest(unittest.TestCase):
    def test_empty_record(self):
        self.assertEqual(longest_win_streak([]), 0)

    def test_no_wins(self):
        self.assertEqual(longest_win_streak([L, L, L]), 0)

    def test_single_win(self):
        self.assertEqual(longest_win_streak([W]), 1)

    def test_longest_of_several_runs(self):
        self.assertEqual(longest_win_streak([W, W, L, W, W, W, L, W]), 3)

    def test_run_at_end_of_career(self):
        self.assertEqual(longest_win_streak([L, W, W, W, W]), 4)

    def test_dead_heat_counts_as_win(self):
        self.assertEqual(longest_win_streak([W, DH, W, L]), 3)


class StreakThenLossTest(unittest.TestCase):
    def test_run_of_exact_length_then_loss(self):
        self.assertTrue(streak_then_loss([W] * 7 + [L], 7))

    def test_longer_run_then_loss(self):
        self.assertTrue(streak_then_loss([W] * 8 + [L], 7))

    def test_run_too_short(self):
        self.assertFalse(streak_then_loss([W] * 6 + [L], 7))

    def test_unbeaten_run_never_ends_in_loss(self):
        self.assertFalse(streak_then_loss([W] * 7, 7))

    def test_loss_must_follow_directly(self):
        # The second loss follows a loss, not a run of wins.
        self.assertFalse(streak_then_loss([W, W, L, L], 3))

    def test_later_run_qualifies(self):
        self.assertTrue(streak_then_loss([W, L, W, W, W, L], 3))

    def test_dead_heat_extends_run(self):
        self.assertTrue(streak_then_loss([W, DH, L], 2))


class TextMatchesTest(unittest.TestCase):
    def test_exact_ignores_case_and_spacing(self):
        self.assertTrue(text_matches("japan cup", "  Japan   Cup ", "exact"))

    def test_exact_rejects_partial(self):
        self.assertFalse(text_matches("Japan", "Japan Cup", "exact"))

    def test_contains_whole_word(self):
        self.assertTrue(text_matches("Monarch", "The Monarch", "contains"))

    def test_contains_rejects_part_of_word(self):
        self.assertFalse(text_matches("Monarch", "Monarchy", "contains"))
        self.assertFalse(text_matches("Arr", "The Golden Arrow", "contains"))

    def test_contains_multi_word_in_order(self):
        self.assertTrue(text_matches("Golden Arrow", "The Golden Arrow", "contains"))
        self.assertFalse(text_matches("Arrow Golden", "The Golden Arrow", "contains"))

    def test_punctuation_is_ignored(self):
        self.assertTrue(text_matches("St. Leger", "St Leger Stakes", "contains"))

    def test_empty_target_never_matches(self):
        self.assertFalse(text_matches("", "Anything", "contains"))
        self.assertFalse(text_matches("!!", "Anything", "exact"))

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            text_matches("a", "a", "fuzzy")


class NormalizeCountryTest(unittest.TestCase):
    def test_names_and_suffixes_map_to_suffix(self):
        cases = {
            "Japan": "JPN", "jpn": "JPN",
            "United States": "USA", "us": "USA",
            "Great Britain": "GB", "UK": "GB",
            "  ireland ": "IRE",
            "New Zealand": "NZ",
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_country(raw), want)

    def test_unlisted_value_is_stripped_and_uppercased(self):
        self.assertEqual(normalize_country(" arg "), "ARG")


if __name__ == "__main__":
    unittest.main()
