"""Host-facing data-subject request register (BE-8)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from .. import access, alerts, auth, db, dsr, security
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter(dependencies=[Depends(security.protect_host_post)])

_CLOSED = ("fulfilled", "refused", "withdrawn")


@router.get("/privacy-requests")
def privacy_requests_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    return render(
        request,
        "privacy_requests.html",
        {
            "requests": dsr.list_for_owner(owner_id),
            "channels": dsr.CHANNELS,
            "request_types": dsr.REQUEST_TYPES,
            "subject_kinds": dsr.SUBJECT_KINDS,
            "statuses": dsr.STATUSES,
        },
    )


@router.post("/privacy-requests")
async def privacy_request_create(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    channel = _form_str(form, "channel")
    request_type = _form_str(form, "request_type")
    subject_kind = _form_str(form, "subject_kind")
    if (
        channel not in dsr.CHANNELS
        or request_type not in dsr.REQUEST_TYPES
        or subject_kind not in dsr.SUBJECT_KINDS
    ):
        return _back("/privacy-requests", err=_flash(request, "flash.error.bad_dsr"))
    guest_raw = _form_str(form, "guest_id").strip()
    owner_id = access.owner_id(request)
    request_id = dsr.create(
        owner_user_id=owner_id,
        received_at=_form_str(form, "received_at") or db.utcnow(),
        channel=channel,
        request_type=request_type,
        subject_kind=subject_kind,
        guest_id=int(guest_raw) if guest_raw.isdigit() else None,
        handled_by=owner_id,
    )
    db.audit("dsr_created", f"request={request_id} type={request_type}")
    return _back("/privacy-requests", msg=_flash(request, "flash.dsr.created"))


@router.post("/privacy-requests/{request_id}")
async def privacy_request_update(request_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    row = dsr.get(request_id)
    if not row or row["owner_user_id"] != access.owner_id(request):
        return _back("/privacy-requests", err=_flash(request, "flash.error.no_such_dsr"))
    form = await request.form()
    values = {}
    status = _form_str(form, "status")
    if status in dsr.STATUSES:
        values["status"] = status
        if status in _CLOSED:
            values["closed_at"] = db.utcnow()
    if "outcome_note" in form:
        values["outcome_note"] = _form_str(form, "outcome_note")
    if "identity_checked" in form:
        values["identity_checked_at"] = db.utcnow()
    if values:
        dsr.update(request_id, values)
        if values.get("status") in _CLOSED:
            alerts.resolve(f"dsr_due:{request_id}")
    db.audit("dsr_updated", f"request={request_id}")
    return _back("/privacy-requests", msg=_flash(request, "flash.dsr.updated"))
