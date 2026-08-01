"""httpx client for the v4, workspace-scoped TeuxDeux API.

Login is a Flask cookie session that yields a `_txdxtxdx_token`; the JSON API wants it as
an `Authorization: Bearer` token (cookies alone get a 401). See API.md.
"""

import datetime as dt
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self

import httpx

from .models import Todo, User

BASE_URL = "https://teuxdeux.com"
# {ws} = numeric workspace id (find yours via workspaces() or set TEUXDEUX_WORKSPACE_ID).
TODOS_PATH = "/api/v4/workspaces/{ws}/todos"  # ?since=&until= → {"todos": [...]}
TODO_PATH = "/api/v4/workspaces/{ws}/todos/{id}"  # PATCH {"text": str} → {"todo": {...}}; DELETE → 204
STATE_PATH = "/api/v4/workspaces/{ws}/todos/{id}/state"  # POST {"done": bool} → {"todo": {...}}
WORKSPACES_PATH = "/api/v4/workspaces"  # → {"workspaces": [...]}
ACCOUNT_PATH = "/api/v4/account"  # → {"account": {...}}
_TOKEN_COOKIE = "_txdxtxdx_token"
_CSRF_RE = re.compile(r'name="csrf_token"[^>]*\bvalue="([^"]+)"')
_CSRF_RE_ALT = re.compile(r'\bvalue="([^"]+)"[^>]*name="csrf_token"')


def default_cache_path() -> Path:
    """Where the session token is cached between CLI invocations (override: TEUXDEUX_TOKEN_CACHE).

    Login costs ~2.5s; caching the Bearer token turns every later call into a single ~0.2s
    request and only re-logs in when the token is rejected (401)."""
    override = os.environ.get("TEUXDEUX_TOKEN_CACHE")
    if override:
        return Path(override)
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return Path(base) / "teuxdeux" / "token.json"


class TeuxDeuxError(RuntimeError):
    """Any failure talking to TeuxDeux (network, auth, or unexpected shape)."""


