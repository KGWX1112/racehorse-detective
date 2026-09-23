"""Evaluator findings. Milestone 4 adds a truth table per evaluator here."""

import unittest

from horsedetective.evaluators import Clue, Status
from horsedetective.models import Horse


def evaluate(clue_type, horse, **params):
    return Clue("test clue", clue_type, params).evaluate(horse)


class InternationalTest(unittest.TestCase):
    def test_raced_countries_with_unknown_foaling_country(self):
        f = evaluate("international", Horse(name="Test Horse", raced_countries=["IRE", "GB"]))
        self.assertEqual(f.status, Status.UNKNOWN)
        self.assertIn("Country of foaling is unknown", f.explanation)
        self.assertIn("IRE, GB", f.explanation)
        self.assertEqual(f.fields, ["raced_countries"])

    def test_flag_still_used_when_foaling_country_unknown(self):
        horse = Horse(name="Test Horse", raced_countries=["IRE"], international=True)
        f = evaluate("international", horse)
        self.assertEqual(f.status, Status.MATCH)
        self.assertEqual(f.fields, ["international"])

    def test_no_data(self):
        f = evaluate("international", Horse(name="Test Horse"))
        self.assertEqual(f.status, Status.UNKNOWN)
        self.assertEqual(f.explanation, "No record of where the horse raced.")


class RaceRecordTest(unittest.TestCase):
    # Derived codes: W, W (walkover), DH, L (disqualified), W.
    RACES = [
        {"finish": 1, "country": "GB"},
        {"outcome": "walkover", "country": "GB"},
        {"finish": 1, "outcome": "dead_heat", "country": "GB"},
        {"finish": 3, "outcome": "disqualified", "country": "FR"},
        {"finish": 1, "country": "GB"},
    ]

    def complete(self):
        return Horse(name="Test Horse", country="GB", races=self.RACES, complete_fields=["races"])

    def partial(self):
        return Horse(name="Test Horse", country="GB", races=self.RACES)

    def test_win_streak(self):
        f = evaluate("win_streak", self.complete(), min=3)
        self.assertEqual((f.status, f.fields), (Status.MATCH, ["races"]))
        self.assertEqual(evaluate("win_streak", self.complete(), min=4).status, Status.CONTRADICTION)
        self.assertEqual(evaluate("win_streak", self.partial(), min=4).status, Status.UNKNOWN)

    def test_loss_after_streak(self):
        self.assertEqual(evaluate("loss_after_streak", self.complete(), min=3).status, Status.MATCH)
        self.assertEqual(evaluate("loss_after_streak", self.complete(), min=4).status, Status.CONTRADICTION)
        self.assertEqual(evaluate("loss_after_streak", self.partial(), min=4).status, Status.UNKNOWN)

    def test_unbeaten_sees_loss_in_partial_list(self):
        f = evaluate("unbeaten", self.partial())
        self.assertEqual((f.status, f.fields), (Status.CONTRADICTION, ["races"]))

    def test_career_counts_need_complete_list(self):
        self.assertEqual(evaluate("career", self.complete(), field="starts", op="eq", n=5).status, Status.MATCH)
        self.assertEqual(evaluate("career", self.complete(), field="wins", op="eq", n=4).status, Status.MATCH)
        self.assertEqual(evaluate("career", self.partial(), field="starts", op="eq", n=5).status, Status.UNKNOWN)

    def test_complete_list_with_unknown_result_gives_starts_only(self):
        h = Horse(name="Test Horse", races=[{"finish": 1}, {}], complete_fields=["races"])
        self.assertEqual(evaluate("career", h, field="starts", op="eq", n=2).status, Status.MATCH)
        self.assertEqual(evaluate("career", h, field="wins", op="gte", n=1).status, Status.UNKNOWN)
        self.assertEqual(evaluate("win_streak", h, min=2).status, Status.UNKNOWN)

    def test_international_from_partial_list(self):
        f = evaluate("international", self.partial())
        self.assertEqual((f.status, f.fields), (Status.MATCH, ["races", "country"]))

    def test_international_complete_list_at_home(self):
        h = Horse(name="Test Horse", country="GB", races=[{"country": "GB"}], complete_fields=["races"])
        self.assertEqual(evaluate("international", h).status, Status.CONTRADICTION)

    def test_international_complete_list_with_missing_country(self):
        h = Horse(name="Test Horse", country="GB", races=[{"country": "GB"}, {}], complete_fields=["races"])
        f = evaluate("international", h)
        self.assertEqual(f.status, Status.UNKNOWN)
        self.assertIn("some races have no country", f.explanation)

    def test_international_races_without_countries(self):
        f = evaluate("international", Horse(name="Test Horse", country="GB", races=[{"finish": 1}]))
        self.assertEqual(f.explanation, "No record of where the horse raced.")

    def test_void_race_is_skipped(self):
        races = [{"finish": 1}, {"outcome": "void"}, {"finish": 1}, {"finish": 2}]
        h = Horse(name="Test Horse", races=races, complete_fields=["races"])
        self.assertEqual(evaluate("win_streak", h, min=2).status, Status.MATCH)
        self.assertEqual(evaluate("loss_after_streak", h, min=2).status, Status.MATCH)
        self.assertEqual(evaluate("career", h, field="starts", op="eq", n=3).status, Status.MATCH)

    def test_complete_list_with_unknown_result_counts_starts_without_void(self):
        h = Horse(name="Test Horse", races=[{"finish": 1}, {}, {"outcome": "void"}], complete_fields=["races"])
        self.assertEqual(evaluate("career", h, field="starts", op="eq", n=2).status, Status.MATCH)

    def test_race_abroad_adds_to_partial_raced_countries(self):
        h = Horse(name="Test Horse", country="GB", raced_countries=["GB"], races=[{"country": "FR"}])
        self.assertEqual(evaluate("international", h).status, Status.MATCH)


