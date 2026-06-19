# TeuxDeux API reference

Reverse-engineered (TeuxDeux has no official API). The **current v4 API** below is confirmed
end-to-end from a live session (2026-06); `client.py` implements it. Legacy notes at the end.

## Auth — Flask cookie login → Bearer token

1. `GET /login` → HTML form with a hidden `csrf_token`; sets a signed Flask `session` cookie.
2. `POST /login` (`application/x-www-form-urlencoded`): `username`, `password`, `csrf_token`,
   plus `Origin`/`Referer` of `https://teuxdeux.com` (Flask-WTF rejects HTTPS POSTs without it).
   Success → **302 `/home`**, setting auth cookies (`_txdxtxdx_token`, `refresh_token`,
   `remember_token`, new `session`).
3. **The v4 JSON API does *not* accept the cookie session** — cookie-only GETs return `401`.
   Send the `_txdxtxdx_token` cookie value as `Authorization: Bearer <token>`. (404 = wrong
   path; 401 = right path, missing/invalid Bearer.)

## Data API

Base: `https://teuxdeux.com/api/v4`. Workspace-scoped data lives under
`/api/v4/workspaces/{workspace_id}` (the default account is `123456`).

Confirmed endpoints (all need the Bearer header):

| Method/path | Returns |
|---|---|
| `GET /api/v4/account` | `{"account": {...}}` — the authenticated user |
| `GET /api/v4/workspaces` | `{"workspaces": [...]}` — id, name, list_sets, … |
| `GET /api/v4/workspaces/{ws}` | `{"workspace", "calendar_todos", "recurring_todos"}` |
| `GET /api/v4/workspaces/{ws}/todos?since=&until=` | `{"todos": [...]}` — dated todos |
| `POST /api/v4/workspaces/{ws}/todos/{id}/state` | body `{"done": bool}` → `{"todo": {...}}` — toggle done |
| `GET /api/v4/workspaces/{ws}/day-labels?since=&until=` | `{"day_labels": [...]}` |

`PATCH /todos/{id}` exists but rejects `{"done": ...}` (422 "Unknown field"); done-state is its
own `/state` sub-resource. Mutations send `Origin`/`Referer` headers like the browser.

`since`/`until` are `YYYY-MM-DD` (inclusive).

## Models

- **Todo** (`/workspaces/{ws}/todos`): `id`, `text`, `done`, `current_date` (`YYYY-MM-DD`,
  null for undated list todos), `position`, `list_id`, `workspace_id`, `uuid`, `has_details`,
  `recurring_todo_id`, `created_at`, `updated_at`. Timestamps are `%Y-%m-%dT%H:%M:%S%z`.
- **User** (`/account`): `id`, `email`, `display_name`, `timezone`, `confirmed` (plus
  `subscription`, `features`, `workspaces`, … which `from_api` ignores).

## Legacy (defunct)

The pre-rebuild API ([`badboy/teuxdeux`](https://github.com/badboy/teuxdeux), ~2011) used HTTP
Basic auth on `/api/user.json` and `/api/list.json` with a `todo`/`do_on` todo shape (someday =
`1989-12-DD`) — all now `404`. Superseded entirely by the v4 API above.
