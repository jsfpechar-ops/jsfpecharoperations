# 1065: baseline numbers: first-run stage times and per-route query counts

Status: blocked
Depends on: none | Base commit: 0d851ca4 | Branch: task/1065-baseline-funnel-metrics
Executor: Opus (owner override for this brief; written to Haiku standard) | Fits one session: 30 tool calls, 60k tokens
Queue item 0.2 (Tier B). Plan: [speed-and-ease](../plans/speed-and-ease.md) section 9 (how we measure "2x faster") and section 10 row 10 ("Use /metrics only; the access log stays off").

## 1. Objective

Capture the baseline before Wave 1 ships, server-side and first-party only: (1) the time from account created to first property, first calendar, first valid police details and first guest registered, read from timestamps that already exist; (2) database query count and database time per route template on `/metrics`. No cookies, no script on any page, nothing sent to PostHog, no migration.

**Not in this brief:** queue item 1.7 (Q7: `Server-Timing` header, shared queries once per request, alerts top N). It comes later and edits `App/app/main.py` and `App/app/metrics.py` too, so this brief goes first. Do not add a header, do not touch `templating.py`, `access.py` or `alerts.py`.

## 2. Context

### 2.1 Stages and timestamps (all confirmed by grep on the base commit)

| Stage | Existing timestamp | Where it is already read |
|---|---|---|
| Account created | `user_account.created_at` | `admin_funnel.py`, `CORE_STAGES` `("created", "created_at")` |
| First property | `apartment.created_at` | `first_property_at` in `_SQL` |
| First calendar | `ical_feed.created_at` where `last_status = 'ok'` | `first_calendar_at` in `_SQL` |
| First guest registered | `reservation.registration_completed_at` (demo source excluded) | `first_guest_at` in `_SQL` |
| First valid police details | `apartment.ubyport_verified_at` (migration `0023_billing.sql`; set only by a passed UbyPort connection test: `billing_trial.mark_verified`, called from `routes/admin.py` right after the `ubyport_connection_ok` audit) | **not read yet**; this brief adds it |

There is no "police details valid" stage in `CORE_STAGES`, and none is added: `posthog_sync.py` iterates `admin_funnel.stages()`, so a new stage would change the PostHog sync, the stage counts and the CSV columns. The new column is read in `_SQL` only and used by a separate function. Honest limit: a host who files without ever pressing the connection test has no `ubyport_verified_at`, so this stage under-counts. That is accepted for a baseline; no new column is allowed.

### 2.2 "Guest seconds per registration" is DROPPED

The plan marks it unverified. Checked: `reservation_claim.claimed_at` is when a stay link was claimed by e-mail, not when the form was opened; `guest` has `filled_at` and `signed_at` but no start timestamp and no `created_at`; `reservation.registration_completed_at` is per stay, not per guest. No pair of existing timestamps measures one registration's duration. It would need a new column (form opened), which is out of scope and would need a retention line. Do not build it.

### 2.3 Existing per-request stats and `/metrics`

`App/app/db.py`: `RequestStats` has `queries`, `db_seconds`, `lock_seconds`. `App/app/main.py` middleware creates `stats = db.start_request_stats()` for every request and today only logs it when `config.ACCESS_LOG` is on (off in production). The metrics call in the same middleware (the anchor for step 4):

```python
    if request.url.path not in ("/metrics", "/healthz") and not request.url.path.startswith("/static/"):
        metrics.observe_request(
            request.method, _access_route(request), response.status_code,
            time.perf_counter() - started,
        )
    return response
```

`_access_route(request)` returns the matched route template, or the constant `<unmatched>`, so label values are bounded by the route table. `App/app/metrics.py` holds the registry (`observe_request`, `render`) with no dependency. Protection: `/metrics` has no login in the app; both `deploy/lightsail/caddy/Caddyfile.acme` and `Caddyfile.cloudflare` answer `respond @metrics 404`, and alloy scrapes `ubyhost:8080` inside the compose network. No protection change here.

### 2.4 Privacy

