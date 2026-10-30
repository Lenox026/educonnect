"""Teachers and admins post homework; every signed-in role reads it."""

import json
import os
import sys
import types
import unittest
from pathlib import Path

os.environ.setdefault("TABLE_NAME", "educonnect-homework")

boto3 = sys.modules.setdefault("boto3", types.ModuleType("boto3"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "aws"))

import homework_handler as handler


class FakeTable:
    def __init__(self, store):
        self.store = store

    def put_item(self, Item):
        self.store[Item["sort_key"]] = dict(Item)

    def query(self, **kwargs):
        newest_first = kwargs.get("ScanIndexForward", True) is False
        rows = sorted(self.store.values(), key=lambda row: row["sort_key"], reverse=newest_first)
        return {"Items": rows[: kwargs.get("Limit", len(rows))]}


class HomeworkTests(unittest.TestCase):
    def setUp(self):
        self.store = {}
        boto3.resource = lambda name: types.SimpleNamespace(Table=lambda table: FakeTable(self.store))

    def call(self, method, body=None, groups="[teacher]", email="teacher@example.com"):
        claims = {"email": email}
        if groups:
            claims["cognito:groups"] = groups
        event = {
            "requestContext": {
                "http": {"method": method, "path": "/homework"},
                "authorizer": {"jwt": {"claims": claims}},
            }
        }
        if body is not None:
            event["body"] = json.dumps(body)
        result = handler.handler(event, None)
        return result["statusCode"], json.loads(result["body"])

    def test_teacher_can_post(self):
        status, body = self.call(
            "POST",
            {"title": "Algebra worksheet", "body": "Pages 12 to 14.", "due_date": "2026-11-04"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["title"], "Algebra worksheet")
        self.assertEqual(body["due_date"], "2026-11-04")
        self.assertEqual(len(self.store), 1)

    def test_parent_cannot_post(self):
        status, body = self.call("POST", {"title": "Hi", "body": "Hi"}, groups="[parent]")
        self.assertEqual(status, 403)
        self.assertEqual(self.store, {})

    def test_parent_can_read(self):
        self.call("POST", {"title": "Read chapter 3", "body": "Due Friday."})
        status, body = self.call("GET", groups="[parent]")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["homework"]), 1)

    def test_bad_due_date_is_rejected(self):
        status, body = self.call("POST", {"title": "Quiz", "body": "Friday", "due_date": "soon"})
        self.assertEqual(status, 400)
        self.assertEqual(self.store, {})


if __name__ == "__main__":
    unittest.main()
