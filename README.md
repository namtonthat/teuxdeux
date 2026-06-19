# teuxdeux

A small, typed, **unofficial** Python client for [TeuxDeux](https://teuxdeux.com).

Built on `httpx` and stdlib `dataclasses` — no heavy dependencies. It was
reverse-engineered against the current **v4** API (`login → Bearer token → todos`).
For the underlying endpoints and auth flow, see [`API.md`](API.md).

> **Note** — TeuxDeux has no official API. This project is not affiliated with or
> endorsed by TeuxDeux, and the API it targets may change without warning.

## Requirements

- Python 3.11+
- A TeuxDeux account

## Quick start

```sh
./scripts/setup.sh        # create a venv, install the package, and scaffold .env
```

Then open `.env` and fill in your credentials:

```ini
TEUXDEUX_USERNAME=you@example.com
TEUXDEUX_PASSWORD=your-password
TEUXDEUX_WORKSPACE_ID=123456    # optional — discover it with `client.workspaces()`
```

Credentials are read from `.env` or from real environment variables (real env vars
win). `.env` is gitignored — **never commit it.**

<details>
<summary>Manual install (without the script)</summary>

```sh
uv venv && uv pip install -e ".[dev]"
cp .env.example .env
```
</details>

## Usage

### Command line

```sh
teuxdeux user                 # auth check → prints your account as JSON
teuxdeux todos --lookback 3   # todos from the last 3 days → JSON array
teuxdeux todos --since 2026-06-16
teuxdeux todos --since 2026-06-20 --until 2026-06-20   # explicit window (may be in the future)
teuxdeux set-done 12345       # mark a todo done (--undone to reverse)
```

`--since` / `--until` accept any date, including future ones — `--lookback N` is just a
shortcut for `--since N-days-ago --until today`.

### Python

```python
import datetime as dt
from teuxdeux import TeuxDeuxClient

with TeuxDeuxClient(username, password) as client:
    since = dt.date.today() - dt.timedelta(days=3)
    for todo in client.todos(since=since):
        print(todo.date, todo.to_markdown())
```

The client is a context manager — it logs in on enter and closes the HTTP session
on exit.

## Models

Defined in [`src/teuxdeux/models.py`](src/teuxdeux/models.py) as `@dataclass`es. Each
is built with `from_api(dict)`, which keeps the modelled fields and ignores the rest.

| Model    | Key fields                                                        | Helpers                                          |
| -------- | ----------------------------------------------------------------- | ------------------------------------------------ |
| `Todo`   | `id`, `text`, `done`, `current_date`, `position`, …               | `is_someday`, `date`, `updated_at_dt`, `to_markdown()` |
| `User`   | `id`, `email`, `display_name`, `timezone`, `confirmed`            | —                                                |

Undated ("list") todos have `current_date = null`.

## Tests

```sh
pytest            # offline model tests against tests/fixtures/*.json
pytest -m live    # live login + fetch (needs TEUXDEUX_USERNAME / TEUXDEUX_PASSWORD)
```

## License

Unofficial, provided as-is. Use at your own risk.
