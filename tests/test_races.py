"""Race records: derived result codes, validation, sources, and round trips."""

import json
import os
import tempfile
import unittest

from horsedetective.models import Horse, Race
from horsedetective.store import HorseStore


def horse(**kw):
    kw.setdefault("name", "Test Horse")
    return Horse(**kw)


class ResultCodeTest(unittest.TestCase):
    # finish, outcome, derived code
    TABLE = [
        (1, None, "W"),
        (1, "finished", "W"),
        (2, "finished", "L"),
        (None, "finished", None),
        (None, None, None),
        (1, "dead_heat", "DH"),
        (3, "dead_heat", "L"),
        (None, "dead_heat", None),
        (None, "walkover", "W"),
        (1, "walkover", "W"),
        (2, "disqualified", "L"),
        (None, "disqualified", "L"),
        (1, "promoted", "W"),
        (2, "promoted", "L"),
        (None, "promoted", None),
        (None, "fell", "L"),
        (None, "pulled_up", "L"),
        (None, "void", None),
    ]

    def test_table(self):
        for finish, outcome, code in self.TABLE:
            with self.subTest(finish=finish, outcome=outcome):
                self.assertEqual(Race(finish=finish, outcome=outcome).result_code, code)

    def test_outcome_spelling_is_normalized(self):
        self.assertEqual(Race(outcome="Pulled up").outcome, "pulled_up")
        self.assertEqual(Race(finish=1, outcome="dead-heat").result_code, "DH")

    def test_walkover_flag(self):
        self.assertTrue(Race(outcome="walkover").is_walkover)
        self.assertFalse(Race(finish=1).is_walkover)

    def test_void_race_is_not_a_start(self):
        self.assertFalse(Race(outcome="void").counts_as_start)
        self.assertTrue(Race(finish=5).counts_as_start)

    def test_grade_key_keeps_published_text(self):
        r = Race(grade="Group 1")
        self.assertEqual(r.grade, "Group 1")
        self.assertEqual(r.grade_key, Race(grade="G1").grade_key)

    def test_country_is_normalized(self):
        self.assertEqual(Race(country="France").country, "FR")


class RaceValidationTest(unittest.TestCase):
    def assertRejected(self, fragment, **race):
        with self.assertRaises(ValueError) as cm:
            horse(races=[race])
        self.assertIn(fragment, str(cm.exception))

    def test_bad_dates(self):
        for bad in ("1875-13", "1875-02-30", "June 1875", "75", "1875/06/12"):
            with self.subTest(date=bad):
                self.assertRejected("date", date=bad)

    def test_partial_dates_and_integer_year_accepted(self):
        h = horse(races=[{"date": "1875"}, {"date": "1876-06"}, {"date": "1876-06-12"}, {"date": 1877}])
        self.assertEqual(h.races[3].date, "1877")

    def test_unknown_outcome(self):
        self.assertRejected("unknown outcome", outcome="won")

    def test_finish_must_be_positive_whole_number(self):
        for bad in (0, -1, 1.5, "1", True):
            with self.subTest(finish=bad):
                self.assertRejected("finish must be", finish=bad)

    def test_finish_outside_field(self):
        self.assertRejected("outside a field of 5", finish=6, field_size=5)

    def test_distance_must_be_positive(self):
        self.assertRejected("distance_m", distance_m=0)

    def test_disqualified_cannot_finish_first(self):
        self.assertRejected("disqualified horse cannot", finish=1, outcome="disqualified")

    def test_walkover_cannot_finish_second(self):
        self.assertRejected("walkover must", finish=2, outcome="walkover")

    def test_non_finisher_has_no_finish(self):
        self.assertRejected("did not finish", finish=4, outcome="fell")

    def test_void_race_has_no_finish(self):
        self.assertRejected("void race has no official result", finish=1, outcome="void")

    def test_unknown_race_field(self):
        self.assertRejected("Unknown race fields", position=1)

    def test_error_names_the_race(self):
        self.assertRejected("race 1 (Test Stakes, 1875-13)", race="Test Stakes", date="1875-13")


class CareerOrderTest(unittest.TestCase):
    def test_backwards_dates_rejected(self):
        with self.assertRaises(ValueError) as cm:
            horse(races=[{"date": "1875-06-12"}, {"date": "1875-06-01"}])
        self.assertIn("race 2 (1875-06-01) is dated before an earlier race", str(cm.exception))

    def test_compared_with_every_earlier_race(self):
        # "1875" does not conflict with either neighbour, but the third race is before the first.
        with self.assertRaises(ValueError):
            horse(races=[{"date": "1875-06-12"}, {"date": "1875"}, {"date": "1875-03-01"}])

    def test_overlapping_partial_dates_and_same_day_accepted(self):
        horse(races=[{"date": "1875-06-12"}, {"date": "1875"}, {"date": "1875-06"}, {"date": "1875-06-12"}])

    def test_undated_races_are_skipped(self):
        horse(races=[{"date": "1876"}, {}, {"date": "1876-05"}])

    def test_race_before_foaling_year_rejected(self):
        with self.assertRaises(ValueError) as cm:
            horse(foaled=1875, races=[{"date": "1874-12"}])
        self.assertIn("before the foaling year 1875", str(cm.exception))
        horse(foaled=1875, races=[{"date": "1875"}])