def race_horse(races, complete=True, **kw):
    kw.setdefault("name", "Test Horse")
    kw.setdefault("country", "GB")
    kw.setdefault("foaled", 2000)
    return Horse(races=races, complete_fields=["races"] if complete else [], **kw)


def race_status(h, **params):
    return evaluate("race", h, **params).status


G1_WIN = {"grade": "G1", "finish": 1, "country": "GB"}
G1_LOSS = {"grade": "Group 1", "finish": 4, "country": "GB"}
G2_WIN = {"grade": "G2", "finish": 1, "country": "GB"}
NO_GRADE_WIN = {"finish": 1, "country": "GB"}
NO_GRADE_LOSS = {"finish": 5, "country": "GB"}


class RaceQuantifierTest(unittest.TestCase):
    def test_won_any(self):
        self.assertEqual(race_status(race_horse([G2_WIN, G1_WIN]), quantifier="won_any", grade="G1"), Status.MATCH)
        self.assertEqual(race_status(race_horse([G2_WIN, G1_LOSS]), quantifier="won_any", grade="G1"), Status.CONTRADICTION)
        self.assertEqual(race_status(race_horse([G2_WIN, G1_LOSS], complete=False), quantifier="won_any", grade="G1"), Status.UNKNOWN)
        # An ungraded win might have been a G1.
        self.assertEqual(race_status(race_horse([NO_GRADE_WIN, G1_LOSS]), quantifier="won_any", grade="G1"), Status.UNKNOWN)
        # An ungraded loss cannot be a G1 win.
        self.assertEqual(race_status(race_horse([NO_GRADE_LOSS, G1_LOSS]), quantifier="won_any", grade="G1"), Status.CONTRADICTION)

    def test_lost_any(self):
        self.assertEqual(race_status(race_horse([G1_WIN, G1_LOSS]), quantifier="lost_any", grade="G1"), Status.MATCH)
        self.assertEqual(race_status(race_horse([G1_WIN, NO_GRADE_WIN]), quantifier="lost_any", grade="G1"), Status.CONTRADICTION)
        self.assertEqual(race_status(race_horse([G2_WIN]), quantifier="lost_any", grade="G1"), Status.CONTRADICTION)
        self.assertEqual(race_status(race_horse([G1_WIN], complete=False), quantifier="lost_any", grade="G1"), Status.UNKNOWN)

    def test_won_all(self):
        self.assertEqual(race_status(race_horse([G1_WIN, G2_WIN, NO_GRADE_WIN]), quantifier="won_all", grade="G1"), Status.MATCH)
        self.assertEqual(race_status(race_horse([G1_WIN, G1_LOSS], complete=False), quantifier="won_all", grade="G1"), Status.CONTRADICTION)
        self.assertEqual(race_status(race_horse([G1_WIN], complete=False), quantifier="won_all", grade="G1"), Status.UNKNOWN)
        # An ungraded loss might have been a G1 loss.
        self.assertEqual(race_status(race_horse([G1_WIN, NO_GRADE_LOSS]), quantifier="won_all", grade="G1"), Status.UNKNOWN)
        # The plan's table gives no CONTRADICTION when no race matches at all.
        self.assertEqual(race_status(race_horse([G2_WIN]), quantifier="won_all", grade="G1"), Status.UNKNOWN)

    def test_count(self):
        h = race_horse([G1_WIN, G1_WIN, G1_LOSS, G2_WIN])
        self.assertEqual(race_status(h, quantifier="count", grade="G1", op="eq", n=3), Status.MATCH)
        self.assertEqual(race_status(h, quantifier="count", grade="G1", result="won", op="eq", n=2), Status.MATCH)
        self.assertEqual(race_status(h, quantifier="count", grade="G1", result="won", op="gte", n=3), Status.CONTRADICTION)
        partial = race_horse([G1_WIN, G1_WIN], complete=False)
        self.assertEqual(race_status(partial, quantifier="count", grade="G1", op="gte", n=2), Status.MATCH)
        self.assertEqual(race_status(partial, quantifier="count", grade="G1", op="lte", n=1), Status.CONTRADICTION)
        self.assertEqual(race_status(partial, quantifier="count", grade="G1", op="eq", n=2), Status.UNKNOWN)
        uncertain = race_horse([G1_WIN, NO_GRADE_WIN])
        self.assertEqual(race_status(uncertain, quantifier="count", grade="G1", op="lte", n=2), Status.MATCH)
        self.assertEqual(race_status(uncertain, quantifier="count", grade="G1", op="eq", n=1), Status.UNKNOWN)

    def test_first_and_last(self):
        h = race_horse([G2_WIN, G1_LOSS, G1_WIN])
        self.assertEqual(race_status(h, quantifier="first", grade="G1", result="lost"), Status.MATCH)
        self.assertEqual(race_status(h, quantifier="first", grade="G1", result="won"), Status.CONTRADICTION)
        self.assertEqual(race_status(h, quantifier="last", grade="G1", result="won"), Status.MATCH)
        self.assertEqual(race_status(race_horse([G2_WIN]), quantifier="first", grade="G1", result="won"), Status.CONTRADICTION)
        self.assertEqual(race_status(race_horse([G1_LOSS], complete=False), quantifier="first", grade="G1", result="lost"), Status.UNKNOWN)
        # An ungraded race before the first G1 might itself be a G1.
        self.assertEqual(race_status(race_horse([NO_GRADE_WIN, G1_LOSS]), quantifier="first", grade="G1", result="lost"), Status.UNKNOWN)

    def test_no_race_records(self):
        self.assertEqual(race_status(Horse(name="Test Horse", results=["W"]), quantifier="won_any"), Status.UNKNOWN)

    def test_results_supply_unknown_race_result(self):
        h = Horse(name="Test Horse", results=["W"], races=[{"grade": "G1"}], complete_fields=["races"])
        self.assertEqual(race_status(h, quantifier="won_any", grade="G1"), Status.MATCH)


