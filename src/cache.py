"""Today's attendance in Redis.

PostgreSQL keeps every mark. Redis keeps only the current school day so a
lookup does not have to read the database.

One Redis hash per day:

    attendance:2026-10-12
        field 1001:10  ->  absent

The field is student_id:class_id. The value is present, absent, or late.
"""

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import redis

DEFAULT_URL = "redis://localhost:6379/0"
SCHOOL_ZONE = ZoneInfo("Africa/Johannesburg")


def redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_URL)


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(redis_url(), decode_responses=True)


def school_today() -> date:
    return datetime.now(SCHOOL_ZONE).date()


def attendance_key(day: date) -> str:
    return f"attendance:{day.isoformat()}"


def save_mark(student_id: int, class_id: int, day: date, status: str) -> None:
    """Store one mark for a learner in one class on one day."""
    client = redis_client()
    client.hset(attendance_key(day), f"{student_id}:{class_id}", status)


def cache_attendance_events(events: list[dict], day: date | None = None) -> int:
    """Copy one day's attendance events into Redis. Returns how many were stored."""
    if day is None:
        day = school_today()
    day_text = day.isoformat()
    todays = [
        event
        for event in events
        if event.get("event_type") == "attendance" and event.get("attendance_date") == day_text
    ]
    if not todays:
        return 0
    client = redis_client()
    mapping = {
        f"{event['student_id']}:{event['class_id']}": event["status"] for event in todays
    }
    client.hset(attendance_key(day), mapping=mapping)
    return len(mapping)


def list_marks(day: date, student_id: int | None = None) -> list[dict]:
    """Read one day's marks from Redis."""
    raw = redis_client().hgetall(attendance_key(day))
    marks = []
    for field, status in raw.items():
        learner, school_class = field.split(":")
        if student_id is not None and int(learner) != student_id:
            continue
        marks.append(
            {
                "student_id": int(learner),
                "class_id": int(school_class),
                "attendance_date": day.isoformat(),
                "status": status,
            }
        )
    marks.sort(key=lambda mark: (mark["student_id"], mark["class_id"]))
    return marks


def list_absences(day: date) -> list[dict]:
    """Absences per class for one day, written by src/streaming/absence_counter.py."""
    raw = redis_client().hgetall(f"absences:{day.isoformat()}")
    rows = [
        {"class_id": int(class_id), "absences": int(count)}
        for class_id, count in raw.items()
        if int(count) > 0
    ]
    rows.sort(key=lambda row: row["class_id"])
    return rows
