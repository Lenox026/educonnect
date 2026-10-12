"""
Print a pass or fail report for data/generated/events.json.

The three checks are the data-quality rules for this project:

- every event has a student_id
- an attendance status is present, absent, or late
- a grade is from 0 up to that assignment's maximum

From the project root:

    python src/generator/produce_events.py
    python src/quality/check_events.py

A FAIL exits with status 1 so a later Airflow job can stop instead of loading bad rows.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "generated" / "events.json"
ALLOWED_STATUS = ("present", "absent", "late")


def main() -> None:
    events = read_events(DEFAULT_INPUT)
    checks = run_checks(events)
    print_report(DEFAULT_INPUT, events, checks)
    if any(check["problems"] > 0 for check in checks):
        raise SystemExit(1)


def read_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(
            f"Missing {path}. Create it first with:\n"
            "  python src/generator/produce_events.py"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("synthetic"):
        raise SystemExit("Refusing to check a file that is not marked synthetic.")
    events = pd.DataFrame(payload["events"])
    if events.empty:
        raise SystemExit("The file has no events.")
    return events


def run_checks(events: pd.DataFrame) -> list[dict]:
    """Count the rows that break each rule. Zero problems means that check passed."""
    attendance = events[events["event_type"] == "attendance"]
    grades = events[events["event_type"] == "grade"]

    missing_student = events["student_id"].isna()
    bad_status = attendance["status"].isna() | ~attendance["status"].isin(ALLOWED_STATUS)
    bad_score = (
        grades["score"].isna()
        | grades["max_score"].isna()
        | (grades["score"] < 0)
        | (grades["score"] > grades["max_score"])
    )

    return [
        {"check": "student_id is present", "problems": int(missing_student.sum())},
        {"check": "attendance status is valid", "problems": int(bad_status.sum())},
        {"check": "grade is between 0 and max_score", "problems": int(bad_score.sum())},
    ]


def print_report(path: Path, events: pd.DataFrame, checks: list[dict]) -> None:
    failed = any(check["problems"] > 0 for check in checks)
    print("EduConnect data quality report")
    print(f"File: {path}")
    print(f"Events: {len(events)}")
    print()
    print(f"{'Check':<36} {'Result':<8} Problems")
    for check in checks:
        result = "FAIL" if check["problems"] else "PASS"
        print(f"{check['check']:<36} {result:<8} {check['problems']}")
    print()
    print("Overall: FAIL" if failed else "Overall: PASS")


if __name__ == "__main__":
    main()
