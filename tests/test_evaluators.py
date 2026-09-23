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

    def test_race_abroad_adds_to_partial_raced_countries(self):
        h = Horse(name="Test Horse", country="GB", raced_countries=["GB"], races=[{"country": "FR"}])
        self.assertEqual(evaluate("international", h).status, Status.MATCH)


if __name__ == "__main__":
    unittest.main()
