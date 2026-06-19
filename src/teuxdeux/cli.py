"""Command-line interface: `teuxdeux user` / `todos [--since|--lookback]` / `set-done <id>`.

Credentials come from env: TEUXDEUX_USERNAME and TEUXDEUX_PASSWORD.
`todos` prints a JSON array; `set-done` flips a todo's done state (the vault sync uses both).
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
    todos.add_argument("--lookback", type=int, metavar="N",
                       help="shortcut for --since N days ago")
    done = sub.add_parser("set-done", help="mark a todo done (or undone) by id")
    done.add_argument("id", type=int, help="todo id")
    done.add_argument("--undone", action="store_true", help="mark not-done instead of done")
    args = parser.parse_args(argv)

    since = args.__dict__.get("since")
    until = None
    if args.__dict__.get("lookback") is not None:
        since = (dt.date.today() - dt.timedelta(days=args.lookback)).isoformat()
        until = dt.date.today().isoformat()

    username, password = _credentials()
    try:
        with TeuxDeuxClient(username, password) as client:
            if args.cmd == "user":
                print(json.dumps(dataclasses.asdict(client.user()), indent=2))
            elif args.cmd == "set-done":
                t = client.set_done(args.id, done=not args.undone)
                print(json.dumps(t.to_dict(), indent=2))
            else:
                items = client.todos(since=since, until=until)
                print(json.dumps([t.to_dict() for t in items], indent=2))
    except TeuxDeuxError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
