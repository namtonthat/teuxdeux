"""Client request-shape tests using a stubbed httpx transport (no network)."""

import datetime as dt
import json

import httpx

from teuxdeux.client import TeuxDeuxClient


def _client(handler):
    c = TeuxDeuxClient("u", "p", workspace_id=123456)
    c._http = httpx.Client(base_url="https://teuxdeux.com", transport=httpx.MockTransport(handler))
    c._token = "FAKE"  # pretend logged in
    return c


def test_create_todo_request_and_parse():
    seen = {}

    def handler(req):
        seen["method"] = req.method
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json={"todo": {
            "id": 999, "text": "Buy milk", "done": False,
            "current_date": "2026-06-20", "position": 3}})

    todo = _client(handler).create_todo("Buy milk", current_date=dt.date(2026, 6, 20))

    assert seen["method"] == "POST"
    assert seen["path"] == "/api/v4/workspaces/123456/todos"
    assert seen["auth"] == "Bearer FAKE"
    assert seen["body"] == {"text": "Buy milk", "done": False,
                            "highlight_identifier": None, "current_date": "2026-06-20"}
    assert todo.id == 999 and todo.text == "Buy milk" and todo.done is False


def test_create_todo_done_and_undated():
    def handler(req):
        body = json.loads(req.content)
        assert body == {"text": "x", "done": True, "highlight_identifier": None,
                        "current_date": None}
        return httpx.Response(200, json={"todo": {"id": 1, "text": "x", "done": True}})

    todo = _client(handler).create_todo("x", done=True)
    assert todo.is_someday is True  # no current_date
