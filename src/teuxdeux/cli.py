"""CLI: `teuxdeux user | workspaces | todos [--since|--until|--lookback] | set-done | add | edit | delete | apply`.

Credentials from env (TEUXDEUX_USERNAME / TEUXDEUX_PASSWORD); commands print JSON.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import sys

from dotenv import find_dotenv, load_dotenv

from .client import TeuxDeuxClient, TeuxDeuxError


def _credentials() -> tuple[str, str]:
    username = os.environ.get("TEUXDEUX_USERNAME")
    password = os.environ.get("TEUXDEUX_PASSWORD")
    if not username or not password:
        sys.exit("error: set TEUXDEUX_USERNAME and TEUXDEUX_PASSWORD in the environment")
    return username, password


def apply_ops(client, ops: list[dict]) -> list[dict]:
    """Run a batch of mutations against one logged-in client, in order, returning one result
    per op. A failing op is reported as {"ok": False, "error": …} and does NOT abort the rest,
    so a single bad delete can't strand the creates that follow it. Op shapes:

      {"op": "add", "text": str, "date": "YYYY-MM-DD"|null, "done": bool}
      {"op": "set-done", "id": int, "done": bool}
      {"op": "edit", "id": int, "text": str}
      {"op": "delete", "id": int}
    """
    results: list[dict] = []
    for op in ops:
        kind = op.get("op")
        try:
            if kind == "add":
                t = client.create_todo(op["text"], current_date=op.get("date"), done=op.get("done", False))
                results.append({"op": "add", "ok": True, "todo": t.to_dict()})
            elif kind == "set-done":
                t = client.set_done(op["id"], done=op.get("done", True))
                results.append({"op": "set-done", "ok": True, "todo": t.to_dict()})
            elif kind == "edit":
                t = client.update_todo(op["id"], op["text"])
                results.append({"op": "edit", "ok": True, "todo": t.to_dict()})
            elif kind == "delete":
                client.delete_todo(op["id"])
                results.append({"op": "delete", "ok": True, "id": op["id"]})
            else:
                results.append({"op": kind, "ok": False, "error": f"unknown op {kind!r}"})
        except (TeuxDeuxError, KeyError) as e:
            results.append({"op": kind, "ok": False, "error": str(e)})
    return results


def main(argv: list[str] | None = None) -> None:
    # usecwd: search from the caller's directory, not this file's — a tool-installed CLI
    # lives in site-packages, where the default upward search would never find a .env.
    load_dotenv(find_dotenv(usecwd=True))  # real env vars still take precedence
    parser = argparse.ArgumentParser(prog="teuxdeux", description="Unofficial TeuxDeux client")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("user", help="print the authenticated user (auth check)")
    sub.add_parser("workspaces", help="list workspaces (find your workspace id)")
    todos = sub.add_parser("todos", help="print todos as a JSON array")
    todos.add_argument("--since", metavar="YYYY-MM-DD", help="only todos on/after this date")
    todos.add_argument("--until", metavar="YYYY-MM-DD",
                       help="only todos on/before this date (may be in the future)")
    todos.add_argument("--lookback", type=int, metavar="N",
                       help="shortcut for --since N days ago (until defaults to today)")
    done = sub.add_parser("set-done", help="mark a todo done (or undone) by id")
    done.add_argument("id", type=int, help="todo id")
    done.add_argument("--undone", action="store_true", help="mark not-done instead of done")
    add = sub.add_parser("add", help="create a todo")
    add.add_argument("text", help="todo text")
    add.add_argument("--date", metavar="YYYY-MM-DD", help="calendar date (default: undated)")
    add.add_argument("--done", action="store_true", help="create it already done")
    edit = sub.add_parser("edit", help="edit a todo's text by id")
    edit.add_argument("id", type=int, help="todo id")
    edit.add_argument("text", help="new todo text")
    delete = sub.add_parser("delete", help="delete a todo by id")
    delete.add_argument("id", type=int, help="todo id")
    sub.add_parser("apply", help="run a JSON array of ops (from stdin) in one session")
    args = parser.parse_args(argv)

    since = args.__dict__.get("since")
    until = args.__dict__.get("until")
    if args.__dict__.get("lookback") is not None:
        since = (dt.date.today() - dt.timedelta(days=args.lookback)).isoformat()
        until = until or dt.date.today().isoformat()

    username, password = _credentials()
    try:
        with TeuxDeuxClient(username, password) as client:
            if args.cmd == "user":
                print(json.dumps(dataclasses.asdict(client.user()), indent=2))
            elif args.cmd == "workspaces":
                print(json.dumps(client.workspaces(), indent=2))
            elif args.cmd == "set-done":
                t = client.set_done(args.id, done=not args.undone)
                print(json.dumps(t.to_dict(), indent=2))
            elif args.cmd == "add":
                t = client.create_todo(args.text, current_date=args.date, done=args.done)
                print(json.dumps(t.to_dict(), indent=2))
            elif args.cmd == "edit":
                t = client.update_todo(args.id, args.text)
                print(json.dumps(t.to_dict(), indent=2))
            elif args.cmd == "delete":
                client.delete_todo(args.id)
                print(json.dumps({"deleted": args.id}, indent=2))
            elif args.cmd == "apply":
                ops = json.loads(sys.stdin.read() or "[]")
                print(json.dumps(apply_ops(client, ops), indent=2))
            else:
                items = client.todos(since=since, until=until)
                print(json.dumps([t.to_dict() for t in items], indent=2))
    except TeuxDeuxError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
