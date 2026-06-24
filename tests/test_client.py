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


def _login_mock(token="NEWTOKEN", on_api=None, log=None):
    """A MockTransport handler that fakes the /login → /home cookie dance, then delegates
    every API request to on_api. Appends 'GET /login' / 'POST /login' to log when given."""
    def handler(req):
        path = req.url.path
        if path == "/login" and req.method == "GET":
            if log is not None:
                log.append("GET /login")
            return httpx.Response(200, html='<input name="csrf_token" value="abc">')
        if path == "/login" and req.method == "POST":
            if log is not None:
                log.append("POST /login")
            return httpx.Response(302, headers={"location": "/home",
                                                "set-cookie": f"_txdxtxdx_token={token}; Path=/"})
        if path == "/home":
            return httpx.Response(200, text="home")
        return on_api(req)
    return handler


def _cached_client(cache, handler):
    c = TeuxDeuxClient("u", "p", workspace_id=123456, cache_path=str(cache))
    # follow_redirects mirrors the real client so the login 302 → /home dance works.
    c._http = httpx.Client(base_url="https://teuxdeux.com", follow_redirects=True,
                           transport=httpx.MockTransport(handler))
    return c


def test_cached_token_skips_login(tmp_path):
    cache = tmp_path / "token.json"
    cache.write_text(json.dumps({"u": "CACHED"}))
    log = []
    seen = {}

    def on_api(req):
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json={"todos": []})

    c = _cached_client(cache, _login_mock(on_api=on_api, log=log))
    c.__enter__()      # should adopt the cached token, no network
    c.todos()
    assert seen["auth"] == "Bearer CACHED"
    assert log == []   # never hit /login


def test_login_writes_token_to_cache(tmp_path):
    cache = tmp_path / "token.json"
    c = _cached_client(cache, _login_mock(token="FRESH", on_api=lambda r: httpx.Response(200, json={})))
    c.login()
    assert json.loads(cache.read_text())["u"] == "FRESH"
    assert oct(cache.stat().st_mode)[-3:] == "600"   # not world/group readable


def test_relogin_and_retry_on_401(tmp_path):
    cache = tmp_path / "token.json"
    cache.write_text(json.dumps({"u": "STALE"}))
    log = []
    calls = {"api": 0}

    def on_api(req):
        calls["api"] += 1
        if req.headers.get("authorization") == "Bearer STALE":
            return httpx.Response(401, json={"error": "unauthorized"})
        return httpx.Response(200, json={"account": {"id": 7}})

    c = _cached_client(cache, _login_mock(token="GOOD", on_api=on_api, log=log))
    c.__enter__()                       # adopts STALE from cache
    user = c.user()
    assert user.id == 7
    assert "POST /login" in log         # re-logged in on the 401
    assert calls["api"] == 2            # first 401, then the retry
    assert json.loads(cache.read_text())["u"] == "GOOD"  # cache refreshed


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
