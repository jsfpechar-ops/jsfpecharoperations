"""Legacy first-flat setup URLs.

0092: there is no numbered wizard any more. ``/setup`` and the old step pages
send the host to the short Add property page, or to the property itself. The
old POST handlers stay as guarded adapters (same login, ownership, operator,
address and calendar rules) so a form that was open in a tab still saves, and
then returns to the property page.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from .. import access, auth, db, guest_slug, icalsync, onboarding
from ..feed_url import FeedUrlError, validate_calendar_url
from ..templating import render
from .admin import (
    CALENDAR_PLATFORMS,
    _apartment_payload,
    _calendar_platform,
    _feed_already_added,
    _form_int,
    _property_operator_error,
    _save_address_only,
)
from .admin_helpers import back as _back
from .admin_helpers import flash_plural as _flash_plural
from .admin_helpers import form_str as _form_str
from .admin_helpers import host_text as _host_text

router = APIRouter()

def _booking_sources(request: Request):
    """0089: the calendar platforms (one shared allowlist) plus "I take bookings myself"."""
    sources = [
        (key, name or _host_text(request, "setup.bookings.source.other"))
        for key, name in CALENDAR_PLATFORMS
    ]
    sources.append(("myself", _host_text(request, "setup.bookings.source.myself")))
    return sources


def _wizard_apartment(request: Request):
    owner_user_id = access.owner_id(request)
    if not owner_user_id:
        return None
    return onboarding.first_apartment(owner_user_id)


def _step_context(request: Request, step: str, **extra: Any) -> Dict[str, Any]:
    if step == "name":
        # 0088: the name step creates the property, so it carries the same
        # required operator field as the full form.
        extra.setdefault("entities", access.entities(request))
    return {
        "nav": "dashboard",
        "show_nav": False,
        "wizard_step": step,
        "wizard_step_number": onboarding.wizard_step_number(step),
        "wizard_total_steps": onboarding.WIZARD_TOTAL_STEPS,
        "apartment": _wizard_apartment(request),
        **extra,
    }


def _canonical_entry(request: Request, anchor: str = "") -> str:
    """Where a legacy setup URL leads: create when there is no property yet,
    otherwise the host's first property (with the step's section anchor)."""
    apartment = _wizard_apartment(request)
    if not apartment:
        return "/apartments/new"
    return f"/apartments/{apartment['id']}" + (
        f"{_ANCHOR_VIEWS.get(anchor, '')}#{anchor}" if anchor else ""
    )


_LEGACY_STEP_ANCHORS = {"welcome": "", "name": "", "address": "address", "bookings": "calendars"}
# 0094: the query picks the property tab without JavaScript; the hash scrolls.
_ANCHOR_VIEWS = {"address": "?view=settings&section=property", "calendars": "?view=bookings", "basics": "?view=settings&section=property"}


@router.get("/setup")
def setup_entry(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    return RedirectResponse(_canonical_entry(request), status_code=303)


@router.get("/setup/{step}")
def setup_get(step: str, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if step not in onboarding.WIZARD_STEPS:
        return RedirectResponse("/setup", status_code=303)
    return RedirectResponse(
        _canonical_entry(request, _LEGACY_STEP_ANCHORS[step]), status_code=303
    )


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
        return RedirectResponse(_canonical_entry(request), status_code=303)

    if step == "name":
        name = _form_str(form, "internal_name").strip()
        submitted = {"internal_name": name, "legal_entity_id": _form_int(form, "legal_entity_id")}
        if "operator_refresh" in form:
            return render(
                request,
                "setup/name.html",
                _step_context(request, step, draft=submitted),
            )
        if not name:
            return render(
                request,
                "setup/name.html",
                _step_context(request, step, name_error=True, draft=submitted),
                status_code=400,
            )
        payload = _apartment_payload(form)
        operator_error = _property_operator_error(request, form, payload)
        if operator_error:
            return render(
                request,
                "setup/name.html",
                _step_context(request, step, operator_error=operator_error, draft=submitted),
                status_code=400,
            )
        if apartment:
            db.execute(
                "UPDATE apartment SET internal_name = ?, legal_entity_id = ? WHERE id = ?",
                (name, payload["legal_entity_id"], apartment["id"]),
            )
            apartment_id = apartment["id"]
        else:
            payload["internal_name"] = name
            payload["active"] = 1
            payload["data_controller_entity_id"] = None
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
            return RedirectResponse(
                f"/apartments/{apartment_id}?view=bookings&created=1#calendar-connect", status_code=303
            )
        return RedirectResponse(
            f"/apartments/{apartment_id}?view=settings&section=property#basics", status_code=303
        )

    if step == "address":
        if not apartment:
            return RedirectResponse("/apartments/new", status_code=303)
        rejected = _save_address_only(apartment["id"], request, form)
        if rejected:
            return rejected
        return RedirectResponse(
            f"/apartments/{apartment['id']}?view=settings&section=property#address", status_code=303
        )

    if step == "bookings":
        if not apartment:
            return RedirectResponse("/apartments/new", status_code=303)
        calendars_url = f"/apartments/{apartment['id']}?view=bookings#calendars"
        if _form_str(form, "action") == "finish":
            return RedirectResponse(f"/apartments/{apartment['id']}", status_code=303)
        source = _form_str(form, "source") or _form_str(form, "chosen_source")
        url = _form_str(form, "url").strip()
        other = _form_str(form, "label_other")
        # A platform button with no link yet only opens the link field.
        choosing = _form_str(form, "action") != "add" and not url
        if source == "myself":
            # A manual stay, never a calendar row.
            return RedirectResponse(
                f"/reservations?new=1&apartment={apartment['id']}#add-stay-panel",
                status_code=303,
            )
        if source and choosing:
            # Choosing a platform no longer opens a wizard page: the property's
            # own calendar form takes the platform and the link together.
            return RedirectResponse(calendars_url, status_code=303)
        values, platform_errors = _calendar_platform(source, other, "")

        def _refuse(**errors):
            return render(
                request,
                "setup/bookings.html",
                _step_context(
                    request,
                    step,
                    booking_sources=_booking_sources(request),
                    selected_source=source if source in {key for key, _ in CALENDAR_PLATFORMS} else "",
                    feed_draft={"url": url, "label_other": other},
                    **errors,
                ),
                status_code=400,
            )

        if platform_errors:
            return _refuse(platform_error_key=next(iter(platform_errors.values())))
        if not url:
            return _refuse(url_error=True)
        try:
            url = validate_calendar_url(url)
        except FeedUrlError as exc:
            return _refuse(url_error=True, feed_error_key=exc.key)
        already = _feed_already_added(apartment["id"], url)
        if already:
            return _refuse(feed_duplicate=already)
        db.insert(
            "ical_feed",
            {
                "apartment_id": apartment["id"],
                "url": url,
                "label": values["label"],
                "own_name": values["own_name"],
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
                    booking_sources=_booking_sources(request),
                    sync_error=True,
                ),
                status_code=400,
            )
        return _back(
            calendars_url,
            msg=_flash_plural(request, "flash.feeds.added", totals["created"]),
        )

    return RedirectResponse("/setup", status_code=303)
