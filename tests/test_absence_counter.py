"""The absence counter turns Debezium changes into +1, -1, or nothing."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from streaming.absence_counter import day_text, delta_for, parse_message

DAY = 20738  # 2026-10-12 as Debezium sends it: days since 1970-01-01


def row(status, class_id=10, day=DAY):
    return {"student_id": 1001, "class_id": class_id, "attendance_date": day, "status": status}


class AbsenceCounterTests(unittest.TestCase):
    def test_new_absence_adds_one(self):
        self.assertEqual(delta_for({"op": "c", "before": None, "after": row("absent")}), (day_text(DAY), 10, 1))

    def test_new_present_mark_changes_nothing(self):
        self.assertIsNone(delta_for({"op": "c", "before": None, "after": row("present")}))

    def test_snapshot_rows_count_like_inserts(self):
        self.assertEqual(delta_for({"op": "r", "before": None, "after": row("absent")})[2], 1)

    def test_absent_corrected_to_present_removes_one(self):
        change = {"op": "u", "before": row("absent"), "after": row("present")}
        self.assertEqual(delta_for(change), (day_text(DAY), 10, -1))

    def test_present_changed_to_absent_adds_one(self):
        change = {"op": "u", "before": row("present"), "after": row("absent")}
        self.assertEqual(delta_for(change)[2], 1)

    def test_absent_to_absent_update_changes_nothing(self):
        self.assertIsNone(delta_for({"op": "u", "before": row("absent"), "after": row("absent")}))

    def test_deleting_an_absence_removes_one(self):
        self.assertEqual(delta_for({"op": "d", "before": row("absent"), "after": None})[2], -1)

    def test_tombstone_and_unknown_ops_are_ignored(self):
        self.assertIsNone(delta_for(None))
        self.assertIsNone(delta_for({"op": "t"}))

    def test_date_comes_from_days_since_1970(self):
        self.assertEqual(day_text(0), "1970-01-01")
        self.assertEqual(day_text(20738), "2026-10-12")
        self.assertEqual(day_text("2026-10-12"), "2026-10-12")

    def test_message_may_be_wrapped_in_a_payload(self):
        plain = {"op": "c", "after": row("absent")}
        self.assertEqual(parse_message(json.dumps(plain).encode()), plain)
        self.assertEqual(parse_message(json.dumps({"schema": {}, "payload": plain}).encode()), plain)
        self.assertIsNone(parse_message(None))


if __name__ == "__main__":
    unittest.main()
