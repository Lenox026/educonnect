"""
Weekly attendance rate per class, using Spark on this laptop.

Present and late both count as attended. Absent does not.
A school week starts on Monday.

From the project root:

    python src/generator/produce_events.py
    python src/batch/weekly_attendance.py

The script writes data/generated/weekly_attendance.json. That folder is gitignored.
"""

import json
import os
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

ROOT = Path(__file__).resolve().parents[2]
EVENTS_PATH = ROOT / "data" / "generated" / "events.json"
OUTPUT_PATH = ROOT / "data" / "generated" / "weekly_attendance.json"


def main() -> None:
    payload = read_payload(EVENTS_PATH)
    spark = start_spark()
    summary = weekly_attendance(spark, payload)
    rows = [normalise(row.asDict()) for row in summary.collect()]
    spark.stop()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} weekly attendance rows to {OUTPUT_PATH}")
    for row in rows[:5]:
        print(
            f"  {row['week_start']}  {row['class_name']}: "
            f"{row['attended']}/{row['marks']} ({row['attendance_rate']})"
        )


def read_payload(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Missing {path}. Create it first with:\n"
            "  python src/generator/produce_events.py"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("synthetic"):
        raise SystemExit("Refusing to process a file that is not marked synthetic.")
    return payload


def start_spark() -> SparkSession:
    """Local mode uses this machine only. There is no Spark cluster."""
    use_java_17()
    spark = (
        SparkSession.builder.appName("educonnect-weekly-attendance")
        .master("local[*]")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "Africa/Johannesburg")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def use_java_17() -> None:
    """Spark 3.5 runs on Java 17. Leave JAVA_HOME alone when it is already set."""
    if os.environ.get("JAVA_HOME"):
        return
    for candidate in (
        Path("/usr/lib/jvm/java-17-openjdk-amd64"),
        Path("/usr/lib/jvm/java-17-openjdk-arm64"),
    ):
        if candidate.exists():
            os.environ["JAVA_HOME"] = str(candidate)
            return


def weekly_attendance(spark: SparkSession, payload: dict):
    """One row per class per Monday-start week."""
    attendance_rows = [
        event for event in payload["events"] if event["event_type"] == "attendance"
    ]
    attendance = spark.createDataFrame(attendance_rows)
    classes = spark.createDataFrame(payload["classes"])

    # Spark numbers Sunday as 1. Shift back so the week label is that Monday.
    week_start = F.date_sub(F.col("day"), (F.dayofweek("day") + 5) % 7)
    attended = F.when(F.col("status").isin("present", "late"), 1).otherwise(0)

    grouped = (
        attendance.withColumn("day", F.to_date("attendance_date"))
        .withColumn("week_start", week_start)
        .withColumn("attended", attended)
        .groupBy("class_id", "week_start")
        .agg(
            F.count("*").alias("marks"),
            F.sum("attended").alias("attended"),
        )
        .withColumn("attendance_rate", F.round(F.col("attended") / F.col("marks"), 3))
    )
    return (
        grouped.join(
            classes.select("class_id", "class_name", "subject", "grade_level"),
            "class_id",
        )
        .orderBy("week_start", "class_id")
        .select(
            "week_start",
            "class_id",
            "class_name",
            "subject",
            "grade_level",
            "marks",
            "attended",
            "attendance_rate",
        )
    )


def normalise(row: dict) -> dict:
    """JSON cannot store Spark date objects, so write the week as text."""
    row["week_start"] = row["week_start"].isoformat()
    row["attended"] = int(row["attended"])
    row["marks"] = int(row["marks"])
    row["attendance_rate"] = float(row["attendance_rate"])
    return row


if __name__ == "__main__":
    main()
