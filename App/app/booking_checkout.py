"""Booking site checkout (brief 0815, plan booking-site-v1).

Hold the dates under a lock, store the pending booking, then open a Stripe
Checkout Session on the host's connected account (direct charge, 0 % fee).
The webhook (0816) turns a paid session into a reservation.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from . import booking_site, config, db, demo, stripe_connect

log = logging.getLogger(__name__)

HOLD_MINUTES = 15
# Stripe's minimum session lifetime is 30 minutes; one more absorbs clock skew.
SESSION_MINUTES = 31


def hold_dates(apartment_id: int, date_from: str, date_to: str,
               *, minutes: int = HOLD_MINUTES) -> Optional[int]:
    """Re-check and hold under a lock; None if the nights were taken meanwhile."""
    now = db.utcnow()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    with db.immediate() as cur:
        db.lock_key(cur, "booking_site_dates", apartment_id)
        cur.execute(
            "SELECT id FROM reservation WHERE apartment_id = ? AND status = 'active'"
            " AND date_from < ? AND date_to > ?",
            (apartment_id, date_to, date_from),
        )
        if cur.fetchone() is not None:
            return None
        cur.execute(
            "SELECT id FROM booking_hold WHERE apartment_id = ? AND expires_at > ?"
            " AND date_from < ? AND date_to > ?",
            (apartment_id, now, date_to, date_from),
        )
        if cur.fetchone() is not None:
            return None
        cur.execute(
            "INSERT INTO booking_hold (apartment_id, date_from, date_to, expires_at, created_at)"
            " VALUES (?, ?, ?, ?, ?) RETURNING id",
            (apartment_id, date_from, date_to, expires, now),
        )
        return int(cur.fetchone()["id"])


def _cz_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day}. {d.month}. {d.year}"


def product_name(name: str, q: Dict[str, Any], lang: str) -> str:
    """What the guest sees on Stripe Checkout and the receipt."""
    if lang == "cs":
        return f"Ubytování {name}, {_cz_date(q['date_from'])} – {_cz_date(q['date_to'])}"
    return f"Stay at {name}, {q['date_from']} – {q['date_to']}"


def start(apartment_id: int, slug: str, q: Dict[str, Any], *,
          guest_name: str, guest_email: str, lang: str) -> Dict[str, Any]:
    """{"url": <Stripe URL>, "booking_id": n} or {"error": "taken"|"unavailable"}."""
    apartment = db.query_one(
        "SELECT owner_user_id, internal_name, legal_entity_id FROM apartment WHERE id = ?",
        (apartment_id,),
    )
    if apartment is None or demo.is_demo_apartment(apartment):
        # A demo property is never publicly bookable, even if it survived a
        # switch from mock to a real UbyPort environment.
        return {"error": "unavailable"}
    owner = int(apartment["owner_user_id"])
    account = stripe_connect.account_for_owner(owner)
    if account is None or account["onboarding_state"] != "complete":
        return {"error": "unavailable"}
    hold_id = hold_dates(apartment_id, q["date_from"], q["date_to"])
    if hold_id is None:
        return {"error": "taken"}
    booking = booking_site.create_pending(
        apartment_id, owner, q, guest_name=guest_name, guest_email=guest_email,
        lang=lang, hold_id=hold_id,
    )
    base = config.PUBLIC_BASE_URL.rstrip("/")
    try:
        api = stripe_connect._api()
        session = api.v1.checkout.sessions.create(
            params={
                "mode": "payment",
                "line_items": [{
                    "quantity": 1,
                    "price_data": {
                        "currency": "czk",
                        "unit_amount": int(q["total_czk"]) * 100,
                        "product_data": {
                            "name": product_name(apartment["internal_name"], q, lang),
                        },
                    },
                }],
                "customer_email": booking["guest_email"],
                "locale": "cs" if lang == "cs" else "en",
                "expires_at": int(time.time()) + SESSION_MINUTES * 60,
                "success_url": f"{base}/p/{slug}/thanks?lang={lang}",
                "cancel_url": f"{base}/p/{slug}?book=cancelled&lang={lang}",
                "metadata": {"site_booking_id": str(booking["id"])},
                "payment_intent_data": {
                    "metadata": {"site_booking_id": str(booking["id"])},
                },
            },
            options={"stripe_account": account["stripe_account_id"]},
        )
    except Exception:  # Stripe down, cap reached, bad key: free the dates
        log.exception("site booking %s: checkout session failed", booking["id"])
        db.execute("DELETE FROM booking_hold WHERE id = ?", (hold_id,))
        booking_site.set_status(int(booking["id"]), "expired")
        return {"error": "unavailable"}
    booking_site.attach_session(int(booking["id"]), str(session["id"]))
    db.audit(
        "site_booking_checkout",
        f"id={booking['id']} session={session['id']}",
        owner_user_id=owner,
    )
    return {"url": str(session["url"]), "booking_id": int(booking["id"])}


REQUEST_HOURS = 24


def start_direct(apartment_id: int, q: Dict[str, Any], *, guest_name: str,
                 guest_email: str, lang: str) -> Dict[str, Any]:
    """{"booking": row} or {"error": "taken"|"unavailable"}. Holds the dates for
    24 hours and stores a `requested` booking. No reservation yet (0998)."""
    from . import booking_rails

    apartment = db.query_one(
        "SELECT owner_user_id, internal_name, legal_entity_id FROM apartment WHERE id = ?",
        (apartment_id,),
    )
    if apartment is None or demo.is_demo_apartment(apartment):
        # A demo property is never publicly bookable.
        return {"error": "unavailable"}
    if not booking_rails.ready(apartment_id):
        return {"error": "unavailable"}
    hold_id = hold_dates(apartment_id, q["date_from"], q["date_to"], minutes=REQUEST_HOURS * 60)
    if hold_id is None:
        return {"error": "taken"}
    expires = (datetime.now(timezone.utc) + timedelta(hours=REQUEST_HOURS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    booking = booking_site.create_pending(
        apartment_id, int(apartment["owner_user_id"]), q, guest_name=guest_name,
        guest_email=guest_email, lang=lang, hold_id=hold_id, status="requested",
        pay_method="direct", request_expires_at=expires,
    )
    db.audit("site_booking_requested", f"id={booking['id']}",
             owner_user_id=int(apartment["owner_user_id"]))
    from . import booking_direct

    booking_direct.notify_request(booking)
    booking_direct.notify_request_guest(booking)
    return {"booking": booking}


def expire_requests() -> int:
    """Scheduler job: requests not confirmed within 24 h expire and free their dates."""
    now = db.utcnow()
    rows = db.query(
        "SELECT id, hold_id FROM site_booking WHERE status = 'requested'"
        " AND request_expires_at IS NOT NULL AND request_expires_at <= ?", (now,))
    done = 0
    for row in rows:
        try:
            moved = booking_site.set_status(int(row["id"]), "expired")
        except ValueError:
            continue
        if moved:
            done += 1
        if moved and row["hold_id"]:
            db.execute("DELETE FROM booking_hold WHERE id = ?", (row["hold_id"],))
    return done
