"""Validate the pydantic models against the captured API fixtures."""

import json
import pathlib

from teuxdeux.models import Todo, User

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_user_parses():
    u = User.model_validate(load("user.json"))
    assert u.id == 42
    assert u.email == "user@inter.net"
    assert u.utc_offset == 60


def test_todo_parses_and_renders():
    t = Todo.model_validate(load("todo.json"))
    assert t.id == 12345
    assert t.todo == "new todo"
    assert t.done is False
    assert t.is_someday is False
    assert t.date is not None and t.date.isoformat() == "2011-05-27"
    assert t.to_markdown() == "- [ ] new todo"


def test_todo_list_and_done_marker():
    todos = [Todo.model_validate(x) for x in load("todo_list.json")]
    assert len(todos) == 2
    done = next(t for t in todos if t.done)
    assert done.to_markdown() == "- [x] write specs"


def test_someday_has_no_calendar_date():
    t = Todo.model_validate(load("someday.json"))
    assert t.is_someday is True
    assert t.date is None
