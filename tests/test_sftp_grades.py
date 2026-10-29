"""The SFTP upload check accepts good rows and rejects the bad ones, with line numbers."""

import json
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ingest.make_sample_upload import build_rows
from ingest.sftp_grades import validate_upload

MAX_SCORES = {501: 25, 502: 30}
STUDENTS = {1001, 1002}


def frame(rows):
    return pd.DataFrame(rows, columns=["student_id", "assignment_id", "score", "graded_at"])


class SftpGradeTests(unittest.TestCase):
    def test_good_upload_has_no_problems(self):
        rows = [[1001, 501, 20, "2026-10-20T10:00:00+02:00"], [1002, 502, 30, "2026-10-20T10:00:00+02:00"]]
        self.assertEqual(validate_upload(frame(rows), MAX_SCORES, STUDENTS), [])

    def test_score_above_maximum_is_named_by_line(self):
        problems = validate_upload(frame([[1001, 501, 26, "x"]]), MAX_SCORES, STUDENTS)
        self.assertEqual(problems, ["line 2: score 26 is outside 0..25"])

    def test_unknown_learner_and_assignment(self):
        problems = validate_upload(frame([[9999, 501, 5, "x"], [1001, 777, 5, "x"]]), MAX_SCORES, STUDENTS)
        self.assertIn("line 2: no learner with student_id 9999", problems)
        self.assertIn("line 3: no assignment 777", problems)

    def test_empty_value_and_text_score(self):
        problems = validate_upload(frame([[1001, 501, None, "x"], [1001, 501, "high", "x"]]), MAX_SCORES, STUDENTS)
        self.assertIn("line 2: an empty value", problems)
        self.assertIn("line 3: student_id, assignment_id, and score must be numbers", problems)

    def test_missing_column_and_empty_file(self):
        self.assertEqual(
            validate_upload(pd.DataFrame({"student_id": [1]}), MAX_SCORES, STUDENTS)[0],
            "missing column: assignment_id",
        )
        self.assertEqual(validate_upload(frame([]), MAX_SCORES, STUDENTS), ["the file has no rows"])

    def test_sample_upload_passes_and_bad_flag_fails(self):
        events = Path(__file__).resolve().parents[1] / "data" / "generated" / "events.json"
        if not events.exists():
            self.skipTest("generated events.json not present")
        payload = json.loads(events.read_text(encoding="utf-8"))
        max_scores = {a["assignment_id"]: a["max_score"] for a in payload["assignments"]}
        students = {s["student_id"] for s in payload["students"]}
        self.assertEqual(validate_upload(build_rows(payload), max_scores, students), [])
        self.assertEqual(len(validate_upload(build_rows(payload, bad=True), max_scores, students)), 1)


if __name__ == "__main__":
    unittest.main()
