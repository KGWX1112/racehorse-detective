"""Command-line behavior that the benchmark cannot check."""

import contextlib
import io
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
