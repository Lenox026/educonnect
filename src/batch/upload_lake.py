"""
Upload today's date folder to the S3 data lake.

export_lake.py writes data/lake/raw-events/YYYY/MM/DD/ on this laptop. This
script copies that folder to the same path in the private bucket the SAM stack
creates:

    s3://educonnect-data-lake-<account id>/raw-events/YYYY/MM/DD/

From the project root, signed in to the AWS account you deployed to:

    python src/batch/upload_lake.py
    python src/batch/upload_lake.py --bucket educonnect-data-lake-123456789012
    python src/batch/upload_lake.py --day 2026-10-15

Without --bucket the script asks AWS for your account id and builds the name.
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
LAKE = ROOT / "data" / "lake" / "raw-events"
SCHOOL_ZONE = ZoneInfo("Africa/Johannesburg")


def day_folder(day: date, lake: Path = LAKE) -> Path:
    return lake / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.day:02d}"


def s3_prefix(day: date) -> str:
    return f"raw-events/{day.year:04d}/{day.month:02d}/{day.day:02d}"


def plan_upload(day: date, lake: Path = LAKE) -> list[tuple[Path, str]]:
    """Return (local file, S3 key) pairs for one day. Stops if the folder is missing."""
    folder = day_folder(day, lake)
    if not folder.is_dir():
        raise SystemExit(
            f"No folder for {day.isoformat()} at {folder}.\n"
            "Create it first with: python src/batch/export_lake.py"
        )
    files = sorted(path for path in folder.iterdir() if path.is_file())
    if not files:
        raise SystemExit(f"{folder} is empty. Nothing to upload.")
    prefix = s3_prefix(day)
    return [(path, f"{prefix}/{path.name}") for path in files]


def upload(client, bucket: str, pairs: list[tuple[Path, str]]) -> list[str]:
    """Upload each file with an S3 client. Returns the keys that were written."""
    keys = []
    for path, key in pairs:
        client.upload_file(str(path), bucket, key)
        keys.append(key)
    return keys


def default_bucket() -> str:
    import boto3  # imported here so the planning code works without AWS installed

    account = boto3.client("sts").get_caller_identity()["Account"]
    return f"educonnect-data-lake-{account}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--bucket", help="Data-lake bucket. Default: educonnect-data-lake-<account id>")
    parser.add_argument("--day", help="Date folder to upload, YYYY-MM-DD. Default: today in South Africa.")
    args = parser.parse_args()

    day = date.fromisoformat(args.day) if args.day else datetime.now(SCHOOL_ZONE).date()
    pairs = plan_upload(day)

    import boto3

    bucket = args.bucket or default_bucket()
    keys = upload(boto3.client("s3"), bucket, pairs)
    print(f"Uploaded {len(keys)} files to s3://{bucket}/{s3_prefix(day)}/")
    for key in keys:
        print(f"  {key}")


if __name__ == "__main__":
    sys.exit(main())
