"""httpx client for the v4, workspace-scoped TeuxDeux API.

Login is a Flask cookie session that yields a `_txdxtxdx_token`; the JSON API wants it as
an `Authorization: Bearer` token (cookies alone get a 401). See API.md.
"""

from __future__ import annotations

import datetime as dt
import os
import re

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
    ) -> None:
        self._username = username
        self._password = password
        self._base = base_url.rstrip("/")
        self._ws = str(workspace_id or os.environ.get("TEUXDEUX_WORKSPACE_ID") or "").strip()
        self._csrf: str | None = None
        self._token: str | None = None  # _txdxtxdx_token, sent as Authorization: Bearer
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=httpx.HTTPTransport(retries=retries),
            follow_redirects=True,
            headers={"User-Agent": "teuxdeux-py/0.1 (+https://github.com/namtonthat/teuxdeux)"},
        )

    # ── session ───────────────────────────────────────────────────────────
    def login(self) -> "TeuxDeuxClient":
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
        return self

    def __enter__(self) -> "TeuxDeuxClient":
        return self.login()

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

    def _get_json(self, path: str, **params: object):
        if not self._token:
            raise TeuxDeuxError("not logged in — call login() (or use the client as a context manager)")
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self._token}"}
        try:
            r = self._http.get(path, params=params or None, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise TeuxDeuxError(
                f"{e.response.status_code} {e.response.reason_phrase} for {path}"
            ) from e
        except httpx.HTTPError as e:
            raise TeuxDeuxError(f"request failed for {path}: {e}") from e

    # ── endpoints ─────────────────────────────────────────────────────────
    def user(self) -> User:
        """The authenticated account."""
        return User.from_api(self._get_json(ACCOUNT_PATH)["account"])

    def workspaces(self) -> list[dict]:
        """Raw workspace records (id, name, list_sets, …) — use to find a workspace id."""
        return self._get_json(WORKSPACES_PATH).get("workspaces", [])

    def todos(
        self,
        since: dt.date | str | None = None,
        until: dt.date | str | None = None,
    ) -> list[Todo]:
        """Dated todos in [since, until] (YYYY-MM-DD)."""
        def iso(d):
            return d.isoformat() if isinstance(d, dt.date) else d

        params: dict[str, object] = {}
        if since is not None:
            params["since"] = iso(since)
        if until is not None:
            params["until"] = iso(until)

        data = self._get_json(TODOS_PATH.format(ws=self._ws_required()), **params)
        return [Todo.from_api(t) for t in data.get("todos", [])]

    def _mutate_headers(self) -> dict:
        """Auth + same-origin headers the browser sends on every mutation (POST/PATCH/DELETE)."""
        if not self._token:
            raise TeuxDeuxError("not logged in — call login() (or use the client as a context manager)")
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Origin": self._base,
            "Referer": f"{self._base}/home",
        }

    def _post_json(self, path: str, body: dict):
        """POST JSON with the same auth + same-origin headers the browser sends on mutations."""
        headers = self._mutate_headers()
        try:
            r = self._http.post(path, json=body, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise TeuxDeuxError(f"{e.response.status_code} {e.response.reason_phrase} for {path}") from e
        except httpx.HTTPError as e:
            raise TeuxDeuxError(f"request failed for {path}: {e}") from e

    def _patch_json(self, path: str, body: dict):
        """PATCH JSON (edit a todo's fields). Returns the decoded response."""
        headers = self._mutate_headers()
        try:
            r = self._http.patch(path, json=body, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise TeuxDeuxError(f"{e.response.status_code} {e.response.reason_phrase} for {path}") from e
        except httpx.HTTPError as e:
            raise TeuxDeuxError(f"request failed for {path}: {e}") from e

    def _delete(self, path: str) -> None:
        """DELETE a resource. The server replies 204 No Content, so there's nothing to parse."""
        headers = self._mutate_headers()
        try:
            r = self._http.request("DELETE", path, headers=headers)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TeuxDeuxError(f"{e.response.status_code} {e.response.reason_phrase} for {path}") from e
        except httpx.HTTPError as e:
            raise TeuxDeuxError(f"request failed for {path}: {e}") from e

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

        (Toggling done is a separate sub-resource; use set_done. Reverse-engineered June 2026.)
        """
        path = TODO_PATH.format(ws=self._ws_required(), id=todo_id)
        data = self._patch_json(path, {"text": text})
        return Todo.from_api(data.get("todo", data))

    def delete_todo(self, todo_id: int) -> None:
        """Delete a todo — DELETE /todos/{id} (server returns 204). Reverse-engineered June 2026."""
        self._delete(TODO_PATH.format(ws=self._ws_required(), id=todo_id))
