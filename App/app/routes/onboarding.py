"""First-run onboarding: the demo dataset, the checklist and celebrations.

These are the routes that make an empty install explorable and then get out of
the way. ``admin.router`` includes this router, so the host POST protection is
unchanged.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from .. import access, auth, celebrations, db, demo, onboarding, security
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter()


@router.post("/demo")
def load_demo(request: Request):
    """Fill an empty install with something to click through."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment_id = demo.seed(access.owner_id(request))
    if not apartment_id:
        return _back(
            "/",
            err=_flash(request, "flash.error.demo_staging_only"),
        )
    return _back("/", msg=_flash(request, "flash.demo.loaded"))


@router.post("/demo/reset")
def reset_demo(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not demo.clear(access.owner_id(request)):
        return _back("/", err=_flash(request, "flash.error.demo_missing"))
    return _back("/", msg=_flash(request, "flash.demo.cleared"))


@router.get("/onboarding")
def onboarding_view(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    return render(request, "onboarding.html")


@router.post("/onboarding/dismiss")
async def onboarding_dismiss(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    owner_user_id = access.owner_id(request)
    onboarding.set_dismissed(owner_user_id, True)
    db.audit("onboarding.dismissed", owner_user_id=owner_user_id)
    return RedirectResponse(
        security.safe_local_path(_form_str(form, "return_to"), "/"), status_code=303
    )


@router.post("/onboarding/resume")
async def onboarding_resume(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    owner_user_id = access.owner_id(request)
    onboarding.set_dismissed(owner_user_id, False)
    db.audit("onboarding.resumed", owner_user_id=owner_user_id)
    return RedirectResponse(
        security.safe_local_path(_form_str(form, "return_to"), "/onboarding"),
        status_code=303,
    )


@router.post("/celebrations/dismiss")
async def dismiss_celebration(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    milestone = int(_form_str(form, "milestone") or "0")
    owner_user_id = access.owner_id(request)
    if owner_user_id and milestone:
        celebrations.acknowledge(owner_user_id, milestone)
    return RedirectResponse(
        security.safe_local_path(_form_str(form, "return_to"), "/"), status_code=303
    )
