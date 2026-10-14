"""0102: focused onboarding wizard — one page per setup step."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, Request

from .. import access, auth, config, db, demo, guest_slug, host_i18n, payments, property_setup, reporting, security
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter(dependencies=[Depends(security.protect_host_post)])

_SETUP_ACTIONS = {
    "skip": property_setup.SKIPPABLE,
    "done": property_setup.TEACHING,
    "wait": frozenset({"police"}),
    "demo": frozenset({"try_it"}),
    "keep_demo": frozenset({"try_it"}),
}
_SETUP_MARKS = {"skip": "skipped", "wait": "waiting"}


def wizard_return_to(apartment_id: int, step: str) -> str:
    """The return_to target after a wizard step save."""
    return property_setup.wizard_url(apartment_id, step)


def wizard_setup_prefix(apartment_id: int) -> str:
    """Shared prefix for a wizard return_to (refuse, save, and calendar add)."""
    return f"/apartments/{int(apartment_id)}/setup/"


def _admin_helpers():
    from . import admin as admin_routes

    return admin_routes


def _door_code_context(apartment, apartment_id: int) -> Optional[Dict[str, Any]]:
    return _admin_helpers()._door_code_context(apartment, apartment_id)


def _guide_after(ctx: Dict[str, Any]):
    """The guide after a mark, using facts already loaded for this request."""
    apartment = ctx["apartment"]
    facts = ctx["wizard_facts"]
    state = property_setup.load(apartment["id"]) or property_setup.legacy_state()
    return property_setup.current(
        apartment,
        state,
        feeds=facts["feeds"],
        report_complete=facts["report_complete"],
        lock_available=ctx["lock_available"],
        stays=facts["stays"],
        guests_registered=facts["guests_registered"],
    )


def _wizard_context(
    request: Request, apartment_id: int, step: str, extra: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
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
    door_code = _door_code_context(apartment, apartment_id)
    lock_available = door_code is not None
    bundle = admin_routes._setup_guide_bundle(
        apartment, feeds=feeds, lock_available=lock_available
    )
    facts_payload = bundle["facts_payload"]
    state = bundle["state"]
    guide = bundle["guide"]
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
        "wizard_number": property_setup.STEPS.index(step) + 1 if step in property_setup.STEPS else None,
        "wizard_total": property_setup.TOTAL_STEPS,
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
        "wizard_facts": facts_payload,
        "checklist": property_setup.checklist(
            state or property_setup.legacy_state(),
            apartment,
            facts_payload,
            lock_available=lock_available,
        )
        if step == "done"
        else [],
        "prev_step": property_setup.prev_applicable_step(
            step, apartment, lock_available=lock_available
        ),
        "next_step": property_setup.next_step(step),
        "wizard_next_return_to": property_setup.wizard_url(
            apartment_id,
            property_setup.next_applicable_step(step, apartment, lock_available=lock_available)
            or "done",
        ),
        "entities": access.entities(request),
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
    ctx: Optional[Dict[str, Any]] = None,
):
    if ctx is None:
        ctx, redirect = _wizard_context(request, apartment_id, step, extra)
        if redirect:
            return redirect
    elif extra:
        ctx = {**ctx, **extra}
    template = f"setup_wizard/{step}.html"
    return render(request, template, ctx, status_code=status_code)


def _posted_setup_step(form) -> str:
    """The wizard step this form belongs to, or '' when the value is not a step."""
    step = _form_str(form, "setup_step")
    if step in property_setup.STEPS:
        return step
    return ""


def refuse_setup_save(
    request: Request,
    apartment: Dict[str, Any],
    form,
    *,
    police_errors: Optional[Dict[str, str]] = None,
    address_errors: Optional[Dict[str, str]] = None,
    fee_account_error: bool = False,
    operator_error: Optional[str] = None,
):
    step = _posted_setup_step(form)
    if not step:
        return None
    admin_routes = _admin_helpers()
    owned = set(property_setup.STEP_FIELDS.get(step, ()))
    draft = dict(apartment)
    for field in admin_routes.APARTMENT_TEXT_FIELDS:
        if field in owned and field in form:
            draft[field] = _form_str(form, field)
    if "legal_entity_id" in owned and "legal_entity_id" in form:
        raw = _form_str(form, "legal_entity_id")
        try:
            draft["legal_entity_id"] = int(raw) if raw else apartment.get("legal_entity_id")
        except (TypeError, ValueError):
            draft["legal_entity_id"] = None
    if "data_controller_entity_id" in owned and "data_controller_entity_id" in form:
        draft["data_controller_entity_id"] = _form_str(form, "data_controller_entity_id")
    if "default_purpose" in owned and "default_purpose" in form:
        draft["default_purpose"] = _form_str(form, "default_purpose")
    if step == "stay_fee":
        from . import stay_fees as stay_fee_routes

        for key, value in stay_fee_routes.fee_form_values(form).items():
            if key != stay_fee_routes.FEE_ACCOUNT_RAW:
                draft[key] = value
        for key in ("account_prefix", "account_number", "account_bank"):
            if key in form:
                draft[key] = _form_str(form, key)
    if step == "automation":
        draft["automation_mode"] = _form_str(form, "automation_mode")
        draft["submit_after_hours"] = _form_str(form, "submit_after_hours")
    if "guest_message" in owned and "guest_message" in form:
        draft["guest_message"] = _form_str(form, "guest_message")
    if "notes" in owned and "notes" in form:
        draft["notes"] = _form_str(form, "notes")
    extra = {
        "draft": draft,
        "police_errors": police_errors or {},
        "address_errors": address_errors or {},
        "fee_account_error": fee_account_error,
        "operator_error": operator_error,
    }
    return render_wizard(request, apartment["id"], step, extra=extra, status_code=400)


@router.get("/apartments/{apartment_id}/setup")
def setup_entry(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    ctx, redirect = _wizard_context(request, apartment_id, "calendar")
    if redirect:
        return redirect
    guide = ctx["guide"]
    state = ctx["setup_state"]
    if guide:
        return _back(guide["url"])
    if state and state.get("finished"):
        return _back(f"/apartments/{apartment_id}?view=overview")
    if state and not state.get("hidden") and not property_setup.wizard_unresolved(
        ctx["apartment"], state, ctx["wizard_facts"], lock_available=ctx["lock_available"]
    ):
        # Recover a wizard left unfinished by the former police-waiting gate.
        property_setup.finish(apartment_id)
        return _back(wizard_return_to(apartment_id, "done"))
    return _back(f"/apartments/{apartment_id}/setup/calendar")


@router.get("/apartments/{apartment_id}/setup/{step}")
def setup_step(apartment_id: int, step: str, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if step != "done" and step not in property_setup.STEPS:
        return _back(f"/apartments/{apartment_id}/setup")
    ctx, redirect = _wizard_context(request, apartment_id, step)
    if redirect:
        return redirect
    guide = ctx["guide"]
    state = ctx["setup_state"] or property_setup.legacy_state()
    if step != "done" and guide and guide["key"] != step:
        if not property_setup.may_view_step(
            step,
            guide,
            state,
            ctx["apartment"],
            ctx["wizard_facts"],
            lock_available=ctx["lock_available"],
        ):
            return _back(guide["url"])
    return render_wizard(request, apartment_id, step, ctx=ctx)


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
        return _back(f"/apartments/{apartment_id}/setup")
    if action == "hide":
        property_setup.set_hidden(apartment_id, True)
        db.audit("property_setup_step", f"apartment={apartment_id} action=hide")
        return _back(overview, msg=_flash(request, "flash.setup.hidden"))
    ctx, redirect = _wizard_context(request, apartment_id, step or "calendar")
    if redirect:
        return redirect
    guide = ctx["guide"] if ctx else None
    if not guide or guide["key"] != step or step not in _SETUP_ACTIONS.get(action, ()):
        return _back(guide["url"] if guide else overview)
    stay = demo.demo_stay_for(apartment_id)
    if step == "try_it" and action == "demo":
        demo.create_demo_stay(apartment_id)
        db.audit("property_setup_step", f"apartment={apartment_id} step=try_it action=demo")
        return _back(wizard_return_to(apartment_id, "try_it"))
    if step == "try_it" and action == "done" and not (stay and reporting.reservation_progress(stay)["filled"] >= 1):
        return _back(guide["url"])
    if action == "keep_demo":
        property_setup.mark(apartment_id, step, "done")
        db.audit("property_setup_step", f"apartment={apartment_id} step={step} action={action}")
        nxt = _guide_after(ctx)
        if nxt:
            return _back(nxt["url"])
        property_setup.finish(apartment_id)
        return _back(
            wizard_return_to(apartment_id, "done"),
            msg=_flash(request, "flash.setup.complete"),
        )
    deleted = False
    if step == "try_it" and action in ("done", "skip") and stay:
        deleted = demo.delete_demo_stay(stay["id"], apartment_id)
    if action == "wait" and step == "police":
        property_setup.mark(apartment_id, step, "waiting")
    else:
        property_setup.mark(apartment_id, step, _SETUP_MARKS.get(action, "done"))
    db.audit("property_setup_step", f"apartment={apartment_id} step={step} action={action}")
    nxt = _guide_after(ctx)
    if nxt:
        return _back(
            nxt["url"],
            msg=_flash(request, "flash.setup.demo_deleted") if deleted else "",
        )
    property_setup.finish(apartment_id)
    return _back(
        wizard_return_to(apartment_id, "done"),
        msg=_flash(request, "flash.setup.complete"),
    )
