# 0814: Booking site data and rules

Status: todo
Depends on: none | Base commit: 47a5dbe | Branch: task/0814-booking-site-model
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the `site_booking` table and one backend module, `App/app/booking_site.py`, holding every rule of the booking site: per-property settings, the Max-plan gate, the price quote, the refund rule and booking rows. No routes and no templates change; briefs 0815 to 0821 build on this (plan: `docs/plans/booking-site-v1.md`).

## 2. Context

- Rules: SQL only through `App/app/db.py` helpers. Production runs PostgreSQL. `App/app/migrations/` (SQLite) gets the next file `0034_site_booking.sql`, and `App/migrations_pg/` gets the matching goose file `00004_site_booking.sql` (docs/context/rules.md#database). `scripts/pg_schema.py apply` runs the SQLite file rendered for PostgreSQL first, then the goose file, so the goose file must use `IF NOT EXISTS` everywhere.
- Settings are JSON in the `settings` table through `db.get_setting(key)` / `db.set_setting(key, value)`, same as `App/app/payment_services.py` (0762).
- `App/app/billing.py`: `enabled()` returns `bool(config.BILLING_ENABLED)`; `entitlements(owner_user_id).plan` is `"standard"` or `"max"`.

Excerpt `App/app/property_page.py` (end of file, must be found verbatim):

```python
    row = db.query_one(
        "SELECT a.owner_user_id FROM apartment a WHERE a.id = ?", (apartment_id,)
    )
    if row is None or nightly_price(apartment_id) is None:
        return False
    account = stripe_connect.account_for_owner(int(row["owner_user_id"]))
```

Excerpt `App/app/retention.py`:

```python
# 0421: stripe_account holds no personal data beyond the owner reference; it
```

Excerpt `App/tests/test_db_postgres.py` (two places):

```python
    assert db.query_one("SELECT COUNT(*) AS n FROM schema_migrations")["n"] == 33
```

```python
    assert payload["tables"]["schema_migrations"]["rows"] == 33
```

Excerpt `docs/context/test-map.md`:

```
| Page booking widget | `test_booking_widget.py test_property_page.py test_stripe_connect.py test_payment_request_model.py` |
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0034_site_booking.sql` | create | SQLite table |
| `App/migrations_pg/00004_site_booking.sql` | create | goose twin |
| `App/app/booking_site.py` | create | rules module |
| `App/app/property_page.py` | edit | Max gate in `widget_ready` |
| `App/app/retention.py` | edit | one comment block |
| `App/tests/test_booking_site.py` | create | tests |
| `App/tests/test_db_postgres.py` | edit | 33 -> 34 in two asserts |
| `docs/context/test-map.md` | edit | new row |
| `docs/tasks/0814-report.md` | create | report |

No other file may change.

## 4. Steps

Commit after every step: `git add -A && git commit -qm "0814 step k"`.

**Step 1.** Create `App/app/migrations/0034_site_booking.sql`:

```sql
-- Brief 0814: booking site v1 (plan booking-site-v1). One row per guest
-- booking made on /p/<slug>; the reservation row is created only when the
-- payment arrives (0816). guest_name / guest_email: see retention.py (0814).
CREATE TABLE IF NOT EXISTS site_booking (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id             INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    owner_user_id            INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    reservation_id           INTEGER REFERENCES reservation(id) ON DELETE SET NULL,
    hold_id                  INTEGER,
    status                   TEXT NOT NULL DEFAULT 'pending',
    date_from                TEXT NOT NULL,
    date_to                  TEXT NOT NULL,
    guests                   INTEGER NOT NULL,
    guest_name               TEXT,
    guest_email              TEXT,
    lang                     TEXT NOT NULL DEFAULT 'cs',
    nights                   INTEGER NOT NULL,
    nightly_czk              INTEGER NOT NULL,
    cleaning_fee_czk         INTEGER NOT NULL DEFAULT 0,
    total_czk                INTEGER NOT NULL,
    refunded_czk             INTEGER NOT NULL DEFAULT 0,
    cancellation_policy      TEXT NOT NULL,
    terms_version            TEXT NOT NULL,
    terms_accepted_at        TEXT,
    stripe_session_id        TEXT UNIQUE,
    stripe_payment_intent_id TEXT,
    cancel_token_hash        TEXT,
    invoice_id               INTEGER REFERENCES invoice(id) ON DELETE SET NULL,
    paid_at                  TEXT,
    cancelled_at             TEXT,
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_site_booking_apartment ON site_booking (apartment_id, date_from);
CREATE INDEX IF NOT EXISTS idx_site_booking_status ON site_booking (status);
```

Run: `cd App && .venv/bin/python -c "from app import db; db.init_db(); print(db.query_one('SELECT COUNT(*) AS n FROM site_booking')['n'])" 2>&1 | tail -3` → `0`.

**Step 2.** Create `App/migrations_pg/00004_site_booking.sql`:

```sql
-- +goose Up
-- Brief 0814: twin of App/app/migrations/0034_site_booking.sql. pg_schema
-- apply runs the SQLite file first, so every statement is IF NOT EXISTS.
CREATE TABLE IF NOT EXISTS site_booking (
    id                       BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    apartment_id             BIGINT NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    owner_user_id            BIGINT NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    reservation_id           BIGINT REFERENCES reservation(id) ON DELETE SET NULL,
    hold_id                  BIGINT,
    status                   TEXT COLLATE "C" NOT NULL DEFAULT 'pending',
    date_from                TEXT COLLATE "C" NOT NULL,
    date_to                  TEXT COLLATE "C" NOT NULL,
    guests                   BIGINT NOT NULL,
    guest_name               TEXT COLLATE "C",
    guest_email              TEXT COLLATE "C",
    lang                     TEXT COLLATE "C" NOT NULL DEFAULT 'cs',
    nights                   BIGINT NOT NULL,
    nightly_czk              BIGINT NOT NULL,
    cleaning_fee_czk         BIGINT NOT NULL DEFAULT 0,
    total_czk                BIGINT NOT NULL,
    refunded_czk             BIGINT NOT NULL DEFAULT 0,
    cancellation_policy      TEXT COLLATE "C" NOT NULL,
    terms_version            TEXT COLLATE "C" NOT NULL,
    terms_accepted_at        TEXT COLLATE "C",
    stripe_session_id        TEXT COLLATE "C" UNIQUE,
    stripe_payment_intent_id TEXT COLLATE "C",
    cancel_token_hash        TEXT COLLATE "C",
    invoice_id               BIGINT REFERENCES invoice(id) ON DELETE SET NULL,
    paid_at                  TEXT COLLATE "C",
    cancelled_at             TEXT COLLATE "C",
    created_at               TEXT COLLATE "C" NOT NULL,
    updated_at               TEXT COLLATE "C" NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_site_booking_apartment ON site_booking (apartment_id, date_from);
CREATE INDEX IF NOT EXISTS idx_site_booking_status ON site_booking (status);

-- +goose Down
DROP TABLE IF EXISTS site_booking;
```

Run: `ls App/migrations_pg | tail -2` → `00003_job.sql`, `00004_site_booking.sql`.

**Step 3.** Create `App/app/booking_site.py` with exactly this content:

```python
"""Booking site v1 rules (brief 0814, plan booking-site-v1).

Everything the public booking flow on /p/<slug> decides lives here: the
host's settings, the Max-plan gate, the price quote, the refund rule and the
site_booking rows. No Stripe calls and no routes: checkout (0815), the
webhook (0816) and iCal (0817) call these functions.

Times are Europe/Prague. Dates are ISO strings like the reservation table.
Money is whole CZK.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from . import db

PRAGUE = ZoneInfo("Europe/Prague")
POLICIES = ("non_refundable", "flexible", "moderate")
NOTICE_DAYS = (0, 1, 2, 3, 7)
STATUSES = ("pending", "paid", "expired", "cancelled", "refunded", "clash_refunded")
MAX_NIGHTS = 30
MAX_PRICE_CZK = 1_000_000
MAX_GUESTS = 60
DEFAULT_CUTOFF_HOUR = 18
DEFAULT_CHECKIN_HOUR = 15
# The guest terms text shown at checkout (0818); bump when the text changes.
TERMS_VERSION = "2026-11-01"

DEFAULTS: Dict[str, Any] = {
    "nightly_price_czk": 0,
    "cleaning_fee_czk": 0,
    "min_nights": 1,
    "max_guests": 0,
    "cancellation_policy": "non_refundable",
    "advance_notice_days": 0,
    "same_day_cutoff_hour": DEFAULT_CUTOFF_HOUR,
    "ical_token": "",
}


def _key(apartment_id: int) -> str:
    return f"booking_site:{int(apartment_id)}"


def _now(now: Optional[datetime]) -> datetime:
    return (now or datetime.now(PRAGUE)).astimezone(PRAGUE)


# --- who may have a booking site -------------------------------------------


def site_allowed(owner_user_id: int) -> bool:
    """Max plan only (owner decision 1 Nov 2026). Billing off = allowed."""
    from . import billing

    if not billing.enabled():
        return True
    return billing.entitlements(int(owner_user_id)).plan == "max"


# --- settings ----------------------------------------------------------------


def settings(apartment_id: int) -> Dict[str, Any]:
    """The host's booking settings with defaults filled in."""
    raw = db.get_setting(_key(apartment_id)) or "{}"
    try:
        stored = json.loads(raw)
    except ValueError:
        stored = {}
    if not isinstance(stored, dict):
        stored = {}
    out = dict(DEFAULTS)
    out.update({k: stored[k] for k in DEFAULTS if k in stored})
    if out["cancellation_policy"] not in POLICIES:
        out["cancellation_policy"] = "non_refundable"
    if out["advance_notice_days"] not in NOTICE_DAYS:
        out["advance_notice_days"] = 0
    if not isinstance(out["same_day_cutoff_hour"], int) or not 0 <= out["same_day_cutoff_hour"] <= 23:
        out["same_day_cutoff_hour"] = DEFAULT_CUTOFF_HOUR
    apartment = db.query_one(
        "SELECT checkin_hour, stay_fee_rate_czk FROM apartment WHERE id = ?",
        (apartment_id,),
    )
    hour = apartment["checkin_hour"] if apartment is not None else None
    out["checkin_hour"] = int(hour) if hour is not None and 0 <= int(hour) <= 23 else DEFAULT_CHECKIN_HOUR
    out["city_tax_czk"] = int(apartment["stay_fee_rate_czk"] or 0) if apartment is not None else 0
    return out


def _whole(value: Any, low: int, high: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(field)
    return value


def save_settings(apartment_id: int, values: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and store. Raises ValueError(<field name>) on a bad value.

    The nightly price is mirrored into property_page.nightly_price_czk so
    the existing widget (0434) and widget_ready() keep reading one source.
    """
    current = settings(apartment_id)
    new = {k: current[k] for k in DEFAULTS}
    for field in ("nightly_price_czk", "cleaning_fee_czk", "min_nights", "max_guests",
                  "cancellation_policy", "advance_notice_days", "same_day_cutoff_hour"):
        if field in values:
            new[field] = values[field]
    _whole(new["nightly_price_czk"], 1, MAX_PRICE_CZK, "nightly_price_czk")
    _whole(new["cleaning_fee_czk"], 0, MAX_PRICE_CZK, "cleaning_fee_czk")
    _whole(new["min_nights"], 1, MAX_NIGHTS, "min_nights")
    _whole(new["max_guests"], 0, MAX_GUESTS, "max_guests")
    _whole(new["same_day_cutoff_hour"], 0, 23, "same_day_cutoff_hour")
    if new["cancellation_policy"] not in POLICIES:
        raise ValueError("cancellation_policy")
    if new["advance_notice_days"] not in NOTICE_DAYS:
        raise ValueError("advance_notice_days")
    db.set_setting(_key(apartment_id), json.dumps(new, sort_keys=True))
    from . import property_page

    property_page.page_for(apartment_id)
    db.execute(
        "UPDATE property_page SET nightly_price_czk = ?, updated_at = ? WHERE apartment_id = ?",
        (new["nightly_price_czk"], db.utcnow(), apartment_id),
    )
    return settings(apartment_id)


def ical_token(apartment_id: int) -> str:
    """The secret in the export URL (0817); created on first use."""
    current = settings(apartment_id)
    if current["ical_token"]:
        return str(current["ical_token"])
    token = secrets.token_urlsafe(18)
    stored = {k: current[k] for k in DEFAULTS}
    stored["ical_token"] = token
    db.set_setting(_key(apartment_id), json.dumps(stored, sort_keys=True))
    return token


# --- quote ---------------------------------------------------------------------


def earliest_check_in(s: Dict[str, Any], now: Optional[datetime] = None) -> date:
    local = _now(now)
    days = int(s["advance_notice_days"])
    if days == 0:
        if local.hour < int(s["same_day_cutoff_hour"]):
            return local.date()
        return local.date() + timedelta(days=1)
    return local.date() + timedelta(days=days)


def quote(apartment_id: int, date_from: str, date_to: str, guests: int,
          *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Price lines for a stay, or {"error": <code>}.

    Error codes (the page maps them to copy): bad_dates, min_nights,
    too_soon, guests, no_price, taken.
    """
    from . import property_page

    s = settings(apartment_id)
    try:
        d_from = date.fromisoformat(str(date_from))
        d_to = date.fromisoformat(str(date_to))
    except ValueError:
        return {"error": "bad_dates"}
    nights = (d_to - d_from).days
    if nights < 1 or nights > MAX_NIGHTS:
        return {"error": "bad_dates"}
    if nights < int(s["min_nights"]):
        return {"error": "min_nights", "min_nights": int(s["min_nights"])}
    if d_from < earliest_check_in(s, now):
        return {"error": "too_soon"}
    if isinstance(guests, bool) or not isinstance(guests, int) or guests < 1:
        return {"error": "guests"}
    if guests > (int(s["max_guests"]) or MAX_GUESTS):
        return {"error": "guests"}
    nightly = int(s["nightly_price_czk"] or 0)
    if nightly < 1:
        return {"error": "no_price"}
    if not property_page.dates_available(apartment_id, d_from.isoformat(), d_to.isoformat()):
        return {"error": "taken"}
    accommodation = nightly * nights
    cleaning = int(s["cleaning_fee_czk"])
    return {
        "error": None,
        "date_from": d_from.isoformat(),
        "date_to": d_to.isoformat(),
        "nights": nights,
        "guests": guests,
        "nightly_czk": nightly,
        "accommodation_czk": accommodation,
        "cleaning_fee_czk": cleaning,
        "total_czk": accommodation + cleaning,
        "city_tax_on_site_czk": int(s["city_tax_czk"]) * guests * nights,
        "cancellation_policy": s["cancellation_policy"],
    }


# --- refunds -------------------------------------------------------------------


def check_in_moment(check_in: str, checkin_hour: int) -> datetime:
    return datetime.combine(date.fromisoformat(check_in), time(int(checkin_hour)), PRAGUE)


def refund_czk(booking: Dict[str, Any], *, checkin_hour: int,
               now: Optional[datetime] = None, by_host: bool = False) -> int:
    """What the guest gets back if the booking is cancelled now.

    Host cancellation (or a double booking) always refunds in full.
    """
    total = int(booking["total_czk"]) - int(booking.get("refunded_czk") or 0)
    if total <= 0:
        return 0
    if by_host:
        return total
    left = check_in_moment(booking["date_from"], checkin_hour) - _now(now)
    policy = booking["cancellation_policy"]
    if policy == "flexible":
        return total if left >= timedelta(hours=24) else 0
    if policy == "moderate":
        if left >= timedelta(days=5):
            return total
        if left > timedelta(0):
            cleaning = int(booking["cleaning_fee_czk"])
            return min(total, cleaning + (int(booking["total_czk"]) - cleaning) // 2)
        return 0
    return 0


# --- booking rows --------------------------------------------------------------


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_pending(apartment_id: int, owner_user_id: int, q: Dict[str, Any], *,
                   guest_name: str, guest_email: str, lang: str,
                   hold_id: Optional[int]) -> Dict[str, Any]:
    """A pending booking from a good quote. Returns the row plus the one-time
    cancel token (only its hash is stored)."""
    if q.get("error"):
        raise ValueError("quote has an error")
    token = secrets.token_urlsafe(24)
    now = db.utcnow()
    booking_id = db.insert("site_booking", {
        "apartment_id": apartment_id,
        "owner_user_id": owner_user_id,
        "hold_id": hold_id,
        "status": "pending",
        "date_from": q["date_from"],
        "date_to": q["date_to"],
        "guests": q["guests"],
        "guest_name": " ".join((guest_name or "").split())[:120] or None,
        "guest_email": (guest_email or "").strip()[:254] or None,
        "lang": lang if lang in ("cs", "en") else "cs",
        "nights": q["nights"],
        "nightly_czk": q["nightly_czk"],
        "cleaning_fee_czk": q["cleaning_fee_czk"],
        "total_czk": q["total_czk"],
        "cancellation_policy": q["cancellation_policy"],
        "terms_version": TERMS_VERSION,
        "terms_accepted_at": now,
        "cancel_token_hash": token_hash(token),
        "created_at": now,
        "updated_at": now,
    })
    row = get(int(booking_id))
    assert row is not None
    row["cancel_token"] = token
    return row


def get(booking_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one("SELECT * FROM site_booking WHERE id = ?", (booking_id,))
    return dict(row) if row else None


def by_session(session_id: str) -> Optional[Dict[str, Any]]:
    row = db.query_one(
        "SELECT * FROM site_booking WHERE stripe_session_id = ?", (session_id,)
    )
    return dict(row) if row else None


_TRANSITIONS = {
    "pending": {"paid", "expired", "clash_refunded"},
    "paid": {"cancelled", "refunded", "clash_refunded"},
    "cancelled": {"refunded"},
    "expired": {"paid", "clash_refunded"},
    "refunded": set(),
    "clash_refunded": set(),
}


def set_status(booking_id: int, status: str, **fields: Any) -> bool:
    """Move a booking; False if it is already there. Raises on an illegal move.

    ``fields`` may set reservation_id, stripe_session_id,
    stripe_payment_intent_id, refunded_czk, invoice_id, paid_at, cancelled_at.
    """
    if status not in STATUSES:
        raise ValueError(status)
    allowed = {"reservation_id", "stripe_session_id", "stripe_payment_intent_id",
               "refunded_czk", "invoice_id", "paid_at", "cancelled_at"}
    if set(fields) - allowed:
        raise ValueError("unknown field")
    row = get(booking_id)
    if row is None:
        raise ValueError("no such booking")
    if row["status"] == status:
        return False
    if status not in _TRANSITIONS[row["status"]]:
        raise ValueError(f"site_booking {booking_id}: {row['status']} -> {status}")
    sets = ", ".join(f"{name} = ?" for name in fields)
    sql = "UPDATE site_booking SET status = ?, updated_at = ?"
    if sets:
        sql += ", " + sets
    sql += " WHERE id = ? AND status = ?"
    params = [status, db.utcnow(), *fields.values(), booking_id, row["status"]]
    return db.execute_rowcount(sql, params) == 1


def attach_session(booking_id: int, session_id: str) -> None:
    db.execute(
        "UPDATE site_booking SET stripe_session_id = ?, updated_at = ? WHERE id = ?",
        (session_id, db.utcnow(), booking_id),
    )
```

Run: `cd App && .venv/bin/ruff check app/booking_site.py 2>&1 | tail -5` → `All checks passed!`

**Step 4.** In `App/app/property_page.py`, replace the excerpt from §2 with:

```python
    row = db.query_one(
        "SELECT a.owner_user_id FROM apartment a WHERE a.id = ?", (apartment_id,)
    )
    if row is None or nightly_price(apartment_id) is None:
        return False
    from . import booking_site

    if not booking_site.site_allowed(int(row["owner_user_id"])):
        return False
    account = stripe_connect.account_for_owner(int(row["owner_user_id"]))
```

Run: `cd App && .venv/bin/python -m pytest tests/test_property_page.py -q --tb=short -x 2>&1 | tail -5` → passes.

**Step 5.** In `App/app/retention.py`, insert these lines directly above the line `# 0421: stripe_account holds no personal data beyond the owner reference; it`:

```python
# 0814: site_booking.guest_name / guest_email are the booker's name and
# address from the booking site. Kept with the booking (the host's money and
# accommodation record; the invoice repeats them); deleted with the apartment
# or the workspace by the foreign-key cascade. Used only for that booking's
# confirmation, invoice and cancellation mails.
```

Run: `cd App && .venv/bin/python -c "import app.retention" 2>&1 | tail -2` → no output.

**Step 6.** In `App/tests/test_db_postgres.py`, change both excerpts' `33` to `34` (only those two lines). Run: `grep -n '== 34' App/tests/test_db_postgres.py | head` → two lines.

**Step 7.** Create `App/tests/test_booking_site.py`:

```python
"""Brief 0814: booking site rules (settings, quote, refunds, rows)."""
from __future__ import annotations

from datetime import datetime

import pytest

from app import auth, booking_site, db, property_page

OWNER = "bookingsitehost"
PRAGUE = booking_site.PRAGUE


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Booking Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    try:
        yield int(oid)
    finally:
        _cleanup()


def _apartment(oid: int) -> int:
    return int(db.insert("apartment", {
        "owner_user_id": oid, "internal_name": "Site Flat", "created_at": db.utcnow(),
        "stay_fee_rate_czk": 50, "checkin_hour": 15,
    }))


NOW = datetime(2026, 11, 2, 12, 0, tzinfo=PRAGUE)


def _priced(aid: int, **extra) -> None:
    values = {"nightly_price_czk": 2000, "cleaning_fee_czk": 500}
    values.update(extra)
    booking_site.save_settings(aid, values)


def test_defaults_and_save(owner):
    aid = _apartment(owner)
    s = booking_site.settings(aid)
    assert s["cancellation_policy"] == "non_refundable"
    assert s["same_day_cutoff_hour"] == 18
    assert s["checkin_hour"] == 15 and s["city_tax_czk"] == 50
    _priced(aid, cancellation_policy="moderate", min_nights=2, max_guests=4)
    s = booking_site.settings(aid)
    assert (s["nightly_price_czk"], s["min_nights"], s["max_guests"]) == (2000, 2, 4)
    assert property_page.nightly_price(aid) == 2000


@pytest.mark.parametrize("field,value", [
    ("nightly_price_czk", 0), ("cleaning_fee_czk", -1), ("min_nights", 31),
    ("max_guests", 61), ("cancellation_policy", "strict"),
    ("advance_notice_days", 5), ("same_day_cutoff_hour", 24),
    ("nightly_price_czk", "2000"), ("min_nights", True),
])
def test_save_rejects_bad_values(owner, field, value):
    aid = _apartment(owner)
    with pytest.raises(ValueError, match=field):
        booking_site.save_settings(aid, {"nightly_price_czk": 1000, field: value})


def test_quote_lines(owner):
    aid = _apartment(owner)
    _priced(aid)
    q = booking_site.quote(aid, "2026-11-10", "2026-11-13", 2, now=NOW)
    assert q["error"] is None
    assert (q["nights"], q["accommodation_czk"], q["total_czk"]) == (3, 6000, 6500)
    assert q["city_tax_on_site_czk"] == 50 * 2 * 3


@pytest.mark.parametrize("dates,guests,code", [
    (("2026-11-10", "2026-11-10"), 2, "bad_dates"),
    (("bad", "2026-11-10"), 2, "bad_dates"),
    (("2026-11-10", "2026-12-15"), 2, "bad_dates"),
    (("2026-11-10", "2026-11-11"), 2, "min_nights"),
    (("2026-11-01", "2026-11-04"), 2, "too_soon"),
    (("2026-11-10", "2026-11-13"), 0, "guests"),
    (("2026-11-10", "2026-11-13"), 5, "guests"),
])
def test_quote_errors(owner, dates, guests, code):
    aid = _apartment(owner)
    _priced(aid, min_nights=2, max_guests=4)
    assert booking_site.quote(aid, dates[0], dates[1], guests, now=NOW)["error"] == code


def test_quote_without_price(owner):
    aid = _apartment(owner)
    assert booking_site.quote(aid, "2026-11-10", "2026-11-13", 2, now=NOW)["error"] == "no_price"


def test_quote_taken_by_reservation(owner):
    aid = _apartment(owner)
    _priced(aid)
    db.insert("reservation", {
        "apartment_id": aid, "source": "manual", "uid": "t-1",
        "date_from": "2026-11-12", "date_to": "2026-11-14", "status": "active",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    assert booking_site.quote(aid, "2026-11-10", "2026-11-13", 2, now=NOW)["error"] == "taken"
    assert booking_site.quote(aid, "2026-11-14", "2026-11-16", 2, now=NOW)["error"] is None


def test_same_day_cutoff_and_notice(owner):
    aid = _apartment(owner)
    _priced(aid)
    s = booking_site.settings(aid)
    assert booking_site.earliest_check_in(s, NOW).isoformat() == "2026-11-02"
    late = datetime(2026, 11, 2, 18, 0, tzinfo=PRAGUE)
    assert booking_site.earliest_check_in(s, late).isoformat() == "2026-11-03"
    _priced(aid, advance_notice_days=3)
    s = booking_site.settings(aid)
    assert booking_site.earliest_check_in(s, NOW).isoformat() == "2026-11-05"


def _booking(policy: str) -> dict:
    return {"total_czk": 6500, "cleaning_fee_czk": 500, "refunded_czk": 0,
            "date_from": "2026-11-10", "cancellation_policy": policy}


@pytest.mark.parametrize("policy,when,expected", [
    ("non_refundable", datetime(2026, 11, 1, 12, 0), 0),
    ("flexible", datetime(2026, 11, 9, 15, 0), 6500),
    ("flexible", datetime(2026, 11, 9, 15, 1), 0),
    ("moderate", datetime(2026, 11, 5, 15, 0), 6500),
    ("moderate", datetime(2026, 11, 8, 12, 0), 500 + 3000),
    ("moderate", datetime(2026, 11, 10, 15, 0), 0),
])
def test_refund_rule(policy, when, expected):
    now = when.replace(tzinfo=PRAGUE)
    assert booking_site.refund_czk(_booking(policy), checkin_hour=15, now=now) == expected


def test_refund_by_host_is_full():
    now = datetime(2026, 11, 10, 20, 0, tzinfo=PRAGUE)
    assert booking_site.refund_czk(_booking("non_refundable"), checkin_hour=15,
                                   now=now, by_host=True) == 6500


def test_booking_rows_and_transitions(owner):
    aid = _apartment(owner)
    _priced(aid)
    q = booking_site.quote(aid, "2026-11-10", "2026-11-13", 2, now=NOW)
    row = booking_site.create_pending(aid, owner, q, guest_name="  Jana   Nová ",
                                      guest_email="jana@example.test", lang="cs", hold_id=None)
    assert row["status"] == "pending" and row["guest_name"] == "Jana Nová"
    assert row["cancel_token_hash"] == booking_site.token_hash(row["cancel_token"])
    booking_site.attach_session(row["id"], "cs_test_1")
    assert booking_site.by_session("cs_test_1")["id"] == row["id"]
    assert booking_site.set_status(row["id"], "paid", paid_at=db.utcnow()) is True
    assert booking_site.set_status(row["id"], "paid") is False
    with pytest.raises(ValueError):
        booking_site.set_status(row["id"], "pending")
    assert booking_site.set_status(row["id"], "cancelled", refunded_czk=0) is True


def test_ical_token_is_stable(owner):
    aid = _apartment(owner)
    token = booking_site.ical_token(aid)
    assert len(token) >= 20 and booking_site.ical_token(aid) == token


def test_site_allowed_follows_plan(owner, monkeypatch):
    from app import billing, config

    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    assert booking_site.site_allowed(owner) is True
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(billing, "entitlements",
                        lambda oid: billing.Entitlements(status="active", plan="standard"))
    assert booking_site.site_allowed(owner) is False
    monkeypatch.setattr(billing, "entitlements",
                        lambda oid: billing.Entitlements(status="active", plan="max"))
    assert booking_site.site_allowed(owner) is True
```

Run: `cd App && .venv/bin/python -m pytest tests/test_booking_site.py -q --tb=short -x 2>&1 | tail -15` → all pass.

**Step 8.** In `docs/context/test-map.md`, insert this row directly below the "Page booking widget" excerpt line:

```
| Booking site (rules, checkout, webhook, iCal) | `test_booking_site.py test_property_page.py test_stripe_connect.py` |
```

Run: `python3 scripts/context_lint.py 2>&1 | tail -3` → ends with `context lint: OK`.

## 5. Do not touch

`App/app/db.py`, `App/app/migrations/0001`-`0033`, `App/migrations_pg/00001`-`00003`, every route and template, `stripe_connect.py`, `payment_links.py`. Hard rules 3, 4 (no new dependency: `zoneinfo` is stdlib), 5, 8.

## 6. Commands

From `App/`:

```
.venv/bin/ruff check app/booking_site.py tests/test_booking_site.py 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_booking_site.py tests/test_property_page.py tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -30
```

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3`.

`test_db_postgres.py` needs PostgreSQL; do not run it locally (CI job `test-postgres` runs it).

## 7. Acceptance

- [ ] `site_booking` exists on a fresh SQLite database (step 1 command prints `0`).
- [ ] `App/migrations_pg/00004_site_booking.sql` exists with `-- +goose Up` and `-- +goose Down`.
- [ ] The §6 test run passes with no failures.
- [ ] `git diff --stat origin/main` lists only the §3 files.
- [ ] context lint OK.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0814-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Do not push; the orchestrator pushes and opens the PR.

## Risk list (for the reviewer)

`App/migrations_pg/00004_site_booking.sql` (must match 0034 column for column), `App/app/booking_site.py` (`refund_czk`, `set_status`), `App/app/property_page.py`.

## Owner steps

1. Merge the PR when CI is green (both `test-postgres` jobs included).
2. Deploy as usual. The deploy script applies the new database step (goose 00004) by itself; nothing to click.
