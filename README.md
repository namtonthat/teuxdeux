# teuxdeux

Typed, unofficial **TeuxDeux** client — `httpx` + `pydantic`. Pulls your todos out of
TeuxDeux (e.g. into an Obsidian/NotePlan vault) with clean data models as the reference point.

## Status

TeuxDeux has no official API. The endpoints in `client.py` are the **legacy** ones from
[`badboy/teuxdeux`](https://github.com/badboy/teuxdeux), which no longer work after TeuxDeux's
rebuild. The models, CLI, and tests are real and passing; the live fetch needs the current
endpoints captured — see [`API.md`](API.md).

## Install

```sh
uv venv && uv pip install -e ".[dev]"
```

## Usage

```sh
cp .env.example .env   # then fill in TEUXDEUX_EMAIL / PASSWORD / WORKSPACE_ID (gitignored)

teuxdeux user                # auth check
teuxdeux todos --lookback 3  # todos from the last 3 days → JSON
teuxdeux todos --since 2026-06-16
```

Creds load from `.env` (via python-dotenv) or real env vars (env vars win).

```python
import datetime as dt
from teuxdeux import TeuxDeuxClient

with TeuxDeuxClient(email, password) as c:
    for t in c.todos(since=dt.date.today() - dt.timedelta(days=3)):
        print(t.date, t.to_markdown())
```

## Data models — `src/teuxdeux/models.py`

- **`Todo`**: `id, todo, done, do_on, position, user_id, updated_at` + `is_someday`, `date`,
  `to_markdown()`. Someday items use `do_on = 1989-12-DD`.
- **`User`**: `id, login, email, time_zone, utc_offset`.

## Tests

```sh
pytest          # model tests — offline, against tests/fixtures/*.json
teuxdeux user   # live auth check — needs working endpoints (see Status)
```

Credit: endpoint reference and fixtures adapted from [`badboy/teuxdeux`](https://github.com/badboy/teuxdeux).
