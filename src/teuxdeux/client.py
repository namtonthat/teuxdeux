"""A small, robust TeuxDeux REST client (httpx + pydantic).

⚠️  STATUS: the endpoints below are the LEGACY API (pre-rebuild) documented by
github.com/badboy/teuxdeux, which TeuxDeux's own client README confirms no longer
works. They are kept as a starting point. To make this fetch real, capture the
current request from the TeuxDeux web app (DevTools → Network → the JSON request that
loads your lists → "Copy as cURL") and update BASE_URL, the paths, and the auth in
`_AUTH`/`_get` accordingly. The models and the rest of the plumbing stay the same.
"""

from __future__ import annotations

import base64
import datetime as dt

import httpx

from .models import Todo, User

DEFAULT_BASE_URL = "https://teuxdeux.com/api"  # legacy — verify against current app


class TeuxDeuxError(RuntimeError):
    """Any failure talking to TeuxDeux (network, auth, or unexpected status)."""


class TeuxDeuxClient:
    """Authenticated client. Use as a context manager so the connection closes.

    >>> with TeuxDeuxClient(email, password) as c:
    ...     todos = c.todos(since=dt.date.today() - dt.timedelta(days=3))
    """

    def __init__(
        self,
        email: str,
        password: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        token = base64.b64encode(f"{email}:{password}".encode()).decode()
        # httpx retries connection-level failures; status retries are handled in _get.
        transport = httpx.HTTPTransport(retries=retries)
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
                "User-Agent": "teuxdeux-py/0.1 (+https://github.com/namtonthat/teuxdeux)",
            },
        )

    def __enter__(self) -> "TeuxDeuxClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _get(self, path: str, **params: object):
        try:
            resp = self._http.get(path, params=params or None)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            hint = " (legacy endpoint — verify against the current API)" if code in (401, 404) else ""
            raise TeuxDeuxError(f"{code} {e.response.reason_phrase} for {path}{hint}") from e
        except httpx.HTTPError as e:
            raise TeuxDeuxError(f"request failed for {path}: {e}") from e

    # ── endpoints ───────────────────────────────────────────────────────────
    def user(self) -> User:
        """The authenticated user (also the simplest auth check)."""
        return User.model_validate(self._get("/user.json"))

    def todos(self, since: dt.date | str | None = None) -> list[Todo]:
        """All dated todos, optionally only those on/after `since` (date or YYYY-MM-DD)."""
        params: dict[str, object] = {}
        if since is not None:
            params["since"] = since.isoformat() if isinstance(since, dt.date) else since
        data = self._get("/list.json", **params)
        return [Todo.model_validate(t) for t in data]
