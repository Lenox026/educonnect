"""Publish and read attendance events on Redpanda.

Redpanda speaks the Kafka protocol. The topic is named attendance.
Each message is the same JSON shape as data/samples/attendance_event.json.

The broker address matches the external port in docker-compose.yml.
"""

import os

from kafka import KafkaConsumer, KafkaProducer
from kafka.serializer.json import JsonSerializer

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:19092")
TOPIC = "attendance"


def publish_attendance(event: dict) -> None:
    """Send one attendance event. Raises if Redpanda is not running."""
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=JsonSerializer(),
        request_timeout_ms=5000,
        retries=1,
    )
    try:
        producer.send(TOPIC, event).get(timeout=10)
    finally:
        producer.close()


def listen() -> None:
    """Print events as they arrive. Ctrl+C stops the script."""
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        auto_offset_reset="latest",
        group_id="educonnect-demo",
        value_deserializer=JsonSerializer(),
    )
    print("Waiting for attendance events on Redpanda. Press Ctrl+C to stop.")
    for message in consumer:
        event = message.value
        print(
            f"{event['attendance_date']}  "
            f"student {event['student_id']}  "
            f"class {event['class_id']}  "
            f"{event['status']}"
        )
