"""Write go/internal/web/booking/testdata/golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/booking_site_golden.py

Brief 1351. It seeds a throwaway SQLite database with the rows in SEED and
records, with a fixed clock (NOW), what the Python booking site computes:
settings, quotes, refund amounts, manage tokens and URLs, slug resolution,
month grids, pay rails, iCal feeds and the stay calendar.
go/internal/web/booking/golden_test.go seeds PostgreSQL from the same file
and compares every case. App/tests/test_go_booking_golden.py fails when this
file is stale.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "booking" / "testdata" / "golden.json"

SECRET = "golden-secret-key-not-for-real-use-1351"
PUBLIC_BASE = "https://book.example.test/"
STRIPE_MODE = "test"
STAMP = "2026-11-01T00:00:00+00:00"
NOW = "2026-11-28T10:00:00+00:00"       # Prague 11:00, before the 18:00 cutoff
NOW_LATE = "2026-11-28T17:30:00+00:00"  # Prague 18:30, after the cutoff
NAME_1 = "Flat, Old; Town\\A\nB"


def _settings(**values) -> str:
    return json.dumps(values, sort_keys=True)


SEED = [
    {"table": "user_account", "columns": ["id", "username", "password_hash", "role", "created_at"],
     "rows": [[1, "h1@example.test", "x", "host", STAMP], [2, "h2@example.test", "x", "host", STAMP],
              [3, "h3@example.test", "x", "host", STAMP]]},
    {"table": "legal_entity", "columns": ["id", "name", "iban", "bank_account", "created_at"],
     "rows": [[1, "Host One", "CZ6508000000192000145399", None, STAMP],
              [2, "Host Two", None, "123456789/0800", STAMP],
              [3, "Host Three", "   ", None, STAMP]]},
    {"table": "apartment",
     "columns": ["id", "owner_user_id", "legal_entity_id", "internal_name", "checkin_hour",
                 "stay_fee_rate_czk", "stay_fee_guest_rails", "stay_fee_guest_revolut_link",
                 "stay_fee_guest_cash_note", "stay_fee_guest_default_rail", "created_at"],
     "rows": [
         # 1: full settings, every rail works, city tax 50.
         [1, 1, 1, NAME_1, 15, 50, "iban,revolut,cash", "https://revolut.me/host1", "At the desk", "", STAMP],
         # 2: no settings row (price from property_page), legacy qr rail, account number only.
         [2, 2, 2, "Garden", None, 0, "qr", None, None, "qr", STAMP],
         # 3: settings not JSON, no price, bad Revolut link, check-in hour out of range.
         [3, 3, None, "Draft", 25, 0, "revolut", "http://revolut.me/x", None, "", STAMP],
         # 4: bad settings values fall back to defaults; cash only.
         [4, 1, None, "River", 10, 20, "cash", None, None, "", STAMP],
         # 5: settings is a JSON list; no rails.
         [5, 2, None, "Five", 15, 0, "", None, None, "", STAMP],
         # 6: seven days notice, blank IBAN.
         [6, 3, 3, "Six", 16, 0, "iban", None, None, "", STAMP],
         # 7: only a history slug, no live slug.
         [7, 1, None, "Seven", 15, 0, "", None, None, "", STAMP],
     ]},
    {"table": "property_slug", "columns": ["id", "apartment_id", "slug", "published", "created_at", "updated_at"],
     "rows": [[11, 1, "old-town", 1, STAMP, STAMP], [12, 2, "garden", 1, STAMP, STAMP],
              [13, 3, "draft", 0, STAMP, STAMP], [14, 4, "river", 1, STAMP, STAMP],
              [16, 6, "six", 1, STAMP, STAMP]]},
    {"table": "property_slug_history", "columns": ["old_slug", "apartment_id", "created_at"],
     "rows": [["old-town-2025", 1, STAMP], ["river-old", 4, STAMP], ["gone-old", 7, STAMP]]},
    {"table": "property_page", "columns": ["id", "apartment_id", "nightly_price_czk", "created_at", "updated_at"],
     "rows": [[21, 1, 1800, STAMP, STAMP], [22, 2, 1500, STAMP, STAMP], [23, 3, None, STAMP, STAMP]]},
    {"table": "settings", "columns": ["key", "value"],
     "rows": [
         ["booking_site:1", _settings(nightly_price_czk=2000, cleaning_fee_czk=500, min_nights=2, max_guests=4,
                                      cancellation_policy="moderate", advance_notice_days=0,
                                      same_day_cutoff_hour=18, ical_token="tok-apt-1")],
         ["booking_site:3", "not json"],
         ["booking_site:4", _settings(cancellation_policy="weird", advance_notice_days=5,
                                      same_day_cutoff_hour=30, nightly_price_czk=900)],
         ["booking_site:5", "[1]"],
         ["booking_site:6", '{"nightly_price_czk": 1000, "advance_notice_days": 7.0, '
                            '"cancellation_policy": "flexible", "same_day_cutoff_hour": 18.0, "min_nights": 1}'],
     ]},
    {"table": "reservation",
     "columns": ["id", "apartment_id", "source", "uid", "date_from", "date_to", "status", "archived_at",
                 "created_at", "updated_at"],
     "rows": [
         [101, 1, "site", "r101", "2026-12-10", "2026-12-13", "active", None, STAMP, STAMP],
         [102, 1, "manual", "r102", "2026-12-20", "2026-12-22", "cancelled", None, STAMP, STAMP],
         [103, 1, "ical", "r103", "2027-01-05", "2027-01-08", "active", None, STAMP, STAMP],
         [104, 1, "manual", "r104", "2027-01-10", "2027-01-12", "active", STAMP, STAMP, STAMP],
         [105, 1, "manual", "r105", "2026-10-01", "2026-10-20", "active", None, STAMP, STAMP],
         [106, 1, "manual", "r106", "2026-10-25", "2026-11-02", "active", None, STAMP, STAMP],
         [107, 1, "site", "r107", "2026-12-31", "2027-01-02", "active", None, STAMP, STAMP],
         [201, 2, "site", "r201", "2026-12-05", "2026-12-07", "active", None, STAMP, STAMP],
     ]},
    {"table": "booking_hold", "columns": ["id", "apartment_id", "date_from", "date_to", "expires_at", "created_at"],
     "rows": [[301, 1, "2026-12-15", "2026-12-17", "2026-11-28T10:15:00+00:00", STAMP],
              [302, 1, "2026-12-18", "2026-12-19", "2026-11-28T09:59:59+00:00", STAMP],
              [303, 1, "2026-12-19", "2026-12-20", NOW, STAMP]]},
    {"table": "stripe_account",
     "columns": ["id", "owner_user_id", "stripe_account_id", "mode", "onboarding_state", "created_at", "updated_at"],
     "rows": [[31, 1, "acct_one", "test", "complete", STAMP, STAMP],
              [32, 2, "acct_two", "live", "complete", STAMP, STAMP],
              [33, 3, "acct_three", "test", "pending", STAMP, STAMP]]},
    {"table": "site_booking",
     "columns": ["id", "apartment_id", "owner_user_id", "status", "date_from", "date_to", "guests", "lang", "nights",
                 "nightly_czk", "cleaning_fee_czk", "total_czk", "cancellation_policy", "terms_version",
                 "created_at", "updated_at"],
     "rows": [[501, 1, 1, "paid", "2026-12-10", "2026-12-13", 2, "cs", 3, 2000, 500, 6500, "moderate",
               "2026-11-03", STAMP, STAMP],
              [502, 1, 1, "cancelled", "2026-12-20", "2026-12-22", 2, "en", 2, 2000, 500, 4500, "moderate",
               "2026-11-03", STAMP, STAMP],
              [503, 1, 1, "pending", "2027-02-01", "2027-02-03", 1, "cs", 2, 2000, 500, 4500, "moderate",
               "2026-11-03", STAMP, STAMP]]},
]

APARTMENTS = [1, 2, 3, 4, 5, 6, 7, 99]

# (apartment, date_from, date_to, guests, now)
QUOTES = [
    (1, "2026-12-01", "2026-12-04", 2, NOW), (1, "2026-12-01", "2026-12-02", 2, NOW),
    (1, "2026-02-30", "2026-03-02", 2, NOW), (1, "", "2026-12-04", 2, NOW), (1, "garbage", "x", 2, NOW),
    (1, "2026-12-04", "2026-12-01", 2, NOW), (1, "2026-12-01", "2026-12-01", 2, NOW),
    (1, "2027-02-01", "2027-03-04", 2, NOW), (1, "2027-02-01", "2027-03-03", 2, NOW),
    (1, "2026-11-27", "2026-11-30", 2, NOW), (1, "2026-11-28", "2026-11-30", 2, NOW),
    (1, "2026-11-28", "2026-11-30", 2, NOW_LATE), (1, "2026-11-29", "2026-12-01", 2, NOW_LATE),
    (1, "2026-12-01", "2026-12-04", 0, NOW), (1, "2026-12-01", "2026-12-04", 5, NOW),
    (1, "2026-12-01", "2026-12-04", 4, NOW), (1, "2026-12-01", "2026-12-04", -1, NOW),
    (1, "2026-12-11", "2026-12-14", 2, NOW), (1, "2026-12-13", "2026-12-15", 2, NOW),
    (1, "2026-12-14", "2026-12-16", 2, NOW), (1, "2026-12-18", "2026-12-20", 2, NOW),
    (1, "2026-12-20", "2026-12-22", 2, NOW), (1, "20261201", "20261204", 2, NOW),
    (1, "2026-W49-2", "2026-W49-5", 2, NOW), (1, "2026120199", "2026-12-04", 2, NOW),
    (1, "2027-01-05", "2027-01-07", 2, NOW), (1, "2027-01-10", "2027-01-12", 1, NOW),
    (1, "2027-02-01", "2027-02-03", 3, NOW),
    (2, "2026-12-01", "2026-12-02", 60, NOW), (2, "2026-12-01", "2026-12-02", 61, NOW),
    (2, "2026-12-06", "2026-12-08", 1, NOW), (2, "2026-12-07", "2026-12-09", 1, NOW),
    (3, "2026-12-01", "2026-12-03", 1, NOW), (4, "2026-11-28", "2026-11-29", 1, NOW),
    (4, "2026-11-28", "2026-11-29", 1, NOW_LATE),
    (6, "2026-12-04", "2026-12-05", 1, NOW), (6, "2026-12-05", "2026-12-06", 1, NOW),
    (99, "2026-12-05", "2026-12-06", 1, NOW),
]

_BASE = {"total_czk": 6500, "refunded_czk": 0, "cleaning_fee_czk": 500, "date_from": "2026-12-10"}
_NOWS = ["2026-12-04T09:00:00+01:00", "2026-12-05T15:00:00+01:00", "2026-12-05T15:00:01+01:00",
         "2026-12-09T15:00:00+01:00", "2026-12-09T14:00:00+00:00", "2026-12-09T15:00:01+01:00",
         "2026-12-10T14:59:59+01:00", "2026-12-10T15:00:00+01:00", "2026-12-11T00:00:00+01:00"]


def _refund_cases() -> list:
    cases = []
    for policy in ("flexible", "moderate", "non_refundable", "weird"):
        for now in _NOWS:
            cases.append((dict(_BASE, cancellation_policy=policy), 15, now, False))
    m = dict(_BASE, cancellation_policy="moderate")
    late = "2026-12-08T12:00:00+01:00"
    cases += [
        (dict(m, refunded_czk=4000), 15, late, False), (dict(m, refunded_czk=6500), 15, late, False),
        (dict(m, refunded_czk=7000), 15, late, False), (dict(m, total_czk=6501), 15, late, False),
        (dict(m, cleaning_fee_czk=0), 15, late, False), (dict(m, cleaning_fee_czk=0, total_czk=1), 15, late, False),
        (dict(_BASE, cancellation_policy="non_refundable"), 15, late, True),
        (dict(m, refunded_czk=6500), 15, late, True), (dict(m, refunded_czk=1000), 15, late, True),
        (dict(_BASE, cancellation_policy="flexible"), 0, "2026-12-09T00:00:00+01:00", False),
        (dict(_BASE, cancellation_policy="flexible"), 23, "2026-12-09T23:30:00+01:00", False),
        # DST: Python subtracts Prague wall clocks, so a 23 h real gap reads as 24 h.
        (dict(_BASE, cancellation_policy="flexible", date_from="2027-03-28"), 15, "2027-03-27T15:00:00+01:00", False),
        (dict(_BASE, cancellation_policy="moderate", date_from="2027-04-01"), 15, "2027-03-27T15:00:00+01:00", False),
        (dict(_BASE, cancellation_policy="flexible", date_from="2026-10-25"), 15, "2026-10-24T15:30:00+02:00", False),
        (dict(_BASE, cancellation_policy="flexible", date_from="2026-10-26"), 15, "2026-10-25T15:00:00+01:00", False),
    ]
    return cases


# (apartment, year, month, date_from, date_to, now)
MONTHS = [
    (1, 2026, 12, "", "", NOW), (1, 2026, 12, "2026-12-13", "", NOW),
    (1, 2026, 12, "2026-12-01", "2026-12-04", NOW), (1, 2026, 12, "2026-12-04", "2026-12-01", NOW),
    (1, 2026, 11, "", "", NOW), (1, 2027, 10, "", "", NOW), (1, 2027, 11, "", "", NOW),
    (1, 2026, 12, " 2026-12-20 ", "bad", NOW_LATE), (1, 2027, 1, "2026-12-30", "", NOW),
    (1, 2026, 10, "", "", NOW), (6, 2026, 12, "", "", NOW), (99, 2026, 12, "", "", NOW),
    (1, 2027, 2, "2027-02-01", "2027-02-03", NOW),
]

REVOLUT_LINKS = ["https://revolut.me/host", "https://REVOLUT.ME/x", "https://pay.revolut.com/x",
                 "http://revolut.me/x", "https://revolut.me.evil.test/x", "https://evilrevolut.me/x",
                 "https://user@revolut.me/x", "https://@revolut.me/x", "https://:pw@revolut.me/x",
                 "https://revolut.me:443/x", "https://revolut.me:444/x", "https://revolut.me:0443/x",
                 "https://revolut.me:99999/x", "https://revolut.me:abc/x", "  https://revolut.me/x  ",
                 "https://revo\tlut.me/x", "", "revolut.me/x", "HTTPS://revolut.com"]

PARSE_DATES = ["2026-12-01", "20261201", "2026-W49-1", "2026W491", "2026-W49", "2026W49", "2026-12-1",
               "+2026-12-01", " 2026-12-01", "2026-12-01T00", "2026-02-30", "2026120199", "2026W49123",
               "2026-W4911", "2026-W53", "2020-W53", "2025-W53", "2026-W00", "2026W497", "2026W498",
               "0000-01-01", "2026-12-0x", "99991231", "2026-W01-1", "2026x12x01", "2026-1201xx",
               "202612-01x", "2026W01", "", "2024-02-29", "2023-02-29", "2026-13-01"]

SLUGS = ["old-town", "old-town-2025", "draft", "nope", "gone-old", "river-old", "garden", "river"]


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        moment = datetime.fromisoformat(NOW)
        return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _resolved(value) -> dict:
    if value is None:
        return {"kind": "none"}
    if "redirect" in value:
        return {"kind": "redirect", "redirect": value["redirect"]}
    if value.get("missing"):
        return {"kind": "missing", "apartment_id": int(value["apartment_id"])}
    return {"kind": "live", "apartment_id": int(value["apartment_id"])}


def _grid(g: dict) -> dict:
    return {
        "year": g["year"], "month": g["month"],
        "weeks": [[dict(c, pick=list(c["pick"]) if c["pick"] else None) for c in week] for week in g["weeks"]],
        "prev": list(g["prev"]) if g["prev"] else None,
        "next": list(g["next"]) if g["next"] else None,
    }


def render() -> str:
    """Seed a fresh database, run every case, and return the golden JSON text."""
    from app import (booking_calendar, booking_ical, booking_manage, booking_rails, booking_site, db,
                     property_page)
    from app import config

    db.init_db()
    _seed(db)
    prague = booking_site.PRAGUE
    fixed = datetime.fromisoformat(NOW)
    saved = (db.utcnow, booking_site._now, booking_ical.datetime, booking_manage.datetime,
             config.PUBLIC_BASE_URL, config.STRIPE_MODE, config._SECRET_KEY)
    config._SECRET_KEY = SECRET
    db.utcnow = lambda: NOW
    booking_site._now = lambda now: (now or fixed).astimezone(prague)
    booking_ical.datetime = _FixedDatetime
    booking_manage.datetime = _FixedDatetime
    config.PUBLIC_BASE_URL = PUBLIC_BASE.rstrip("/")
    config.STRIPE_MODE = STRIPE_MODE
    try:
        out = {
            "secret": SECRET, "public_base": PUBLIC_BASE, "stripe_mode": STRIPE_MODE, "now": NOW,
            "seed": SEED,
            "settings": [{"apartment_id": a, "result": booking_site.settings(a)} for a in APARTMENTS],
            "parse_dates": [{"value": v, "iso": _iso(v), "day": _day(booking_calendar, v)} for v in PARSE_DATES],
            "quotes": [{"apartment_id": a, "date_from": f, "date_to": t, "guests": g, "now": n,
                        "result": _quote(db, booking_site, a, f, t, g, n)}
                       for a, f, t, g, n in QUOTES],
            "refunds": [{"booking": b, "checkin_hour": h, "now": n, "by_host": host,
                         "result": booking_site.refund_czk(b, checkin_hour=h, now=datetime.fromisoformat(n),
                                                           by_host=host)}
                        for b, h, n, host in _refund_cases()],
            "tokens": [{"booking_id": i, "token": booking_site.manage_token(i),
                        "url": booking_site.manage_url({"id": i, "apartment_id": a})}
                       for i, a in ((1, 1), (501, 1), (999999, 5))],
            "token_hash": {"value": "abc", "result": booking_site.token_hash("abc")},
            "resolve": [{"slug": s, "result": _resolved(property_page.resolve(s)),
                         "feed_apartment": booking_ical.apartment_for_slug(s)} for s in SLUGS],
            "months": [{"apartment_id": a, "year": y, "month": m, "date_from": f, "date_to": t, "now": n,
                        "result": _month(booking_calendar, booking_site, a, y, m, f, t, n, prague)}
                       for a, y, m, f, t, n in MONTHS],
            "revolut_links": [{"link": link, "ok": _revolut_ok(link)} for link in REVOLUT_LINKS],
            "rails": [{"apartment_id": a, "owner_user_id": o, "enabled": booking_rails.enabled(a),
                       "ready": booking_rails.ready(a), "pay_modes": booking_rails.pay_modes(a, o)}
                      for a, o in ((1, 1), (2, 2), (3, 3), (4, 1), (5, 2), (6, 3), (7, 1), (99, 1))],
            "ical": [{"apartment_id": a, "today": d, "body": booking_ical.export_ics(a, today=date.fromisoformat(d))}
                     for a, d in ((1, "2026-11-28"), (1, "2026-10-01"), (2, "2026-11-28"), (99, "2026-11-28"))],
            "stay_ics": [{"booking_id": 501, "date_from": "2026-12-10", "date_to": "2026-12-13", "name": NAME_1,
                          "body": booking_manage.calendar_ics(
                              {"id": 501, "date_from": "2026-12-10", "date_to": "2026-12-13"}, NAME_1)}],
            "feed_token": {
                "apartment_1_good": booking_ical.token_ok(1, "tok-apt-1"),
                "apartment_1_bad": booking_ical.token_ok(1, "tok-apt-2"),
            },
        }
        # Apartment 2 has no token: a failed check mints and stores one.
        out["feed_token"]["apartment_2_bad"] = booking_ical.token_ok(2, "guess")
        stored = db.get_setting("booking_site:2")
        token = json.loads(stored)["ical_token"]
        out["feed_token"]["apartment_2_length"] = len(token)
        out["feed_token"]["apartment_2_stored"] = stored.replace(token, "<token>")
        out["feed_token"]["apartment_2_again"] = booking_ical.token_ok(2, token)
    finally:
        (db.utcnow, booking_site._now, booking_ical.datetime, booking_manage.datetime,
         config.PUBLIC_BASE_URL, config.STRIPE_MODE, config._SECRET_KEY) = saved
    return json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def _iso(value: str):
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _day(booking_calendar, value: str):
    day = booking_calendar.parse_day(value)
    return day.isoformat() if day else None


def _utc_stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _quote(db, booking_site, a, f, t, g, n):
    """quote() with db.utcnow (hold expiry) on the same clock as now."""
    moment = datetime.fromisoformat(n)
    db.utcnow = lambda: _utc_stamp(moment)
    try:
        return booking_site.quote(a, f, t, g, now=moment)
    finally:
        db.utcnow = lambda: NOW


def _month(booking_calendar, booking_site, a, y, m, f, t, n, prague):
    from app import db

    moment = datetime.fromisoformat(n)
    keep = booking_site._now
    booking_site._now = lambda now: (now or moment).astimezone(prague)
    db.utcnow = lambda: _utc_stamp(moment)
    try:
        return _grid(booking_calendar.month_grid(a, y, m, date_from=f, date_to=t))
    finally:
        booking_site._now = keep
        db.utcnow = lambda: NOW


def _revolut_ok(link: str) -> bool:
    from app.routes import stay_fees

    return stay_fees.revolut_link_ok(link)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "booking_site_golden.sqlite3"))
    os.environ["UBYHOST_SECRET_KEY"] = SECRET
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
