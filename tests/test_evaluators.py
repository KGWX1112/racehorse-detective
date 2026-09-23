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


if __name__ == "__main__":
    unittest.main()
