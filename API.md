# TeuxDeux API reference

Reverse-engineered (TeuxDeux has no official API). The **current v4 API** below is confirmed
from a live session (2026-06); `client.py` implements it. Legacy notes at the end.

## Auth — Flask, cookie session

1. `GET /login` → HTML form with a hidden `csrf_token`; sets a signed Flask `session` cookie.
2. `POST /login` (`application/x-www-form-urlencoded`): `username`, `password`, `csrf_token`,
   plus `Origin`/`Referer` of `https://teuxdeux.com` (Flask-WTF rejects HTTPS POSTs without it).
   Success → **302 `/home`**, setting auth cookies (`_txdxtxdx_token`, `refresh_token`,
   `remember_token`, new `session`).
3. `GET /api/v4/...` rides those cookies — GETs need no CSRF header.

## Data API

Base: `https://teuxdeux.com/api/v4/workspaces/{workspace_id}` (the capture used `123456`).
Date-range endpoints take `?since=YYYY-MM-DD&until=YYYY-MM-DD`.

Confirmed GETs: `day-labels/for-date-range`, `day-labels`, `day-labels/locales/{year}`,
`day-labels/subscriptions`, `settings/focus-modes`.

## Models

- **Todo**: `id`, `todo` (text), `done`, `do_on` (`YYYY-MM-DD`; someday = `1989-12-DD`),
  `position`, `user_id`, `updated_at`. *(Legacy shape — v4 likely renames to
  `text`/`completed`/`current_date`; confirm and map via `Field(alias=...)`.)*
- **User**: `id`, `login`, `email`, `time_zone`, `utc_offset`.

## Outstanding — one authenticated run

The only unconfirmed piece is the **todos endpoint + its JSON shape**. Best guess:
`/todos/for-date-range` (sibling of `day-labels/for-date-range`). `client.py`'s `todos()`
prints the real field names on a parse mismatch, so the first authed run reveals them — then
set `TODOS_PATH` and the `Todo` aliases.

## Legacy (defunct)

The pre-rebuild API ([`badboy/teuxdeux`](https://github.com/badboy/teuxdeux), ~2011) used HTTP
Basic auth on `/api/user.json` and `/api/list.json` — now `404`. The JSON fixtures in `tests/`
come from it and seeded the initial models.
