# teuxdeux

Typed, unofficial **TeuxDeux** client — `httpx` + stdlib `dataclasses`, no heavy deps. Pulls
your todos out of TeuxDeux (e.g. into an Obsidian/NotePlan vault) with clean data models.

## Status

TeuxDeux has no official API; this targets the current **v4** API, reverse-engineered and
confirmed end-to-end (login → Bearer token → todos). See [`API.md`](API.md) for the full
auth flow and endpoints.

## Install

```sh
uv venv && uv pip install -e ".[dev]"
```

## Usage

```sh
cp .env.example .env   # then fill in TEUXDEUX_USERNAME / PASSWORD / WORKSPACE_ID (gitignored)

teuxdeux user                # auth check
teuxdeux todos --lookback 3  # todos from the last 3 days → JSON
teuxdeux todos --since 2026-06-16
```

Creds load from `.env` (via python-dotenv) or real env vars (env vars win).

```python
import datetime as dt
from teuxdeux import TeuxDeuxClient

with TeuxDeuxClient(username, password) as c:
    for t in c.todos(since=dt.date.today() - dt.timedelta(days=3)):
        print(t.date, t.to_markdown())
```

## Data models — `src/teuxdeux/models.py`

- **`Todo`**: `id, text, done, current_date, position, list_id, workspace_id, uuid,
  has_details, recurring_todo_id, created_at, updated_at` + `is_someday`, `date`,
  `updated_at_dt`, `to_markdown()`. Undated (list) todos have `current_date = null`.
- **`User`**: `id, email, display_name, timezone, confirmed`.

Both are `@dataclass`es; `from_api(dict)` builds one while ignoring the extra keys the API returns.

## Tests

```sh
pytest               # model tests — offline, against tests/fixtures/*.json
pytest -m live       # live login + fetch — needs TEUXDEUX_USERNAME/PASSWORD
teuxdeux user        # quick live auth check
```
