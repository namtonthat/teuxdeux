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

## Capturing the CURRENT API (to make fetching work)

The post-rebuild app is a SPA with its own (undocumented) endpoints. To find them:

1. Log in at https://teuxdeux.com in a browser.
2. Open DevTools → **Network**, filter to **Fetch/XHR**, reload.
3. Find the request that returns your lists/todos (look for JSON with your task text).
4. Right-click → **Copy → Copy as cURL**.

From that cURL, fill in:

- [ ] **Base URL / path** (likely `…/api/v…/`) → `DEFAULT_BASE_URL` + paths in `client.py`
- [ ] **Auth** — cookie/bearer/CSRF instead of Basic? → update the `headers` in `client.py`
- [ ] **Response shape** — field names/nesting → adjust `models.py` (use `Field(alias=...)` for renames)
- [ ] **Date param** — what filters by date (if any) → `todos(since=...)`

Paste the cURL here when captured:

```
# (paste DevTools "Copy as cURL" output)
```
