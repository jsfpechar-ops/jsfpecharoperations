# 0817: Booking site iCal export

Status: todo
Depends on: 0815 | Base commit: tip of task/0815-booking-site-checkout | Branch: task/0817-booking-site-ical
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Serve a private calendar feed `/p/<slug>/<token>.ics` with the property's website and manual stays, so Airbnb and Booking.com can import it and block those nights (owner decision 1 Nov; plan `docs/plans/booking-site-v1.md`). The host's copy button is brief 0819.

## 2. Context

- `booking_site.ical_token(apartment_id)` (0814) returns the secret, created on first use.
- Only `source IN ('site', 'manual')` stays are exported: stays imported from Airbnb/Booking (`source = 'ical'`) are never sent back to them (no loops). Cancelled (`status <> 'active'`) and archived (`archived_at IS NOT NULL`) stays are left out; stays that ended more than 30 days ago are left out.
- No personal data in the feed: SUMMARY is a fixed word, no names, no e-mails.
- The feed keeps working after a rename (old slugs live in `property_slug_history`) and while the page is unpublished; it does not check the plan (a downgraded host must not get double bookings).
- Public GET, rate-limited like the page (`rate_limit.client_key`, `blocked`, `record`).

Excerpt `App/app/routes/property_page.py` (verbatim):

```python
@router.get("/p/{slug}/thanks")
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/booking_ical.py` | create | feed builder |
| `App/app/routes/property_page.py` | edit | the route |
| `App/tests/test_booking_ical.py` | create | tests |
| `docs/tasks/0817-report.md` | create | report |

No other file may change.

## 4. Steps

Commit after every step: `git add -A && git commit -qm "0817 step k"`.

**Step 1.** Create `App/app/booking_ical.py`:

```python
"""Booking site iCal export (brief 0817, plan booking-site-v1).

Website and manual stays only, so OTAs block nights sold elsewhere without
their own bookings looping back to them. No personal data in the feed.
"""
from __future__ import annotations

import hmac
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from . import booking_site, db

EXPORT_SOURCES = ("site", "manual")
KEEP_PAST_DAYS = 30


def apartment_for_slug(slug: str) -> Optional[int]:
    """Live or historic slug -> apartment id (feeds survive renames)."""
    row = db.query_one("SELECT apartment_id FROM property_slug WHERE slug = ?", (slug,))
    if row is None:
        row = db.query_one(
            "SELECT apartment_id FROM property_slug_history WHERE old_slug = ?", (slug,)
        )
    return int(row["apartment_id"]) if row else None


def token_ok(apartment_id: int, token: str) -> bool:
    return hmac.compare_digest(booking_site.ical_token(apartment_id), str(token or ""))


def _d(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%Y%m%d")


def export_ics(apartment_id: int, *, today: Optional[date] = None) -> str:
    today = today or date.today()
    since = (today - timedelta(days=KEEP_PAST_DAYS)).isoformat()
    rows = db.query(
        "SELECT id, date_from, date_to FROM reservation"
        " WHERE apartment_id = ? AND status = 'active' AND archived_at IS NULL"
        " AND source IN ('site', 'manual') AND date_to >= ?"
        " ORDER BY date_from, id",
        (apartment_id, since),
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UbyHost//Booking site//CS",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for row in rows:
        lines += [
            "BEGIN:VEVENT",
            f"UID:ubyhost-{row['id']}@ubyhost.cz",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{_d(row['date_from'])}",
            f"DTEND;VALUE=DATE:{_d(row['date_to'])}",
            "SUMMARY:Reserved",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
```

Run: `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_ical.py 2>&1 | tail -3` → `All checks passed!`

**Step 2.** In `App/app/routes/property_page.py`, insert directly above the excerpt line `@router.get("/p/{slug}/thanks")`:

```python
@router.get("/p/{slug}/{token}.ics")
def property_page_ical(request: Request, slug: str, token: str):
    """0817: private calendar feed for Airbnb / Booking.com import."""
    from .. import booking_ical

    scope = "property_page_ical"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _RATE_MAX, _RATE_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    apartment_id = booking_ical.apartment_for_slug(slug)
    if apartment_id is None or not booking_ical.token_ok(apartment_id, token):
        return Response(status_code=404)
    return Response(
        booking_ical.export_ics(apartment_id).encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "private, max-age=300", "X-Robots-Tag": "noindex"},
    )


```

