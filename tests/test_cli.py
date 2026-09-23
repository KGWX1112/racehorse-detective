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