class RaceFilterTest(unittest.TestCase):
    def test_abroad(self):
        h = race_horse([{"country": "GB", "finish": 1}, {"country": "FR", "finish": 3}])
        self.assertEqual(race_status(h, quantifier="first", abroad=True, result="lost"), Status.MATCH)
        self.assertEqual(race_status(h, quantifier="won_all", abroad=False), Status.MATCH)
        unknown = race_horse([{"finish": 3}, {"country": "FR", "finish": 1}])
        self.assertEqual(race_status(unknown, quantifier="first", abroad=True, result="won"), Status.UNKNOWN)

    def test_year_range(self):
        h = race_horse([{"date": "2002", "finish": 1}, {"date": "2003-05", "finish": 2}])
        self.assertEqual(race_status(h, quantifier="won_any", year_min=2003), Status.CONTRADICTION)
        self.assertEqual(race_status(h, quantifier="won_any", year_max=2002), Status.MATCH)

    def test_race_name_and_venue(self):
        h = race_horse([{"race": "The Coolah Cup", "venue": "Coolah Park", "finish": 1}])
        self.assertEqual(race_status(h, quantifier="won_any", race="Coolah Cup"), Status.CONTRADICTION)
        self.assertEqual(race_status(h, quantifier="won_any", race="Coolah Cup", mode="contains"), Status.MATCH)
        self.assertEqual(race_status(h, quantifier="won_any", venue="Coolah"), Status.MATCH)

    def test_age_either_birthday_fits(self):
        # Foaled in AUS: 2 under its own birthday in March 2003, 3 under GB's.
        h = race_horse([{"date": "2003-03-01", "country": "GB", "finish": 1}], country="AUS")
        self.assertEqual(race_status(h, quantifier="won_any", age_min=3, age_max=3), Status.MATCH)
        self.assertEqual(race_status(h, quantifier="won_any", age_min=2, age_max=2), Status.MATCH)
        self.assertEqual(race_status(h, quantifier="won_any", age_min=4), Status.CONTRADICTION)

    def test_age_with_unknown_race_country_is_open(self):
        # 2 under the AUS birthday; the race country's birthday could give 3.
        h = race_horse([{"date": "2003-03-01", "finish": 1}], country="AUS")
        self.assertEqual(race_status(h, quantifier="won_any", age_min=3, age_max=3), Status.UNKNOWN)
        self.assertEqual(race_status(h, quantifier="won_any", age_min=2, age_max=2), Status.MATCH)

    def test_exclude_walkovers(self):
        h = race_horse([{"outcome": "walkover"}, {"finish": 1}, {"finish": 2}])
        self.assertEqual(race_status(h, quantifier="count", result="won", op="eq", n=2), Status.MATCH)
        self.assertEqual(race_status(h, quantifier="count", result="won", op="eq", n=1, exclude_walkovers=True), Status.MATCH)
        self.assertEqual(race_status(h, quantifier="first", result="won", exclude_walkovers=True), Status.MATCH)

    def test_void_race_is_not_counted(self):
        h = race_horse([{"outcome": "void", "grade": "G1"}, G1_WIN])
        self.assertEqual(race_status(h, quantifier="count", grade="G1", op="eq", n=1), Status.MATCH)

    def test_bad_params(self):
        h = race_horse([G1_WIN])
        for params in ({"quantifier": "most"}, {"quantifier": "won_any", "grd": "G1"},
                       {"quantifier": "first"}, {"quantifier": "count", "op": "eq"},
                       {"quantifier": "won_any", "result": "placed"}):
            with self.subTest(params=params):
                with self.assertRaises(ValueError):
                    evaluate("race", h, **params)


class TitleFromRacesTest(unittest.TestCase):
    def test_won_race_proves_title(self):
        h = race_horse([{"race": "Coolah Cup", "finish": 1}], major_titles=["Other Cup"])
        f = evaluate("title", h, text="Coolah Cup")
        self.assertEqual((f.status, f.fields), (Status.MATCH, ["races"]))

    def test_race_proves_title_missing_from_complete_title_list(self):
        h = Horse(name="Test Horse", major_titles=["Other Cup"], races=[{"race": "Coolah Cup", "finish": 1}],
                  complete_fields=["major_titles"])
        self.assertEqual(evaluate("title", h, text="Coolah Cup").status, Status.MATCH)

    def test_lost_race_does_not_prove_title(self):
        h = race_horse([{"race": "Coolah Cup", "finish": 2}])
        self.assertEqual(evaluate("title", h, text="Coolah Cup").status, Status.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
