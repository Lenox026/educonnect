"""
Load data/generated/events.json into PostgreSQL.

The script checks the events, rebuilds the tables from sql/schema.sql, then
inserts teachers, learners, classes, and the attendance and grade events.

From the project root, after Docker is running:

    docker compose up -d
    python src/generator/produce_events.py
    python src/loader/load_events.py

Running it again replaces the school. That is safe because the data is fake.
"""

import json
import sys
import time
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from database import connect  # noqa: E402

DEFAULT_INPUT = ROOT / "data" / "generated" / "events.json"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"
ALLOWED_STATUS = {"present", "absent", "late"}


def main() -> None:
    payload = read_payload(DEFAULT_INPUT)
    check_events(payload)
    wait_for_database()
    with connect() as conn:
        apply_schema(conn, SCHEMA_PATH)
        insert_school(conn, payload)
    print_summary(payload)


def read_payload(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Missing {path}. Create it first with:\n"
            "  python src/generator/produce_events.py"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("synthetic"):
        raise SystemExit("Refusing to load a file that is not marked synthetic.")
    return payload


def check_events(payload: dict) -> None:
    """Stop before any insert if a row would break the table rules."""
    enrolled = {(row["student_id"], row["class_id"]) for row in payload["enrollments"]}
    problems = []

    for event in payload["events"]:
        pair = (event["student_id"], event["class_id"])
        if pair not in enrolled:
            problems.append(f"{event['event_id']} is for a learner who is not in that class")
            continue
        if event["event_type"] == "attendance" and event["status"] not in ALLOWED_STATUS:
            problems.append(f"{event['event_id']} has status {event['status']!r}")
        if event["event_type"] == "grade":
            score = event["score"]
            max_score = event["max_score"]
            if score < 0 or score > max_score:
                problems.append(
                    f"{event['event_id']} has score {score}, which is outside 0..{max_score}"
                )

    if problems:
        preview = "\n".join(problems[:5])
        raise SystemExit(f"Found {len(problems)} bad events. Nothing was loaded.\n{preview}")


def wait_for_database() -> None:
    deadline = time.time() + 30
    last_error = None
    while time.time() < deadline:
        try:
            with connect() as conn:
                conn.execute("SELECT 1")
            return
        except psycopg.OperationalError as error:
            last_error = error
            print("Waiting for PostgreSQL...")
            time.sleep(2)
    raise SystemExit(
        "Could not connect to PostgreSQL. Start it with:\n"
        "  docker compose up -d\n"
        f"{last_error}"
    )


def apply_schema(conn, path: Path) -> None:
    """Run sql/schema.sql. PostgreSQL accepts one statement at a time."""
    statements = []
    current = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("--"):
            continue
        current.append(line)
        if line.strip().endswith(";"):
            statement = "\n".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)


def insert_school(conn, payload: dict) -> None:
    attendance = [event for event in payload["events"] if event["event_type"] == "attendance"]
    grades = [event for event in payload["events"] if event["event_type"] == "grade"]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO teachers (teacher_id, teacher_name)
            VALUES (%(teacher_id)s, %(teacher_name)s)
            """,
            payload["teachers"],
        )
        cur.executemany(
            """
            INSERT INTO students (student_id, first_name, last_name, grade_level)
            VALUES (%(student_id)s, %(first_name)s, %(last_name)s, %(grade_level)s)
            """,
            payload["students"],
        )
        cur.executemany(
            """
            INSERT INTO classes (class_id, subject, class_name, grade_level, teacher_id)
            VALUES (%(class_id)s, %(subject)s, %(class_name)s, %(grade_level)s, %(teacher_id)s)
            """,
            payload["classes"],
        )
        cur.executemany(
            """
            INSERT INTO enrollments (student_id, class_id)
            VALUES (%(student_id)s, %(class_id)s)
            """,
            payload["enrollments"],
        )
        cur.executemany(
            """
            INSERT INTO assignments (assignment_id, class_id, title, max_score)
            VALUES (%(assignment_id)s, %(class_id)s, %(title)s, %(max_score)s)
            """,
            payload["assignments"],
        )
        cur.executemany(
            """
            INSERT INTO attendance (student_id, class_id, attendance_date, status, recorded_at)
            VALUES (%(student_id)s, %(class_id)s, %(attendance_date)s, %(status)s, %(event_time)s)
            """,
            attendance,
        )
        cur.executemany(
            """
            INSERT INTO grades (student_id, assignment_id, score, graded_at)
            VALUES (%(student_id)s, %(assignment_id)s, %(score)s, %(event_time)s)
            """,
            grades,
        )


def print_summary(payload: dict) -> None:
    events = payload["events"]
    attendance = sum(1 for event in events if event["event_type"] == "attendance")
    grades = sum(1 for event in events if event["event_type"] == "grade")
    first_student = payload["students"][0]["student_id"]
    print("Loaded the fake school into PostgreSQL.")
    print(f"  students: {len(payload['students'])}")
    print(f"  attendance rows: {attendance}")
    print(f"  grade rows: {grades}")
    print(f"After the API is running, try student {first_student}:")
    print(f"  curl http://127.0.0.1:8000/students/{first_student}/attendance")


if __name__ == "__main__":
    main()
