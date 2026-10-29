"""
Read the batch reports so the API can serve them.

The nightly pipeline copies weekly_attendance.json and grade_distribution.json
into data/lake/raw-events/YYYY/MM/DD/. The API reads the newest date folder,
which is the same layout the S3 data lake uses. If there is no lake folder yet
it falls back to data/generated/.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAKE = ROOT / "data" / "lake" / "raw-events"
GENERATED = ROOT / "data" / "generated"

REPORTS = {
    "weekly-attendance": "weekly_attendance.json",
    "grade-distribution": "grade_distribution.json",
}


def latest_lake_folder(lake: Path = LAKE) -> Path | None:
    """The newest YYYY/MM/DD folder. Folder names sort in date order."""
    if not lake.is_dir():
        return None
    days = [
        path
        for year in lake.iterdir() if year.is_dir()
        for month in year.iterdir() if month.is_dir()
        for path in month.iterdir() if path.is_dir()
    ]
    days.sort(key=lambda path: (path.parent.parent.name, path.parent.name, path.name))
    return days[-1] if days else None


def read_report(name: str, lake: Path = LAKE, generated: Path = GENERATED):
    """Return (report data, where it came from). Raises FileNotFoundError if there is no file."""
    if name not in REPORTS:
        raise KeyError(name)
    filename = REPORTS[name]
    folder = latest_lake_folder(lake)
    if folder is not None and (folder / filename).exists():
        origin = f"lake {folder.relative_to(lake.parent)}"
        return json.loads((folder / filename).read_text(encoding="utf-8")), origin
    fallback = generated / filename
    if fallback.exists():
        return json.loads(fallback.read_text(encoding="utf-8")), "generated"
    raise FileNotFoundError(filename)


def only_class(report, class_id: int | None):
    """Keep one class. Weekly attendance is a list. Grade distribution is a dict of lists."""
    if class_id is None:
        return report
    if isinstance(report, list):
        return [row for row in report if row.get("class_id") == class_id]
    return {
        key: [row for row in rows if row.get("class_id") == class_id]
        for key, rows in report.items()
    }
