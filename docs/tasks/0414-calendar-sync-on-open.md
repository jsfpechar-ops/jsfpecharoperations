# 0414: Sync calendars when the host opens the app, and say how syncing works

Status: review
Depends on: none | Base commit: 838bec1 | Branch: claude/project-thread-kpvhyc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A host got a last-minute booking and it did not show in UbyHost, because calendars are only read once an hour (`UBYHOST_ICAL_POLL_MINUTES=60`). Owner ask (2026-10-26): tell hosts how often calendars update and that "Update calendars" fetches them now, and sync automatically when the host opens the app. Sessions last for weeks (e-mail link login, `remember=True`), so "on login" means "on opening the dashboard or the Stays page".

## 2. Context

- `icalsync.sync_feed(feed)` reconciles one calendar row. `ical_feed.last_checked_at` is set on every check, including failures (`_record_feed_failure`).
- Web runs several uvicorn workers and jobs run in a separate worker container, so a per-process lock is not enough. Each feed is claimed with one conditional `UPDATE` (rowcount 1 = this request won it). `db.execute_rowcount` returns the rowcount.
- Starlette runs a sync `BackgroundTask` in the threadpool after the response is sent, so the page never waits for Airbnb. The host sees new stays on the next page load.
- The test client runs background tasks inline, so tests turn the feature off with `UBYHOST_ICAL_OPEN_SYNC_MINUTES=0` in `conftest.py`; the new test turns it on by monkeypatching `config`.
- Copy rules: en, cs and vi; no em dashes; outside the wizard help lives in the existing `?` help tip, no new paragraphs.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/config.py | edit | new `ICAL_OPEN_SYNC_MINUTES` |
| App/tests/conftest.py | edit | default the feature off in tests |
| App/app/icalsync.py | edit | new `sync_owner_if_stale` |
| App/app/routes/admin.py | edit | attach it to dashboard and Stays responses |
| App/app/host_i18n.py | edit | two copy keys, en and cs |
| App/app/host_vi_i18n.py | edit | the same two keys in vi |
| App/tests/test_calendar_sync_on_open.py | create | tests |
| docs/ENVIRONMENT.md | edit | one row |

No other file may change.

## 4. Steps

1. `App/app/config.py`, find:
```python
ICAL_POLL_MINUTES = int(os.environ.get("UBYHOST_ICAL_POLL_MINUTES", "60"))
```
Replace with:
```python
ICAL_POLL_MINUTES = int(os.environ.get("UBYHOST_ICAL_POLL_MINUTES", "60"))
# 0414: opening the dashboard or Stays re-reads calendars checked longer ago than this. 0 turns it off.
ICAL_OPEN_SYNC_MINUTES = int(os.environ.get("UBYHOST_ICAL_OPEN_SYNC_MINUTES", "10"))
```

2. `App/tests/conftest.py`, find:
```python
os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
```
Replace with:
```python
os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
os.environ.setdefault("UBYHOST_ICAL_OPEN_SYNC_MINUTES", "0")
```

3. `App/app/icalsync.py`, find:
```python
def sync_all(
    apartment_id: Optional[int] = None, owner_user_id: Optional[int] = None
) -> Dict[str, Any]:
```
Insert directly above it:
```python
def sync_owner_if_stale(owner_user_id: Optional[int]) -> int:
    """0414: re-read an owner's calendars when they open the app.

    A booking made since the hourly poll should be there when the host looks.
    Only calendars not checked for ``ICAL_OPEN_SYNC_MINUTES`` are read, and each
    is claimed with one conditional UPDATE so two workers (or a quick reload)
    never read the same calendar twice. Returns how many calendars were read.
    """
    minutes = config.ICAL_OPEN_SYNC_MINUTES
    if minutes <= 0:
        return 0
    now = db.utcnow()
    cutoff = (datetime.fromisoformat(now) - timedelta(minutes=minutes)).isoformat()
    feeds = db.query(
        "SELECT f.* FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
        f"WHERE f.active = 1 AND a.active = 1 AND {db.null_safe_eq('a.owner_user_id')} "
        "AND (f.last_checked_at IS NULL OR f.last_checked_at < ?)",
        (owner_user_id, cutoff),
    )
    read = 0
    for feed in feeds:
        claimed = db.execute_rowcount(
            "UPDATE ical_feed SET last_checked_at = ? "
            "WHERE id = ? AND (last_checked_at IS NULL OR last_checked_at < ?)",
            (now, feed["id"], cutoff),
        )
        if not claimed:
            continue
        read += 1
        try:
            sync_feed(feed)
        except Exception as exc:  # noqa: BLE001 - one feed must not stop the rest
            log.exception("ical open-sync feed %s failed", feed["id"])
            _record_feed_failure(feed, exc, db.utcnow())
    if read:
        log.info("ical_open_sync feeds=%s", read)
    return read


```
Check: `grep -n "def sync_owner_if_stale" App/app/icalsync.py` prints one line.

