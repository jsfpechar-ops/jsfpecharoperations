# 0278: CI fixes for welcome back (route split list, dashboard query budget)

Status: todo
Depends on: 0275 | Branch: claude/project-thread-4b2e7k (commit here, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

CI on PR #429 fails two tests, both from 0275 (welcome back):
1. `tests/test_admin_route_split.py`: `app.routes.onboarding` now also owns `POST /welcome-back/dismiss`, which the list does not name.
2. `tests/test_query_budget.py::…[/]`: the dashboard makes 21 queries, the budget is under 20. Welcome back added two single-key settings reads (`last_seen_<id>`, `welcome_back_<id>`). Read those two together with the dashboard's existing `last_ical_sync` read in one query, so the dashboard is back to 19. Do not change the budget.

## 2. Context

- `App/app/db.py` line ~1485 has `get_setting(key, default)`; `query(sql, params)` returns rows. SQL only through db helpers, Postgres-portable (a plain `IN (?, ?, …)` is fine).
- `App/app/welcome_back.py` `check(user_id, owner_user_id, today)` reads both keys with `db.get_setting`.
- `App/app/routes/admin.py` dashboard: line ~435 `welcome = welcome_back.check(account["id"] if account else None, owner_user_id, today)` and line ~486 `"last_sync": db.get_setting("last_ical_sync"),`.

## 3. Files

| Path | Action |
|---|---|
| App/app/db.py | add `get_settings` |
| App/app/welcome_back.py | optional `settings` argument |
| App/app/routes/admin.py | two lines |
| App/tests/test_admin_route_split.py | one line |
| App/tests/test_welcome_back_0275.py | one test |

No other file may change.

## 4. Steps

**Step 1. db.py.** Right after `get_setting`, add:

```python
def get_settings(keys: Iterable[str]) -> Dict[str, Optional[str]]:
    """Several settings in one query; a missing key is absent from the result."""
    keys = list(keys)
    if not keys:
        return {}
    marks = ", ".join("?" for _ in keys)
    return {row["key"]: row["value"] for row in query(f"SELECT key, value FROM settings WHERE key IN ({marks})", keys)}
```

Check `Iterable`, `Dict`, `Optional` are imported at the top of db.py (add to the existing `typing` import if not).

**Step 2. welcome_back.py.** Add a helper and use it:

```python
def keys_for(user_id: int) -> tuple:
    """The settings check() reads, so a page can fetch them with others in one query."""
    return (_seen_key(user_id), _line_key(user_id))
```

Change the signature to `def check(user_id, owner_user_id, today, settings: Optional[Dict[str, Optional[str]]] = None)` (keep the existing type hints). At the start of the body, after `if not user_id: return None`, add:

```python
    if settings is None:
        settings = db.get_settings(keys_for(user_id))
```

Replace `db.get_setting(_seen_key(user_id))` with `settings.get(_seen_key(user_id))`. For the line: the function may have just written it, so replace
`    raw = db.get_setting(_line_key(user_id)) or ""`
with:
```python
    if last_seen and (today - last_seen).days >= AWAY_DAYS:
        raw = f"{last_seen.isoformat()}|{today.isoformat()}"
    else:
        raw = settings.get(_line_key(user_id)) or ""
```
and keep the existing `db.set_setting(_line_key(...), ...)` line in its `if` above. (Read the function first; the `if` that writes the line stays, only the `raw =` line changes as shown.)

**Step 3. admin.py dashboard.** Replace
```python
    welcome = welcome_back.check(account["id"] if account else None, owner_user_id, today)
```
with
```python
    user_id = account["id"] if account else None
    # One settings read for welcome back and the last calendar sync (query budget).
    settings = db.get_settings((*welcome_back.keys_for(user_id), "last_ical_sync") if user_id else ("last_ical_sync",))
    welcome = welcome_back.check(user_id, owner_user_id, today, settings)
```
and in the same function change `"last_sync": db.get_setting("last_ical_sync"),` to `"last_sync": settings.get("last_ical_sync"),`. Only the one in the dashboard function (~line 486), not the one near line 1208. If a variable called `user_id` or `settings` already exists in that function, use `welcome_user_id` / `dash_settings` instead and say so.

**Step 4. Route split test.** In `tests/test_admin_route_split.py` `MOVED_PATHS[onboarding]`, add `("POST", "/welcome-back/dismiss"),` after `("POST", "/celebrations/dismiss"),`.

**Step 5. Test.** In `tests/test_welcome_back_0275.py` add:

```python
def test_check_uses_preloaded_settings(host):
    owner = host["user_id"] if "user_id" in host else None
```
Look at how the other tests in that file get `owner` and copy that; then: `_set_seen(owner, (TODAY - timedelta(days=20)).isoformat())`, `settings = db.get_settings(welcome_back.keys_for(owner))`, `assert welcome_back.check(owner, owner, TODAY, settings) is not None`. Check the imports (`db`, `timedelta`) exist in the file. Commit `0278 steps 1-5`.

## 5. Do not touch

Budgets, other tests, other routes. Never push.

## 6. Commands (from `App/`)

1. `.venv/bin/python -m pytest tests/test_query_budget.py tests/test_admin_route_split.py tests/test_welcome_back_0275.py tests/test_dashboard_order.py tests/test_dashboard_queue.py tests/test_host_quiet_dashboard.py -q --tb=short 2>&1 | tail -15` (0 failed)
2. `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -3`
3. `.venv/bin/python -m pytest tests -q -x --tb=short -p no:cacheprovider --ignore-glob='*_browser.py' 2>&1 | tail -15` (timeout 900000 ms). Name any failure; compare with `git stash`-free reasoning only, do not edit unrelated tests.

## 7. Acceptance

- [ ] Commands 1 and 2 pass; command 3 has no new failure.
- [ ] The dashboard query budget is unchanged.

## 8. Stop and ask

Per TEMPLATE.

## 9. Report

`docs/tasks/0278-report.md` (300 tokens max), `Status: review`. Do not push.