No personal-data field is added, so no line in `App/app/retention.py`. New metric labels are `method` and `route` (the same template labels the existing families use); values are counts and seconds. The stage times are aggregates (count, median, 75th percentile) over existing host-account timestamps and print no id, name or e-mail. No outbound request, no migration, no cookie, no script.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/admin_funnel.py` | edit | read `first_police_at`; add `first_run_times()` and a `python -m app.admin_funnel` printout |
| `App/app/metrics.py` | edit | two new counter families; `observe_request` takes optional db numbers |
| `App/app/main.py` | edit | pass `stats.queries` and `stats.db_seconds` to `observe_request` |
| `App/tests/test_admin_funnel.py` | edit | tests for part 1 |
| `App/tests/test_metrics_0427.py` | edit | tests for part 2; `_reset` clears the new registries |
| `docs/context/test-map.md` | edit | add one row (this area has none) |
| `docs/tasks/1065-report.md` | create | the report (section 9) |

No other file may change.

Order: `docs/context/test-map.md` is also named by open briefs 0350, 0428, 0810 and 0999 (each adds or edits its own row). Order does not matter for 1065: step 7 inserts one row after the Analytics row; if that anchor is gone, STOP.

`App/app/main.py` is also named by older open briefs (0131, 0219, 0344, 0350, 0351, 0428). 1065 goes first of those: its edit is one call in the middleware, quoted in step 4; if the anchor is gone, STOP. Q7 (item 1.7) runs after 1065.

## 4. Steps

Work from `App/`. If any anchor below is not found verbatim, STOP (section 8).

### Step 1: `admin_funnel.py`, read the police timestamp

Anchor, in `_SQL`:

```python
    "fs.first_filing_at, fs.last_filing_at, "
```

Replace with (a new select column placed just before it; the stage list and CSV stay unchanged):

```python
    "(SELECT MIN(a.ubyport_verified_at) FROM apartment a "
    "WHERE a.owner_user_id = u.id) AS first_police_at, "
    "fs.first_filing_at, fs.last_filing_at, "
```

Command: `.venv/bin/python -c "from app import admin_funnel as f; print(f.stages()[-1]); print('first_police_at' in f._SQL)" 2>&1 | tail -30`
Expected: `('retained', 'retained_at')` then `True`.

### Step 2: `admin_funnel.py`, imports and `first_run_times()`

Anchor (top of file):

```python
import csv
import io
from datetime import date, datetime, timedelta, timezone
```

Replace with:

```python
import csv
import io
import json
import math
from datetime import date, datetime, timedelta, timezone
```

Then append at the very end of the file (after `weekly()`; two blank lines first):

```python
# Brief 1065: first-run stage times, the baseline for the speed plan (section 9).
# Not part of stages(): the PostHog sync, the counts and the CSV read stages().
FIRST_RUN_TIMES: Tuple[Tuple[str, str], ...] = (
    ("first_property", "first_property_at"),
    ("first_calendar", "first_calendar_at"),
    ("first_police", "first_police_at"),
    ("first_guest", "first_guest_at"),
)


def _seconds_between(start: Any, end: Any) -> Optional[int]:
    """Whole seconds from start to end (ISO strings), or None if missing, unparsable or negative."""
    try:
        first = datetime.fromisoformat(str(start))
        last = datetime.fromisoformat(str(end))
    except (TypeError, ValueError):
        return None
    if first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    seconds = int((last - first).total_seconds())
    return seconds if seconds >= 0 else None


def first_run_times(data: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Optional[int]]]:
    """Per stage: accounts that reached it, median and 75th percentile seconds since account created.

    Aggregates only; no account id, name or e-mail leaves this function.
    """
    data = data if data is not None else rows()
    result: Dict[str, Dict[str, Optional[int]]] = {}
    for key, column in FIRST_RUN_TIMES:
        values = sorted(
            s
            for s in (_seconds_between(r.get("created_at"), r.get(column)) for r in data["rows"])
            if s is not None
        )
        if not values:
            result[key] = {"accounts": 0, "median_seconds": None, "p75_seconds": None}
            continue
        mid = len(values) // 2
        median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) // 2
        result[key] = {
            "accounts": len(values),
            "median_seconds": median,
            "p75_seconds": values[max(0, math.ceil(0.75 * len(values)) - 1)],
        }
    return result


def main() -> None:
    """``python -m app.admin_funnel``: print the first-run stage times as JSON."""
    print(json.dumps(first_run_times(), indent=2))


if __name__ == "__main__":
    main()
