# teuxdeux

Typed, unofficial **TeuxDeux** client — `httpx` + stdlib `dataclasses`, no heavy deps.
Reverse-engineered against the current **v4** API (login → Bearer token → todos); see
[`API.md`](API.md) for the endpoints and auth flow.

## Install

```sh
uv venv && uv pip install -e ".[dev]"
cp .env.example .env   # fill in TEUXDEUX_USERNAME / PASSWORD / WORKSPACE_ID (gitignored)
```

Creds load from `.env` or real env vars (env vars win).

## Usage

```sh
teuxdeux user                # auth check → account JSON
teuxdeux todos --lookback 3  # last 3 days of todos → JSON array
teuxdeux todos --since 2026-06-16
```

```python
import datetime as dt
from teuxdeux import TeuxDeuxClient

with TeuxDeuxClient(username, password) as c:
    for t in c.todos(since=dt.date.today() - dt.timedelta(days=3)):
        print(t.date, t.to_markdown())
```

## Models — `src/teuxdeux/models.py`

`@dataclass`es built via `from_api(dict)`, which keeps modelled fields and ignores the rest.

- **`Todo`**: `id, text, done, current_date, position, …` + `is_someday`, `date`,
  `updated_at_dt`, `to_markdown()`. Undated (list) todos have `current_date = null`.
- **`User`**: `id, email, display_name, timezone, confirmed`.

## Tests

```sh
pytest          # offline model tests against tests/fixtures/*.json
pytest -m live  # live login + fetch (needs TEUXDEUX_USERNAME/PASSWORD)
```
