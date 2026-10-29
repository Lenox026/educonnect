"""The API reads the newest lake folder, filters by class, and falls back to data/generated."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import reports


def write(folder: Path, name: str, data):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(data), encoding="utf-8")


class ReportTests(unittest.TestCase):
    def test_newest_date_folder_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            lake = Path(tmp) / "raw-events"
            write(lake / "2026" / "09" / "30", "weekly_attendance.json", [{"class_id": 1, "v": "old"}])
            write(lake / "2026" / "10" / "02", "weekly_attendance.json", [{"class_id": 1, "v": "new"}])
            data, origin = reports.read_report("weekly-attendance", lake, Path(tmp) / "none")
        self.assertEqual(data[0]["v"], "new")
        self.assertTrue(origin.endswith("raw-events/2026/10/02"))

    def test_falls_back_to_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated = Path(tmp) / "generated"
            write(generated, "grade_distribution.json", {"averages": [], "bands": []})
            data, origin = reports.read_report("grade-distribution", Path(tmp) / "no-lake", generated)
        self.assertEqual(origin, "generated")
        self.assertEqual(data, {"averages": [], "bands": []})

    def test_no_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                reports.read_report("weekly-attendance", Path(tmp) / "a", Path(tmp) / "b")

    def test_unknown_report_name(self):
        with self.assertRaises(KeyError):
            reports.read_report("nonsense")

    def test_class_filter_for_list_and_dict(self):
        rows = [{"class_id": 1}, {"class_id": 2}]
        self.assertEqual(reports.only_class(rows, 2), [{"class_id": 2}])
        self.assertEqual(reports.only_class({"averages": rows, "bands": rows}, 1), {"averages": [{"class_id": 1}], "bands": [{"class_id": 1}]})
        self.assertEqual(reports.only_class(rows, None), rows)


if __name__ == "__main__":
    unittest.main()
