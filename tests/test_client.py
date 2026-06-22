"""Client request-shape tests using a stubbed httpx transport (no network)."""

import datetime as dt
import json

import httpx
import pytest

from teuxdeux.client import TeuxDeuxClient, TeuxDeuxError


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


def test_update_todo_request_and_parse():
    seen = {}

    def handler(req):
        seen["method"] = req.method
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json={"todo": {
            "id": 999, "text": "Buy oat milk", "done": False,
            "current_date": "2026-06-20", "position": 3}})

    todo = _client(handler).update_todo(999, "Buy oat milk")

    assert seen["method"] == "PATCH"
    assert seen["path"] == "/api/v4/workspaces/123456/todos/999"
    assert seen["auth"] == "Bearer FAKE"
    assert seen["body"] == {"text": "Buy oat milk"}
    assert todo.id == 999 and todo.text == "Buy oat milk"


def test_update_todo_raises_on_http_error():
    def handler(req):
        return httpx.Response(422, json={"error": "Unknown field"})

    with pytest.raises(TeuxDeuxError):
        _client(handler).update_todo(999, "nope")


def test_delete_todo_request_and_no_content():
    seen = {}

    def handler(req):
        seen["method"] = req.method
        seen["path"] = req.url.path
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(204)  # No Content, empty body

    result = _client(handler).delete_todo(999)

    assert seen["method"] == "DELETE"
    assert seen["path"] == "/api/v4/workspaces/123456/todos/999"
    assert seen["auth"] == "Bearer FAKE"
    assert result is None


def test_delete_todo_raises_on_http_error():
    def handler(req):
        return httpx.Response(404, text="not found")

    with pytest.raises(TeuxDeuxError):
        _client(handler).delete_todo(999)