```

Command: `.venv/bin/python -c "from app import admin_funnel as f; print(f._seconds_between('2026-01-01T00:00:00+00:00','2026-01-01T00:10:00+00:00'), f.first_run_times({'rows': []})['first_police'])" 2>&1 | tail -30`
Expected: `600 {'accounts': 0, 'median_seconds': None, 'p75_seconds': None}`.

### Step 3: `metrics.py`, record and render db numbers

3a. Module docstring. Replace the block from the line `Two families only, all PII-free (OPS-3): route *templates* and numeric` through the line `- ubyhost_request_duration_seconds{method,route}     histogram (seconds)` with:

```
Four families, all PII-free (OPS-3): route *templates* and numeric
status codes, never a path, token, query string or user identifier.

- ubyhost_requests_total{method,route,status}         counter
- ubyhost_request_duration_seconds{method,route}     histogram (seconds)
- ubyhost_request_db_queries_total{method,route}     counter (statements run)
- ubyhost_request_db_seconds_total{method,route}     counter (seconds inside the db helpers)

Queries per request on a route = rate of the db_queries counter divided by
the rate of ubyhost_request_duration_seconds_count (brief 1065).
```

3b. Registries. Anchor: `_duration_counts: dict[str, dict[str, int]] = {}`. Replace with:

```python
_duration_counts: dict[str, dict[str, int]] = {}
# route template -> method -> total (brief 1065)
_db_queries: dict[str, dict[str, int]] = {}
_db_seconds: dict[str, dict[str, float]] = {}
```

3c. `observe_request`. Anchor: `def observe_request(method: str, route: str, status: int, duration_seconds: float) -> None:` Replace with:

```python
def observe_request(
    method: str,
    route: str,
    status: int,
    duration_seconds: float,
    db_queries: int = 0,
    db_seconds: float = 0.0,
) -> None:
```

Anchor (last two lines of the function body):

```python
        counts = _duration_counts.setdefault(route, {})
        counts[method] = counts.get(method, 0) + 1
```

Replace with:

```python
        counts = _duration_counts.setdefault(route, {})
        counts[method] = counts.get(method, 0) + 1
        queries = _db_queries.setdefault(route, {})
        queries[method] = queries.get(method, 0) + max(0, int(db_queries))
        waited = _db_seconds.setdefault(route, {})
        waited[method] = waited.get(method, 0.0) + max(0.0, float(db_seconds))
```

3d. `render`. Anchor (the last lines of `render`):

```python
                lines.append(f"ubyhost_request_duration_seconds_count{{{labels}}} {_duration_counts[route][method]}")
        return "\n".join(lines) + "\n"
```

Replace with:

```python
                lines.append(f"ubyhost_request_duration_seconds_count{{{labels}}} {_duration_counts[route][method]}")
        lines.append("# HELP ubyhost_request_db_queries_total Database statements run by finished requests, by route template and method.")
        lines.append("# TYPE ubyhost_request_db_queries_total counter")
        for route in sorted(_db_queries):
            for method, total in sorted(_db_queries[route].items()):
                lines.append(
                    f'ubyhost_request_db_queries_total{{method="{_label_value(method)}",route="{_label_value(route)}"}} {total}'
                )
        lines.append("# HELP ubyhost_request_db_seconds_total Seconds finished requests spent in the database helpers, by route template and method.")
        lines.append("# TYPE ubyhost_request_db_seconds_total counter")
        for route in sorted(_db_seconds):
            for method, total in sorted(_db_seconds[route].items()):
                lines.append(
                    f'ubyhost_request_db_seconds_total{{method="{_label_value(method)}",route="{_label_value(route)}"}} {total!r}'
                )
        return "\n".join(lines) + "\n"
```

Command: `.venv/bin/python -c "from app import metrics as m; m.observe_request('GET','/x/{id}',200,0.01,db_queries=3,db_seconds=0.02); print([l for l in m.render().splitlines() if 'db_' in l and not l.startswith('#')])" 2>&1 | tail -30`
Expected: a list with `ubyhost_request_db_queries_total{method="GET",route="/x/{id}"} 3` and `ubyhost_request_db_seconds_total{method="GET",route="/x/{id}"} 0.02`.

### Step 4: `main.py`, pass the stats

Anchor (exact, in `App/app/main.py`):

```python
        metrics.observe_request(
            request.method, _access_route(request), response.status_code,
            time.perf_counter() - started,
        )
```

Replace with:

```python
        metrics.observe_request(
            request.method, _access_route(request), response.status_code,
            time.perf_counter() - started,
            db_queries=stats.queries, db_seconds=stats.db_seconds,
        )