class RacesAndOtherFieldsTest(unittest.TestCase):
    RACES = [{"finish": 1}, {"finish": 1, "outcome": "dead_heat"}, {"finish": 2}]

    def test_matching_results_accepted(self):
        horse(results=["W", "DH", "L"], races=self.RACES)

    def test_results_code_mismatch_rejected(self):
        with self.assertRaises(ValueError) as cm:
            horse(results=["W", "W", "L"], races=self.RACES)
        self.assertIn("results says W but the race record gives DH", str(cm.exception))

    def test_results_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            horse(results=["W", "DH"], races=self.RACES)

    def test_results_skip_void_races(self):
        horse(results=["W", "DH", "L"], races=self.RACES[:1] + [{"outcome": "void"}] + self.RACES[1:])
        with self.assertRaises(ValueError):
            horse(results=["W", "L", "DH", "L"], races=self.RACES[:1] + [{"outcome": "void"}] + self.RACES[1:])

    def test_void_races_are_not_counted_against_summary(self):
        races = self.RACES + [{"outcome": "void"}]
        horse(races=races, complete_fields=["races"], summary={"starts": 3, "wins": 2})

    def test_void_race_abroad_is_not_racing_abroad(self):
        h = horse(country="GB", international=False, races=[{"country": "GB", "finish": 1},
                                                            {"country": "FR", "outcome": "void"}])
        self.assertEqual(h.race_countries(), ["GB"])

    def test_void_race_still_checked_for_date_order(self):
        with self.assertRaises(ValueError):
            horse(races=[{"date": "1875-06"}, {"date": "1875-01", "outcome": "void"}])

    def test_results_can_supply_an_unknown_race_result(self):
        horse(results=["W", "DH", "L", "W"], races=self.RACES + [{"race": "Result not recorded"}])

    def test_complete_races_must_match_summary(self):
        with self.assertRaises(ValueError):
            horse(races=self.RACES, complete_fields=["races"], summary={"starts": 4})
        with self.assertRaises(ValueError):
            horse(races=self.RACES, complete_fields=["races"], summary={"wins": 1})
        horse(races=self.RACES, complete_fields=["races"], summary={"starts": 3, "wins": 2})

    def test_partial_races_cannot_exceed_summary(self):
        with self.assertRaises(ValueError):
            horse(races=self.RACES, summary={"starts": 2})
        with self.assertRaises(ValueError):
            horse(races=self.RACES, summary={"wins": 1})
        horse(races=self.RACES, summary={"starts": 10, "wins": 5})

    def test_unknown_results_widen_the_wins_check(self):
        races = self.RACES + [{}]
        horse(races=races, complete_fields=["races"], summary={"starts": 4, "wins": 3})
        with self.assertRaises(ValueError):
            horse(races=races, complete_fields=["races"], summary={"starts": 4, "wins": 4})

    def test_complete_raced_countries_must_cover_races(self):
        with self.assertRaises(ValueError) as cm:
            horse(country="GB", raced_countries=["GB"], complete_fields=["raced_countries"],
                  races=[{"country": "France"}])
        self.assertIn("['FR']", str(cm.exception))

    def test_international_false_conflicts_with_race_abroad(self):
        with self.assertRaises(ValueError):
            horse(country="GB", international=False, races=[{"country": "FR"}])

    def test_races_can_be_marked_complete(self):
        self.assertTrue(horse(races=self.RACES, complete_fields=["races"]).is_complete("races"))
        with self.assertRaises(ValueError):
            horse(complete_fields=["races"])


class SourceTest(unittest.TestCase):
    def test_race_sources_when_races_has_no_own_source(self):
        h = horse(races=[{"source": "A"}, {"source": "B"}, {"source": "A"}], sources={"*": "Fallback"})
        self.assertEqual(h.source_for("races"), "A; B")

    def test_fallback_when_no_race_has_a_source(self):
        self.assertEqual(horse(races=[{}], sources={"*": "Fallback"}).source_for("races"), "Fallback")

    def test_own_source_first(self):
        h = horse(races=[{"source": "A"}], sources={"races": "Own"})
        self.assertEqual(h.source_for("races"), "Own")


class RoundTripTest(unittest.TestCase):
    def sample(self):
        return horse(country="GB", foaled=1984, complete_fields=["races"], races=[
            {"date": "1986-06", "race": "Test Stakes", "country": "gb", "grade": "Group 3",
             "distance_m": 1600, "finish": 1, "source": "Test fixture"},
        ])

    def test_json_round_trip(self):
        h = self.sample()
        self.assertEqual(Horse.from_dict(json.loads(json.dumps(h.to_dict()))), h)

    def test_store_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with HorseStore(os.path.join(tmp, "test.db")) as store:
                h = self.sample()
                store.upsert(h)
                self.assertEqual(store.get(h.id), h)

    def test_v01_row_without_races_loads(self):
        row = {
            "name": "Test Horse", "country": "GB", "foaled": 1990, "id": "test-horse-gb-1990",
            "sex": None, "nicknames": None, "trainers": None, "jockeys": None, "owners": None,
            "major_titles": None, "records": None, "raced_countries": None, "international": None,
            "results": ["W", "L"], "summary": {"starts": None, "wins": None, "seconds": None, "thirds": None},
            "complete_fields": ["results"], "sources": {"*": "Test"}, "notes": "",
        }
        h = Horse.from_dict(row)
        self.assertIsNone(h.races)
        self.assertEqual(h.results, ["W", "L"])


if __name__ == "__main__":
    unittest.main()
