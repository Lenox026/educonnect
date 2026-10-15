"""
Copy the raw events and the Spark reports into a date folder.

The folder matches the layout the project will use on S3:

    s3://educonnect-data-lake/raw-events/YYYY/MM/DD/

On this laptop the same path is:

    data/lake/raw-events/YYYY/MM/DD/

Run the generator and both Spark jobs first, then:

    python src/batch/export_lake.py

The data/lake folder is gitignored.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "data" / "generated"
LAKE = ROOT / "data" / "lake" / "raw-events"
SCHOOL_ZONE = ZoneInfo("Africa/Johannesburg")

FILES = (
    "events.json",
    "weekly_attendance.json",
    "grade_distribution.json",
)


def main() -> None:
    day = datetime.now(SCHOOL_ZONE).date()
    destination = LAKE / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.day:02d}"
    copied = copy_reports(destination)
    manifest = {
        "exported_on": day.isoformat(),
        "layout": "raw-events/YYYY/MM/DD/",
        "files": copied,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Exported {len(copied)} files to {destination}")
    for name in copied:
        print(f"  {name}")


def copy_reports(destination: Path) -> list[str]:
    missing = [name for name in FILES if not (GENERATED / name).exists()]
    if missing:
        raise SystemExit(
            "Missing files in data/generated:\n"
            + "\n".join(f"  {name}" for name in missing)
            + "\nCreate them first with:\n"
            "  python src/generator/produce_events.py\n"
            "  python src/batch/weekly_attendance.py\n"
            "  python src/batch/grade_distribution.py"
        )
    destination.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(GENERATED / name, destination / name)
    return list(FILES)


if __name__ == "__main__":
    main()
