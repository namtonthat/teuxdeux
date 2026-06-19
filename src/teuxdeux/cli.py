"""Command-line interface: `teuxdeux user` / `teuxdeux todos [--since YYYY-MM-DD]`.

Credentials come from env: TEUXDEUX_EMAIL and TEUXDEUX_PASSWORD.
`todos` prints a JSON array (consumed by the vault's daily-note writer).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

from dotenv import load_dotenv

from .client import TeuxDeuxClient, TeuxDeuxError


def _credentials() -> tuple[str, str]:
    email = os.environ.get("TEUXDEUX_EMAIL")
    password = os.environ.get("TEUXDEUX_PASSWORD")
    if not email or not password:
        sys.exit("error: set TEUXDEUX_EMAIL and TEUXDEUX_PASSWORD in the environment")
    return email, password


def main(argv: list[str] | None = None) -> None:
    load_dotenv()  # load .env if present; real env vars still take precedence
    parser = argparse.ArgumentParser(prog="teuxdeux", description="Unofficial TeuxDeux client")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("user", help="print the authenticated user (auth check)")
    todos = sub.add_parser("todos", help="print todos as a JSON array")
    todos.add_argument("--since", metavar="YYYY-MM-DD", help="only todos on/after this date")
    todos.add_argument("--lookback", type=int, metavar="N",
                       help="shortcut for --since N days ago")
    args = parser.parse_args(argv)

    since = args.__dict__.get("since")
    until = None
    if args.__dict__.get("lookback") is not None:
        since = (dt.date.today() - dt.timedelta(days=args.lookback)).isoformat()
        until = dt.date.today().isoformat()

    email, password = _credentials()
    try:
        with TeuxDeuxClient(email, password) as client:
            if args.cmd == "user":
                print(client.user().model_dump_json(indent=2))
            else:
                items = client.todos(since=since, until=until)
                print(json.dumps([t.model_dump() for t in items], indent=2))
    except TeuxDeuxError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
