"""Validate the dataclass models against the captured v4 API fixtures."""

import json
import pathlib

from teuxdeux.models import Todo, User

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_user_parses_and_ignores_extra():
    u = User.from_api(load("account.json"))
    assert u.id == 1001
    assert u.email == "user@example.com"
    assert u.display_name == "Example User"
    assert u.confirmed is True  # unknown keys (subscription, websocket_token) ignored


def test_todo_parses_and_renders():
    t = Todo.from_api(load("todo.json"))
    assert t.id == 12345
    assert t.text == "new todo "
    assert t.done is False
    assert t.is_someday is False
    assert t.date is not None and t.date.isoformat() == "2026-06-18"
    assert t.to_markdown() == "* [ ] new todo"  # trailing space trimmed
    assert t.updated_at_dt is not None


def test_todo_list_and_done_marker():
    todos = [Todo.from_api(x) for x in load("todo_list.json")]
    assert len(todos) == 2
    done = next(t for t in todos if t.done)
    assert done.to_markdown() == "* [x] write specs"


def test_someday_has_no_calendar_date():
    t = Todo.from_api(load("someday.json"))
    assert t.is_someday is True
    assert t.date is None
