"""Partial dates and racing ages."""

import unittest
from datetime import date

from horsedetective.dates import RacingAge, age_under, date_bounds
from horsedetective.models import Horse, Race


class DateBoundsTest(unittest.TestCase):
    def test_year(self):
        self.assertEqual(date_bounds("1875"), (date(1875, 1, 1), date(1875, 12, 31)))

    def test_month_in_leap_year(self):
        self.assertEqual(date_bounds("1876-02"), (date(1876, 2, 1), date(1876, 2, 29)))

    def test_day(self):
        self.assertEqual(date_bounds("1875-06-12"), (date(1875, 6, 12), date(1875, 6, 12)))


class AgeUnderTest(unittest.TestCase):
    def test_1_january_birthday(self):
        self.assertEqual(age_under(2000, "GB", "2003-01-01"), 3)
        self.assertEqual(age_under(2000, "GB", "2002-12-31"), 2)

    def test_1_august_birthday(self):
        self.assertEqual(age_under(2000, "AUS", "2003-07-31"), 2)
        self.assertEqual(age_under(2000, "AUS", "2003-08-01"), 3)

    def test_year_only_date_is_enough_for_1_january(self):
        self.assertEqual(age_under(2000, "IRE", "2003"), 3)

    def test_year_only_date_spanning_1_august_is_unknown(self):
        self.assertIsNone(age_under(2000, "NZ", "2003"))

    def test_month_date_settles_1_august(self):
        self.assertEqual(age_under(2000, "AUS", "2003-07"), 2)
        self.assertEqual(age_under(2000, "AUS", "2003-08"), 3)

    def test_country_not_in_table_or_unknown(self):
        self.assertIsNone(age_under(2000, "ARG", "2003-05-01"))
        self.assertIsNone(age_under(2000, None, "2003-05-01"))

    def test_before_first_official_birthday(self):
        self.assertIsNone(age_under(2000, "AUS", "2000-03-01"))
        self.assertEqual(age_under(2000, "AUS", "2000-09-01"), 0)


class RacingAgeTest(unittest.TestCase):
    def test_display(self):
        self.assertEqual(str(RacingAge(3, 3)), "3")
        self.assertEqual(str(RacingAge(3, None)), "3")
        self.assertEqual(str(RacingAge(2, 3)), "2/3")
        self.assertEqual(str(RacingAge(None, 3)), "?/3")
        self.assertEqual(str(RacingAge(None, None)), "?")

    def test_known(self):
        self.assertEqual(RacingAge(3, 2).known, [2, 3])
        self.assertEqual(RacingAge(3, 3).known, [3])
        self.assertEqual(RacingAge(None, None).known, [])


class AgeAtTest(unittest.TestCase):
    def test_unknown_foaling_year_or_date(self):
        self.assertIsNone(Horse(name="Test Horse", country="GB").age_at(Race(date="2003")))
        self.assertIsNone(Horse(name="Test Horse", country="GB", foaled=2000).age_at(Race()))

    def test_both_rules(self):
        h = Horse(name="Test Horse", country="AUS", foaled=2000)
        self.assertEqual(h.age_at(Race(date="2003-03-01", country="GB")), RacingAge(2, 3))
        self.assertEqual(h.age_at(Race(date="2003-03-01", country="AUS")), RacingAge(2, 2))
        self.assertEqual(h.age_at(Race(date="2003-03-01")), RacingAge(2, None))


if __name__ == "__main__":
    unittest.main()
