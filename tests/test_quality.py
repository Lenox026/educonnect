"""The three Pandas rules: student id, attendance status, and grade range."""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quality.check_events import run_checks


def frame(rows):
    return pd.DataFrame(rows)


class QualityTests(unittest.TestCase):
    def test_valid_events_pass(self):
        events = frame(
            [
                {
                    "event_type": "attendance",
                    "student_id": 1001,
                    "status": "late",
                    "score": None,
                    "max_score": None,
                },
                {
                    "event_type": "grade",
                    "student_id": 1001,
                    "status": None,
                    "score": 18,
                    "max_score": 20,
                },
            ]
        )
        problems = {check["check"]: check["problems"] for check in run_checks(events)}
        self.assertEqual(problems["student_id is present"], 0)
        self.assertEqual(problems["attendance status is valid"], 0)
        self.assertEqual(problems["grade is between 0 and max_score"], 0)

    def test_broken_rows_are_counted(self):
        events = frame(
            [
                {
                    "event_type": "attendance",
                    "student_id": None,
                    "status": "excused",
                    "score": None,
                    "max_score": None,
                },
                {
                    "event_type": "grade",
                    "student_id": 1002,
                    "status": None,
                    "score": 30,
                    "max_score": 20,
                },
            ]
        )
        problems = {check["check"]: check["problems"] for check in run_checks(events)}
        self.assertEqual(problems["student_id is present"], 1)
        self.assertEqual(problems["attendance status is valid"], 1)
        self.assertEqual(problems["grade is between 0 and max_score"], 1)


if __name__ == "__main__":
    unittest.main()
