"""Attendance API for the AWS slice.

API Gateway calls this Lambda. The function stores the mark in DynamoDB and,
when the status is absent, publishes one email alert to the SNS topic.

The body matches data/samples/attendance_event.json. Learner ids here are the
same synthetic ids as the local school. This function does not read PostgreSQL.
"""

import json
import os
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import boto3

SCHOOL_ZONE = ZoneInfo("Africa/Johannesburg")
STATUSES = ("present", "absent", "late")


def groups(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    raw = str(claims.get("cognito:groups", "")).strip("[]")
    return set(raw.replace(",", " ").split())


def handler(event, context):
    route = event.get("requestContext", {}).get("http", {})
    method = route.get("method", "")
    path = route.get("path", "")

    if method == "POST" and path == "/attendance":
        if not groups(event) & {"teacher", "admin"}:
            return respond(403, {"detail": "Teachers only."})
        return save_mark(event)
    if method == "GET" and path == "/attendance/today":
        return list_today(event)
    return respond(404, {"detail": "Not found."})


def save_mark(event):
    try:
        body = json.loads(event.get("body") or "")
    except json.JSONDecodeError:
        return respond(400, {"detail": "Body must be JSON."})

    mark, error = parse_mark(body)
    if error:
        return respond(400, {"detail": error})

    table().put_item(Item=mark)
    notified = False
    if mark["status"] == "absent":
        boto3.client("sns").publish(
            TopicArn=os.environ["TOPIC_ARN"],
            Subject="EduConnect absence",
            Message=(
                f"Learner {mark['student_id']} was marked absent "
                f"for class {mark['class_id']} on {mark['attendance_date']}."
            ),
        )
        notified = True

    saved = public_mark(mark)
    saved["notified"] = notified
    return respond(200, saved)


def list_today(event):
    params = event.get("queryStringParameters") or {}
    day = params.get("attendance_date") or datetime.now(SCHOOL_ZONE).date().isoformat()
    query = {
        "KeyConditionExpression": "attendance_date = :day",
        "ExpressionAttributeValues": {":day": day},
    }
    student_id = params.get("student_id")
    if student_id:
        if not student_id.isdigit():
            return respond(400, {"detail": "student_id must be a number."})
        query["FilterExpression"] = "student_id = :student_id"
        query["ExpressionAttributeValues"][":student_id"] = int(student_id)

    rows = table().query(**query).get("Items", [])
    return respond(
        200,
        {
            "attendance_date": day,
            "source": "dynamodb",
            "marks": [public_mark(row) for row in rows],
        },
    )


def parse_mark(body):
    """Return a DynamoDB item, or (None, error message)."""
    if not isinstance(body, dict):
        return None, "Body must be a JSON object."

    status = body.get("status")
    if status not in STATUSES:
        return None, "status must be present, absent, or late."

    try:
        student_id = int(body["student_id"])
        class_id = int(body["class_id"])
    except (KeyError, TypeError, ValueError):
        return None, "student_id and class_id are required numbers."
    if student_id < 1 or class_id < 1:
        return None, "student_id and class_id must be positive."

    day = body.get("attendance_date")
    if not isinstance(day, str):
        return None, "attendance_date is required."
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return None, "attendance_date must be YYYY-MM-DD."

    return {
        "attendance_date": day,
        "student_class": f"{student_id}#{class_id}",
        "student_id": student_id,
        "class_id": class_id,
        "status": status,
        "event_id": str(body.get("event_id") or ""),
        "event_time": str(body.get("event_time") or ""),
    }, None


def public_mark(item):
    return {
        "student_id": plain(item["student_id"]),
        "class_id": plain(item["class_id"]),
        "attendance_date": item["attendance_date"],
        "status": item["status"],
        "event_id": item.get("event_id", ""),
        "event_time": item.get("event_time", ""),
    }


def plain(value):
    if isinstance(value, Decimal):
        return int(value)
    return value


def table():
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
