# 0347: Booking and Airbnb import: fetch

Status: todo
Depends on: 0345 merged | Base commit: after 0345 | Branch: task/0297-guide-import-fetch
Executor: Haiku 5.5 (critical: Fable reviews the diff before merge) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the guest guide page the host pastes the public link of their own Booking.com or Airbnb listing; a worker job fetches it through an Apify actor and stores a trimmed, size-capped copy of the text in a `guide_import` row. Fetch and store only: brief 0348 reads the rows (`pending_for`), drafts "Check this" cards and calls `mark_used` ([plan](../plans/guest-guide.md)).

## 2. Context

### Security (why this brief is critical)

- **No user text reaches an HTTP client.** `normalise_url` matches the link against an allowlist and *rebuilds* it: scheme `https`, host `www.booking.com` or `www.airbnb.com`, the matched path only. Query, fragment, userinfo, port, other hosts, IP literals, lookalikes, `http`, non-ASCII, backslashes and short links are refused with a flash key. The only URL opened is the constant `APIFY_API` plus an id from the constant `ACTORS`: no SSRF surface.
- **Secret:** `UBYHOST_APIFY_TOKEN`, env only, read in `config.py` like `UBYHOST_TTLOCK_CLIENT_SECRET`. Unset means off: the page says so calmly, the POST refuses, the worker does nothing. The token travels in an `Authorization: Bearer` header, never in a URL or a log.
- **Untrusted data:** `trim()` keeps only named fields per source (title, description, check-in and check-out times, address, house rules, amenities, location notes), whitespace-collapsed, cut to `MAX_TEXT` / `MAX_ITEM_TEXT`, JSON capped at 64 KB; a response over 4 MB is dropped unread. Logs carry the row id, the source and a short error code, never listing text or the URL.
- **Ownership and CSRF:** every route goes through `_home()` (404 on a foreign or archived property) under the router's `security.protect_host_post`.
- **Cost:** one import per listing (Booking, Airbnb) per property, for good (owner, 2026-10-24: after it the host fills the rest by hand; a failed run does not use it up; non-failed rows are kept without text as that record), one in flight per property, and a global cap on actor runs (`UBYHOST_APIFY_MONTHLY_RUNS`, default 40) counted in the existing `lock_api_usage` table under `provider = 'apify'`, exactly as `ttlock._count_call` does. The page shows what is left.
- Hard rules 2 (new outbound request: this brief is the reason; retention line added), 3, 4 (`requests` is already a dependency), 5, 6, 9.

### Background job, not a synchronous request

Production runs two uvicorn web workers and the scheduler in a separate `worker` role (`config.ROLE`). An actor run takes 30 to 120 s and must not hold a web request. The repo's pattern for long outbound work is a queue table drained by a one-minute job (`cleaning_codes.process_queue()` in `_job_door_codes`, `push.drain()` in `_job_push`). Same here: the POST inserts a `queued` row and redirects; `_job_guide_import` calls `process_queue()` every minute, which calls Apify's synchronous endpoint with `timeout=120`, `maxItems=1` and a `requests` timeout of `(10, 150)`. The host sees "Importing" and reloads (no polling script; 0349 may add one).

### Apify (checked 2026-10-24 on apify.com and docs.apify.com)

