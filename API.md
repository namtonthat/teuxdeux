# TeuxDeux API reference

TeuxDeux ships no official API, so this is **reverse-engineered**. Everything under
"Current API (v4)" below was confirmed end-to-end from a live session (June 2026) and
is what [`src/teuxdeux/client.py`](src/teuxdeux/client.py) implements. Legacy notes
follow at the end for historical context.

---

## Authentication

Auth is a two-step dance: a Flask cookie-session login, then a Bearer token for the
JSON API.

1. **`GET /login`** — returns an HTML form containing a hidden `csrf_token` and sets a
   signed Flask `session` cookie.
2. **`POST /login`** (`application/x-www-form-urlencoded`) with:
   - `username`, `password`, `csrf_token`
   - `Origin` and `Referer` headers set to `https://teuxdeux.com`
     (Flask-WTF rejects HTTPS form POSTs without a same-origin referer)

   On success the server responds **`302 → /home`** and sets the auth cookies:
   `_txdxtxdx_token`, `refresh_token`, `remember_token`, and a fresh `session`.
3. **Authorize JSON requests with the token.** The v4 JSON API does *not* accept the
   cookie session — cookie-only requests return `401`. Take the `_txdxtxdx_token`
   cookie value and send it as a header:

   ```http
   Authorization: Bearer <_txdxtxdx_token>
   ```

   > Reading status codes: **`404`** = wrong path; **`401`** = right path, but a
   > missing or invalid Bearer token.

---

## Current API (v4)

**Base URL:** `https://teuxdeux.com/api/v4`

Workspace-scoped data lives under `/api/v4/workspaces/{workspace_id}`. Discover your
own workspace id from `GET /api/v4/workspaces`.

All endpoints below require the `Authorization: Bearer` header.

| Method   | Path                                                | Returns                                                    |
| -------- | --------------------------------------------------- | ---------------------------------------------------------- |
| `GET`    | `/account`                                          | `{ "account": {…} }` — the authenticated user              |
| `GET`    | `/workspaces`                                       | `{ "workspaces": [...] }` — `id`, `name`, `list_sets`, …   |
| `GET`    | `/workspaces/{ws}`                                  | `{ "workspace", "calendar_todos", "recurring_todos" }`     |
| `GET`    | `/workspaces/{ws}/todos?since=&until=`              | `{ "todos": [...] }` — dated todos                         |
| `POST`   | `/workspaces/{ws}/todos/{id}/state`                 | body `{ "done": bool }` → `{ "todo": {…} }` — toggle done  |
| `GET`    | `/workspaces/{ws}/day-labels?since=&until=`         | `{ "day_labels": [...] }`                                  |

**Notes**

- `since` / `until` are `YYYY-MM-DD` and **inclusive**, and may be **future** dates
  (e.g. fetching tomorrow's planned todos).
- Toggling done is its own sub-resource: `PATCH /todos/{id}` exists but rejects
  `{"done": …}` with `422 "Unknown field"`. Use `POST /todos/{id}/state` instead.
- Mutating requests send the same `Origin` / `Referer` headers as the browser.

---

## Data models

### Todo — `/workspaces/{ws}/todos`

| Field                   | Notes                                            |
| ----------------------- | ------------------------------------------------ |
| `id`                    |                                                  |
| `text`                  |                                                  |
| `done`                  |                                                  |
| `current_date`          | `YYYY-MM-DD`; `null` for undated ("list") todos  |
| `position`              |                                                  |
| `list_id`, `workspace_id`, `uuid` |                                        |
| `has_details`, `recurring_todo_id` |                                       |
| `created_at`, `updated_at` | timestamps in `%Y-%m-%dT%H:%M:%S%z`           |

### User — `/account`

| Field           | Notes                       |
| --------------- | --------------------------- |
| `id`            |                             |
| `email`         |                             |
| `display_name`  |                             |
| `timezone`      |                             |
| `confirmed`     |                             |

Extra fields the server returns (`subscription`, `features`, `workspaces`, …) are
ignored by `from_api`.

---

## Legacy API (defunct)

The pre-rebuild API ([`badboy/teuxdeux`](https://github.com/badboy/teuxdeux), ~2011)
used HTTP Basic auth against `/api/user.json` and `/api/list.json`, with a
`todo` / `do_on` todo shape (someday items encoded as `1989-12-DD`). All of those
endpoints now return `404` — they have been fully superseded by the v4 API above.
