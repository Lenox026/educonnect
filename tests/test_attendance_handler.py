"""The Lambda stores a mark and emails only when the learner is absent."""

import json
import os
import sys
import types
import unittest
from pathlib import Path

os.environ.setdefault("TABLE_NAME", "educonnect-attendance")
os.environ.setdefault("TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:educonnect-absence")

boto3 = sys.modules.setdefault("boto3", types.ModuleType("boto3"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "aws"))

import attendance_handler as handler


class FakeTable:
    def __init__(self, store):
        self.store = store

    def put_item(self, Item):
        self.store[Item["student_class"]] = dict(Item)

    def query(self, **kwargs):
        values = kwargs["ExpressionAttributeValues"]
        rows = [
            row for row in self.store.values() if row["attendance_date"] == values[":day"]
        ]
        if ":student_id" in values:
            rows = [row for row in rows if row["student_id"] == values[":student_id"]]
        return {"Items": rows}


class FakeSns:
    def __init__(self):
        self.messages = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self.sns = FakeSns()
        boto3.resource = lambda name: types.SimpleNamespace(Table=lambda table: FakeTable(self.store))
        boto3.client = lambda name: self.sns

    def post(self, body, groups="[teacher]"):
        claims = {"cognito:groups": groups} if groups else {}
        result = handler.handler(
            {
                "requestContext": {
                    "http": {"method": "POST", "path": "/attendance"},
                    "authorizer": {"jwt": {"claims": claims}},
                },
                "body": json.dumps(body),
            },
            None,
        )
        return result["statusCode"], json.loads(result["body"])

    def test_absent_is_stored_and_emailed(self):
        status, body = self.post(
            {
                "event_id": "demo-1",
                "student_id": 1001,
                "class_id": 10,
                "attendance_date": "2026-10-21",
                "status": "absent",
            }
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["notified"])
        self.assertEqual(len(self.sns.messages), 1)
        self.assertIn("1001", self.sns.messages[0]["Message"])
        self.assertIn("1001#10", self.store)

    def test_late_is_stored_without_an_email(self):
        status, body = self.post(
            {
                "student_id": 1002,
                "class_id": 10,
                "attendance_date": "2026-10-21",
                "status": "late",
            }
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["notified"])
        self.assertEqual(self.sns.messages, [])

    def test_zero_is_rejected(self):
        status, body = self.post(
            {
                "student_id": 0,
                "class_id": 10,
                "attendance_date": "2026-10-21",
                "status": "present",
            }
        )
        self.assertEqual(status, 400)
        self.assertEqual(self.store, {})

    def test_today_can_filter_one_learner(self):
        self.post(
            {
                "student_id": 1001,
                "class_id": 10,
                "attendance_date": "2026-10-21",
                "status": "absent",
            }
        )
        self.post(
            {
                "student_id": 1002,
                "class_id": 10,
                "attendance_date": "2026-10-21",
                "status": "late",
            }
        )
        result = handler.handler(
            {
                "requestContext": {"http": {"method": "GET", "path": "/attendance/today"}},
                "queryStringParameters": {
                    "attendance_date": "2026-10-21",
                    "student_id": "1001",
                },
            },
            None,
        )
        body = json.loads(result["body"])
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual([mark["student_id"] for mark in body["marks"]], [1001])
        self.assertEqual(body["source"], "dynamodb")

    def test_parent_cannot_post(self):
        status, body = self.post(
            {
                "student_id": 1001,
                "class_id": 10,
                "attendance_date": "2026-10-21",
                "status": "absent",
            },
            groups="[parent]",
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.store, {})
        self.assertEqual(self.sns.messages, [])

    def test_no_group_cannot_post(self):
        status, body = self.post(
            {
                "student_id": 1001,
                "class_id": 10,
                "attendance_date": "2026-10-21",
                "status": "absent",
            },
            groups="",
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.store, {})

    def test_admin_can_post(self):
        status, body = self.post(
            {
                "student_id": 1003,
                "class_id": 10,
                "attendance_date": "2026-10-21",
                "status": "present",
            },
            groups="[admin]",
        )
        self.assertEqual(status, 200)

    def test_teacher_among_several_groups_can_post(self):
        status, body = self.post(
            {
                "student_id": 1004,
                "class_id": 10,
                "attendance_date": "2026-10-21",
                "status": "present",
            },
            groups="[parent teacher]",
        )
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()