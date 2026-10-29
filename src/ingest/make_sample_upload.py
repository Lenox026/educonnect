"""
Write a fake SFTP upload: data/sftp/grades_upload.csv.

docker-compose.yml mounts data/sftp as the server's upload folder, so writing
the file here is the same as the school office dropping it on the server.

The file re-marks a few grades from the generated school. Run the generator
first. Add --bad to include one score above the maximum, to show the check failing.

    python src/ingest/make_sample_upload.py
    python src/ingest/make_sample_upload.py --bad
"""

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "data" / "generated" / "events.json"
OUTPUT = ROOT / "data" / "sftp" / "grades_upload.csv"


def build_rows(payload: dict, count: int = 8, bad: bool = False) -> pd.DataFrame:
    """Re-mark the first few grades: each new score is a little higher, capped at the maximum."""
    grades = [event for event in payload["events"] if event["event_type"] == "grade"][:count]
    rows = []
    for event in grades:
        rows.append(
            {
                "student_id": event["student_id"],
                "assignment_id": event["assignment_id"],
                "score": min(event["score"] + 3, event["max_score"]),
                "graded_at": "2026-10-20T10:00:00+02:00",
            }
        )
    if bad and rows:
        last = grades[-1]
        rows[-1]["score"] = last["max_score"] + 10
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bad", action="store_true")
    args = parser.parse_args()
    if not EVENTS.exists():
        raise SystemExit("Missing data/generated/events.json. Run: python src/generator/produce_events.py")
    payload = json.loads(EVENTS.read_text(encoding="utf-8"))
    frame = build_rows(payload, bad=args.bad)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(frame)} re-marked grades to {OUTPUT}")


if __name__ == "__main__":
    main()
