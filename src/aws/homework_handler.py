"""Homework API for the AWS slice.

Teachers and admins post a homework item. Parents, teachers and admins read
the newest ones. A signed-in user with no role gets 403.
"""

import json
import os
import uuid
from datetime import datetime, timezone

import boto3

SCHOOL_ID = "demo-school"
WRITERS = {"teacher", "admin"}
READERS = {"teacher", "admin", "parent"}
MAX_TITLE = 100
MAX_BODY = 1000
MAX_LIST = 50


def handler(event, context):
    route = event.get("requestContext", {}).get("http", {})
    method = route.get("method", "")
    path = route.get("path", "")

    if method == "POST" and path == "/homework":
        if not groups(event) & WRITERS:
            return respond(403, {"detail": "Teachers only."})
        return save_homework(event)
    if method == "GET" and path == "/homework":
        if not groups(event) & READERS:
            return respond(403, {"detail": "No role assigned."})
        return list_homework()
    return respond(404, {"detail": "Not found."})


def claims(event):
    return (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )


def groups(event):
    raw = str(claims(event).get("cognito:groups", "")).strip("[]")
    return set(raw.replace(",", " ").split())


def save_homework(event):
    try:
        body = json.loads(event.get("body") or "")
    except json.JSONDecodeError:
        return respond(400, {"detail": "Body must be JSON."})

    author = str(claims(event).get("email", "unknown"))
    item, error = parse_homework(body, author)
    if error:
        return respond(400, {"detail": error})

    table().put_item(Item=item)
    return respond(200, public(item))


def list_homework():
    rows = (
        table()
        .query(
            KeyConditionExpression="school_id = :school",
            ExpressionAttributeValues={":school": SCHOOL_ID},
            ScanIndexForward=False,
            Limit=MAX_LIST,
        )
        .get("Items", [])
    )
    return respond(200, {"homework": [public(row) for row in rows]})


def parse_homework(body, author):
    """Return a DynamoDB item, or (None, error message)."""
    if not isinstance(body, dict):
        return None, "Body must be a JSON object."

    title = body.get("title")
    text = body.get("body")
    if not isinstance(title, str) or not isinstance(text, str):
        return None, "title and body are required text."
    title = title.strip()
    text = text.strip()
    if not title or not text:
        return None, "title and body are required text."
    if len(title) > MAX_TITLE:
        return None, f"title must be at most {MAX_TITLE} characters."
    if len(text) > MAX_BODY:
        return None, f"body must be at most {MAX_BODY} characters."

    due = body.get("due_date") or ""
    if due:
        if not isinstance(due, str):
            return None, "due_date must be YYYY-MM-DD."
        try:
            datetime.strptime(due, "%Y-%m-%d")
        except ValueError:
            return None, "due_date must be YYYY-MM-DD."

    created_at = datetime.now(timezone.utc).isoformat()
    homework_id = str(uuid.uuid4())
    return {
        "school_id": SCHOOL_ID,
        "sort_key": f"{created_at}#{homework_id}",
        "homework_id": homework_id,
        "title": title,
        "body": text,
        "due_date": due,
        "author": author,
        "created_at": created_at,
    }, None


def public(item):
    return {
        "id": item["homework_id"],
        "title": item["title"],
        "body": item["body"],
        "due_date": item.get("due_date", ""),
        "author": item["author"],
        "created_at": item["created_at"],
    }


def table():
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
