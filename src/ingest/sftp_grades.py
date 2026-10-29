"""
Second data source: re-marked grades that arrive as a CSV on an SFTP server.

The school office drops grades_upload.csv into the SFTP folder. This script
downloads every CSV there, checks it, and upserts the scores into PostgreSQL.
Because Debezium watches the grades table, each corrected score also shows up on
the change stream.

CSV columns: student_id, assignment_id, score, graded_at

From the project root, with docker compose up and the school loaded:

    python src/ingest/make_sample_upload.py
    python src/ingest/sftp_grades.py

If any row breaks a rule, nothing is loaded and the script exits with status 1,
the same way the loader behaves.
"""

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

INCOMING = ROOT / "data" / "generated" / "incoming"
COLUMNS = ["student_id", "assignment_id", "score", "graded_at"]

SFTP_HOST = os.environ.get("SFTP_HOST", "localhost")
SFTP_PORT = int(os.environ.get("SFTP_PORT", "2222"))
SFTP_USER = os.environ.get("SFTP_USER", "educonnect")
SFTP_PASSWORD = os.environ.get("SFTP_PASSWORD", "educonnect")  # local demo only
SFTP_FOLDER = os.environ.get("SFTP_FOLDER", "upload")


def validate_upload(frame: pd.DataFrame, max_scores: dict[int, int], students: set[int]):
    """
    Return a list of problems. An empty list means the upload is safe to load.

    max_scores maps assignment_id to its maximum. students holds known student ids.
    """
    missing = [name for name in COLUMNS if name not in frame.columns]
    if missing:
        return [f"missing column: {name}" for name in missing]
    if frame.empty:
        return ["the file has no rows"]

    problems = []
    for position, row in frame.iterrows():
        line = position + 2  # row 1 is the header
        values = row[COLUMNS]
        if values.isna().any():
            problems.append(f"line {line}: an empty value")
            continue
        try:
            student_id = int(values["student_id"])
            assignment_id = int(values["assignment_id"])
            score = float(values["score"])
        except (TypeError, ValueError):
            problems.append(f"line {line}: student_id, assignment_id, and score must be numbers")
            continue
        if score != int(score):
            problems.append(f"line {line}: score {score} is not a whole number")
            continue
        if student_id not in students:
            problems.append(f"line {line}: no learner with student_id {student_id}")
        if assignment_id not in max_scores:
            problems.append(f"line {line}: no assignment {assignment_id}")
            continue
        if not 0 <= score <= max_scores[assignment_id]:
            problems.append(
                f"line {line}: score {int(score)} is outside 0..{max_scores[assignment_id]}"
            )
    return problems


def fetch_csvs() -> list[Path]:
    """Download every .csv from the SFTP folder into data/generated/incoming/."""
    import paramiko

    INCOMING.mkdir(parents=True, exist_ok=True)
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    try:
        transport.connect(username=SFTP_USER, password=SFTP_PASSWORD)
        client = paramiko.SFTPClient.from_transport(transport)
        downloaded = []
        for name in sorted(client.listdir(SFTP_FOLDER)):
            if name.lower().endswith(".csv"):
                target = INCOMING / name
                client.get(f"{SFTP_FOLDER}/{name}", str(target))
                downloaded.append(target)
        return downloaded
    finally:
        transport.close()


def reference_data(conn):
    max_scores = {
        row["assignment_id"]: row["max_score"]
        for row in conn.execute("SELECT assignment_id, max_score FROM assignments").fetchall()
    }
    students = {
        row["student_id"] for row in conn.execute("SELECT student_id FROM students").fetchall()
    }
    return max_scores, students


def upsert_grades(conn, frame: pd.DataFrame) -> int:
    rows = [
        {
            "student_id": int(row.student_id),
            "assignment_id": int(row.assignment_id),
            "score": int(row.score),
            "graded_at": row.graded_at,
        }
        for row in frame.itertuples()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO grades (student_id, assignment_id, score, graded_at)
            VALUES (%(student_id)s, %(assignment_id)s, %(score)s, %(graded_at)s)
            ON CONFLICT (student_id, assignment_id)
            DO UPDATE SET score = EXCLUDED.score, graded_at = EXCLUDED.graded_at
            """,
            rows,
        )
    return len(rows)


def main() -> None:
    from database import connect

    try:
        files = fetch_csvs()
    except Exception as error:  # paramiko raises several different errors
        raise SystemExit(
            f"Could not read the SFTP server at {SFTP_HOST}:{SFTP_PORT}: {error}\n"
            "Start it with: docker compose up -d"
        )
    if not files:
        raise SystemExit("No .csv files in the SFTP folder. Create one with make_sample_upload.py.")

    with connect() as conn:
        max_scores, students = reference_data(conn)
        loaded = {}
        failed = False
        for path in files:
            frame = pd.read_csv(path)
            problems = validate_upload(frame, max_scores, students)
            if problems:
                failed = True
                print(f"{path.name}: FAIL, nothing loaded")
                for problem in problems[:10]:
                    print(f"  {problem}")
                continue
            loaded[path.name] = upsert_grades(conn, frame)
            print(f"{path.name}: PASS, {loaded[path.name]} grades upserted")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
