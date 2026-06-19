"""Pydantic data models for TeuxDeux entities.

Field shapes are taken from the legacy API fixtures (credit: github.com/badboy/teuxdeux).
The current TeuxDeux app may return a different shape — when you capture the live API,
adjust these models and add an alias for any renamed field via `Field(alias=...)`.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

# TeuxDeux encodes "Someday" items with a sentinel year; do_on = 1989-12-DD where
# DD is the someday-column position (01 = leftmost), not a real calendar date.
SOMEDAY_YEAR = 1989


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    login: str | None = None  # legacy field; may be absent on the v3 /me shape
    email: str | None = None
    time_zone: str | None = None
    utc_offset: int | None = None  # minutes east of UTC


class Todo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    todo: str  # the task text
    done: bool = False
    do_on: str  # "YYYY-MM-DD", or "1989-12-DD" for someday items
    position: int = 0
    user_id: int | None = None
    updated_at: int | None = None  # unix epoch seconds

    @property
    def is_someday(self) -> bool:
        return self.do_on.startswith(f"{SOMEDAY_YEAR}-")

    @property
    def date(self) -> dt.date | None:
        """Calendar date for a dated todo, or None for someday items / unparseable."""
        if self.is_someday:
            return None
        try:
            return dt.date.fromisoformat(self.do_on)
        except ValueError:
            return None

    @property
    def updated_at_dt(self) -> dt.datetime | None:
        if self.updated_at is None:
            return None
        return dt.datetime.fromtimestamp(self.updated_at, dt.timezone.utc)

    def to_markdown(self) -> str:
        """NotePlan/Obsidian checkbox line, e.g. '- [x] write specs'."""
        return f"- [{'x' if self.done else ' '}] {self.todo.strip()}"
