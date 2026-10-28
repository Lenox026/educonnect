"""Teachers and admins post announcements; every signed-in role reads them."""

import json
import os
import sys
import types
import unittest
from pathlib import Path

os.environ.setdefault("TABLE_NAME", "educonnect-announcements")

boto3 = sys.modules.setdefault("boto3", types.ModuleType("boto3"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "aws"))

import announcements_handler as handler


class FakeTable:
    def __init__(self, store):
        self.store = store

    def put_item(self, Item):
        self.store[Item["sort_key"]] = dict(Item)

    def query(self, **kwargs):
        newest_first = kwargs.get("ScanIndexForward", True) is False
        rows = sorted(self.store.values(), key=lambda row: row["sort_key"], reverse=newest_first)
        return {"Items": rows[: kwargs.get("Limit", len(rows))]}


class AnnouncementTests(unittest.TestCase):
    def setUp(self):
        self.store = {}
        boto3.resource = lambda name: types.SimpleNamespace(Table=lambda table: FakeTable(self.store))

    def call(self, method, body=None, groups="[teacher]", email="teacher@example.com"):
        claims = {"email": email}
        if groups:
            claims["cognito:groups"] = groups
        event = {
            "requestContext": {
                "http": {"method": method, "path": "/announcements"},
                "authorizer": {"jwt": {"claims": claims}},
            }
        }
        if body is not None:
            event["body"] = json.dumps(body)
        result = handler.handler(event, None)
        return result["statusCode"], json.loads(result["body"])

    def test_teacher_can_post(self):
        status, body = self.call("POST", {"title": "Sports day", "body": "Friday at 9."})
        self.assertEqual(status, 200)
        self.assertEqual(body["title"], "Sports day")
        self.assertEqual(body["author"], "teacher@example.com")
        self.assertEqual(len(self.store), 1)

    def test_admin_can_post(self):
        status, body = self.call("POST", {"title": "Fees", "body": "Due Monday."}, groups="[admin]")
        self.assertEqual(status, 200)

    def test_parent_cannot_post(self):
        status, body = self.call("POST", {"title": "Hi", "body": "Hi"}, groups="[parent]")
        self.assertEqual(status, 403)
        self.assertEqual(self.store, {})

    def test_no_group_cannot_post_or_read(self):
        status, body = self.call("POST", {"title": "Hi", "body": "Hi"}, groups="")
        self.assertEqual(status, 403)
        status, body = self.call("GET", groups="")
        self.assertEqual(status, 403)

    def test_empty_title_is_rejected(self):
        status, body = self.call("POST", {"title": "  ", "body": "Hello"})
        self.assertEqual(status, 400)
        self.assertEqual(self.store, {})

    def test_long_body_is_rejected(self):
        status, body = self.call("POST", {"title": "Long", "body": "x" * 1001})
        self.assertEqual(status, 400)

    def test_non_text_fields_are_rejected(self):
        status, body = self.call("POST", {"title": ["a"], "body": 5})
        self.assertEqual(status, 400)

    def test_parent_reads_newest_first(self):
        self.call("POST", {"title": "First", "body": "one"})
        self.call("POST", {"title": "Second", "body": "two"})
        status, body = self.call("GET", groups="[parent]", email="parent@example.com")
        self.assertEqual(status, 200)
        self.assertEqual([a["title"] for a in body["announcements"]], ["Second", "First"])


if __name__ == "__main__":
    unittest.main()