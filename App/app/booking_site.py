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
DEFAULT_CHECKOUT_HOUR = 11
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
    if "nightly_price_czk" not in stored:
        # Pages priced before 0814 kept the price only on property_page (0434).
        page = db.query_one(
            "SELECT nightly_price_czk FROM property_page WHERE apartment_id = ?",
            (apartment_id,),
        )
        if page is not None and page["nightly_price_czk"]:
            out["nightly_price_czk"] = int(page["nightly_price_czk"])
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
