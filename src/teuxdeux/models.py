"""Dataclass models for the current (v4) TeuxDeux API.

Field shapes confirmed against the live workspace-scoped API (see API.md). Todos come
from /api/v4/workspaces/{ws}/todos; the account from /api/v4/account. `from_api` keeps
only the fields we model and ignores the ~20 other keys the API returns.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt

# TeuxDeux's API timestamps look like "2026-05-27T08:48:39+0000".
_TS = "%Y-%m-%dT%H:%M:%S%z"


def _parse_ts(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, _TS)
    except ValueError:
        try:
            return dt.datetime.fromisoformat(s)
        except ValueError:
            return None


def _from_api(cls, data: dict):
    """Build a dataclass from an API dict, ignoring unknown keys."""
    known = {f.name for f in dc.fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


@dc.dataclass(slots=True)
class User:
    """The authenticated account (/api/v4/account → {"account": {...}})."""

    id: int
    email: str | None = None
    display_name: str | None = None
    timezone: str | None = None
    confirmed: bool = False

    @classmethod
    def from_api(cls, data: dict) -> "User":
        return _from_api(cls, data)


@dc.dataclass(slots=True)
class Todo:
    """A todo from /api/v4/workspaces/{ws}/todos."""

    id: int
    text: str
    done: bool = False
    current_date: str | None = None  # "YYYY-MM-DD"; null for undated (list/someday) todos
    position: int = 0
    list_id: int | None = None
    workspace_id: int | None = None
    uuid: str | None = None
    has_details: bool = False
    recurring_todo_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> "Todo":
        return _from_api(cls, data)

    @property
    def is_someday(self) -> bool:
        """True for undated todos (parked on a list rather than a calendar day)."""
        return not self.current_date

    @property
    def date(self) -> dt.date | None:
        """Calendar date for a dated todo, or None for undated/unparseable."""
        if not self.current_date:
            return None
        try:
            return dt.date.fromisoformat(self.current_date)
        except ValueError:
            return None

    @property
    def updated_at_dt(self) -> dt.datetime | None:
        return _parse_ts(self.updated_at)

    def to_markdown(self) -> str:
        """NotePlan/Obsidian checkbox line, e.g. '* [x] write specs'."""
        return f"* [{'x' if self.done else ' '}] {self.text.strip()}"

    def to_dict(self) -> dict:
        return dc.asdict(self)
