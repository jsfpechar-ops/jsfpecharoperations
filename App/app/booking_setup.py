"""Booking site setup page logic (brief 0819, plan booking-site-v1)."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from . import booking_rails, booking_site, db, property_page, stripe_connect

ORDER = ("pay", "page", "price", "policy", "calendar", "publish")
ERR_FIELDS = ("nightly_price_czk", "cleaning_fee_czk", "min_nights", "max_guests",
              "cancellation_policy", "advance_notice_days")
# "<days>" or "<0>:<cutoff hour>" (same-day booking until that hour, Prague).
NOTICE_OPTIONS = ("0:12", "0:15", "0:18", "0:21", "1", "2", "3", "7")


def _ical_key(apartment_id: int) -> str:
    return f"booking_site_ical_done:{int(apartment_id)}"


def mark_calendar_done(apartment_id: int) -> None:
    db.set_setting(_ical_key(apartment_id), "1")


def steps(apartment_id: int, owner_user_id: int) -> List[Dict[str, Any]]:
    """The six setup steps in order; exactly one is `current` (the first open one)."""
    s = booking_site.settings(apartment_id)
    page = property_page.page_for(apartment_id)
    account = stripe_connect.account_for_owner(owner_user_id)
    photos = json.loads(page["photos_json"] or "[]")
    done = {
        "pay": bool(account and account["onboarding_state"] == "complete")
        or booking_rails.ready(apartment_id),
        "page": bool(photos) and bool((page["description"] or "").strip()),
        "price": int(s["nightly_price_czk"] or 0) > 0,
        "policy": db.get_setting(f"booking_site:{int(apartment_id)}") is not None,
        "calendar": db.get_setting(_ical_key(apartment_id)) == "1",
        "publish": bool(page["published"]),
    }
    current = next((key for key in ORDER if not done[key]), "")
    return [{"key": key, "done": done[key], "current": key == current} for key in ORDER]


def can_publish(rows: List[Dict[str, Any]]) -> bool:
    """Stripe connected or one direct rail set, a price set, and photos plus a description; the other steps are advice."""
    done = {row["key"]: row["done"] for row in rows}
    return bool(done["pay"] and done["price"] and done["page"])


def notice_value(s: Dict[str, Any]) -> str:
    if int(s["advance_notice_days"]) == 0:
        value = f"0:{int(s['same_day_cutoff_hour'])}"
        return value if value in NOTICE_OPTIONS else "0:18"
    return str(int(s["advance_notice_days"]))


def _whole(form, name: str, *, empty_is_zero: bool = False) -> int:
    text = str(form.get(name) or "").strip().replace(" ", "")
    if not text and empty_is_zero:
        return 0
    if not text.isdigit():
        raise ValueError(name)
    return int(text)


def parse_form(form) -> Dict[str, Any]:
    """Form fields to `save_settings` values. Raises ValueError(<field>)."""
    values: Dict[str, Any] = {
        "nightly_price_czk": _whole(form, "nightly_price_czk"),
        "cleaning_fee_czk": _whole(form, "cleaning_fee_czk", empty_is_zero=True),
        "min_nights": _whole(form, "min_nights"),
        "max_guests": _whole(form, "max_guests", empty_is_zero=True),
        "cancellation_policy": str(form.get("cancellation_policy") or ""),
    }
    notice = str(form.get("notice") or "")
    if notice not in NOTICE_OPTIONS:
        raise ValueError("advance_notice_days")
    days, _, hour = notice.partition(":")
    values["advance_notice_days"] = int(days)
    if hour:
        values["same_day_cutoff_hour"] = int(hour)
    return values


def error_field(exc: ValueError) -> str:
    """The i18n suffix for a `save_settings` / `parse_form` error."""
    field = {"same_day_cutoff_hour": "advance_notice_days"}.get(str(exc), str(exc))
    return field if field in ERR_FIELDS else "nightly_price_czk"