Run: `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/routes/property_page.py 2>&1 | tail -3` → `All checks passed!`

**Step 3.** Create `App/tests/test_booking_ical.py`:

```python
"""Brief 0817: booking site iCal export."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_ical, booking_site, db, property_page
from app.main import app

OWNER = "icalhost"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def apartment():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Ical Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Ical Flat",
                                      "created_at": db.utcnow()}))
    property_page.ensure_slug(aid)
    try:
        yield aid
    finally:
        _cleanup()


def _stay(aid: int, uid: str, source: str, d_from: str, d_to: str, status: str = "active") -> int:
    return int(db.insert("reservation", {
        "apartment_id": aid, "source": source, "uid": uid, "date_from": d_from,
        "date_to": d_to, "summary": "Jana Nová", "guest_email": "jana@example.test",
        "status": status, "created_at": db.utcnow(), "updated_at": db.utcnow(),
    }))


def test_export_has_site_and_manual_only(apartment):
    site = _stay(apartment, "site-1", "site", "2027-05-01", "2027-05-03")
    _stay(apartment, "m-1", "manual", "2027-05-05", "2027-05-06")
    _stay(apartment, "abnb-1", "ical", "2027-05-10", "2027-05-12")
    _stay(apartment, "c-1", "site", "2027-05-20", "2027-05-22", status="cancelled")
    _stay(apartment, "old-1", "manual", "2027-01-01", "2027-01-02")
    body = booking_ical.export_ics(apartment, today=date(2027, 4, 1))
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert body.count("BEGIN:VEVENT") == 2
    assert f"UID:ubyhost-{site}@ubyhost.cz" in body
    assert "DTSTART;VALUE=DATE:20270501" in body and "DTEND;VALUE=DATE:20270503" in body
    assert "Jana" not in body and "@example.test" not in body


def test_route_needs_the_token(apartment):
    _stay(apartment, "site-2", "site", "2027-06-01", "2027-06-04")
    slug = property_page.account_row(apartment)["slug"]
    token = booking_site.ical_token(apartment)
    client = TestClient(app)
    ok = client.get(f"/p/{slug}/{token}.ics")
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("text/calendar")
    assert "DTSTART;VALUE=DATE:20270601" in ok.text
    assert client.get(f"/p/{slug}/wrong-token.ics").status_code == 404
    assert client.get(f"/p/no-such-slug/{token}.ics").status_code == 404


def test_feed_survives_rename(apartment):
    slug = property_page.account_row(apartment)["slug"]
    token = booking_site.ical_token(apartment)
    db.insert("property_slug_history", {"old_slug": "old-name-abcd", "apartment_id": apartment,
                                         "created_at": db.utcnow()})
    client = TestClient(app)
    assert client.get(f"/p/old-name-abcd/{token}.ics").status_code == 200
    assert client.get(f"/p/{slug}/{token}.ics").status_code == 200
```

Run: `cd App && .venv/bin/python -m pytest tests/test_booking_ical.py -q --tb=short -x 2>&1 | tail -15` → 3 passed. If `property_page.ensure_slug` needs a different call shape, read its signature in `App/app/property_page.py` (one grep) and adapt only the fixture line; list it under Deviations.

## 5. Do not touch

`booking_site.py`, `booking_checkout.py`, `booking_webhook.py`, `icalsync.py`, templates, `db.py`, migrations. Hard rules 2, 3, 5, 8.

## 6. Commands

From `App/`:

```
.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -3
.venv/bin/python -m pytest tests/test_booking_site.py tests/test_booking_ical.py tests/test_booking_checkout.py tests/test_property_page.py tests/test_property_slug.py -q --tb=short -x 2>&1 | tail -30
```

## 7. Acceptance

- [ ] The §6 run passes.
- [ ] `git diff --stat task/0815-booking-site-checkout` lists only the §3 files.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0817-report.md` (600 tokens at most) and set `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/booking_ical.py` (SQL filter, no personal data), the route (token check before any data).

## Owner steps

1. Merge after 0815 when CI is green; deploy. The host-facing copy button and where-to-paste help come in 0819.
