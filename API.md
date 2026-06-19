# TeuxDeux API reference

Two parts: the **legacy API** (what this client currently targets, now defunct) and a
**template for capturing the current API** so the client can be updated.

## Legacy API (source: badboy/teuxdeux, ~2011 — no longer works)

Base: `https://teuxdeux.com/api` · Auth: HTTP Basic (`Authorization: Basic base64(email:password)`),
sets a `_barebones_session` cookie.

| Method | Path | Notes |
|---|---|---|
| GET | `/user.json` | authed user; also the auth check |
| GET | `/list.json?since=YYYY-MM-DD` | dated todos (optional `since`) |
| GET | `/list/someday.json` | someday items (`do_on` = `1989-12-DD`) |
| POST | `/todo.json` | create (`todo_item[todo|do_on|done|position]`) |
| POST | `/update.json` | batch update (`todo_item[<id>][done|position|do_on]`) |
| POST | `/todo/<id>` | delete (`_method=delete`) |

### Todo fields
`id` int · `todo` str (text) · `done` bool · `do_on` `YYYY-MM-DD` (or `1989-12-DD` someday)
· `position` int · `user_id` int · `updated_at` unix-epoch int.

### User fields
`id` int · `login` str · `email` str · `time_zone` str · `utc_offset` int (minutes).

## Current API (v4) — confirmed from a live session (2026-06)

Base: `https://teuxdeux.com/api/v4/workspaces/{workspace_id}` (workspace-scoped; the live
capture used workspace `123456`). Date-range endpoints take `?since=YYYY-MM-DD&until=YYYY-MM-DD`
— exactly the lookback window we want.

Observed GETs:
- `/day-labels/for-date-range?since=…&until=…` — per-day labels for a range
- `/day-labels`, `/day-labels/locales/{year}`, `/day-labels/subscriptions`
- `/settings/focus-modes`

### Auth — CONFIRMED (Flask, cookie session)
TeuxDeux is a Flask app. Login:
1. `GET /login` → HTML form with hidden `csrf_token`; sets a `session` cookie (Flask, signed;
   contains the csrf_token).
2. `POST /login` — `application/x-www-form-urlencoded`, body `username` + `password` +
   `csrf_token`. Success → **302 `/home`**, sets auth cookies: `_txdxtxdx_token` (access),
   `refresh_token` (HttpOnly), `remember_token` (HttpOnly), new `session`.
3. `GET /api/v4/...` rides those cookies. GETs need no CSRF header.

`client.py` implements exactly this.

### Still needed (one capture): the todos endpoint + shape
The request whose response holds your **task text** — best guess `/todos/for-date-range`
(sibling of the observed `day-labels/for-date-range`). `client.py`'s `todos()` will print the
real field names if they don't match `models.Todo`, so the first authed run reveals the shape.
Confirm: the exact path, and the todo JSON keys (likely `text`/`completed`/`current_date`).

---

## Legacy probe (v3) — superseded by v4 above

Probed from the live site without logging in:

- `GET /api/user.json` → **404** — legacy API is gone.
- `GET /api/v3/*` (me, lists, todos, dashboard, …) → **400** for everything, i.e. a blanket
  "unauthenticated/bad request" for the whole `/api/v3` namespace. So the API base is
  **`/api/v3`**, but individual endpoint names can't be fingerprinted by status code.
- `/login` is a **form POST** (`<form action="/login">`) with fields **`username`**,
  **`password`**, **`csrf_token`**. The `csrf_token` (and a session cookie) come from
  `GET /login` first.

`client.py` implements this: GET `/login` → scrape `csrf_token` → POST `/login` → session
cookie → `GET /api/v3/...` with `X-CSRF-Token`.

### Login is JS-hijacked
The `<form action="/login" method="POST">` is a progressive-enhancement fallback: a direct
POST to `/login` (even form-encoded) returns **404**, so the app intercepts the submit and
POSTs to an API endpoint via fetch. POST-probing:

| status | endpoint | read |
|---|---|---|
| 404 | `POST /login` | not the real target |
| 405 | `POST /sessions` | route exists, wrong method |
| 400 | `POST /api/v3/sessions` | **likely the real login** (needs proper JSON body) |
| 400 | `POST /api/v3/login` / `/users/sign_in` | ambiguous (blanket /api/v3 400) |

So `client.py`'s `login()` (POST `/login`) is **wrong** and needs the real endpoint.

### Still unconfirmed (needs ONE authenticated capture)
- [ ] **Login**: real endpoint (prob. `POST /api/v3/sessions`), body (JSON? `email`+`password`+csrf?), success signal.
- [ ] **Data endpoint** (`LIST_PATH` in `client.py` is a guess: `/api/v3/dashboard`).
- [ ] **Todo response shape** — likely renamed vs legacy (e.g. `text`/`completed`/`current_date`
      not `todo`/`done`/`do_on`) → update `models.Todo` with `Field(alias=...)`.
- [ ] **Auth header** on `/api/v3` — `X-CSRF-Token`, bearer, or cookie-only.

To capture: log in at https://teuxdeux.com → DevTools → **Network** (Fetch/XHR) → reload →
the request whose JSON contains your task text → **Copy as cURL**, then paste below:

```
# (paste DevTools "Copy as cURL" output here)
```
