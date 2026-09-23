"""Command-line behavior that the benchmark cannot check."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from horsedetective.cli import main
from horsedetective.models import Horse
from horsedetective.store import HorseStore

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        main(list(argv))
    return out.getvalue(), err.getvalue()


class CliTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = os.path.join(tmp.name, "test.db")


class CluesTest(CliTestCase):
    def test_does_not_create_database(self):
        out, _ = run_cli("--db", self.db, "clues")
        self.assertIn("win_streak", out)
        self.assertFalse(os.path.exists(self.db))


class SetCompleteWarningTest(CliTestCase):
    HORSE_ID = "test-runner-gb-2000"

    def setUp(self):
        super().setUp()
        horse = Horse(name="Test Runner", country="GB", foaled=2000,
                      results=["W", "W", "L"], complete_fields=["results"])
        with HorseStore(self.db) as store:
            store.upsert(horse)

    def stored(self):
        with HorseStore(self.db) as store:
            return store.get(self.HORSE_ID)

    def test_warns_when_complete_field_is_replaced(self):
        _, err = run_cli("--db", self.db, "set", self.HORSE_ID, "results", "W L")
        self.assertIn("still marked complete", err)
        self.assertTrue(self.stored().is_complete("results"))

    def test_no_warning_with_incomplete(self):
        _, err = run_cli("--db", self.db, "set", self.HORSE_ID, "results", "W L", "--incomplete")
        self.assertEqual(err, "")
        self.assertFalse(self.stored().is_complete("results"))

    def test_no_warning_with_complete(self):
        _, err = run_cli("--db", self.db, "set", self.HORSE_ID, "results", "W L", "--complete")
        self.assertEqual(err, "")

    def test_no_warning_when_value_unchanged(self):
        _, err = run_cli("--db", self.db, "set", self.HORSE_ID, "results", "w w l")
        self.assertEqual(err, "")

    def test_no_warning_for_source_only(self):
        _, err = run_cli("--db", self.db, "set", self.HORSE_ID, "results", "--source", "Test source")
        self.assertEqual(err, "")


class RacesCliTest(CliTestCase):
    HORSE_ID = "test-runner-gb-2000"

    def setUp(self):
        super().setUp()
        with HorseStore(self.db) as store:
            store.upsert(Horse(name="Test Runner", country="GB", foaled=2000,
                               races=[{"finish": 1}, {"finish": 2}]))

    def test_value_is_refused(self):
        with self.assertRaises(SystemExit) as cm:
            run_cli("--db", self.db, "set", self.HORSE_ID, "races", "[]")
        self.assertIn("use 'import'", str(cm.exception.code))

    def test_mark_complete(self):
        run_cli("--db", self.db, "set", self.HORSE_ID, "races", "--complete")
        with HorseStore(self.db) as store:
            self.assertTrue(store.get(self.HORSE_ID).is_complete("races"))

    def test_list_counts_race_records(self):
        out, _ = run_cli("--db", self.db, "list")
        self.assertIn("2 race records", out)


class ExportImportTest(CliTestCase):
    def test_seed_data_round_trips(self):
        tmp = os.path.dirname(self.db)
        first, second = os.path.join(tmp, "first.json"), os.path.join(tmp, "second.json")
        run_cli("--db", self.db, "import", os.path.join(REPO_ROOT, "data", "seed_horses.json"))
        run_cli("--db", self.db, "export", first)
        other_db = os.path.join(tmp, "other.db")
        run_cli("--db", other_db, "import", first)
        run_cli("--db", other_db, "export", second)
        with open(first, encoding="utf-8") as a, open(second, encoding="utf-8") as b:
            self.assertEqual(json.load(a), json.load(b))


class TimelineTest(CliTestCase):
    def setUp(self):
        super().setUp()
        run_cli("--db", self.db, "import", os.path.join(REPO_ROOT, "data", "seed_horses.json"))

    def timeline(self, horse_id):
        out, _ = run_cli("--db", self.db, "timeline", horse_id)
        return out

    def row(self, out, number):
        lines = out.splitlines()
        start = next(i for i, line in enumerate(lines) if line.split()[:1] == ["#"])
        return next(line.split() for line in lines[start + 1:] if line.split()[:1] == [str(number)])

    def test_race_records(self):
        out = self.timeline("copper-wren-gb-1984")
        self.assertIn("11 race records, marked complete.", out)
        self.assertIn("GB official birthday, 1 January", out)
        # date, age, and running streak through the walkover, void race, and disqualification
        self.assertEqual(self.row(out, 3)[:3] + self.row(out, 3)[-2:], ["3", "1986-08", "2", "walkover", "2"])
        self.assertEqual(self.row(out, 5)[-2:], ["void", "3"])
        self.assertEqual(self.row(out, 7)[-1], "5")
        self.assertIn("2nd of 10 (disqualified)", out)
        self.assertEqual(self.row(out, 8)[-1], "0")
        self.assertEqual(self.row(out, 11)[2], "4")
        self.assertIn("sources: races: V0.2 test data (fictional)", out)

    def test_partial_list_is_flagged(self):
        out = self.timeline("juniper-vale-fr-1966")
        self.assertIn("not marked complete", out)
        self.assertIn("counts only the recorded races", out)

    def test_results_only(self):
        out = self.timeline("silver-comet-jpn-2001")
        self.assertIn("no dates or race details", out)
        self.assertEqual(self.row(out, 7), ["7", "W", "7"])
        self.assertEqual(self.row(out, 8), ["8", "L", "0"])

    def test_no_sequence(self):
        out = self.timeline("old-tempest-gb-1871")
        self.assertIn("Career summary: 30 starts, 30 wins.", out)
        self.assertIn("No race records or results recorded.", out)

    def test_unknown_result_makes_streak_a_lower_bound(self):
        with HorseStore(self.db) as store:
            store.upsert(Horse(name="Test Runner", country="AUS", foaled=2000, races=[
                {"date": "2002-09", "country": "AUS", "finish": 1},
                {"date": "2003-03-01", "country": "GB", "finish": 1},
                {"date": "2003-06", "country": "AUS"},
                {"date": "2003-10", "country": "AUS", "finish": 1},
            ]))
        out = self.timeline("test-runner-aus-2000")
        self.assertEqual(self.row(out, 2)[2], "2/3")
        self.assertEqual(self.row(out, 3)[-2:], ["?", "?"])
        self.assertEqual(self.row(out, 4)[-1], "1+")

    def test_results_fill_unknown_race_results(self):
        with HorseStore(self.db) as store:
            store.upsert(Horse(name="Test Runner", country="GB", foaled=2000, results=["W", "W"],
                               races=[{"finish": 1}, {"race": "Result not in the race record"}]))
        self.assertEqual(self.row(self.timeline("test-runner-gb-2000"), 2)[-1], "2")


class BrokenPipeTest(CliTestCase):
    def test_closed_reader_gives_no_traceback(self):
        # Closing the read end before the child writes makes its first flush
        # fail, as happens when output is piped to `head`.
        proc = subprocess.Popen(
            [sys.executable, "-m", "horsedetective", "--db", self.db, "clues"],
            cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        proc.stdout.close()
        err = proc.stderr.read().decode()
        proc.stderr.close()
        self.assertEqual(proc.wait(timeout=30), 1)
        self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
