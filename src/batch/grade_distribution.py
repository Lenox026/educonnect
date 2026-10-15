"""
Grade distribution per class, using Spark on this laptop.

Each score is turned into a percentage of that assignment's maximum, so a
25-mark quiz and a 50-mark test can be compared. The bands are:

    0-49, 50-59, 60-69, 70-79, 80-100

From the project root:

    python src/generator/produce_events.py
    python src/batch/grade_distribution.py

The script writes data/generated/grade_distribution.json. That folder is gitignored.
"""

import json
import os
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

ROOT = Path(__file__).resolve().parents[2]
EVENTS_PATH = ROOT / "data" / "generated" / "events.json"
OUTPUT_PATH = ROOT / "data" / "generated" / "grade_distribution.json"
BANDS = (
    ("0-49", 1),
    ("50-59", 2),
    ("60-69", 3),
    ("70-79", 4),
    ("80-100", 5),
)


def main() -> None:
    payload = read_payload(EVENTS_PATH)
    spark = start_spark()
    averages, bands = grade_distribution(spark, payload)
    report = {
        "averages": [normalise_average(row.asDict()) for row in averages.collect()],
        "bands": [normalise_band(row.asDict()) for row in bands.collect()],
    }
    spark.stop()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote grade distribution for {len(report['averages'])} classes to {OUTPUT_PATH}")
    for row in report["averages"][:5]:
        print(f"  {row['class_name']}: average {row['average_percent']}% from {row['grades']} grades")


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
        SparkSession.builder.appName("educonnect-grade-distribution")
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


def grade_distribution(spark: SparkSession, payload: dict):
    """Average percentage per class, and how many grades fall in each band."""
    grade_rows = [event for event in payload["events"] if event["event_type"] == "grade"]
    grades = spark.createDataFrame(grade_rows)
    classes = spark.createDataFrame(payload["classes"]).select(
        "class_id", "class_name", "subject", "grade_level"
    )
    band_labels = spark.createDataFrame(BANDS, ["band", "band_order"])

    graded = grades.withColumn(
        "percent",
        F.round(F.col("score") / F.col("max_score") * 100, 1),
    ).withColumn(
        "band",
        F.when(F.col("percent") < 50, "0-49")
        .when(F.col("percent") < 60, "50-59")
        .when(F.col("percent") < 70, "60-69")
        .when(F.col("percent") < 80, "70-79")
        .otherwise("80-100"),
    )

    averages = (
        graded.groupBy("class_id")
        .agg(
            F.count("*").alias("grades"),
            F.round(F.avg("percent"), 1).alias("average_percent"),
        )
        .join(classes, "class_id")
        .orderBy("class_id")
        .select(
            "class_id",
            "class_name",
            "subject",
            "grade_level",
            "grades",
            "average_percent",
        )
    )

    counted = graded.groupBy("class_id", "band").agg(F.count("*").alias("grades"))
    # Every class gets all five bands, including bands with zero grades.
    bands = (
        classes.crossJoin(band_labels)
        .join(counted, ["class_id", "band"], "left")
        .fillna({"grades": 0})
        .withColumn(
            "share",
            F.round(
                F.col("grades") / F.sum("grades").over(Window.partitionBy("class_id")),
                3,
            ),
        )
        .orderBy("class_id", "band_order")
        .select("class_id", "class_name", "subject", "band", "grades", "share")
    )
    return averages, bands


def normalise_average(row: dict) -> dict:
    row["grades"] = int(row["grades"])
    row["average_percent"] = float(row["average_percent"])
    return row


def normalise_band(row: dict) -> dict:
    row["grades"] = int(row["grades"])
    row["share"] = float(row["share"] or 0)
    return row


if __name__ == "__main__":
    main()