4. `App/app/routes/admin.py`, find:
```python
from starlette.concurrency import run_in_threadpool
```
Replace with:
```python
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
```

5. Same file, find:
```python
@router.get("/")
def dashboard(request: Request):
```
Insert directly above it:
```python
def _with_calendar_refresh(request: Request, response):
    """0414: opening the app re-reads stale calendars after the page is sent."""
    if config.ICAL_OPEN_SYNC_MINUTES > 0 and response.background is None:
        response.background = BackgroundTask(icalsync.sync_owner_if_stale, access.owner_id(request))
    return response


```

6. Same file, in `def dashboard`, find:
```python
    milestone, sent_count, minutes_saved = celebrations.celebration_context(owner_user_id)
    return render(
        request,
        "dashboard.html",
```
Replace with:
```python
    milestone, sent_count, minutes_saved = celebrations.celebration_context(owner_user_id)
    return _with_calendar_refresh(request, render(
        request,
        "dashboard.html",
```
Then find the `)` that closes that `render(` call (the first line that is exactly `    )` after it) and replace it with `    ))`.

7. Same file, in `def reservations_list`, find:
```python
    return render(
        request,
        "reservations.html",
```
Replace with:
```python
    return _with_calendar_refresh(request, render(
        request,
        "reservations.html",
```
Then find the closing lines of that call:
```python
            "show_archive": show_archive,
        },
    )
```
and replace the last line `    )` with `    ))`. If `"show_archive"` is not the last key, close the call that starts in this step, wherever it ends.
Check: `cd App && .venv/bin/python -c "import app.routes.admin" 2>&1 | tail -3` prints nothing.

8. `App/app/host_i18n.py`, English block, find:
```python
        "apartment.form.calendars.lede": "iCal feeds give dates only, which is enough to start collecting guest details.",
```
Replace with:
```python
        "apartment.form.calendars.lede": "We read your calendars every hour and each time you open UbyHost. A booking just came in? Press Update calendars to fetch it now.",
```
Czech block, find:
```python
        "apartment.form.calendars.lede": "iCal dává jen termíny, a to stačí k zahájení sběru údajů hostů.",
```
Replace with:
```python
        "apartment.form.calendars.lede": "Kalendáře čteme každou hodinu a pokaždé, když otevřete UbyHost. Právě přišla rezervace? Stiskněte Aktualizovat kalendáře a načte se hned.",
```
English block, find:
```python
        "setup_guide.calendar.text": "Paste the calendar link from Airbnb, Booking.com or another platform, and your stays appear here by themselves.",
```
Replace with:
```python
        "setup_guide.calendar.text": "Paste the calendar link from Airbnb, Booking.com or another platform, and your stays appear here by themselves. We read it every hour and each time you open UbyHost. For a booking made a minute ago, press Update calendars.",
```
Czech block, find:
```python
        "setup_guide.calendar.text": "Vložte odkaz na kalendář z Airbnb, Booking.com nebo jiné platformy a pobyty se tu objeví samy.",
```
Replace with:
```python
        "setup_guide.calendar.text": "Vložte odkaz na kalendář z Airbnb, Booking.com nebo jiné platformy a pobyty se tu objeví samy. Čteme ho každou hodinu a pokaždé, když otevřete UbyHost. Rezervaci z poslední minuty načtete tlačítkem Aktualizovat kalendáře.",
```

