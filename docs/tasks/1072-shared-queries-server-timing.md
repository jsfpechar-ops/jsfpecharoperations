# 1072: shared queries once per request, alerts top N, Server-Timing header

Status: todo
Depends on: 1065 (merged, PR #856) | Base commit: 1194e109 | Branch: claude/1072-shared-queries-server-timing
Executor: Fable 5.2 (**Tier A**: `workspace_user` feeds `access.owner_id` for every guest-data lookup; [workflow] decision 2026-11-09 in [decisions](../context/decisions.md)) | Fits one session: 40 tool calls, 70k tokens
After execution a fresh Fable reviews the full diff of auth.py and access.py line by line vs this brief before the PR.
Queue item 1.7 (Tier A). Plan: [speed-and-ease](../plans/speed-and-ease.md) item Q7, section 3 (speed budget, "Any host page"), section 4.7 (server findings) and section 9 (measuring).

## 1. Objective

Cut the database reads that every signed-in host page repeats, show only the top alerts as cards off the dashboard (the rest is a count), and send a `Server-Timing` header to signed-in hosts so the owner can read query count and time in the browser. Nothing a host sees changes except that an account with more than 12 non-critical alerts gets the same summary count computed from fewer decrypted cards.

**Honest scope.** This brief removes the duplicates that exist. It does not reach the plan's "at most 2 shared queries" target: the host shell still runs about 12 queries per page (listed in 2.3). Reaching 2 needs the onboarding progress block and the nav property list moved into a fragment or a cache. That is a later brief; do not start it here.

## 2. Context

### 2.1 What a host page costs today (measured on base 1194e109, SQLite, fresh test host, `db.py` statement trace)

| Page | Queries before | After this brief |
|---|---|---|
| `/` host with 1 property | 21 | 19 |
| `/apartments`, no property | 15 | 14 |
| `/reservations`, no property | 17 | 16 |
| `/apartments`, an admin previewing a host (impersonation) | 24 (9 are the same `SELECT * FROM user_account WHERE id = <host>`) | 15 |

### 2.2 The duplicates (file:line on the base commit)

1. **`auth.workspace_user`, `App/app/auth.py:332-347`.** Unlike `current_user` (cached on `request.state.user_account`, `auth.py:314-318`), it re-reads the previewed host's account on every call when an admin previews a workspace. It is called by `require_login` (`auth.py:523`), by `access.owner_id` (`access.py:59-61`, so once per `access.*` helper), by `templating.render` (`templating.py:666`) and by 135 call sites in `App/app/`. Nine identical SELECTs on one `/apartments` page. For a normal host it costs no query (returns the cached account), so only the cache of the admin branch matters.
2. **Property list read up to three times a page.** `templating.render` reads `access.apartments(request, "id, internal_name, active, stay_fee_rate_czk")` for the nav (`templating.py:703`); the route reads the same rows again, for example `routes/admin.py:486` (dashboard, `*`), `657`, `1236`; and `onboarding.progress` reads them a third time (`onboarding.py:122`, `*` plus feed count) and then a fourth time through `wizard_step` -> `first_apartment` (`onboarding.py:70`, `onboarding.py:32-41`), which is exactly `apartments[0]` of the third read (same filter, same `ORDER BY a.id`, same `feeds` column).
3. **Not duplicated, so not changed:** billing banner (`base.html:85` -> `_billing_banner.html:2` -> `templating.py:458-462` -> `billing_trial.py:146` -> `billing.py:120`) is one `billing_account` read per page when billing is on (measured: 1). `auth.accounts_exist()` (`auth.py:190`, called from `require_login`, `auth.py:515`) is one query per page. Alerts (`templating.py:692-698`) are one query per page. Do not add caches for these.

### 2.3 What stays after this brief (for the next brief, not this one)

Per page, in `render()` and `require_login`: `user_account LIMIT 1`, `user_account WHERE id`, alerts (1), nav properties (0-1), and `onboarding.progress` (entity count x2, properties with feeds, manual-stay count, `onboarding_dismissed_<id>` setting). The billing banner adds 1 when billing is on.

### 2.4 Alerts: how the stack uses them (why a cap is safe off the dashboard)

`templating.render` loads every open alert (`alerts.open_alerts`, `alerts.py:555-568`: one SELECT, no decrypt) and `alerts.present_many` (`alerts.py:397`) turns each into a card, and `_preload_stays` (`alerts.py:185-215`) reads and decrypts the stays and guests behind them. That presenting is the cost. In `_host_alerts.html` (path `App/app/templates/_host_alerts.html`) every `critical` alert is a card of its own on every page, and the non-critical ones become one summary line ("N alerts need you") unless there is exactly one. The dashboard (`/`) is the only page that lists everything (`needs_you_build(rows, needs_you_queue, open_alerts, ...)` in `dashboard.html:40`, and `alerts_expanded`).

Design: off the dashboard keep **all critical rows plus the first 12 others** (rows arrive sorted by level), present only those, and pass the number left out as `open_alerts_more`; the template adds it to `rest_count`. The SELECT stays one query for all rows because it has no decrypt and the critical rows must never be cut. A filing deadline alert is `critical` (see `reporting.py`), so it is never hidden. The cap is `SHELL_ALERT_LIMIT = 12`; typical hosts have fewer, so their page is identical. Known approximation: rows beyond the 12th are counted raw. Two merges that shrink the count for presented rows are not applied to them: the pin-rotated merge in the template (several `guest_pin_rotated` count as one) and the per-stay merge in `present_many` (`alerts.py:397-436`: rows of one reservation become one card, and a `guest_incomplete_checkin` whose forms are complete is dropped). Both inflate the "more" count. Beyond 12 non-critical alerts the line says a number that may be higher than the dashboard's; accepted.

Because `present_many` can drop or merge every kept non-critical row, the template may reach the summary line with `held.folded` and `rest` both empty while `open_alerts_more > 0`. The summary's level then must not index that empty list (Step 9).

### 2.5 Per-request cache design (no leak between requests or users)

Both caches live on `request.state`. Starlette creates a new `request.state` for every request, so nothing survives the request and nothing is shared between users. No module global, no contextvar, no new dependency, and no SQL outside `db.py` helpers (the memo wraps `db.query`).

- `request.state.workspace_account`: the account `workspace_user` returned. Same pattern as `current_user`.
- `request.state.apartments_memo`: `{(owner_id, include_archived, columns): rows}`. **GET and HEAD only**: a POST may write and read the list in one request, so it always reads the database. A narrower column list (plain column names only) is served from an earlier `*` read of the same request. Rows are `db._HydratedRow` objects (`db.py:1872`, a `dict` subclass), so they are **not** immutable: the memo hands the same row objects to every caller in the request, and only the list is new each time. **Callers must not mutate cached rows** (no `row[...] = ...`, no `row.update(...)`); copy with `dict(row)` first. The method is read with `getattr(request, "method", "")`, the same pattern as `auth.py:546`, so a request object without `method` never uses the memo.
- Writes: the only property insert is `POST /apartments` (`routes/admin.py:1815`, insert at `admin.py:1857`), which runs without the memo and ends in a 303, so the next page is a new request with an empty memo. No invalidation is needed; a test proves it (Step 11, chunk F). If you find a GET route that inserts, archives or renames a property, STOP (section 8).

### 2.6 Server-Timing: who gets it, and why

Header: `Server-Timing: db;dur=<ms>;desc="<n> queries", app;dur=<ms>`, built from the 1065 `RequestStats` (`stats.queries`, `stats.db_seconds`, `db.py:31-67`) and the middleware's `started` clock (`main.py:318-362`).

Decision: **sent only when the request already identified a signed-in account** (`request.state.user_account` is set by `auth.current_user`), never for `/static/`, `/metrics`, `/healthz`, signed-out pages, guest pages (`_is_guest_path(request)`, `main.py:256`: `/l` and `/l/...`) or the shared cleaning schedule (paths starting `/cleaning/shared/`), **even when a signed-in host opens them**. Why: the numbers describe the host's own page and only the host or the owner reads them; a visitor gains nothing, and on `/login` or a guest link a query count could leak whether an account or stay exists. It carries two numbers and the word "queries", no route, id, name or e-mail, and there is no `Timing-Allow-Origin`, so scripts on other origins cannot read it. No new personal data (no line in `App/app/retention.py`), no outbound request, no cookie.

Reach: Python-served pages only. Paths served by Go (`UBYHOST_GO_PATHS` in status.md) do not pass this middleware and get no header. The middleware already reads `request.state.session_payload` after the route (`auth.refresh_session_cookie`), so `request.state` is visible there.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/auth.py` | edit | cache `workspace_user` on `request.state` |
| `App/app/onboarding.py` | edit | `wizard_step` takes the first property `progress` already read |
| `App/app/access.py` | edit | per-request memo in `apartments()` |
| `App/app/alerts.py` | edit | `SHELL_ALERT_LIMIT`, `shell_slice()` |
| `App/app/templating.py` | edit | use `shell_slice` off the dashboard, pass `open_alerts_more` |
| `App/app/templates/_host_alerts.html` | edit | add `open_alerts_more` to `rest_count` |
| `App/app/main.py` | edit | `Server-Timing` header and two helpers |
| `App/tests/test_shared_queries_1072.py` | create | the new tests |
| `docs/tasks/1072-report.md` | create | the report (section 9) |

No other file may change. `docs/context/test-map.md` is deliberately not edited: it is at the lint size cap, and the new test file is named in section 6 instead.

**Order against open briefs and branches** (`git branch -r` on 2026-11-09, files compared with `git diff --name-only origin/main...<branch>`):

| Branch | Shared file with 1072 | Order |
|---|---|---|
| `claude/1068-errors-link-fix` | `App/app/templating.py`: it adds `FIX_TARGETS` near line 37 and one `data.setdefault("flash_fix", ...)` line after the `flash_error` line in `render()` | Either order. Different places; every 1072 anchor is in the alerts block (`templating.py:692-698`) which 1068 does not touch. |
| `claude/1071-host-alert-no-pay-way` | `App/app/alerts.py` (one `_ACTIONS` entry) and `docs/context/test-map.md` (an alerts row) | Either order for `alerts.py`: 1071 edits `_ACTIONS`, 1072 inserts above `def open_alerts` (`alerts.py:555`). 1072 does not edit test-map. |
| `claude/1066-input-attributes`, `1067-dedupe-css-defer-js` | `App/app/templates/base.html` | No overlap: 1072 does not edit `base.html`. |
| `claude/1069-f0-quiet-completion-check`, `1070-file-at-deadline-cap` | none (`status.md` only, not edited here) | none |

If an anchor below is not found verbatim because another brief moved it, STOP (section 8).

## 4. Steps

Work from `App/`. Every command ends in `| tail -30`. If an anchor is not found verbatim, STOP.

### Step 1: `auth.py`, read the cache first in `workspace_user`

Anchor (exactly once):

```python
def workspace_user(request: Request):
    account = current_user(request)
    if not account:
        return None
```

Replace with:

```python
def workspace_user(request: Request):
    cached = getattr(request.state, "workspace_account", None)
    if cached is not None:
        return cached
    account = current_user(request)
    if not account:
        return None
```

Command: `.venv/bin/python -c "import app.auth" 2>&1 | tail -30`
Expected: no output.

### Step 2: `auth.py`, store what `workspace_user` returns

Anchor (exactly once):

```python
        if target:
            return target
    return account


SUPPORT_REASON_MIN = 5
```

Replace with (the expired-impersonation branch above it returns early and is not cached, as before):

```python
        if target:
            request.state.workspace_account = target
            return target
    request.state.workspace_account = account
    return account


SUPPORT_REASON_MIN = 5
```

Command: `.venv/bin/python -m pytest tests/test_access_audit.py tests/test_accounts.py -q --tb=short -x 2>&1 | tail -30`
Expected: `passed`, no failures.

### Step 3: `onboarding.py`, `wizard_step` accepts the property already read

Anchor (exactly once):

```python
def wizard_step(owner_user_id: int) -> str:
    """First unfinished setup-wizard screen after welcome."""
    apartment = first_apartment(owner_user_id)
```

Replace with:

```python
_LOAD = object()


def wizard_step(owner_user_id: int, apartment: Any = _LOAD) -> str:
    """First unfinished setup-wizard screen after welcome.

    ``progress`` passes the first property it already read (1072); a caller that
    passes none gets the old read. ``None`` means "this host has no property".
    """
    if apartment is _LOAD:
        apartment = first_apartment(owner_user_id)
```

Command: `.venv/bin/python -c "import app.onboarding as o; print(o.wizard_step.__defaults__[0] is o._LOAD)" 2>&1 | tail -30`
Expected: `True`.

### Step 4: `onboarding.py`, `progress` passes its first property

Anchor (exactly once; inside `progress`, where the local `first_apartment` is the first row of the properties list, not the function):

```python
    wstep = wizard_step(owner_user_id)
```

Replace with:

```python
    wstep = wizard_step(owner_user_id, first_apartment)
```

Command: `.venv/bin/python -m pytest tests/test_onboarding.py -q --tb=short -x 2>&1 | tail -30`
Expected: `passed`, no failures.

### Step 5: `access.py`, import `re`

Anchor (exactly once):

```python
from __future__ import annotations

from fastapi import Request
```

Replace with:

```python
from __future__ import annotations

import re

from fastapi import Request
```

Command: `.venv/bin/python -c "import app.access" 2>&1 | tail -30`
Expected: no output.

### Step 6: `access.py`, the memo in `apartments()`

Anchor (exactly once, the whole function):

```python
def apartments(request: Request, columns: str = "*", include_archived: bool = False):
    sql = f"SELECT {columns} FROM apartment WHERE {db.null_safe_eq('owner_user_id')}"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    sql += " ORDER BY internal_name"
    return db.query(sql, (owner_id(request),))
```

Replace with:

```python
_PLAIN_COLUMNS = re.compile(r"[a-z_][a-z_0-9]*(\s*,\s*[a-z_][a-z_0-9]*)*")


def apartments(request: Request, columns: str = "*", include_archived: bool = False):
    """The host's properties. On a GET the rows are read once per request (1072):
    a narrower column list is served from an earlier ``*`` read of the same request.
    The rows are shared within the request: callers must not mutate cached rows."""
    owner = owner_id(request)
    memo = None
    if getattr(request, "method", "") in ("GET", "HEAD"):
        memo = getattr(request.state, "apartments_memo", None)
        if memo is None:
            memo = request.state.apartments_memo = {}
        key = (owner, include_archived, columns)
        if key in memo:
            return list(memo[key])
        wide = memo.get((owner, include_archived, "*"))
        if wide is not None and _PLAIN_COLUMNS.fullmatch(columns):
            names = [name.strip() for name in columns.split(",")]
            if all(not wide or name in wide[0].keys() for name in names):
                return list(wide)
    sql = f"SELECT {columns} FROM apartment WHERE {db.null_safe_eq('owner_user_id')}"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    sql += " ORDER BY internal_name"
    rows = db.query(sql, (owner,))
    if memo is not None:
        memo[(owner, include_archived, columns)] = rows
    return list(rows)
```

Command: `.venv/bin/python -c "import app.access" 2>&1 | tail -30`
Expected: no output.

### Step 7: `alerts.py`, the slice helper

Anchor (exactly once):

```python
def open_alerts(owner_user_id: Optional[int] = None) -> List:
```

Replace with (the new block goes above it; keep the `def` line and its body as they are):

```python
# 1072: the most alerts, besides the critical ones, a page other than the
# dashboard turns into cards. The rest is only counted in the summary line.
SHELL_ALERT_LIMIT = 12


def shell_slice(rows: List, limit: int = SHELL_ALERT_LIMIT) -> tuple:
    """(rows to present, how many were left out). Critical rows are never left out.

    ``rows`` arrive ordered by level, so the critical ones come first.
    """
    critical = sum(1 for row in rows if row["level"] == "critical")
    keep = critical + limit
    return rows[:keep], max(0, len(rows) - keep)


def open_alerts(owner_user_id: Optional[int] = None) -> List:
```

Command: `.venv/bin/python -c "from app import alerts; print(alerts.shell_slice([{'level':'critical'}]*3 + [{'level':'info'}]*20)[1])" 2>&1 | tail -30`
Expected: `8`.

### Step 8: `templating.py`, slice off the dashboard

Anchor (exactly once, inside `render()`):

```python
        data["open_alerts"] = alerts.present_many(raw_alerts, data["lang"])
```

Replace with:

```python
        # 1072: only the dashboard lists every alert; elsewhere the extras are a count.
        more = 0
        if request.url.path != "/":
            raw_alerts, more = alerts.shell_slice(raw_alerts)
        data["open_alerts"] = alerts.present_many(raw_alerts, data["lang"])
        data["open_alerts_more"] = more
```

Command: `.venv/bin/python -c "import app.templating" 2>&1 | tail -30`
Expected: no output.

### Step 9: `_host_alerts.html`, count the ones left out, and never index an empty list

Three edits in `App/app/templates/_host_alerts.html`. `present_many` can drop or merge every kept non-critical row (section 2.4), so the summary line must render with `held.folded` and `rest` both empty.

Edit 9a. Anchor (exactly once, line 10):

```jinja
{% if open_alerts %}
{% set path = request.url.path if request is defined and request else '' %}
```

Replace with (the count of left-out rows still shows when no kept row survived):

```jinja
{% if open_alerts or (open_alerts_more | default(0)) %}
{% set path = request.url.path if request is defined and request else '' %}
```

Edit 9b. Anchor (exactly once, one line):

```jinja
{% set rest_count = (rest | rejectattr('kind', 'equalto', 'guest_pin_rotated') | list | length) + (1 if rest_pin else 0) + (held.folded | length) %}
```

Replace with:

```jinja
{% set rest_count = (rest | rejectattr('kind', 'equalto', 'guest_pin_rotated') | list | length) + (1 if rest_pin else 0) + (held.folded | length) + (open_alerts_more | default(0)) %}
```

Edit 9c. Anchor (exactly once, one line):

```jinja
    <article class="notification-bubble {{ (held.folded + rest)[0].level }}" data-notification-summary>
```

Replace with:

```jinja
    <article class="notification-bubble {{ (held.folded + rest)[0].level if (held.folded or rest) else 'warning' }}" data-notification-summary>
```

Without 9c, `(held.folded + rest)[0]` is Jinja `Undefined` and `.level` raises `UndefinedError`: a 500 on every page but `/` for that host.

Command: `grep -c "open_alerts_more\|else 'warning'" app/templates/_host_alerts.html | tail -30`
Expected: `3`.

Command: `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_alert_language.py -q --tb=short -x 2>&1 | tail -30`
Expected: `passed`, no failures.

### Step 10: `main.py`, the header and its two helpers

Anchor (exactly once; the end of the middleware and the comment that follows it):

```python
            db_queries=stats.queries, db_seconds=stats.db_seconds,
        )
    return response


