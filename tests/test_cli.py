"""Tests for the CLI's batch dispatcher (apply_ops) using a fake client (no network)."""

from teuxdeux.cli import apply_ops
from teuxdeux.client import TeuxDeuxError
from teuxdeux.models import Todo


class FakeClient:
    """Records calls and returns canned Todos so apply_ops can be tested offline."""

    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on  # an op kind that should raise

    def _maybe_fail(self, kind):
        if kind == self._fail_on:
            raise TeuxDeuxError(f"boom on {kind}")

    def create_todo(self, text, *, current_date=None, done=False):
        self._maybe_fail("add")
        self.calls.append(("add", text, current_date, done))
        return Todo(id=10, text=text, done=done, current_date=current_date)

    def set_done(self, todo_id, done=True):
        self._maybe_fail("set-done")
        self.calls.append(("set-done", todo_id, done))
        return Todo(id=todo_id, text="x", done=done)

    def update_todo(self, todo_id, text):
        self._maybe_fail("edit")
        self.calls.append(("edit", todo_id, text))
        return Todo(id=todo_id, text=text)

    def delete_todo(self, todo_id):
        self._maybe_fail("delete")
        self.calls.append(("delete", todo_id))


def test_apply_ops_dispatches_every_kind_in_order():
    c = FakeClient()
    ops = [
        {"op": "add", "text": "buy milk", "date": "2026-06-25", "done": False},
        {"op": "set-done", "id": 5, "done": True},
        {"op": "edit", "id": 6, "text": "buy oat milk"},
        {"op": "delete", "id": 7},
    ]
    results = apply_ops(c, ops)

    assert [r["op"] for r in results] == ["add", "set-done", "edit", "delete"]
    assert all(r["ok"] for r in results)
    assert results[0]["todo"]["text"] == "buy milk"
    assert results[3] == {"op": "delete", "ok": True, "id": 7}
    assert c.calls == [
        ("add", "buy milk", "2026-06-25", False),
        ("set-done", 5, True),
        ("edit", 6, "buy oat milk"),
        ("delete", 7),
    ]


def test_apply_ops_continues_after_a_failure():
    c = FakeClient(fail_on="set-done")
    ops = [
        {"op": "add", "text": "a"},
        {"op": "set-done", "id": 1, "done": True},  # this one raises
        {"op": "delete", "id": 2},                  # must still run
    ]
    results = apply_ops(c, ops)

    assert results[0]["ok"] is True
    assert results[1]["ok"] is False and "boom" in results[1]["error"]
    assert results[2]["ok"] is True
    assert ("delete", 2) in c.calls          # later op ran despite the failure


def test_apply_ops_flags_unknown_op():
    results = apply_ops(FakeClient(), [{"op": "frobnicate", "id": 1}])
    assert results[0]["ok"] is False
    assert "frobnicate" in results[0]["error"]
