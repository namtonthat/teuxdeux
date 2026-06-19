"""TeuxDeux client (httpx + pydantic) for the current v4, workspace-scoped API.

Flask cookie-session login, then GET /api/v4/workspaces/{id}/... with since/until. See API.md
for the full auth flow. TODOS_PATH and the Todo shape are the one unconfirmed bit — todos()
prints the real field names on a parse mismatch so the first authed run reveals them.
"""

from __future__ import annotations

import datetime as dt
import os
import re

import httpx

from .models import Todo, User

BASE_URL = "https://teuxdeux.com"
# {ws} = numeric workspace id (the live capture used 123456).
TODOS_PATH = "/api/v4/workspaces/{ws}/todos/for-date-range"  # BEST GUESS — verify (API.md)
ME_PATH = "/api/v4/workspaces/{ws}/me"  # best guess; only used by user()
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
                "(yours from the capture is 123456)"
            )
        return self._ws

    def _get_json(self, path: str, **params: object):
        try:
            r = self._http.get(path, params=params or None, headers={"Accept": "application/json"})
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise TeuxDeuxError(
                f"{e.response.status_code} {e.response.reason_phrase} for {path} "
                "(endpoint/auth unconfirmed — see API.md)"
            ) from e
        except httpx.HTTPError as e:
            raise TeuxDeuxError(f"request failed for {path}: {e}") from e

    # ── endpoints ─────────────────────────────────────────────────────────
    def user(self) -> User:
        return User.model_validate(self._get_json(ME_PATH.format(ws=self._ws_required())))

    def todos(
        self,
        since: dt.date | str | None = None,
        until: dt.date | str | None = None,
    ) -> list[Todo]:
        """Todos in [since, until]. The v4 endpoint takes since/until (YYYY-MM-DD)."""
        def iso(d):
            return d.isoformat() if isinstance(d, dt.date) else d

        params: dict[str, object] = {}
        if since is not None:
            params["since"] = iso(since)
        if until is not None:
            params["until"] = iso(until)

        data = self._get_json(TODOS_PATH.format(ws=self._ws_required()), **params)
        items = data if isinstance(data, list) else (
            data.get("todos") or data.get("items") or data.get("data") or []
        )
        try:
            return [Todo.model_validate(t) for t in items]
        except Exception as e:  # noqa: BLE001 — turn a shape mismatch into a discovery aid
            sample = items[0] if items else {}
            keys = list(sample.keys()) if isinstance(sample, dict) else type(sample).__name__
            raise TeuxDeuxError(
                f"got {len(items)} item(s) from {TODOS_PATH.format(ws=self._ws)} but couldn't "
                f"parse them into Todo ({e}). Actual field names: {keys}. "
                "Map these in models.Todo (Field(alias=...)) — see API.md."
            ) from e