9. `App/app/host_vi_i18n.py`, find the line starting `    "apartment.form.calendars.lede":` and replace its value with:
`"Chúng tôi đọc lịch của bạn mỗi giờ và mỗi khi bạn mở UbyHost. Vừa có đặt phòng mới? Nhấn Cập nhật lịch để lấy ngay."`
Find:
```python
    "setup_guide.calendar.text": "Dán liên kết lịch từ Airbnb, Booking.com hoặc nền tảng khác, và các lượt lưu trú sẽ tự xuất hiện ở đây.",
```
Replace with:
```python
    "setup_guide.calendar.text": "Dán liên kết lịch từ Airbnb, Booking.com hoặc nền tảng khác, và các lượt lưu trú sẽ tự xuất hiện ở đây. Chúng tôi đọc lịch mỗi giờ và mỗi khi bạn mở UbyHost. Với đặt phòng vừa mới có, hãy nhấn Cập nhật lịch.",
```

10. `docs/ENVIRONMENT.md`, find the line starting ``| `UBYHOST_ICAL_POLL_MINUTES` `` and insert directly below it:
```
| `UBYHOST_ICAL_OPEN_SYNC_MINUTES` | `10` | Opening the dashboard or Stays re-reads calendars checked longer ago than this; `0` turns it off. |
```

11. Create `App/tests/test_calendar_sync_on_open.py`. Copy how `App/tests/test_icalsync.py` creates an owner, an apartment and an `ical_feed` row (read only its first 80 lines and its helper functions; do not read the whole file). Monkeypatch `icalsync.sync_feed` with a function that appends `feed["id"]` to a list, and `config.ICAL_OPEN_SYNC_MINUTES` to `10`. Tests:
   - a feed with `last_checked_at` NULL is read once; calling `sync_owner_if_stale` again right away reads nothing (claim holds).
   - a feed with `last_checked_at` = now minus 5 minutes is not read; one with now minus 30 minutes is read.
   - a feed of another owner is not read.
   - with `config.ICAL_OPEN_SYNC_MINUTES = 0` nothing is read.
   - when the fake `sync_feed` raises, the feed ends with `last_status = 'error'` and the function does not raise.

## 5. Do not touch

Every file not listed in section 3, the scheduler, and `sync_all`.

## 6. Commands

From `App/`:
`.venv/bin/python -m pytest tests/test_calendar_sync_on_open.py tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_calendar_sync_ui.py tests/test_dashboard_calendar.py tests/test_dashboard_empty.py -q --tb=short -x 2>&1 | tail -30`
If an i18n test exists for the changed keys, `grep -ln "calendars.lede\|setup_guide.calendar.text" tests/*.py` and run those too. From the repo root: `python3 scripts/context_lint.py | tail -5`.

## 7. Acceptance

- All tests above pass. No browser test is needed: no template or CSS changed.
- `git diff --stat` lists only the files in section 3 plus this brief and the report.

## 8. Stop and ask

Stop and report (do not improvise) if a find string is missing, if `response.background` is already set on either page, or if any existing test fails for a reason you cannot tie to this change.

## 9. Report

Write `docs/tasks/0414-report.md` (400 tokens at most), set `Status: review` in this brief, and commit everything with message `0414: sync calendars when the host opens the app; say how often they update`.

## Risk list (for the reviewer)

- K-F05 (scheduled and manual sync clash) is not fixed; the claim only stops open-syncs from doubling up.
- The claim sets `last_checked_at` before the read, so a read that dies mid-way without `_record_feed_failure` shows a fresh check time with the previous status.

## Owner steps

None. The default is on (10 minutes); set `UBYHOST_ICAL_OPEN_SYNC_MINUTES=0` in the server `.env` to turn it off.