```

Command: `grep -n "db_queries=stats.queries" app/main.py | tail -30`
Expected: one line.

### Step 5: tests, part 2 (`test_metrics_0427.py`)

5a. In `_reset()`, anchor `        m._duration_counts.clear()` and add two lines after it:

```python
        m._db_queries.clear()
        m._db_seconds.clear()
```

5b. Append at the end of the file:

```python
def test_db_counters_sum_per_route_and_method():
    from app import metrics as m

    _reset()
    m.observe_request("GET", "/guide/{item_id}", 200, 0.04, db_queries=7, db_seconds=0.25)
    m.observe_request("GET", "/guide/{item_id}", 200, 0.04, db_queries=5, db_seconds=0.25)
    m.observe_request("POST", "/guide/{item_id}", 200, 0.04)
    out = m.render()
    assert 'ubyhost_request_db_queries_total{method="GET",route="/guide/{item_id}"} 12' in out
    assert 'ubyhost_request_db_seconds_total{method="GET",route="/guide/{item_id}"} 0.5' in out
    assert 'ubyhost_request_db_queries_total{method="POST",route="/guide/{item_id}"} 0' in out


def test_db_counters_use_templates_and_only_two_labels(client):
    """OPS-3: no raw path, no extra label; the middleware feeds the real stats."""
    import re

    _reset()
    client.get("/l/not-a-real-token")
    from app import metrics as m

    out = m.render()
    assert "/l/not-a-real-token" not in out
    lines = [l for l in out.splitlines() if l.startswith("ubyhost_request_db_queries_total{")]
    assert any('route="/l/{token}"' in l for l in lines)
    for line in lines:
        assert re.fullmatch(r'ubyhost_request_db_queries_total\{method="[A-Z]+",route="[^"]+"\} \d+', line), line
```

Command: `.venv/bin/python -m pytest tests/test_metrics_0427.py -q --tb=short -x 2>&1 | tail -30`
Expected: all pass (the 4 old tests plus 2 new), 0 failed.

### Step 6: tests, part 1 (`test_admin_funnel.py`)

Append at the end of the file:

```python
def test_first_run_times_read_existing_timestamps_only():
    uid = _account("times")
    created = NOW - timedelta(days=30)
    db.execute("UPDATE user_account SET created_at = ? WHERE id = ?", (_iso(created), uid))
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Flat times", "owner_user_id": uid,
            "created_at": _iso(created + timedelta(seconds=600)),
            "ubyport_verified_at": _iso(created + timedelta(seconds=1200)),
        },
    )
    db.insert(
        "ical_feed",
        {"apartment_id": apartment_id, "url": "https://example.test/t.ics", "last_status": "ok",
         "created_at": _iso(created + timedelta(seconds=1800))},
    )
    db.insert(
        "reservation",
        {"apartment_id": apartment_id, "uid": f"{PREFIX}times", "date_from": "2026-08-01",
         "date_to": "2026-08-03", "registration_completed_at": _iso(created + timedelta(seconds=3600)),
         "created_at": _iso(created), "updated_at": _iso(created)},
    )
    row = _mine(admin_funnel.rows(now=NOW))[f"{PREFIX}times"]
    assert row["first_police_at"] == _iso(created + timedelta(seconds=1200))
    assert admin_funnel._seconds_between(row["created_at"], row["first_property_at"]) == 600
    assert admin_funnel._seconds_between(row["created_at"], row["first_calendar_at"]) == 1800
    assert admin_funnel._seconds_between(row["created_at"], row["first_police_at"]) == 1200
    assert admin_funnel._seconds_between(row["created_at"], row["first_guest_at"]) == 3600


def test_first_run_times_median_p75_and_gaps():
    guest = "2026-01-01T00:00:00+00:00"

    def r(created, at):
        return {"created_at": created, "first_property_at": at, "first_calendar_at": None,
                "first_police_at": None, "first_guest_at": guest}

    start = "2026-01-01T00:00:00+00:00"
    data = {"rows": [
        r(start, "2026-01-01T00:01:00+00:00"),
        r(start, "2026-01-01T00:03:00+00:00"),
        r(start, "2026-01-01T00:02:00+00:00"),
        r(start, "2026-01-01T00:10:00+00:00"),
        # created after its first guest: negative, dropped; no property: dropped
        r("2026-01-02T00:00:00+00:00", None),
    ]}
    out = admin_funnel.first_run_times(data)
    assert out["first_property"] == {"accounts": 4, "median_seconds": 150, "p75_seconds": 180}
    assert out["first_calendar"] == {"accounts": 0, "median_seconds": None, "p75_seconds": None}
    assert out["first_guest"]["accounts"] == 4
    assert set(out) == {"first_property", "first_calendar", "first_police", "first_guest"}