# WP07: every /static URL in the templates carries ?v=<key>, and the key is
```

Replace with:

```python
            db_queries=stats.queries, db_seconds=stats.db_seconds,
        )
    if _signed_in_page(request):
        response.headers["Server-Timing"] = _server_timing(stats, started)
    return response


def _signed_in_page(request: Request) -> bool:
    """Server-Timing goes only to a signed-in host (1072): the numbers describe
    that host's own page and are not worth showing a visitor or a guest. Guest
    links and the shared cleaning schedule never get it, even for a host."""
    path = request.url.path
    if path.startswith("/static/") or path in ("/metrics", "/healthz"):
        return False
    if _is_guest_path(request) or path.startswith("/cleaning/shared/"):
        return False
    return getattr(request.state, "user_account", None) is not None


def _server_timing(stats: "db.RequestStats", started: float) -> str:
    """``db;dur=<ms>;desc="<n> queries", app;dur=<ms>``: counts and milliseconds only."""
    return (
        f'db;dur={stats.db_seconds * 1000:.1f};desc="{stats.queries} queries", '
        f"app;dur={(time.perf_counter() - started) * 1000:.1f}"
    )


# WP07: every /static URL in the templates carries ?v=<key>, and the key is
```

Command: `.venv/bin/python -c "import app.main as m; print(m._is_guest_path is not None)" 2>&1 | tail -30`
Expected: `True` (`_is_guest_path` is defined at `main.py:256`, above the middleware; no import needed).

### Step 11: create `App/tests/test_shared_queries_1072.py` (6 chunks)

Create the file with chunk A, then append chunks B, C, D, E, F in order, each as the next lines of the same file (use `cat >> tests/test_shared_queries_1072.py <<'EOF'` for B to F; chunk A with `cat >`). The file must be exactly the six chunks joined, with no extra blank lines between chunk ends and starts beyond what each chunk shows.

Chunk A (imports, constants, cleanup, account helper):

```python
"""1072: shared shell queries once per request, alerts top N, Server-Timing."""
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import access, alerts, auth, db
from app.main import app
from tests.conftest import login_as

