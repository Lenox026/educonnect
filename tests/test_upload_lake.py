"""The S3 upload plans the right keys and sends every file in the date folder."""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import batch.upload_lake as up


class FakeS3:
    def __init__(self):
        self.calls = []

    def upload_file(self, filename, bucket, key):
        self.calls.append((Path(filename).name, bucket, key))


class UploadLakeTests(unittest.TestCase):
    def make_lake(self, folder, day):
        target = up.day_folder(day, Path(folder))
        target.mkdir(parents=True)
        for name in ("events.json", "manifest.json"):
            (target / name).write_text("{}\n", encoding="utf-8")

    def test_keys_use_the_date_layout(self):
        day = date(2026, 10, 15)
        with tempfile.TemporaryDirectory() as folder:
            self.make_lake(folder, day)
            pairs = up.plan_upload(day, Path(folder))
        keys = [key for _, key in pairs]
        self.assertEqual(
            keys,
            ["raw-events/2026/10/15/events.json", "raw-events/2026/10/15/manifest.json"],
        )

    def test_every_file_is_sent_to_the_bucket(self):
        day = date(2026, 10, 15)
        with tempfile.TemporaryDirectory() as folder:
            self.make_lake(folder, day)
            pairs = up.plan_upload(day, Path(folder))
            client = FakeS3()
            written = up.upload(client, "educonnect-data-lake-1", pairs)
        self.assertEqual(len(written), 2)
        self.assertTrue(all(call[1] == "educonnect-data-lake-1" for call in client.calls))

    def test_missing_folder_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(SystemExit):
                up.plan_upload(date(2026, 10, 15), Path(folder))


if __name__ == "__main__":
    unittest.main()
