"""
Small API for EduConnect attendance.

Start PostgreSQL, load the fake school, then from the project root run:

    python -m uvicorn api:app --app-dir src --port 8000

Open http://127.0.0.1:8000/docs to try the routes in the browser.
The body of POST /attendance matches data/samples/attendance_event.json.
"""

from datetime import date, datetime
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from database import connect

app = FastAPI(
    title="EduConnect",
    description="Record a fake attendance mark and read it back.",
    version="0.2.0",
)


class AttendanceEvent(BaseModel):
    """The same fields as data/samples/attendance_event.json."""

    event_id: str
    event_type: Literal["attendance"]
    event_time: datetime
    student_id: int
    class_id: int
    attendance_date: date
    status: Literal["present", "absent", "late"]


@app.get("/")
def home():
    return {
        "service": "EduConnect",
        "docs": "/docs",
        "example": "/students/1001/attendance",
    }


@app.get("/health")
def health():
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
    except psycopg.OperationalError:
        raise HTTPException(status_code=503, detail="PostgreSQL is not running.")
    return {"status": "ok"}


@app.get("/students/{student_id}")
def get_student(student_id: int):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT student_id, first_name, last_name, grade_level
            FROM students
            WHERE student_id = %s
            """,
            (student_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No learner with that student_id.")
    return row


@app.get("/students/{student_id}/attendance")
def list_attendance(student_id: int):
    with connect() as conn:
        student = conn.execute(
            "SELECT student_id FROM students WHERE student_id = %s",
            (student_id,),
        ).fetchone()
        if student is None:
            raise HTTPException(status_code=404, detail="No learner with that student_id.")
        rows = conn.execute(
            """
            SELECT
                attendance.attendance_id,
                attendance.attendance_date,
                attendance.status,
                attendance.class_id,
                classes.class_name,
                attendance.recorded_at
            FROM attendance
            JOIN classes ON classes.class_id = attendance.class_id
            WHERE attendance.student_id = %s
            ORDER BY attendance.attendance_date, attendance.class_id
            """,
            (student_id,),
        ).fetchall()
    return rows


@app.post("/attendance")
def record_attendance(event: AttendanceEvent):
    """Save one attendance event. Posting the same learner, class, and day again updates the mark."""
    with connect() as conn:
        student = conn.execute(
            "SELECT student_id FROM students WHERE student_id = %s",
            (event.student_id,),
        ).fetchone()
        if student is None:
            raise HTTPException(
                status_code=404,
                detail="No learner with that student_id. Load the school first.",
            )
        enrolled = conn.execute(
            """
            SELECT 1
            FROM enrollments
            WHERE student_id = %s AND class_id = %s
            """,
            (event.student_id, event.class_id),
        ).fetchone()
        if enrolled is None:
            raise HTTPException(
                status_code=400,
                detail="That learner is not enrolled in that class.",
            )
        row = conn.execute(
            """
            INSERT INTO attendance (
                student_id, class_id, attendance_date, status, recorded_at
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (student_id, class_id, attendance_date)
            DO UPDATE SET
                status = EXCLUDED.status,
                recorded_at = EXCLUDED.recorded_at
            RETURNING attendance_id, student_id, class_id, attendance_date, status, recorded_at
            """,
            (
                event.student_id,
                event.class_id,
                event.attendance_date,
                event.status,
                event.event_time,
            ),
        ).fetchone()
    return row