- Endpoint: `POST https://api.apify.com/v2/acts/{owner~name}/run-sync-get-dataset-items?timeout=&maxItems=&format=json&clean=true`. 201 with a JSON array of items; 408 when the run passes 300 s; `{"error": {"type", "message"}}` otherwise. `[verify]` the endpoint page does not state the auth header; Apify's API docs use `Authorization: Bearer <token>`, which the code sends. A real 401 means stop (§8).
- Booking: `voyager/booking-scraper` (the spike's actor), pay per result, "from $2.00 / 1,000 results". Input: `startUrls`, `maxItems`, `language`, `currency`; direct `/hotel/...html` URLs are supported. Output: `name`, `description`, `checkIn`, `checkOut` (times such as "From 4:00 PM"), `address.full`. `[verify]` `startUrls` item shape: the code sends `[{"url": ...}]`, Apify's request-list shape; the schema page only says "array".
- Airbnb: `tri_angle/airbnb-rooms-urls-scraper` ("direct room URLs"), pay per result, "from $1.95 / 1,000 listings". Input example on the store page: `{"startUrls": [{"url": "https://www.airbnb.com/rooms/53997462"}]}`. Output (the `tri_angle` family): `title`, `description`, `subDescription`, `houseRules` (`additional`, `general[].values[].title`), `amenities[].values[].title` with `available`, `locationDescriptions`, `highlights`, `propertyType`, `roomType`; no check-in time, no street address. `[verify]` field names on the first real run; a renamed key loses that text and breaks nothing.
- Free plan: $5 platform credit a month; 40 runs stay far inside it. The owner adjusts the cap after the first month's bill.

### Anchors (verbatim; a missing anchor means STOP)

`App/app/config.py`: `TTLOCK_MONTHLY_CALLS = int(os.environ.get("UBYHOST_TTLOCK_MONTHLY_CALLS", "30000"))`

`App/app/routes/guest_guide.py`: the line `from .. import access, auth, config, guest_guide, guide_photos, guide_token, payments, security, templating`; the lines `        next_id=_next_open(apartment_id, 0),` followed by `    )`; the line `def _guest_url(apartment_id: int) -> str:`.

`App/app/templates/guest_guide.html`: `{% call ui_section(t('guest_guide.add.title'), id='add-card') %}`

`App/app/host_i18n.py`: `# 0345: the guide's QR code for the host to print.` followed by `_GUIDE_QR_STRINGS = {`

`App/app/scheduler.py`: `    "stay_fee_mail": "warning",` followed by `}`; `        "push": 1,`; `def _job_push() -> None:`; the `add_job` block whose second line is `        _job_push, "interval", minutes=minutes["push"],`.

`App/app/retention.py`: `# Each step takes (today, dry_run, owner_user_id) and returns the affected count.`; `    ("push", _push_step),`; `        "push": "alert queued over 30 days ago, or device unseen for 180 days",`.

`docs/ENVIRONMENT.md`: `## Urgent alerts (web push)`. `docs/privacy/RETENTION.md`: the row starting `| Submission envelopes (XML with doc numbers)`.

Template strings interpolate with `%(n)s`, not `{n}`. Flash keys must exist in en and cs (`tests/test_flash_literals.py`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/MMMM_guide_import.sql` | create | `guide_import` table (MMMM: step 1) |
| `App/app/guest_guide_import.py` | create | Allowlist, queue, Apify call, trim, handoff, purge |
| `App/app/config.py` | edit | `APIFY_TOKEN`, `APIFY_MONTHLY_RUNS`, `APIFY_TIMEOUT` |
| `App/app/routes/guest_guide.py` | edit | Import POST, four context values |
| `App/app/templates/guest_guide.html` | edit | Import section |
| `App/app/host_i18n.py` | edit | `_GUIDE_IMPORT_STRINGS`, en and cs |
| `App/app/scheduler.py` | edit | `_job_guide_import`, every minute |
| `App/app/retention.py` | edit | `guide_imports` step and cutoff line |
| `App/tests/test_guest_guide_import.py` | create | Copied from `docs/plans/0297-files/` (step 10) |
| `docs/ENVIRONMENT.md` | edit | Apify section |
| `docs/privacy/RETENTION.md` | edit | One row |

No other file may change.

## 4. Steps

Commands run from `App/` with `.venv/bin/python` unless said otherwise.

### Step 1: migration

Repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` prints `next free: task NNNN | migration MMMM`. Create `App/app/migrations/MMMM_guide_import.sql` with that `MMMM` (another thread adds migrations from 0015; never reuse an existing number):

```sql
-- Brief 0347: Booking.com and Airbnb listing imports (plan: docs/plans/guest-guide.md).
--
-- guide_import: one request by the host to fetch their own public listing
-- through Apify. url is the rebuilt, allowlisted link (never the pasted text).
-- status: 'queued' (waiting for the worker), 'running', 'done' (raw_json holds
-- the trimmed result for brief 0348), 'failed' (error holds a short code, no
-- listing text), 'used' (0348 drafted cards; raw_json is NULL), 'expired'
-- (raw_json removed by retention after 7 days). Failed rows go after 60 days;
-- the others stay, without text, as the record of the one import per listing.
-- Listing text only, no guest data.
CREATE TABLE IF NOT EXISTS guide_import (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    source        TEXT NOT NULL CHECK (source IN ('booking', 'airbnb')),
    url           TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed', 'used', 'expired')),
    error         TEXT,
    raw_json      TEXT,
    created_at    TEXT NOT NULL,
    started_at    TEXT,
    finished_at   TEXT,
    used_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_guide_import_apartment ON guide_import (apartment_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_guide_import_status ON guide_import (status, id);
```

Command: `.venv/bin/python -m pytest tests/test_migrations.py -q --tb=short -x 2>&1 | tail -5`. Expected: 0 failed.

### Step 2: `App/app/config.py`

After the `TTLOCK_MONTHLY_CALLS` anchor line add:

```python

# Guest guide imports through Apify (brief 0347). Off until the token is set;
# the token is env only. The run cap is shared by every host on the instance.
APIFY_TOKEN = os.environ.get("UBYHOST_APIFY_TOKEN", "").strip()
APIFY_MONTHLY_RUNS = int(os.environ.get("UBYHOST_APIFY_MONTHLY_RUNS", "40"))
APIFY_TIMEOUT = int(os.environ.get("UBYHOST_APIFY_TIMEOUT", "120"))
```

Command: `.venv/bin/python -c "from app import config; print(config.APIFY_TOKEN == '', config.APIFY_MONTHLY_RUNS)"`. Expected: `True 40`.

### Step 3: `App/app/guest_guide_import.py` (new)

```python
"""Brief 0347: fetch a host's own Booking.com or Airbnb listing through Apify.

The pasted link is checked against a strict allowlist and rebuilt from its
parts, so nothing the host typed reaches an HTTP client. The worker runs one
Apify actor per queued row and stores a trimmed, size-capped copy of the text.
Brief 0348 reads it (``pending_for``) and calls ``mark_used``; ``purge`` drops
raw data after seven days at the latest. Listing text and the token are never
logged.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import requests

from . import config, db

log = logging.getLogger("ubyhost.guide_import")

# Apify's API host is a constant: the only URL this module ever opens.
APIFY_API = "https://api.apify.com/v2/acts/"
# Actor ids (owner~name) checked 2026-10-24 on apify.com; pay per result.
ACTORS = {
    "booking": "voyager~booking-scraper",
    "airbnb": "tri_angle~airbnb-rooms-urls-scraper",
}
MAX_URL_LENGTH = 2048
MAX_STORED_BYTES = 64 * 1024
MAX_TEXT = 4000
MAX_LIST_ITEMS = 80
MAX_ITEM_TEXT = 200
RAW_DAYS = 7
ROW_DAYS = 60
# Connect and read timeouts; the read side outlasts the actor timeout we ask
# Apify for, so Apify's own 408 arrives before ours.
HTTP_TIMEOUT = (10, 150)

_BOOKING_HOSTS = frozenset({"booking.com", "www.booking.com", "m.booking.com"})
_BOOKING_PATH = re.compile(r"^/hotel/([a-z]{2})/([a-z0-9][a-z0-9._-]{0,200})\.html$", re.IGNORECASE)
_AIRBNB_HOST = re.compile(
    r"^(?:www\.|m\.)?airbnb\.(?:com|cz|sk|de|at|pl|fr|it|es|nl|ch|hu|ie|ca|co\.uk|com\.au)$"
)
_AIRBNB_PATH = re.compile(r"^/rooms/(?:plus/)?([0-9]{1,20})/?$")


class GuideImportError(Exception):
    """A refusal the host sees; ``key`` is a host_i18n string."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


# --- the link -----------------------------------------------------------------


def normalise_url(raw: str) -> Dict[str, str]:
    """``{"source", "url"}`` for an allowed listing link, rebuilt from the matched
    parts only (fixed scheme and host, matched path); anything else is refused."""
    text = (raw or "").strip()
    if not text or len(text) > MAX_URL_LENGTH or not text.isascii():
        raise GuideImportError("flash.error.guide_import_link")
    if "@" in text or "\\" in text or any(c.isspace() for c in text):
        raise GuideImportError("flash.error.guide_import_link")
    parts = urlsplit(text)
    if parts.scheme != "https" or parts.username or parts.password or parts.port:
        raise GuideImportError("flash.error.guide_import_link")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or ":" in host or host.replace(".", "").isdigit():
        raise GuideImportError("flash.error.guide_import_link")
    path = parts.path or "/"
    if host in _BOOKING_HOSTS:
        match = _BOOKING_PATH.match(path)
        if not match:
            raise GuideImportError("flash.error.guide_import_booking_path")
        return {"source": "booking", "url": f"https://www.booking.com/hotel/{match.group(1).lower()}/{match.group(2)}.html"}
    if _AIRBNB_HOST.match(host):
        match = _AIRBNB_PATH.match(path)
        if not match:
            raise GuideImportError("flash.error.guide_import_airbnb_path")
        return {"source": "airbnb", "url": f"https://www.airbnb.com/rooms/{match.group(1)}"}
    raise GuideImportError("flash.error.guide_import_link")


# --- switches and budgets -----------------------------------------------------


def enabled() -> bool:
    return bool(config.APIFY_TOKEN)


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def used_sources(apartment_id: int) -> set:
    """Sources this property has imported. One import per listing per property, for good
    (owner, 2026-10-24): after it the host fills the rest by hand. A failed run does
    not use it up; the global run budget still counts it."""
    rows = db.query(
        "SELECT DISTINCT source FROM guide_import WHERE apartment_id = ? AND status != 'failed'",
        (apartment_id,),
    )
    return {r["source"] for r in rows}


def imports_left(apartment_id: int) -> int:
    return len(set(ACTORS) - used_sources(apartment_id))


def runs_this_month() -> int:
    row = db.query_one(
        "SELECT calls FROM lock_api_usage WHERE month = ? AND provider = 'apify'", (_month_key(),)
    )
    return int(row["calls"]) if row and row["calls"] is not None else 0


def _count_run() -> None:
    db.execute(
        "INSERT INTO lock_api_usage (month, provider, calls) VALUES (?, 'apify', 1) "
        "ON CONFLICT (month, provider) DO UPDATE SET calls = calls + 1",
        (_month_key(),),
    )


def global_budget_left() -> bool:
    limit = config.APIFY_MONTHLY_RUNS
    return limit <= 0 or runs_this_month() < limit


# --- the queue ----------------------------------------------------------------


def request_import(apartment_id: int, raw_url: str) -> int:
    """Queue one import for a property the caller has checked; returns the row id."""
    if not enabled():
        raise GuideImportError("flash.error.guide_import_off")
    link = normalise_url(raw_url)
    if db.query_one(
        "SELECT id FROM guide_import WHERE apartment_id = ? AND status IN ('queued', 'running')",
        (apartment_id,),
    ):
        raise GuideImportError("flash.error.guide_import_busy")
    if link["source"] in used_sources(apartment_id):
        raise GuideImportError("flash.error.guide_import_limit")
    if not global_budget_left():
        raise GuideImportError("flash.error.guide_import_budget")
    return int(db.insert("guide_import", {
        "apartment_id": apartment_id, "source": link["source"], "url": link["url"],
        "status": "queued", "created_at": db.utcnow(),
    }) or 0)


def imports(apartment_id: int) -> List[Dict[str, Any]]:
    """Newest first, without the raw data."""
    rows = db.query(
        "SELECT id, source, url, status, error, created_at, finished_at FROM guide_import "
        "WHERE apartment_id = ? ORDER BY id DESC LIMIT 10",
        (apartment_id,),
    )
    return [dict(r) for r in rows]


def in_progress(apartment_id: int) -> bool:
    return any(r["status"] in ("queued", "running") for r in imports(apartment_id))


def pending_for(apartment_id: int) -> List[Dict[str, Any]]:
    """Handoff to brief 0348: fetched, unused imports with their data parsed."""
    rows = db.query(
        "SELECT id, source, url, raw_json, created_at FROM guide_import "
        "WHERE apartment_id = ? AND status = 'done' AND raw_json IS NOT NULL ORDER BY id",
        (apartment_id,),
    )
    out = []
    for r in rows:
        try:
            data = json.loads(r["raw_json"])
        except ValueError:
            continue
        out.append({"id": r["id"], "source": r["source"], "url": r["url"], "data": data})
    return out


def mark_used(import_id: int) -> None:
    """Brief 0348 calls this after drafting cards: the raw data goes at once."""
    db.execute(
        "UPDATE guide_import SET status = 'used', raw_json = NULL, used_at = ? WHERE id = ? AND status = 'done'",
        (db.utcnow(), import_id),
    )


# --- trimming -----------------------------------------------------------------

_TEXT_FIELDS = {
    "booking": ("name", "description", "checkIn", "checkOut"),
    "airbnb": ("title", "description", "subDescription", "propertyType", "roomType"),
}
_LIST_FIELDS = {
    "booking": (),
    "airbnb": ("amenities", "houseRules", "locationDescriptions", "highlights"),
}


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    return " ".join(str(value).split())[:limit]


def _flatten(value: Any, out: List[str], depth: int = 0) -> None:
    """Collect the short strings of a nested list or dict (titles, rule lines)."""
    if len(out) >= MAX_LIST_ITEMS or depth > 6:
        return
    if isinstance(value, str):
        text = _text(value, MAX_ITEM_TEXT)
        if text and text not in out:
            out.append(text)
    elif isinstance(value, list):
        for item in value:
            _flatten(item, out, depth + 1)
    elif isinstance(value, dict):
        if value.get("available") is False:
            return
        for key in ("title", "content", "subtitle", "values", "additional", "general"):
            if key in value:
                _flatten(value[key], out, depth + 1)


def trim(source: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """Named text fields, lists, address; size-capped."""
    if not isinstance(item, dict):
        return {}
    out: Dict[str, Any] = {"source": source}
    for key in _TEXT_FIELDS.get(source, ()):
        text = _text(item.get(key))
        if text:
            out[key] = text
    for key in _LIST_FIELDS.get(source, ()):
        lines: List[str] = []
        _flatten(item.get(key), lines)
        if lines:
            out[key] = lines
    address = item.get("address")
    if isinstance(address, dict):
        text = _text(address.get("full") or address.get("street"), 300)
        if text:
            out["address"] = text
    elif isinstance(address, str):
        out["address"] = _text(address, 300)
    encoded = json.dumps(out, ensure_ascii=False)
    while len(encoded.encode("utf-8")) > MAX_STORED_BYTES:
        for key, value in list(out.items()):
            if isinstance(value, list):
                out[key] = value[: max(1, len(value) // 2)]
            elif isinstance(value, str) and len(value) > 50:
                out[key] = value[: len(value) // 2]
        encoded = json.dumps(out, ensure_ascii=False)
    return out


# --- the worker side ----------------------------------------------------------


def _actor_input(source: str, url: str) -> Dict[str, Any]:
    body: Dict[str, Any] = {"startUrls": [{"url": url}]}
    if source == "booking":
        body.update({"maxItems": 1, "language": "en-gb", "currency": "CZK"})
    return body


def _fetch(source: str, url: str) -> Dict[str, Any]:
    """One synchronous actor run. Raises GuideImportError with a short code."""
    actor = ACTORS[source]
    endpoint = f"{APIFY_API}{actor}/run-sync-get-dataset-items"
    params = {"timeout": config.APIFY_TIMEOUT, "maxItems": 1, "clean": "true", "format": "json"}
    headers = {"Authorization": f"Bearer {config.APIFY_TOKEN}", "Content-Type": "application/json"}
    try:
        response = requests.post(
            endpoint, params=params, headers=headers, timeout=HTTP_TIMEOUT,
            data=json.dumps(_actor_input(source, url)), allow_redirects=False,
        )
    except requests.RequestException:
        raise GuideImportError("network")
    if response.status_code == 408:
        raise GuideImportError("timeout")
    if response.status_code not in (200, 201):
        raise GuideImportError(f"http_{response.status_code}")
    if len(response.content) > 4 * 1024 * 1024:
        raise GuideImportError("too_large")
    try:
        items = response.json()
    except ValueError:
        raise GuideImportError("bad_json")
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise GuideImportError("empty")
    return items[0]


def _run_one(row) -> None:
    import_id = row["id"]
    db.execute(
        "UPDATE guide_import SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
        (db.utcnow(), import_id),
    )
    _count_run()
    try:
        item = _fetch(row["source"], row["url"])
        data = trim(row["source"], item)
        if len(data) <= 1:
            raise GuideImportError("empty")
        db.execute(
            "UPDATE guide_import SET status = 'done', raw_json = ?, finished_at = ? WHERE id = ?",
            (json.dumps(data, ensure_ascii=False), db.utcnow(), import_id),
        )
        log.info("guide import id=%s source=%s done", import_id, row["source"])
    except GuideImportError as exc:
        db.execute(
            "UPDATE guide_import SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
            (exc.key[:40], db.utcnow(), import_id),
        )
        log.warning("guide import id=%s source=%s failed kind=%s", import_id, row["source"], exc.key)


def process_queue(limit: int = 3) -> int:
    """Run queued imports, oldest first. Called by the worker every minute."""
    if not enabled():
        return 0
    rows = db.query(
        "SELECT id, apartment_id, source, url FROM guide_import WHERE status = 'queued' ORDER BY id LIMIT ?",
        (limit,),
    )
    done = 0
    for row in rows:
        if not global_budget_left():
            db.execute(
                "UPDATE guide_import SET status = 'failed', error = 'budget', finished_at = ? WHERE id = ?",
                (db.utcnow(), row["id"]),
            )
            continue
        _run_one(row)
        done += 1
    return done


# --- retention ----------------------------------------------------------------


def purge(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Raw data gone after RAW_DAYS; failed rows after ROW_DAYS. Other rows stay,
    without data, as the record that the listing was imported (one import for good)."""
    if owner_user_id is not None:
        return 0
    raw_cutoff = (today - timedelta(days=RAW_DAYS)).isoformat()
    row_cutoff = (today - timedelta(days=ROW_DAYS)).isoformat()
    stale = db.query_one(
        "SELECT COUNT(*) AS n FROM guide_import WHERE raw_json IS NOT NULL AND created_at < ?", (raw_cutoff,)
    )
    old = db.query_one(
        "SELECT COUNT(*) AS n FROM guide_import WHERE status = 'failed' AND created_at < ?", (row_cutoff,)
    )
    count = int(stale["n"] if stale else 0) + int(old["n"] if old else 0)
    if not dry_run and count:
        db.execute(
            "UPDATE guide_import SET raw_json = NULL, status = CASE WHEN status = 'done' THEN 'expired' ELSE status END "
            "WHERE raw_json IS NOT NULL AND created_at < ?",
            (raw_cutoff,),
        )
        db.execute("DELETE FROM guide_import WHERE status = 'failed' AND created_at < ?", (row_cutoff,))
    return count
```

Command: `.venv/bin/python -c "from app import guest_guide_import as g; print(g.normalise_url('https://www.airbnb.cz/rooms/123?x=1'))"`. Expected: `{'source': 'airbnb', 'url': 'https://www.airbnb.com/rooms/123'}`.

### Step 4: `App/app/routes/guest_guide.py`

4a. Replace the import anchor line with:

```python
from .. import access, auth, config, guest_guide, guest_guide_import, guide_photos, guide_token, payments, security, templating
```

4b. In `guide_index`, replace the `progress=` / `next_id=` anchor with:

```python
        progress=guest_guide.progress(apartment_id),
        next_id=_next_open(apartment_id, 0),
        import_on=guest_guide_import.enabled(),
        import_left=guest_guide_import.imports_left(apartment_id),
        import_busy=guest_guide_import.in_progress(apartment_id),
        imports=guest_guide_import.imports(apartment_id),
    )
```

4c. Directly above `def _guest_url(apartment_id: int) -> str:` insert (above the `/{item_id}` routes, which would otherwise swallow `/import`):

```python
@router.post("/apartments/{apartment_id}/guide/import")
async def guide_import(request: Request, apartment_id: int):
    """Queue one Booking or Airbnb import (brief 0347). Must stay above the {item_id} routes."""
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    try:
        guest_guide_import.request_import(apartment_id, str(form.get("url", ""))[:guest_guide_import.MAX_URL_LENGTH])
    except guest_guide_import.GuideImportError as exc:
        return back(f"{_base(apartment_id)}#import", err=flash(request, exc.key))
    return back(f"{_base(apartment_id)}#import", msg=flash(request, "flash.guest_guide.import_queued"))


```

Command: `.venv/bin/python -c "from app.main import app; print([r.path for r in app.routes if r.path.endswith('/guide/import')])"`. Expected: `['/apartments/{apartment_id}/guide/import']`.

### Step 5: `App/app/templates/guest_guide.html`

Directly above the `add-card` section anchor insert (the button stays `secondary`; the one primary is "Continue"):

```jinja
{% call ui_section(t('guest_guide.import.title'), id='import') %}
{% if not import_on %}
<p class="ui-sub">{{ t('guest_guide.import.off') }}</p>
{% else %}
{% if import_busy %}{{ ui_banner('neutral', t('guest_guide.import.running')) }}{% endif %}
<p class="ui-sub">{{ t('guest_guide.import.help') }} {{ t('guest_guide.import.left', n=import_left) }}</p>
{% if import_left > 0 and not import_busy %}
<form method="post" action="{{ base_url }}/import">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{{ ui_field('guide-import-url', t('guest_guide.import.url'), name='url', type='url', placeholder='https://www.airbnb.com/rooms/...', attrs='maxlength="2048" required inputmode="url" autocomplete="off"') }}
<div class="ui-form-actions">{{ ui_button(t('guest_guide.import.button'), 'secondary', type='submit', icon_name='download') }}</div>
</form>
{% endif %}
{% if imports %}
{{ ui_table_begin([(t('guest_guide.import.col.source'), ''), (t('guest_guide.import.col.state'), '')], label=t('guest_guide.import.title')) }}
{% for row in imports %}
<tr class="ui-row">
  <td class="ui-cell-first" data-card="primary">{{ t('guest_guide.import.source.' ~ row.source) }}<span class="ui-sub"> {{ row.created_at[:10] }}</span></td>
  <td data-card="badge">{% if row.status in ('queued', 'running') %}{{ ui_badge('action', t('guest_guide.import.state.running')) }}{% elif row.status == 'failed' %}{{ ui_badge('attention', t('guest_guide.import.state.failed')) }}{% else %}{{ ui_badge('done', t('guest_guide.import.state.done')) }}{% endif %}</td>
</tr>
{% endfor %}
{{ ui_table_end() }}
{% endif %}
{% endif %}
{% endcall %}

```

Command (repo root): `python3 scripts/design_lint.py | tail -3`. Expected: `design lint: OK`.

### Step 6: `App/app/host_i18n.py`

Directly above the `# 0345: the guide's QR code for the host to print.` anchor insert:

```python
# 0347: Booking and Airbnb listing imports on the guest guide page.
_GUIDE_IMPORT_STRINGS = {
    "en": {
        "guest_guide.import.title": "Import from Booking or Airbnb",
        "guest_guide.import.help": "Paste the public link of your own listing. We fetch its description, house rules and check-in times and turn them into draft cards for you to check.",
        "guest_guide.import.left": "Imports left for this property: %(n)s. Each listing can be imported once.",
        "guest_guide.import.off": "Imports are not switched on for this UbyHost. You can still fill the cards by hand.",
        "guest_guide.import.running": "Importing. This usually takes a minute. Reload the page to see the result.",
        "guest_guide.import.url": "Listing link",
        "guest_guide.import.button": "Import",
        "guest_guide.import.col.source": "Listing",
        "guest_guide.import.col.state": "State",
        "guest_guide.import.source.booking": "Booking.com",
        "guest_guide.import.source.airbnb": "Airbnb",
        "guest_guide.import.state.running": "Importing",
        "guest_guide.import.state.failed": "Did not work",
        "guest_guide.import.state.done": "Fetched",
        "flash.guest_guide.import_queued": "Import started. It usually takes a minute; reload the page to see the result.",
        "flash.error.guide_import_link": "That does not look like a Booking.com or Airbnb listing link. Open your listing, copy the link from the address bar and paste it here.",
        "flash.error.guide_import_booking_path": "Paste the link of the listing page itself: it starts with https://www.booking.com/hotel/.",
        "flash.error.guide_import_airbnb_path": "Paste the link of the listing page itself: it looks like https://www.airbnb.com/rooms/12345678.",
        "flash.error.guide_import_off": "Imports are not switched on for this UbyHost.",
        "flash.error.guide_import_busy": "An import is already running for this property. Reload the page in a minute.",
        "flash.error.guide_import_limit": "This listing was already imported for this property. Fill in the rest of the cards by hand.",
        "flash.error.guide_import_budget": "Imports are paused for this month. You can fill the cards by hand.",
        "notification.job_name.guide_import": "guest guide imports",
    },
    "cs": {
        "guest_guide.import.title": "Import z Booking nebo Airbnb",
        "guest_guide.import.help": "Vložte veřejný odkaz na svou vlastní nabídku. Stáhneme její popis, pravidla domu a časy příjezdu a připravíme z nich návrhy karet ke kontrole.",
        "guest_guide.import.left": "Zbývající importy pro toto ubytování: %(n)s. Každý inzerát lze naimportovat jednou.",
        "guest_guide.import.off": "Importy nejsou na tomto UbyHostu zapnuté. Karty můžete vyplnit ručně.",
        "guest_guide.import.running": "Importujeme. Obvykle to trvá minutu. Výsledek uvidíte po obnovení stránky.",
        "guest_guide.import.url": "Odkaz na nabídku",
        "guest_guide.import.button": "Importovat",
        "guest_guide.import.col.source": "Nabídka",
        "guest_guide.import.col.state": "Stav",
        "guest_guide.import.source.booking": "Booking.com",
        "guest_guide.import.source.airbnb": "Airbnb",
        "guest_guide.import.state.running": "Importujeme",
        "guest_guide.import.state.failed": "Nepovedlo se",
        "guest_guide.import.state.done": "Staženo",
        "flash.guest_guide.import_queued": "Import běží. Obvykle trvá minutu, výsledek uvidíte po obnovení stránky.",
        "flash.error.guide_import_link": "Tohle nevypadá jako odkaz na nabídku na Booking.com nebo Airbnb. Otevřete svou nabídku, zkopírujte odkaz z adresního řádku a vložte ho sem.",
        "flash.error.guide_import_booking_path": "Vložte odkaz přímo na stránku nabídky: začíná https://www.booking.com/hotel/.",
        "flash.error.guide_import_airbnb_path": "Vložte odkaz přímo na stránku nabídky: vypadá jako https://www.airbnb.com/rooms/12345678.",
        "flash.error.guide_import_off": "Importy nejsou na tomto UbyHostu zapnuté.",
        "flash.error.guide_import_busy": "Pro toto ubytování už jeden import běží. Obnovte stránku za minutu.",
        "flash.error.guide_import_limit": "Tento inzerát už byl pro toto ubytování naimportovaný. Zbytek karet vyplňte ručně.",
        "flash.error.guide_import_budget": "Importy jsou tento měsíc pozastavené. Karty můžete vyplnit ručně.",
        "notification.job_name.guide_import": "importy průvodce pro hosty",
    },
}

for _lang, _strings in _GUIDE_IMPORT_STRINGS.items():
    STRINGS[_lang].update(_strings)

```

Command: `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_flash_literals.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -5`. Expected: 0 failed.

### Step 7: `App/app/scheduler.py`

7a. In the `from . import (` list add `guest_guide_import,` on its own line in alphabetical order (after `filing_watchdog,`).

7b. In `_JOB_LEVELS`, replace the anchor with:

```python
    "stay_fee_mail": "warning",
    "guide_import": "warning",
}
```

7c. In `job_intervals()`, replace `        "push": 1,` with:

```python
        "push": 1,
        "guide_import": 1,
```

7d. Directly above `def _job_push() -> None:` insert:

```python
def _job_guide_import() -> None:
    """Brief 0347: run the queued Booking and Airbnb imports, one actor run each."""
    started = time.perf_counter()
    try:
        ran = guest_guide_import.process_queue()
        if ran:
            log.info("guide import: %s run(s)", ran)
    except Exception:
        log.exception("guide import job failed")
        _job_failed("guide_import")
        _log_run("guide_import", started, False)
        return
    _job_ok("guide_import")
    _log_run("guide_import", started, True, {"runs": ran})


```

7e. Directly after the `_job_push` `add_job` anchor block insert:

```python
    _scheduler.add_job(
        _job_guide_import, "interval", minutes=minutes["guide_import"],
        id="guide_import", max_instances=1, coalesce=True,
    )
```

Command: `.venv/bin/python -m pytest tests/test_scheduler.py tests/test_push.py tests/test_admin_operations.py -q --tb=short -x 2>&1 | tail -5`. Expected: 0 failed.

### Step 8: `App/app/retention.py`

8a. Directly above the `# Each step takes (today, dry_run, owner_user_id)` anchor insert:

```python
def _guide_import_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Brief 0347: imported listing text 7 days after the fetch; the request row after 60."""
    from . import guest_guide_import
    return guest_guide_import.purge(today, dry_run, owner_user_id)


```

8b. Replace `    ("push", _push_step),` with:

```python
    ("push", _push_step),
    ("guide_imports", _guide_import_step),
```

8c. In `_cutoffs`, directly after the `"push": ...` anchor line add:

```python
        "guide_imports": f"listing text fetched before {(today - timedelta(days=7)).isoformat()}, failed request rows before {(today - timedelta(days=60)).isoformat()}",
```

Command: `.venv/bin/python -m pytest tests/test_retention.py tests/test_retention_alignment.py tests/test_retention_job.py -q --tb=short -x 2>&1 | tail -5`. Expected: 0 failed.

### Step 9: docs

9a. `docs/ENVIRONMENT.md`: directly above `## Urgent alerts (web push)` insert:

```markdown
## Guest guide imports (Apify)

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_APIFY_TOKEN` | unset | Apify API token. Unset means imports are off and the guide page says so. Set in Lightsail `.env` or Render Environment only, never in git. |
| `UBYHOST_APIFY_MONTHLY_RUNS` | `40` | Shared monthly cap on Apify actor runs (all hosts). `0` removes the cap. Each run is one listing on Apify's pay-per-result pricing; the cap keeps a month inside the free credit. |
| `UBYHOST_APIFY_TIMEOUT` | `120` | Seconds one actor run may take before Apify stops it. Keep under 300 (Apify's limit for synchronous runs). |

```

9b. `docs/privacy/RETENTION.md`: directly above the row that starts `| Submission envelopes (XML with doc numbers)` insert this row:

```markdown
| Imported listing text (Booking.com, Airbnb: description, house rules, address, check-in times; no guest data) | `guide_import.raw_json` | fetch | deleted when brief 0348 drafts cards, 7 days at the latest; a failed request row 60 days, other request rows kept without the text as the record of the one import | `guest_guide_import.purge` (`retention.py` guide_imports step) | Minimisation |
```

Command (repo root): `python3 scripts/context_lint.py 2>&1 | tail -2`. Expected: `context lint: OK`.

### Step 10: `App/tests/test_guest_guide_import.py` (new)

The file is kept next to this brief so the brief stays under its token cap. From the repo root:

```bash
cp docs/plans/0297-files/test_guest_guide_import.py App/tests/test_guest_guide_import.py
```

It covers: the allowlist (good links rebuilt without tracking; 23 evil links: other hosts, userinfo, `http`, IP literals, ports, lookalikes, short links, traversal, non-ASCII, over-long), queue and count-down, one in flight, the per-property month limit, the global budget, off without a token, foreign property 404, the worker (mocked `requests.post`: endpoint, Bearer header, timeouts, `allow_redirects=False`, input body, trimmed output, `pending_for` and `mark_used`), Booking input and address, the size cap, failure codes with `raw_json` NULL, a network error, the worker stopping at the budget, and retention. No test opens the network.
Command: `.venv/bin/python -m pytest tests/test_guest_guide_import.py tests/test_guest_guide_pages.py -q --tb=short -x 2>&1 | tail -5`. Expected: `51 passed`.

### Step 11: screenshot

Host template changed (rule 7): run the host rows of the test-map (§6) and take one 390 px screenshot of `/apartments/{id}/guide` with `UBYHOST_APIFY_TOKEN` set to any value, showing the import section. Put the path in the report.

## 5. Do not touch

- `App/app/guest_guide.py`, `guide_photos.py`, `guide_token.py`, `routes/guest_guide_view.py`, the guest templates, `i18n.py`: 0341 to 0345 own them.
- No AI call, no card drafting, no `guide_item` write: that is 0348. No polling script or review UX: 0349.
- No scraper of our own, no other HTTP host than `api.apify.com`, no new dependency, no token in a URL or a log.
- Hard rules 2, 3, 4, 5, 6, 8, 9 of AGENTS.md.

## 6. Commands

From `App/`, each ending `-q --tb=short -x 2>&1 | tail -30`:

- `tests/test_guest_guide_import.py tests/test_guest_guide_pages.py` (51 passed)
- `tests/test_migrations.py tests/test_db_*.py`
- `tests/test_retention*.py tests/test_privacy_*.py tests/test_no_tracking.py tests/test_cookie_inventory.py tests/test_pii_encryption.py tests/test_dsr_audit.py tests/test_data_keys.py`
- `tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py`
- `tests/test_scheduler.py tests/test_push.py tests/test_admin_operations.py`
- `tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py` (0 skipped)

Repo root: `python3 scripts/design_lint.py | tail -3`, `python3 scripts/context_lint.py 2>&1 | tail -3`.

## 7. Acceptance

- [ ] The migration file carries the number `context_lint` printed and `tests/test_migrations.py` passes.
- [ ] Every URL in the `test_evil_links_are_refused` list is refused; the three good links are rebuilt without query strings.
- [ ] With `UBYHOST_APIFY_TOKEN` unset the guide page shows the "not switched on" sentence and no link field, and the POST redirects with `err=`.
- [ ] A foreign property's import POST is 404 and writes no row.
- [ ] A second import of the same listing and a second concurrent import are refused with a flash; a failed run does not use the import up; the page shows "Imports left for this property: N."
- [ ] `process_queue` with a mocked `requests.post` calls only `https://api.apify.com/v2/acts/<actor>/run-sync-get-dataset-items` with `Authorization: Bearer`, `timeout=(10, 150)`, `allow_redirects=False`, and stores only the trimmed fields; a failure stores a short code and `raw_json` NULL.
- [ ] `purge` nulls `raw_json` after 7 days and deletes the row after 60; `"guide_imports"` is in `retention.STEPS`.
- [ ] `grep -rn "APIFY_TOKEN" App/app | grep -v config.py` shows only `guest_guide_import.py` (`enabled()` and the header).
- [ ] Every command in §6 ends with 0 failed, 0 skipped on the browser rows; design lint and context lint OK.
- [ ] One 390 px screenshot of the guide page with the import section.

## 8. Stop and ask

Stop and write the report if: an excerpt is not found; a test fails twice; 30 tool calls or about 60k tokens (report as `blocked`, see executor.md); a new dependency seems needed; a file outside §3 or in §5 needs a change; a step is unclear; you need push, merge, secrets, SSH or deploy (hand it to the owner with the exact command).

## 9. Report

Write `docs/tasks/0297-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations (including the migration number used).
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/guest_guide_import.py`: `normalise_url` (the whole SSRF guard), `_fetch` (the one outbound call: constant host, Bearer header, timeouts, size check, no redirects), `trim` (what is kept), `purge`.
- `App/app/routes/guest_guide.py`: `guide_import` sits above the `{item_id}` routes and goes through `_home`.
- `App/app/migrations/MMMM_guide_import.sql`: number and CHECK constraints.
- `App/tests/test_guest_guide_import.py` (copied from `docs/plans/0297-files/`): the evil-URL list; `requests.post` is monkeypatched before every `process_queue`.

Security: ownership (`_home`, `apartment_id` in every SQL), CSRF, input limits. Privacy: no guest data, listing text 7 days, no text in logs. UX: one primary button, cs and en. Design: catalog macros, lint, 390 px screenshot. Function: happy path and each refusal tested. Cost: one per listing per property for good, 40 runs shared, about $0.002 a run.

## Owner steps

Apify account and token (about ten minutes, no card needed):

1. Open apify.com, click "Sign up" (top right), use the UbyHost mailbox and a password from your password manager, confirm the e-mail.
2. In the Apify Console click your profile picture (bottom left), then "Settings", then "API & Integrations" in the left menu.
3. Under "Personal API tokens" click "Create a new token", name it `ubyhost-production`, click "Create". If Apify offers scoped permissions, tick only running actors and reading datasets.
4. Copy the token (starts with `apify_api_`) into your password manager as "Apify UbyHost token". It is not shown again.
5. In Settings open "Billing" and check the plan is "Free" with the monthly credit. Do not add a card; the 40-run cap stays inside the credit.
6. In the Console search box open `voyager/booking-scraper` and `tri_angle/airbnb-rooms-urls-scraper` once each (click "Try for free"); no need to run them.

Server (Lightsail):

7. In a terminal connect with the ssh command you use for deploys, then `cd /opt/ubyhost/deploy/lightsail && nano .env`.
8. At the end of the file add `UBYHOST_APIFY_TOKEN=apify_api_...` (your token, no quotes, no spaces). Press Ctrl+O, Enter, Ctrl+X.
9. Run `./scripts/deploy.sh`; it restarts web and worker with the new `.env`.
10. In UbyHost open a property, "Guest guide". The section "Import from Booking or Airbnb" shows the link field and "Imports left for this property: 2." Paste your own Airbnb link, click "Import", reload after a minute: "Fetched". "Did not work" means tell the orchestrator; the worker log line `guide import id=... failed kind=...` says why (`http_401` is a wrong token).
11. Staging on Render: service `ubyhost-staging`, "Environment", "Add Environment Variable", key `UBYHOST_APIFY_TOKEN`, paste, "Save Changes".
12. After the first month look at Apify "Billing" and tell the orchestrator the amount, so the cap can be adjusted.