HOST_A = "shared1072a"
HOST_B = "shared1072b"
ADMIN = "shared1072adm"
BUDGET_DASHBOARD = 19  # measured before 1072: 21
BUDGET_PREVIEW = 15  # measured before 1072: 24
TIMING = re.compile(r'^db;dur=\d+\.\d;desc="(\d+) queries", app;dur=\d+\.\d$')


def _cleanup():
    for name in (HOST_A, HOST_B, ADMIN):
        row = db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))
        if not row:
            continue
        uid = row["id"]
        for table in ("alert", "apartment", "audit", "login_token", "legal_acceptance"):
            column = "user_account_id" if table in ("login_token", "legal_acceptance") else "owner_user_id"
            db.execute(f"DELETE FROM {table} WHERE {column} = ?", (uid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


def _account(name, role="host"):
    auth.create_account(f"{name}@example.test", name, username=name)
    if role == "admin":
        db.execute("UPDATE user_account SET role = 'admin' WHERE username = ?", (name,))
    return db.query_one("SELECT * FROM user_account WHERE username = ?", (name,))
```

Chunk B (property and alert helpers, fixture, header parser):

```python
def _property(owner_id, name):
    return db.insert("apartment", {
        "owner_user_id": owner_id, "internal_name": name,
        "permalink_token": f"tok-{name.replace(' ', '-').lower()}",
        "permalink_pin": "1234", "automation_mode": "manual",
        "submit_after_hours": 24, "active": 1, "created_at": db.utcnow(),
    })


def _alert(owner_id, level, n):
    alerts.raise_alert(level, "cancelled_after_report", f"stay {n}", reservation_id=9000 + n,
                       owner_user_id=owner_id, dedupe_key=f"c1072:{owner_id}:{n}")


@pytest.fixture
def hosts():
    db.init_db()
    _cleanup()
    a, b = _account(HOST_A), _account(HOST_B)
    _property(a["id"], "Alpha 1072")
    _property(b["id"], "Bravo 1072")
    ca, cb = TestClient(app), TestClient(app)
    login_as(ca, HOST_A, url="/login?lang=en", follow_redirects=False)
    login_as(cb, HOST_B, url="/login?lang=en", follow_redirects=False)
    try:
        yield SimpleNamespace(a=a, b=b, ca=ca, cb=cb)
    finally:
        _cleanup()


def _queries(response) -> int:
    match = TIMING.match(response.headers["server-timing"])
    assert match, response.headers.get("server-timing")
    return int(match.group(1))
```

Chunk C (header tests and the dashboard budget):

```python
def test_server_timing_is_well_formed_for_a_signed_in_host(hosts):
    response = hosts.ca.get("/apartments?lang=en")
    assert response.status_code == 200
    assert _queries(response) > 0


def test_server_timing_is_not_sent_to_visitors_or_for_static_files():
    anonymous = TestClient(app)
    assert "server-timing" not in anonymous.get("/login?lang=en").headers
    assert "server-timing" not in anonymous.get("/healthz").headers
    assert "server-timing" not in anonymous.get("/static/app2.css").headers


def test_server_timing_carries_nothing_but_counts_and_milliseconds(hosts):
    value = hosts.ca.get("/apartments?lang=en").headers["server-timing"]
    assert "Alpha" not in value and HOST_A not in value and "@" not in value


def test_the_dashboard_costs_fewer_queries(hosts):
    assert _queries(hosts.ca.get("/?lang=en")) <= BUDGET_DASHBOARD
```

Chunk D (admin preview budget, two hosts in turn, memo unit test):

```python
def test_an_admin_previewing_a_host_reads_the_host_account_once():
    db.init_db()
    _cleanup()
    admin, host = _account(ADMIN, "admin"), _account(HOST_A)
    try:
        token = auth.issue_session(admin["id"], admin["session_version"], workspace_user_id=host["id"])
        client = TestClient(app)
        client.cookies.set(auth.SESSION_COOKIE, token)
        response = client.get("/apartments?lang=en")
        assert response.status_code == 200
        assert _queries(response) <= BUDGET_PREVIEW
    finally:
        _cleanup()


def test_two_hosts_in_turn_each_get_only_their_own_data(hosts):
    for _ in range(2):
        page_a = hosts.ca.get("/apartments?lang=en").text
        page_b = hosts.cb.get("/apartments?lang=en").text
        assert "Alpha 1072" in page_a and "Bravo 1072" not in page_a
        assert "Bravo 1072" in page_b and "Alpha 1072" not in page_b
    dash_a = hosts.ca.get("/?lang=en").text
    assert "Bravo 1072" not in dash_a
```

Chunk E (alerts cap and critical-never-cut):

```python
def test_the_property_list_is_read_once_per_get_and_never_on_a_post(monkeypatch):
    calls = []
    real = db.query
    monkeypatch.setattr(access.db, "query", lambda sql, params=(): calls.append(sql) or real(sql, params))
    monkeypatch.setattr(access.auth, "workspace_user", lambda request: {"id": 1})
    get = SimpleNamespace(method="GET", state=SimpleNamespace())
    access.apartments(get, "*")
    access.apartments(get, "id, internal_name")
    access.apartments(get, "*")
    assert len(calls) == 1
    post = SimpleNamespace(method="POST", state=SimpleNamespace())
    access.apartments(post, "*")
    access.apartments(post, "*")
    assert len(calls) == 3


def test_a_page_other_than_the_dashboard_presents_at_most_the_top_alerts(hosts, monkeypatch):
    for n in range(15):
        _alert(hosts.a["id"], "warning", n)
    seen = []
    real = alerts.present_many
    monkeypatch.setattr(alerts, "present_many", lambda rows, lang: seen.append(len(rows)) or real(rows, lang))
    page = hosts.ca.get("/settings?lang=en")
    assert seen == [alerts.SHELL_ALERT_LIMIT]
    assert "15 alerts need you" in page.text
    hosts.ca.get("/?lang=en")
    assert seen[-1] == 15


def test_critical_alerts_are_never_left_out():
    rows = [{"level": "critical"}] * 14 + [{"level": "warning"}] * 20
    kept, more = alerts.shell_slice(rows)
    assert sum(1 for row in kept if row["level"] == "critical") == 14
    assert len(kept) == 14 + alerts.SHELL_ALERT_LIMIT and more == 8
    assert alerts.shell_slice(rows[:3]) == (rows[:3], 0)
```

Chunk F (review findings: empty summary, guest paths, preview, cache edges):

```python
def test_the_summary_line_survives_when_every_kept_row_vanishes(hosts, monkeypatch):
    _alert(hosts.a["id"], "critical", 99)
    for n in range(15):
        _alert(hosts.a["id"], "warning", n)
    real = alerts.present_many
    monkeypatch.setattr(alerts, "present_many",
                        lambda rows, lang: [c for c in real(rows, lang) if c["level"] == "critical"])
    page = hosts.ca.get("/settings?lang=en")
    assert page.status_code == 200
    assert "data-notification-summary" in page.text
    monkeypatch.setattr(alerts, "present_many", lambda rows, lang: [])
    page = hosts.ca.get("/settings?lang=en")
    assert page.status_code == 200
    assert "3 alerts need you" in page.text


def test_server_timing_is_never_sent_on_guest_or_shared_cleaning_pages(hosts):
    assert "server-timing" in hosts.ca.get("/apartments?lang=en").headers
    for path in ("/l/tok-alpha-1072", "/cleaning/shared/not-a-token-1072"):
        response = hosts.ca.get(path, follow_redirects=False)
        assert "server-timing" not in response.headers, path


def test_an_admin_preview_shows_the_host_property_and_the_own_view_does_not():
    db.init_db()
    _cleanup()
    admin, host = _account(ADMIN, "admin"), _account(HOST_A)
    _property(host["id"], "Alpha 1072")
    try:
        preview = TestClient(app)
        preview.cookies.set(auth.SESSION_COOKIE, auth.issue_session(
            admin["id"], admin["session_version"], workspace_user_id=host["id"]))
        page = preview.get("/apartments?lang=en")
        assert page.status_code == 200 and "Alpha 1072" in page.text
        own = TestClient(app)
        own.cookies.set(auth.SESSION_COOKIE, auth.issue_session(admin["id"], admin["session_version"]))
        assert "Alpha 1072" not in own.get("/apartments?lang=en").text
    finally:
        _cleanup()


def test_an_expired_preview_is_not_cached(monkeypatch):
    admin = {"id": 7, "role": "admin"}
    monkeypatch.setattr(auth, "current_user", lambda request: admin)
    monkeypatch.setattr(auth, "impersonation_expired", lambda payload: True)
    request = SimpleNamespace(method="GET", state=SimpleNamespace(session_payload={"as": 8, "ast": 0}))
    assert auth.workspace_user(request) is admin
    assert getattr(request.state, "workspace_account", None) is None
    assert request.state.impersonation_expired_for == 8


def test_a_narrow_read_then_a_star_read_returns_full_rows(hosts, monkeypatch):
    monkeypatch.setattr(access.auth, "workspace_user", lambda request: hosts.a)
    get = SimpleNamespace(method="GET", state=SimpleNamespace())
    narrow = access.apartments(get, "id, internal_name")
    wide = access.apartments(get, "*")
    assert set(narrow[0].keys()) == {"id", "internal_name"}
    assert wide[0]["internal_name"] == "Alpha 1072"
    assert wide[0]["permalink_token"] == "tok-alpha-1072"


def test_one_browser_switching_users_gets_each_users_data(hosts):
    client = TestClient(app)
    for name, mine, theirs in ((HOST_A, "Alpha 1072", "Bravo 1072"), (HOST_B, "Bravo 1072", "Alpha 1072")):
        client.cookies.clear()
        login_as(client, name, url="/login?lang=en", follow_redirects=False)
        page = client.get("/apartments?lang=en").text
        assert mine in page and theirs not in page


def test_a_property_created_in_the_request_is_listed(hosts, monkeypatch):
    assert "Alpha 1072 new" not in hosts.ca.get("/apartments?lang=en").text
    monkeypatch.setattr(access.auth, "workspace_user", lambda request: hosts.a)
    post = SimpleNamespace(method="POST", state=SimpleNamespace())
    assert [r["internal_name"] for r in access.apartments(post, "id, internal_name")] == ["Alpha 1072"]
    _property(hosts.a["id"], "Alpha 1072 new")
    assert len(access.apartments(post, "id, internal_name")) == 2
    monkeypatch.undo()
    assert "Alpha 1072 new" in hosts.ca.get("/apartments?lang=en").text
```

The last test needs no cache invalidation: a property is created only by `POST /apartments`, which never uses the memo, and the next page is a new request. If it fails, do not add invalidation on your own: STOP (section 8).

Command: `.venv/bin/python -m pytest tests/test_shared_queries_1072.py -q --tb=short -x 2>&1 | tail -30`
Expected: `16 passed`.

The two budgets (`BUDGET_DASHBOARD = 19`, `BUDGET_PREVIEW = 15`) are the numbers measured on the finished change; the "before" numbers are in the comments (21 and 24). If a budget fails by 1 or 2 on your machine, do not raise it: STOP and report the measured number (section 8). Query counts here are SQLite counts of the 1065 `RequestStats`.

### Step 12: prove the new tests fail without the change (once)

Command: `git stash push -q -- app/ && .venv/bin/python -m pytest tests/test_shared_queries_1072.py -q --tb=line 2>&1 | tail -30; git stash pop -q && git status --short | tail -30`
Expected: the pytest output shows failures (`server-timing` KeyError, budgets exceeded, `shell_slice` missing, no `data-notification-summary` in the vanish test; the cache-edge tests of chunk F may pass on the base, which is fine), and after `stash pop` `git status` lists the seven `App/app` files again plus the new test file. If the tests pass without the change, STOP.

## 5. Do not touch

- `App/app/templates/base.html`, `App/app/static/*` (1066 and 1067 own them), `App/app/db.py`, `App/app/metrics.py`, `App/app/billing*.py`, `App/app/retention.py`.
- Any migration, any new dependency, any new outbound request, any cookie or script (hard rules 2, 4, 5).
- The alert wording, levels, dedupe or dismissal behaviour, and the dashboard's "What needs you" logic. `/` keeps loading every alert.
- `docs/context/test-map.md` and `docs/context/status.md` (the orchestrator updates status; test-map is at its size cap).
- Hard rule 7 and 10 apply: section 10 (UX gate) is not optional.

## 6. Commands

From `App/`, in this order. Only the [test-map](../context/test-map.md) rows for what changed, plus the new file:

1. New and nearest tests: `.venv/bin/python -m pytest tests/test_shared_queries_1072.py tests/test_alert_stack.py tests/test_alert_language.py tests/test_onboarding.py tests/test_metrics_0427.py tests/test_access_audit.py tests/test_accounts.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30` Expected: `119 passed` (the 16 new tests included; on the prototype this set gave 112 with the 9 tests of chunks A to E, plus the 7 of chunk F).
2. Host pages row (non-browser files): `.venv/bin/python -m pytest tests/test_host_*.py tests/test_property_*.py tests/test_first_*.py tests/test_dashboard_calendar*.py -q --tb=short -x 2>&1 | tail -30` Expected: no failures. Skips here are the browser files; they run in section 10.
3. Browser and geometry (section 10).

## 7. Acceptance

- [ ] `tests/test_shared_queries_1072.py`: 16 passed, and step 12 shows they fail without the change.
- [ ] Section 6 commands 1 and 2: no failures.
- [ ] `_signed_in_page` is false for `/static/`, `/metrics`, `/healthz`, a signed-out request, `/l/...` and `/cleaning/shared/...` (the last two even for a signed-in host); the header regex in the test matches a signed-in `/apartments`.
- [ ] No `App/app` file outside section 3 changed (`git diff --stat`), and `base.html` is untouched.
- [ ] Two hosts alternating on `/apartments` and `/` never see each other's property names (`test_two_hosts_in_turn_each_get_only_their_own_data`).
- [ ] `/settings` renders 200 with the summary line when `present_many` keeps none of the non-critical rows (`test_the_summary_line_survives_when_every_kept_row_vanishes`).
- [ ] After the executor: a fresh Fable reviewed the full diff of `auth.py` and `access.py` line by line against this brief, before the PR (Tier A).
- [ ] UX gate (section 10) done, with the per-page lines in the report.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found verbatim (another brief may have moved it: name it in the report);
- a test fails twice, or a query budget fails (do not raise it);
- you reach 40 tool calls or about 60k tokens (write the report as `blocked`);
- a new dependency, a migration or a file outside section 3 seems needed;
- section 5 would be touched;
- `request.state.user_account` is not visible in the middleware (header missing for a signed-in host): do not switch to a cookie read; report it;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1072-report.md` (600 tokens at most) and set `Status: review`. It has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. UX gate: per page "390: ...; 768: ...; 1280: ..." (what you saw), and the design-system checklist ticked.
5. Deviations.
6. Questions.
7. Owner steps left.

## 10. UX gate (hard rules 7 and 10)

Nothing is meant to look different: the template edits change only a number and guard an empty list, and only for a host with more than 12 non-critical alerts. The gate still runs because a host template changed.

From `App/`, with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots` set (install Chromium first if missing, as `App/run.sh` and the 1066 report describe):

1. `.venv/bin/python -m pytest tests/test_host_alert_stack_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30` Expected: no failures, **0 skipped**.
2. `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30` Expected: green, 0 skipped, zero findings for host pages.
3. Open with the Read tool: `/tmp/shots/many-settings-390.png`, `many-settings-768.png`, `many-settings-1280.png` and `many-stays-390.png`, `many-stays-768.png`, `many-stays-1280.png` (written by the alert stack test), and `/tmp/shots/layout-lint/` host dashboard and settings pages at the same three widths. Look for: the alert cards still on their own lines, the one "N alerts need you" line unclipped, no horizontal overflow at 390.
4. Tick the [design-system checklist](../design/design-system.md) in the report. Never ask the owner to look; never silence a finding.

## Risk list (for the reviewer)

Read these diffs line by line:

- `App/app/auth.py` `workspace_user`: the cache must never hold a different user's account. It is per `request.state`; the expired-impersonation branch still returns early without caching.
- `App/app/access.py` `apartments`: GET/HEAD only; key includes the owner id; wide `*` serves narrow lists only for plain column names that exist on the row.
- `App/app/main.py` `_signed_in_page`: the header must never reach signed-out requests, guest links (`_is_guest_path`) or `/cleaning/shared/`, even with a host cookie.
- `App/app/templating.py` and `_host_alerts.html`: `/` must still present every alert; critical rows never cut; the summary's level never indexes an empty list.
- `App/app/access.py`: cached rows are shared `dict` objects; no caller in the diff may mutate one.
- Left alone on purpose: routes that read narrower property columns before `render()` (for example `routes/admin.py:3588`, `id, internal_name`) still cost one extra read for the nav; the billing banner and `accounts_exist` are single reads.

## Owner steps

1. Open the PR once the executor's report says `review`. CI runs the full suite.
2. After you deploy: sign in as a host, open any page, open the browser's developer tools, Network tab, click the page request, Timing tab. "Server Timing" shows `db` with the query count and `app` with the total time.
3. Unconfirmed (check once after the deploy): Cloudflare and Caddy pass `Server-Timing` through unchanged. The header is not in either Caddyfile today. If it is missing in the browser, tell the orchestrator; nothing in the app needs to change.
