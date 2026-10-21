"""Spark counts present and late as attended, and groups grades into five bands."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from batch.grade_distribution import grade_distribution
from batch.weekly_attendance import start_spark, weekly_attendance


CLASS_ROW = {
    "class_id": 10,
    "class_name": "Grade 10 Mathematics",
    "subject": "Mathematics",
    "grade_level": 10,
}


class SparkReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = start_spark()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_present_and_late_count_as_attended(self):
        payload = {
            "classes": [CLASS_ROW],
            "events": [
                mark(1001, "2026-10-20", "present"),
                mark(1002, "2026-10-20", "late"),
                mark(1003, "2026-10-20", "absent"),
                mark(1004, "2026-10-21", "present"),
            ],
        }
        rows = [row.asDict() for row in weekly_attendance(self.spark, payload).collect()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows[0]["week_start"]), "2026-10-19")
        self.assertEqual(int(rows[0]["marks"]), 4)
        self.assertEqual(int(rows[0]["attended"]), 3)
        self.assertAlmostEqual(float(rows[0]["attendance_rate"]), 0.75)

    def test_grades_fall_into_bands(self):
        payload = {
            "classes": [CLASS_ROW],
            "events": [
                grade(1001, 40, 100),
                grade(1002, 80, 100),
            ],
        }
        averages, bands = grade_distribution(self.spark, payload)
        average = averages.collect()[0].asDict()
        self.assertEqual(int(average["grades"]), 2)
        self.assertAlmostEqual(float(average["average_percent"]), 60.0)

        by_band = {row["band"]: row.asDict() for row in bands.collect()}
        self.assertEqual(set(by_band), {"0-49", "50-59", "60-69", "70-79", "80-100"})
        self.assertEqual(int(by_band["0-49"]["grades"]), 1)
        self.assertEqual(int(by_band["80-100"]["grades"]), 1)
        self.assertEqual(int(by_band["50-59"]["grades"]), 0)
        self.assertAlmostEqual(float(by_band["0-49"]["share"]), 0.5)
        self.assertAlmostEqual(float(by_band["80-100"]["share"]), 0.5)


def mark(student_id, day, status):
    return {
        "event_type": "attendance",
        "student_id": student_id,
        "class_id": 10,
        "attendance_date": day,
        "status": status,
    }


def grade(student_id, score, max_score):
    return {
        "event_type": "grade",
        "student_id": student_id,
        "class_id": 10,
        "score": score,
        "max_score": max_score,
    }


if __name__ == "__main__":
    unittest.main()
