"""First-flat setup wizard: welcome, name, address and calendar booking source."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from .. import access, auth, db, guest_slug, icalsync, onboarding, security, validation
from ..feed_url import FeedUrlError, validate_calendar_url
from ..templating import render
from .admin import (
    _apartment_payload,
    _feed_already_added,
    _save_apartment_form,
)
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter()

_BOOKING_SOURCES = (
    ("airbnb", "setup.bookings.source.airbnb"),
    ("booking", "setup.bookings.source.booking"),
    ("echalupy", "setup.bookings.source.echalupy"),
    ("other", "setup.bookings.source.other"),
    ("myself", "setup.bookings.source.myself"),
)


def _wizard_apartment(request: Request):
    owner_user_id = access.owner_id(request)
    if not owner_user_id:
        return None
    return onboarding.first_apartment(owner_user_id)


def _step_context(request: Request, step: str, **extra: Any) -> Dict[str, Any]:
    return {
        "nav": "dashboard",
        "show_nav": False,
        "wizard_step": step,
        "wizard_step_number": onboarding.wizard_step_number(step),
        "wizard_total_steps": onboarding.WIZARD_TOTAL_STEPS,
        "apartment": _wizard_apartment(request),
        **extra,
    }


def _prev_step(step: str) -> Optional[str]:
    order = list(onboarding.WIZARD_STEPS)
    try:
        index = order.index(step)
    except ValueError:
        return None
    return order[index - 1] if index > 0 else None


def _next_step(step: str) -> Optional[str]:
    order = list(onboarding.WIZARD_STEPS)
    try:
        index = order.index(step)
    except ValueError:
        return None
    return order[index + 1] if index + 1 < len(order) else None


def _address_preview(apartment) -> str:
    if not apartment:
        return ""
    parts = [
        (apartment["addr_street"] or "").strip(),
        " ".join(
            part
            for part in (
                (apartment["addr_house_no"] or "").strip(),
                (apartment["addr_orient_no"] or "").strip(),
            )
            if part
        ).strip(),
        (apartment["addr_obec_cast"] or "").strip(),
        (apartment["addr_obec"] or "").strip(),
        validation.normalise_zip(apartment["addr_zip"] or ""),
    ]
    return ", ".join(part for part in parts if part)


def _upcoming_stays(apartment_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    today = db.utcnow()[:10]
    return db.query(
        "SELECT date_from, date_to FROM reservation "
        "WHERE apartment_id = ? AND status = 'active' AND date_to >= ? "
        "ORDER BY date_from LIMIT ?",
        (apartment_id, today, limit),
    )


@router.get("/setup")
def setup_entry(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_user_id = access.owner_id(request)
    step = onboarding.wizard_step(owner_user_id)
    if step == "complete":
        apartment = onboarding.first_apartment(owner_user_id)
        if apartment:
            return RedirectResponse(
                f"/apartments/{apartment['id']}#ubyport",
                status_code=303,
            )
        return RedirectResponse("/setup/welcome", status_code=303)
    return RedirectResponse(f"/setup/{step}", status_code=303)


@router.get("/setup/{step}")
def setup_get(step: str, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if step not in onboarding.WIZARD_STEPS:
        return RedirectResponse("/setup", status_code=303)
    apartment = _wizard_apartment(request)
    if step == "name" and apartment and request.query_params.get("edit") != "1":
        return RedirectResponse("/setup/address", status_code=303)
    if step in ("address", "bookings") and not apartment:
        return RedirectResponse("/setup/name", status_code=303)
    template = f"setup/{step}.html"
    extra: Dict[str, Any] = {}
    if step == "address":
        extra["address_preview"] = _address_preview(apartment)
        extra["split_address"] = hasattr(validation, "split_czech_address")
    if step == "bookings":
        extra["booking_sources"] = _BOOKING_SOURCES
        extra["selected_source"] = request.query_params.get("source", "")
        extra["sync_result"] = request.query_params.get("result") == "1"
        extra["stay_count"] = int(request.query_params.get("count") or "0")
        extra["upcoming_stays"] = (
            _upcoming_stays(apartment["id"]) if apartment and extra["sync_result"] else []
        )
        extra["sync_error"] = request.query_params.get("sync_error") == "1"
    return render(request, template, _step_context(request, step, **extra))


@router.post("/setup/{step}")
async def setup_post(step: str, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if step not in onboarding.WIZARD_STEPS:
        return RedirectResponse("/setup", status_code=303)
    form = await request.form()
    owner_user_id = access.owner_id(request)
    apartment = _wizard_apartment(request)

    if step == "welcome":
        nxt = _next_step(step) or "name"
        return RedirectResponse(f"/setup/{nxt}", status_code=303)

    if step == "name":
        name = _form_str(form, "internal_name").strip()
        if not name:
            return render(
                request,
                "setup/name.html",
                _step_context(request, step, name_error=True),
                status_code=400,
            )
        if apartment:
            db.execute(
                "UPDATE apartment SET internal_name = ? WHERE id = ?",
                (name, apartment["id"]),
            )
            apartment_id = apartment["id"]
        else:
            payload = _apartment_payload(form)
            payload["internal_name"] = name
            payload["active"] = 1
            payload["permalink_token"] = auth.new_permalink_token()
            payload["permalink_pin"] = auth.new_permalink_pin()
            payload["created_at"] = db.utcnow()
            payload["owner_user_id"] = owner_user_id
            payload.pop("_stay_fee_account_raw", None)
            apartment_id = db.insert("apartment", payload)
            guest_slug.ensure(
                db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
            )
            db.audit("apartment_created", f"id={apartment_id}")
        return RedirectResponse("/setup/address", status_code=303)

    if step == "address":
        if not apartment:
            return RedirectResponse("/setup/name", status_code=303)
        rejected = _save_apartment_form(apartment["id"], request, form)
        if rejected:
            return rejected
        return RedirectResponse("/setup/bookings", status_code=303)

    if step == "bookings":
        if not apartment:
            return RedirectResponse("/setup/name", status_code=303)
        if _form_str(form, "action") == "finish":
            return RedirectResponse(
                f"/apartments/{apartment['id']}#ubyport",
                status_code=303,
            )
        source = _form_str(form, "source")
        url = _form_str(form, "url").strip()
        if source and not url:
            if source == "myself":
                return RedirectResponse(
                    "/reservations?new=1&return_to=/setup#add-stay-panel",
                    status_code=303,
                )
            return RedirectResponse(
                f"/setup/bookings?source={source}",
                status_code=303,
            )
        if not url:
            return render(
                request,
                "setup/bookings.html",
                _step_context(
                    request,
                    step,
                    booking_sources=_BOOKING_SOURCES,
                    selected_source=source,
                    url_error=True,
                ),
                status_code=400,
            )
        try:
            url = validate_calendar_url(url)
        except FeedUrlError as exc:
            return render(
                request,
                "setup/bookings.html",
                _step_context(
                    request,
                    step,
                    booking_sources=_BOOKING_SOURCES,
                    selected_source=source,
                    url_error=True,
                    feed_error_key=exc.key,
                ),
                status_code=400,
            )
        already = _feed_already_added(apartment["id"], url)
        if already:
            return render(
                request,
                "setup/bookings.html",
                _step_context(
                    request,
                    step,
                    booking_sources=_BOOKING_SOURCES,
                    selected_source=source,
                    feed_duplicate=already,
                ),
                status_code=400,
            )
        db.insert(
            "ical_feed",
            {
                "apartment_id": apartment["id"],
                "url": url,
                "label": source or "other",
                "own_name": source or "other",
                "active": 1,
                "created_at": db.utcnow(),
            },
        )
        totals = await run_in_threadpool(icalsync.sync_all, apartment["id"])
        if totals["errors"]:
            db.execute(
                "DELETE FROM ical_feed WHERE apartment_id = ? AND url = ?",
                (apartment["id"], url),
            )
            return render(
                request,
                "setup/bookings.html",
                _step_context(
                    request,
                    step,
                    booking_sources=_BOOKING_SOURCES,
                    sync_error=True,
                ),
                status_code=400,
            )
        stay_count = int(
            db.query_one(
                "SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ? AND status = 'active'",
                (apartment["id"],),
            )["n"]
        )
        return RedirectResponse(
            f"/setup/bookings?result=1&count={stay_count}",
            status_code=303,
        )

    return RedirectResponse("/setup", status_code=303)
