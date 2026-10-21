"""The date-folder export copies the three generated reports."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import batch.export_lake as lake


class ExportLakeTests(unittest.TestCase):
    def test_copy_writes_the_three_reports(self):
        original = lake.GENERATED
        try:
            with tempfile.TemporaryDirectory() as folder:
                generated = Path(folder) / "generated"
                generated.mkdir()
                for name in lake.FILES:
                    (generated / name).write_text("{}\n", encoding="utf-8")
                lake.GENERATED = generated
                destination = Path(folder) / "2026" / "10" / "21"
                copied = lake.copy_reports(destination)
                self.assertEqual(copied, list(lake.FILES))
                self.assertEqual((destination / "events.json").read_text(encoding="utf-8"), "{}\n")
        finally:
            lake.GENERATED = original

    def test_missing_report_stops_the_export(self):
        original = lake.GENERATED
        try:
            with tempfile.TemporaryDirectory() as folder:
                lake.GENERATED = Path(folder)
                with self.assertRaises(SystemExit):
                    lake.copy_reports(Path(folder) / "out")
        finally:
            lake.GENERATED = original


if __name__ == "__main__":
    unittest.main()
