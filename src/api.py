"""
Small API for EduConnect attendance.

Start PostgreSQL, load the fake school, then from the project root run:

    python -m uvicorn api:app --app-dir src --port 8000

Open http://127.0.0.1:8000/docs to try the routes in the browser.
The body of POST /attendance matches data/samples/attendance_event.json.
GET /attendance/today reads Redis, not PostgreSQL.
"""

from datetime import date, datetime
from typing import Literal

import psycopg
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cache import list_marks, save_mark, school_today
from database import connect

app = FastAPI(
    title="EduConnect",
    description="Record a fake attendance mark and read today's marks from Redis.",
    version="0.3.0",
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
        "example": "/attendance/today",
    }


@app.get("/health")
def health():
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
    except psycopg.OperationalError:
        raise HTTPException(status_code=503, detail="PostgreSQL is not running.")
    try:
        list_marks(school_today())
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Redis is not running.")
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


@app.get("/attendance/today")
def attendance_today(student_id: int | None = None):
    """Read today's marks from Redis. Pass student_id to see one learner."""
    day = school_today()
    try:
        marks = list_marks(day, student_id)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Redis is not running.")
    return {
        "attendance_date": day.isoformat(),
        "source": "redis",
        "marks": marks,
    }


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
    cached = True
    try:
        save_mark(event.student_id, event.class_id, event.attendance_date, event.status)
    except redis.RedisError:
        cached = False
    body = dict(row)
    body["cached"] = cached
    return body