def test_first_run_times_do_not_change_stages_or_csv():
    keys = [key for key, _column in admin_funnel.stages()]
    assert "first_police" not in keys
    headers = [h for h, _k in admin_funnel.csv_columns("2026-09", "2026-10")]
    assert "first_police" not in headers and "first_police_at" not in headers
```

Arithmetic in the second test: property values sorted are 60, 120, 180, 600, so the median is (120+180)//2 = 150 and the 75th percentile index is `ceil(3.0) - 1 = 2`, which is 180. The four rows created at `start` have a first guest at 0 s (kept); the fifth is dropped as negative.

Command: `.venv/bin/python -m pytest tests/test_admin_funnel.py -q --tb=short -x 2>&1 | tail -30`
Expected: all pass, 0 failed.

### Step 7: test-map row

In `docs/context/test-map.md`, anchor the row:

```
| Analytics | `test_posthog_*.py test_umami_guard.py test_meta_capi.py` |
```

Add directly after it:

```
| Funnel stage times, `/metrics` | `test_admin_funnel.py test_metrics_0427.py test_posthog_*.py` |
```

Command (from the repo root): `grep -n "Funnel stage times" docs/context/test-map.md | tail -30`
Expected: one line.

## 5. Do not touch

`App/app/templating.py`, `access.py`, `alerts.py` (Q7 territory); any template, CSS or JS; `posthog_sync.py` and `analytics.py`; `db.py` and `App/app/migrations/` (no schema change; if a stage seems to need a column, STOP); the Caddyfiles; `retention.py`. Hard rules from AGENTS.md that apply: no tracking cookies, no script on pages, nothing to PostHog, SQL only through `db.py` helpers, never push to `main`.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_admin_funnel.py tests/test_metrics_0427.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.
2. `.venv/bin/python -m pytest tests/test_posthog_*.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass (proves the `stages()` consumers are unaffected).

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected last line: `context lint: OK`.

## 7. Acceptance

- [ ] `stages()` and `csv_columns()` are unchanged (`test_first_run_times_do_not_change_stages_or_csv` passes).
- [ ] `first_run_times()` returns the four stages with `accounts`, `median_seconds`, `p75_seconds`, from existing columns only; `git diff --stat` shows no file under `App/app/migrations/` and no `db.py`.
- [ ] `/metrics` output contains `ubyhost_request_db_queries_total` and `ubyhost_request_db_seconds_total` with only `method` and `route` labels; a request to `/l/not-a-real-token` shows `route="/l/{token}"` and the raw token is absent.
- [ ] No new template, script, cookie or outbound request; no change to `retention.py` (no personal-data field added).
- [ ] The two test commands in section 6 and the context lint pass.
- [ ] "Guest seconds per registration" is not built; the report repeats the reason from 2.2.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found verbatim (a Q7 or other change may have landed first);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency or a new column seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1065-report.md` (600 tokens at most) and set `Status: review`. The report has: 1. files changed (`git diff --stat`); 2. each command with the last 5 lines of its output; 3. section 7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

`App/app/main.py` (one call in the request middleware: confirm `stats` is the object created by `db.start_request_stats()` earlier in the same function and the extra kwargs cannot raise); `App/app/metrics.py` (label escaping unchanged, registries cleared in tests); the `_SQL` string in `App/app/admin_funnel.py` (one added correlated subquery on `apartment`, indexed by `owner_user_id`; one extra subquery per host row).

## Owner steps

Nothing is visible until the owner deploys. After the deploy, to capture the baseline for one week:

1. Stage times: on the server, from the compose folder, run `docker compose exec ubyhost python -m app.admin_funnel 2>&1 | tail -30`. It prints four blocks with accounts, median and 75th percentile seconds. Save the output with its date.
2. Query counts: in Grafana Cloud (the alloy scrape already exists), chart `sum by (route) (rate(ubyhost_request_db_queries_total[1d])) / sum by (route) (rate(ubyhost_request_duration_seconds_count[1d]))`. Counters restart at 0 on every deploy and each uvicorn worker counts alone; Prometheus sums workers.
3. Leave the access log off (`ACCESS_LOG`); nothing here needs it.