class TeuxDeuxClient:
    def __init__(
        self,
        username: str,
        password: str,
        *,
        workspace_id: int | str | None = None,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        retries: int = 3,
        cache_path: str | Path | None = None,
        use_cache: bool = True,
    ) -> None:
        self._username = username
        self._password = password
        self._base = base_url.rstrip("/")
        self._ws = str(workspace_id or os.environ.get("TEUXDEUX_WORKSPACE_ID") or "").strip()
        self._csrf: str | None = None
        self._token: str | None = None  # _txdxtxdx_token, sent as Authorization: Bearer
        self._use_cache = use_cache
        self._cache_path = Path(cache_path) if cache_path else default_cache_path()
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=httpx.HTTPTransport(retries=retries),
            follow_redirects=True,
            headers={"User-Agent": "teuxdeux-py/0.1 (+https://github.com/namtonthat/teuxdeux)"},
        )

    # ── session ───────────────────────────────────────────────────────────
    def login(self) -> Self:
        page = self._http.get("/login")
        page.raise_for_status()
        m = _CSRF_RE.search(page.text) or _CSRF_RE_ALT.search(page.text)
        if not m:
            raise TeuxDeuxError("no csrf_token on /login — login page shape changed")
        self._csrf = m.group(1)
        resp = self._http.post(
            "/login",
            data={"username": self._username, "password": self._password,
                  "csrf_token": self._csrf},
            # match the browser — Flask-WTF rejects HTTPS POSTs without a same-origin Referer
            headers={"Origin": self._base, "Referer": f"{self._base}/login"},
        )
        # Success redirects to /home; a rejected login re-renders /login.
        if resp.status_code >= 400:
            raise TeuxDeuxError(f"login failed (HTTP {resp.status_code})")
        if resp.url.path.rstrip("/").endswith("/login"):
            raise TeuxDeuxError("login rejected — check TEUXDEUX_USERNAME / TEUXDEUX_PASSWORD")
        # The v4 JSON API authenticates with this cookie as a Bearer token (cookies → 401).
        self._token = self._http.cookies.get(_TOKEN_COOKIE)
        if not self._token:
            raise TeuxDeuxError(f"logged in but no {_TOKEN_COOKIE} cookie — auth shape changed")
        self._store_token(self._token)
        return self

    def ensure_session(self) -> Self:
        """Make the client usable with as few logins as possible: keep the in-memory token,
        else adopt a cached one (unverified — a stale token is caught by the 401 retry in
        _send), else perform a full login."""
        if self._token:
            return self
        cached = self._cached_token() if self._use_cache else None
        if cached:
            self._token = cached
            return self
        return self.login()

    # ── token cache ───────────────────────────────────────────────────────
    def _read_cache(self) -> dict[str, str]:
        try:
            data = json.loads(self._cache_path.read_text())
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
            return {}
        except (FileNotFoundError, ValueError, OSError):
            return {}

    def _cached_token(self) -> str | None:
        return self._read_cache().get(self._username)

    def _write_cache(self, data: dict[str, str]) -> None:
        if not self._use_cache:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(data))
            os.chmod(self._cache_path, 0o600)  # the token is a credential — owner-only
        except OSError:
            pass  # caching is best-effort; never fail a sync over it

    def _store_token(self, token: str) -> None:
        data = self._read_cache()
        data[self._username] = token
        self._write_cache(data)

    def _drop_token(self) -> None:
        data = self._read_cache()
        if data.pop(self._username, None) is not None:
            self._write_cache(data)

    def __enter__(self) -> Self:
        return self.ensure_session()

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # ── requests ──────────────────────────────────────────────────────────
    def _ws_required(self) -> str:
        if not self._ws:
            raise TeuxDeuxError(
                "workspace id not set — pass workspace_id=… or set TEUXDEUX_WORKSPACE_ID "
                "(find yours via workspaces())"
            )
        return self._ws

    def _send(self, method: str, path: str, *, params: Mapping[str, str] | None = None,
              json_body: Mapping[str, Any] | None = None,
              mutate: bool = False) -> httpx.Response:
        """One authenticated request with a one-shot relogin: a cached/expired token that
        yields 401 is dropped, re-logged-in fresh, and the request retried once. Mutations
        add the same-origin Content-Type/Origin/Referer headers the browser sends."""
        self.ensure_session()
        for attempt in (0, 1):
            headers = {"Accept": "application/json", "Authorization": f"Bearer {self._token}"}
            if mutate:
                headers.update({"Content-Type": "application/json",
                                "Origin": self._base, "Referer": f"{self._base}/home"})
            resp = self._http.request(method, path, params=params, json=json_body, headers=headers)
            if resp.status_code == 401 and attempt == 0:
                self._drop_token()
                self._token = None
                self.login()
                continue
            return resp
        raise AssertionError("unreachable — the second attempt always returns")

    def _request_json(self, method: str, path: str, *, params: Mapping[str, str] | None = None,
                      json_body: Mapping[str, Any] | None = None,
                      mutate: bool = False, parse: bool = True) -> Any:
        try:
            r = self._send(method, path, params=params, json_body=json_body, mutate=mutate)
            r.raise_for_status()
            return r.json() if parse else None
        except httpx.HTTPStatusError as e:
            raise TeuxDeuxError(f"{e.response.status_code} {e.response.reason_phrase} for {path}") from e
        except httpx.HTTPError as e:
            raise TeuxDeuxError(f"request failed for {path}: {e}") from e

    def _get_json(self, path: str, **params: str) -> Any:
        return self._request_json("GET", path, params=params or None)

    # ── endpoints ─────────────────────────────────────────────────────────
    def user(self) -> User:
        """The authenticated account."""
        return User.from_api(self._get_json(ACCOUNT_PATH)["account"])

    def workspaces(self) -> list[dict[str, Any]]:
        """Raw workspace records (id, name, list_sets, …) — use to find a workspace id."""
        return self._get_json(WORKSPACES_PATH).get("workspaces", [])

    def todos(
        self,
        since: dt.date | str | None = None,
        until: dt.date | str | None = None,
    ) -> list[Todo]:
        """Dated todos in [since, until] (YYYY-MM-DD)."""
        def iso(d: dt.date | str) -> str:
            return d.isoformat() if isinstance(d, dt.date) else d

        params: dict[str, str] = {}
        if since is not None:
            params["since"] = iso(since)
        if until is not None:
            params["until"] = iso(until)

        data = self._get_json(TODOS_PATH.format(ws=self._ws_required()), **params)
        return [Todo.from_api(t) for t in data.get("todos", [])]

    def _post_json(self, path: str, body: Mapping[str, Any]) -> Any:
        """POST JSON with the same auth + same-origin headers the browser sends on mutations."""
        return self._request_json("POST", path, json_body=body, mutate=True)

    def _patch_json(self, path: str, body: Mapping[str, Any]) -> Any:
        """PATCH JSON (edit a todo's fields). Returns the decoded response."""
        return self._request_json("PATCH", path, json_body=body, mutate=True)

    def _delete(self, path: str) -> None:
        """DELETE a resource. The server replies 204 No Content, so there's nothing to parse."""
        self._request_json("DELETE", path, mutate=True, parse=False)

    def set_done(self, todo_id: int, done: bool = True) -> Todo:
        """Mark a todo done/undone — POST /todos/{id}/state with {"done": bool}."""
        path = STATE_PATH.format(ws=self._ws_required(), id=todo_id)
        return Todo.from_api(self._post_json(path, {"done": done})["todo"])

    def create_todo(
        self,
        text: str,
        *,
        current_date: dt.date | str | None = None,
        done: bool = False,
    ) -> Todo:
        """Create a todo — POST /todos with {text, done, current_date}. Returns the new Todo.

        current_date is a date or "YYYY-MM-DD" (None creates an undated/list todo).
        """
        cd = current_date.isoformat() if isinstance(current_date, dt.date) else current_date
        path = TODOS_PATH.format(ws=self._ws_required())
        data = self._post_json(
            path,
            {"text": text, "done": done, "highlight_identifier": None, "current_date": cd},
        )
        return Todo.from_api(data.get("todo", data))

    def update_todo(self, todo_id: int, text: str) -> Todo:
        """Edit a todo's text — PATCH /todos/{id} with {"text": …}. Returns the updated Todo.

        (Toggling done is a separate sub-resource; use set_done. Confirmed live, June 2026.)
        """
        path = TODO_PATH.format(ws=self._ws_required(), id=todo_id)
        data = self._patch_json(path, {"text": text})
        return Todo.from_api(data.get("todo", data))

    def delete_todo(self, todo_id: int) -> None:
        """Delete a todo — DELETE /todos/{id} (server returns 204). Confirmed live, June 2026."""
        self._delete(TODO_PATH.format(ws=self._ws_required(), id=todo_id))
