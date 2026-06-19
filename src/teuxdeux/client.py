"""A small, robust TeuxDeux client (httpx + pydantic) for the current (v3) site.

Reverse-engineered from the live site (see API.md), since TeuxDeux has no official API:
  - login is a form POST to /login with `username`, `password`, `csrf_token`
    (the csrf_token + a session cookie come from GET /login first)
  - the JSON API lives under /api/v3/ and is reached with that session cookie
    (+ an X-CSRF-Token header)

CONFIRMED by probing: /login form fields and that /api/v3/* exists.
NOT yet confirmed (needs one authenticated DevTools "Copy as cURL"): the exact data
endpoint + its JSON shape. `user()` targets the likely `/api/v3/me`; `todos()` targets
LIST_PATH below — adjust both (and `models.Todo`) once you've seen a real response.
"""

from __future__ import annotations

import datetime as dt
import re

import httpx

from .models import Todo, User

BASE_URL = "https://teuxdeux.com"
API = "/api/v3"
LIST_PATH = "/api/v3/dashboard"  # TBD — confirm via DevTools (could be /lists, /refresh, …)
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
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        self._username = username
        self._password = password
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
        """Establish an authenticated session (csrf + cookie via /login, then POST creds)."""
        page = self._http.get("/login")
        page.raise_for_status()
        m = _CSRF_RE.search(page.text) or _CSRF_RE_ALT.search(page.text)
        if not m:
            raise TeuxDeuxError("no csrf_token on /login — the login page shape changed")
        self._csrf = m.group(1)

        resp = self._http.post(
            "/login",
            data={"username": self._username, "password": self._password,
                  "csrf_token": self._csrf},
            headers={"X-CSRF-Token": self._csrf},
        )
        if resp.status_code >= 400:
            raise TeuxDeuxError(f"login failed (HTTP {resp.status_code})")
        if resp.url.path.rstrip("/").endswith("/login"):
            raise TeuxDeuxError("login rejected — check TEUXDEUX_EMAIL / TEUXDEUX_PASSWORD")
        return self

    def __enter__(self) -> "TeuxDeuxClient":
        return self.login()

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # ── requests ──────────────────────────────────────────────────────────
    def _get_json(self, path: str, **params: object):
        headers = {"Accept": "application/json"}
        if self._csrf:
            headers["X-CSRF-Token"] = self._csrf
        try:
            r = self._http.get(path, params=params or None, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise TeuxDeuxError(
                f"{e.response.status_code} {e.response.reason_phrase} for {path} "
                "(endpoint/shape unconfirmed — see API.md)"
            ) from e
        except httpx.HTTPError as e:
            raise TeuxDeuxError(f"request failed for {path}: {e}") from e

    # ── endpoints (shapes pending live confirmation) ──────────────────────
    def user(self) -> User:
        """Authenticated user — also the simplest live auth check."""
        return User.model_validate(self._get_json(f"{API}/me"))

    def todos(self, since: dt.date | str | None = None) -> list[Todo]:
        """Todos, optionally on/after `since`. Endpoint + shape unconfirmed (see API.md)."""
        params: dict[str, object] = {}
        if since is not None:
            params["since"] = since.isoformat() if isinstance(since, dt.date) else since
        data = self._get_json(LIST_PATH, **params)
        items = data if isinstance(data, list) else (data.get("todos") or data.get("items") or [])
        try:
            return [Todo.model_validate(t) for t in items]
        except Exception as e:  # noqa: BLE001 — surface a clear "shape changed" message
            raise TeuxDeuxError(
                f"could not parse todos from {LIST_PATH} ({e}); the v3 shape likely differs "
                "from models.Todo — capture a real response (API.md) and update the model"
            ) from e
