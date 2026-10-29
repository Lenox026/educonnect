"""
Count absences per class from the Debezium change stream.

Debezium watches the PostgreSQL attendance table and publishes every insert,
update, and delete to the Redpanda topic educonnect.public.attendance. This job
reads that topic and keeps a running count of absences for each class and day
in Redis:

    absences:2026-10-12
        field 10  ->  3        (class 10 has 3 absences that day)

Because it reads changes, not API calls, it stays correct when a mark is
corrected. Changing absent to present lowers the count by one.

From the project root, with docker compose up and the connector registered:

    python src/streaming/absence_counter.py

The pure functions below hold the rules, so the tests run without Redpanda.
"""

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:19092")
TOPIC = "educonnect.public.attendance"
EPOCH = date(1970, 1, 1)


def day_text(value) -> str:
    """Debezium sends a DATE as days since 1970-01-01. Accept ISO text too."""
    if isinstance(value, int):
        return (EPOCH + timedelta(days=value)).isoformat()
    return str(value)[:10]


def is_absent(row) -> bool:
    return bool(row) and row.get("status") == "absent"


def delta_for(change: dict | None):
    """
    Turn one Debezium change into (attendance_date, class_id, delta), or None.

    op is c (insert), r (snapshot row), u (update), or d (delete).
    Needs REPLICA IDENTITY FULL on the table so before is filled in for u and d.
    """
    if not change:
        return None
    op = change.get("op")
    before = change.get("before")
    after = change.get("after")

    if op in ("c", "r"):
        change_in_count = 1 if is_absent(after) else 0
        row = after
    elif op == "u":
        change_in_count = int(is_absent(after)) - int(is_absent(before))
        row = after
    elif op == "d":
        change_in_count = -1 if is_absent(before) else 0
        row = before
    else:
        return None

    if change_in_count == 0 or not row:
        return None
    return day_text(row["attendance_date"]), int(row["class_id"]), change_in_count


def parse_message(raw: bytes | None):
    """The message value as a dictionary. Deletes also leave an empty tombstone."""
    if not raw:
        return None
    body = json.loads(raw)
    # With schemas turned on Debezium wraps the change in {"schema":..., "payload":...}.
    return body.get("payload", body) if isinstance(body, dict) else None


def run() -> None:
    from kafka import KafkaConsumer
    import redis

    from cache import redis_client

    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        auto_offset_reset="earliest",
        group_id="educonnect-absence-counter",
    )
    client = redis_client()
    print(f"Counting absences from {TOPIC}. Press Ctrl+C to stop.")
    try:
        for message in consumer:
            result = delta_for(parse_message(message.value))
            if result is None:
                continue
            day, class_id, delta = result
            total = client.hincrby(f"absences:{day}", str(class_id), delta)
            print(f"{day}  class {class_id}  {delta:+d}  ->  {total} absent")
    except redis.RedisError as error:
        raise SystemExit(f"Redis problem: {error}")


if __name__ == "__main__":
    run()
