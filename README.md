# teuxdeux

An unofficial, typed TeuxDeux REST client — `httpx` + `pydantic`. Built to pull todos
out of TeuxDeux (e.g. into an Obsidian/NotePlan vault), with clean data models as the
reference point.

> **Status — the live API needs capturing.** TeuxDeux has no official API. The endpoints
> here come from the legacy client [`badboy/teuxdeux`](https://github.com/badboy/teuxdeux),
> whose own README confirms they stopped working after TeuxDeux's rebuild. The models,
> CLI, and plumbing are real; the **endpoints in `client.py` are placeholders**. To make
> fetching work, capture the current request from the web app (DevTools → Network → the
> JSON request that loads your lists → *Copy as cURL*) and update `BASE_URL`, the paths,
> and the auth in `src/teuxdeux/client.py`. See [`API.md`](API.md).

## Install (dev)

```sh
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Use

```sh
export TEUXDEUX_EMAIL=you@example.com
export TEUXDEUX_PASSWORD=...

teuxdeux user                      # auth check
teuxdeux todos --lookback 3        # todos from the last 3 days, as JSON
teuxdeux todos --since 2026-06-16  # todos on/after a date, as JSON
```

```python
import datetime as dt
from teuxdeux import TeuxDeuxClient

with TeuxDeuxClient(email, password) as c:
    for t in c.todos(since=dt.date.today() - dt.timedelta(days=3)):
        print(t.date, t.to_markdown())
```

## Data models (`src/teuxdeux/models.py`)

- **`Todo`** — `id, todo, done, do_on, position, user_id, updated_at`; helpers `is_someday`,
  `date`, `updated_at_dt`, `to_markdown()`. Someday items use `do_on = 1989-12-DD`.
- **`User`** — `id, login, email, time_zone, utc_offset`.

## Tests

```sh
pytest            # validates the models against tests/fixtures/*.json
```

## Credit

Endpoint reference and JSON fixtures adapted from [`badboy/teuxdeux`](https://github.com/badboy/teuxdeux).
