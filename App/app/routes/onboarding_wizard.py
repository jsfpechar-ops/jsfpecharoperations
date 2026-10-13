"""0102: focused onboarding wizard — one page per setup step."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request

from .. import access, auth, config, db, demo, guest_slug, host_i18n, payments, property_setup, reporting, security, ttlock
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter(dependencies=[Depends(security.protect_host_post)])

_SETUP_ACTIONS = {
    "skip": property_setup.SKIPPABLE,
    "done": property_setup.TEACHING,
    "keep": frozenset({"automation"}),
    "wait": frozenset({"police"}),
    "demo": frozenset({"try_it"}),
    "keep_demo": frozenset({"try_it"}),
}
_SETUP_MARKS = {"skip": "skipped", "wait": "waiting"}


def _wizard_step_path(apartment_id: int, step: str) -> str:
    return property_setup.wizard_url(apartment_id, step)


def _admin_helpers():
    from . import admin as admin_routes

    return admin_routes


def _door_code_context(apartment, apartment_id: int) -> Optional[Dict[str, Any]]:
    admin_routes = _admin_helpers()
    if not ttlock.allowed_for(apartment["owner_user_id"]):
        return None
    account = ttlock.account_for(apartment["owner_user_id"])
    locks = [
        {
            **lock,
            "used_by": ", ".join(
                admin_routes._properties_using_lock(
                    apartment["owner_user_id"], lock["lock_id"], apartment_id
                )
            ),
        }
        for lock in (ttlock.locks_of(account) if account else [])
    ]
    free_locks = [lock for lock in locks if not lock["used_by"]]
    selected = next((lock for lock in locks if lock["lock_id"] == apartment["lock_id"]), None)
    cin, cout = apartment["checkin_hour"], apartment["checkout_hour"]
    return {
        "account": account,
        "locks": locks,
        "enabled": apartment["lock_provider"] == "ttlock",
        "lock_id": apartment["lock_id"],
        "default_lock_id": free_locks[0]["lock_id"] if len(free_locks) == 1 else "",
        "checkin_hour": cin,
        "checkout_hour": cout,
        "tz_warning": bool(
            selected and selected["tz_offset_ms"] not in (None, 3_600_000, 7_200_000)
        ),
        "overlap": admin_routes._door_code_hours_overlap(cin, cout),
        "buffer": config.DOOR_CODE_BUFFER_HOURS,
        "test_mode": not getattr(config, "DOOR_CODES_LIVE", False),
    }


def _wizard_context(request: Request, apartment_id: int, step: str, extra: Optional[Dict[str, Any]] = None):
    admin_routes = _admin_helpers()
    apartment = admin_routes._ensure_apartment_pin(access.apartment(request, apartment_id))
    if not apartment:
        return None, _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    feeds = db.query("SELECT * FROM ical_feed WHERE apartment_id = ? ORDER BY id", (apartment_id,))
    readiness = admin_routes._readiness(
        apartment,
        access.entities(request),
        list(admin_routes._apartment_issues(apartment)),
        bool(feeds),
        invite=False,
    )
    report_complete = all(item["done"] for item in readiness["report"])
    facts = admin_routes._setup_facts(apartment_id)
    state = admin_routes._setup_state(
        apartment, feeds=len(feeds), report_complete=report_complete, stays=facts["stays"]
    )
    door_code = _door_code_context(apartment, apartment_id)
    lock_available = door_code is not None
    guide = property_setup.current(
        apartment,
        state,
        feeds=len(feeds),
        report_complete=report_complete,
        lock_available=lock_available,
        stays=facts["stays"],
        guests_registered=facts["guests_registered"],
    )
    link_key = guest_slug.link_key(apartment)
    lang = host_i18n.lang_from_request(request)
    setup_demo = None
    if step == "try_it":
        stay = demo.demo_stay_for(apartment_id)
        if stay:
            progress = reporting.reservation_progress(stay)
            setup_demo = {
                "state": "registered" if progress["filled"] >= 1 else "open",
                "reservation": stay,
                "progress": progress,
                "guest_url": f"/l/{link_key}/{stay['id']}?lang={lang}",
                "pin": apartment["permalink_pin"],
            }
        else:
            setup_demo = {"state": "none"}
    ctx = {
        "apartment": apartment,
        "wizard_step": step,
        "guide": guide,
        "setup_state": state,
        "setup_finished": guide is None and state and state.get("finished"),
        "setup_hidden": bool(state and state.get("hidden") and not state.get("finished")),
        "door_code": door_code,
        "lock_available": lock_available,
        "permalink": f"{config.PUBLIC_BASE_URL}/l/{link_key}",
        "link_key": link_key,
        "pin": apartment["permalink_pin"] or "",
        "fee_account": payments.czech_account_parts(apartment["stay_fee_council_account"] or ""),
        "has_password": bool(apartment["uby_ws_password_enc"]),
        "calendar_platforms": admin_routes.CALENDAR_PLATFORMS,
        "setup_demo": setup_demo,
        "setup_sweep_minutes": config.SUBMIT_SWEEP_MINUTES,
        "reporting_waiting": bool(
            state and state["steps"].get("police") == "waiting" and not report_complete
        ),
        "checklist": property_setup.checklist(state or property_setup.legacy_state(), apartment, {
            "feeds": len(feeds),
            "stays": facts["stays"],
            "guests_registered": facts["guests_registered"],
            "report_complete": report_complete,
        }, lock_available=lock_available) if step == "done" else [],
        "prev_step": property_setup.prev_step(step),
        "next_step": property_setup.next_step(step),
        "nav": "apartments",
        "show_nav": True,
    }
    if extra:
        ctx.update(extra)
    return ctx, None


def render_wizard(
    request: Request,
    apartment_id: int,
    step: str,
    *,
    extra: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
):
    ctx, redirect = _wizard_context(request, apartment_id, step, extra)
    if redirect:
        return redirect
    template = f"setup_wizard/{step}.html"
    return render(request, template, ctx, status_code=status_code)


def refuse_setup_save(
    request: Request,
    apartment: Dict[str, Any],
    form,
    *,
    police_errors: Optional[Dict[str, str]] = None,
    address_errors: Optional[Dict[str, str]] = None,
    fee_account_error: bool = False,
):
    return_to = _form_str(form, "return_to")
    step = ""
    if "/setup/" in return_to:
        step = return_to.rstrip("/").split("/")[-1]
    if step not in property_setup.STEPS:
        return None
    draft = dict(apartment)
    for key in form.keys():
        if key in draft or key.startswith(("uby_", "addr_", "stay_fee", "account_", "automation", "door_", "lock", "checkin", "checkout", "internal_name", "legal_entity", "city_en", "default_purpose")):
            draft[key] = _form_str(form, key) if key != "legal_entity_id" else int(_form_str(form, key) or 0) or apartment.get("legal_entity_id")
    extra = {"draft": draft, "police_errors": police_errors or {}, "address_errors": address_errors or {}, "fee_account_error": fee_account_error}
    return render_wizard(request, apartment["id"], step, extra=extra, status_code=400)


@router.get("/apartments/{apartment_id}/setup")
def setup_entry(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    admin_routes = _admin_helpers()
    feeds = db.query("SELECT id FROM ical_feed WHERE apartment_id = ?", (apartment_id,))
    readiness = admin_routes._readiness(
        apartment,
        access.entities(request),
        list(admin_routes._apartment_issues(apartment)),
        bool(feeds),
        invite=False,
    )
    report_complete = all(item["done"] for item in readiness["report"])
    facts = admin_routes._setup_facts(apartment_id)
    state = admin_routes._setup_state(
        apartment, feeds=len(feeds), report_complete=report_complete, stays=facts["stays"]
    )
    door_code = _door_code_context(apartment, apartment_id)
    guide = property_setup.current(
        apartment,
        state,
        feeds=len(feeds),
        report_complete=report_complete,
        lock_available=door_code is not None,
        stays=facts["stays"],
        guests_registered=facts["guests_registered"],
    )
    if guide:
        return _back(guide["url"])
    if state and state.get("finished"):
        return _back(f"/apartments/{apartment_id}?view=overview")
    return _back(f"/apartments/{apartment_id}/setup/calendar")


@router.get("/apartments/{apartment_id}/setup/{step}")
def setup_step(apartment_id: int, step: str, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if step == "done":
        return render_wizard(request, apartment_id, step)
    if step not in property_setup.STEPS:
        return _back(f"/apartments/{apartment_id}/setup")
    ctx, redirect = _wizard_context(request, apartment_id, step)
    if redirect:
        return redirect
    guide = ctx["guide"]
    if guide and guide["key"] != step and step != "done":
        return _back(guide["url"])
    return render_wizard(request, apartment_id, step)


@router.post("/apartments/{apartment_id}/setup")
async def setup_action(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    step, action = _form_str(form, "step"), _form_str(form, "action")
    overview = f"/apartments/{apartment_id}?view=overview"
    if action == "show":
        stored = property_setup.load(apartment_id)
        if stored and stored["hidden"]:
            property_setup.set_hidden(apartment_id, False)
            db.audit("property_setup_step", f"apartment={apartment_id} action=show")
        ctx, _ = _wizard_context(request, apartment_id, "calendar")
        guide = ctx["guide"] if ctx else None
        return _back(guide["url"] if guide else _wizard_step_path(apartment_id, "calendar"))
    ctx, _ = _wizard_context(request, apartment_id, step or "calendar")
    guide = ctx["guide"] if ctx else None
    if action == "hide":
        property_setup.set_hidden(apartment_id, True)
        db.audit("property_setup_step", f"apartment={apartment_id} action=hide")
        return _back(overview, msg=_flash(request, "flash.setup.hidden"))
    if action == "wait" and step == "police":
        property_setup.mark(apartment_id, step, "waiting")
        db.audit("property_setup_step", f"apartment={apartment_id} step=police action=wait")
        nxt = property_setup.next_step("police") or "stay_fee"
        return _back(_wizard_step_path(apartment_id, nxt))
    if not guide or guide["key"] != step or step not in _SETUP_ACTIONS.get(action, ()):
        return _back(guide["url"] if guide else overview)
    stay = demo.demo_stay_for(apartment_id)
    if step == "try_it":
        if action == "demo":
            demo.create_demo_stay(apartment_id)
            db.audit("property_setup_step", f"apartment={apartment_id} step=try_it action=demo")
            return _back(_wizard_step_path(apartment_id, "try_it"))
        if action == "done" and not (stay and reporting.reservation_progress(stay)["filled"] >= 1):
            return _back(guide["url"])
        if action == "keep_demo":
            property_setup.mark(apartment_id, step, "done")
            nxt = property_setup.next_step(step)
            return _back(_wizard_step_path(apartment_id, nxt or "done"))
    deleted = False
    if step == "try_it" and action == "done" and stay:
        deleted = demo.delete_demo_stay(stay["id"], apartment_id)
    if action == "keep":
        property_setup.mark(apartment_id, step, "done")
    else:
        property_setup.mark(apartment_id, step, _SETUP_MARKS.get(action, "done"))
    db.audit("property_setup_step", f"apartment={apartment_id} step={step} action={action}")
    ctx, _ = _wizard_context(request, apartment_id, step)
    guide = ctx["guide"] if ctx else None
    if guide:
        return _back(
            guide["url"],
            msg=_flash(request, "flash.setup.demo_deleted") if deleted else "",
        )
    property_setup.finish(apartment_id)
    return _back(
        _wizard_step_path(apartment_id, "done"),
        msg=_flash(request, "flash.setup.complete"),
    )
