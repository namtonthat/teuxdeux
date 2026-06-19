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

    def set_done(self, todo_id: int, done: bool = True) -> Todo:
        """Mark a todo done/undone — POST /todos/{id}/state with {"done": bool}."""
        if not self._token:
            raise TeuxDeuxError("not logged in — call login() first")
        path = STATE_PATH.format(ws=self._ws_required(), id=todo_id)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Origin": self._base,
            "Referer": f"{self._base}/home",
        }
        try:
            r = self._http.post(path, json={"done": done}, headers=headers)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TeuxDeuxError(f"{e.response.status_code} {e.response.reason_phrase} for {path}") from e
        except httpx.HTTPError as e:
            raise TeuxDeuxError(f"request failed for {path}: {e}") from e
        return Todo.from_api(r.json()["todo"])
