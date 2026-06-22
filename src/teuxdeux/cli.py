"""CLI: `teuxdeux user | todos [--since|--until|--lookback] | set-done <id> | add | edit | delete`.

Credentials from env (TEUXDEUX_USERNAME / TEUXDEUX_PASSWORD); commands print JSON.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import sys

from dotenv import load_dotenv

from .client import TeuxDeuxClient, TeuxDeuxError


def _credentials() -> tuple[str, str]:
    username = os.environ.get("TEUXDEUX_USERNAME")
    password = os.environ.get("TEUXDEUX_PASSWORD")
    if not username or not password:
        sys.exit("error: set TEUXDEUX_USERNAME and TEUXDEUX_PASSWORD in the environment")
    return username, password


def main(argv: list[str] | None = None) -> None:
    load_dotenv()  # load .env if present; real env vars still take precedence
    parser = argparse.ArgumentParser(prog="teuxdeux", description="Unofficial TeuxDeux client")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("user", help="print the authenticated user (auth check)")
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
            else:
                items = client.todos(since=since, until=until)
                print(json.dumps([t.to_dict() for t in items], indent=2))
    except TeuxDeuxError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
