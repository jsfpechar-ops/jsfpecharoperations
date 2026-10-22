"""Where the ISDS Odesílací brána sends the host back (brief 0239).

Public and outside the host CSRF dependency: ISDS may come back with a POST,
and the host's UbyHost session may have expired while they were in their data
box. The pages read nothing from the request and store nothing; UbyHost never
sees or keeps data-box login details. A signed-in host is sent back to the
Stay fee page of their newest pending send instead (brief 0240).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request

from .. import auth, db, stay_fee, stay_fee_filing
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash

router = APIRouter()


def _page(request: Request, ok: bool):
    # lang_next drops the query string, so nothing ISDS sends is echoed back.
    return render(request, "databox_return.html", {"ok": ok, "open_alerts": [], "lang_next": request.url.path})


def _land(request: Request, ok: bool):
    user = auth.current_user(request)
    if not user:
        return _page(request, ok)
    grace = datetime.now(timezone.utc) - timedelta(minutes=30)
    row = db.query_one(
        "SELECT * FROM stay_fee_databox_send WHERE user_account_id = ? AND state = 'pending' "
        "AND expires_at > ? ORDER BY id DESC LIMIT 1",
        (user["id"], grace.replace(microsecond=0).isoformat()),
    )
    key = "flash.stay_fees.databox_back" if ok else "flash.stay_fees.databox_error"
    if not row:
        return _back("/stay-fees", **({"msg": _flash(request, key)} if ok else {"err": _flash(request, key)}))
    db.update("stay_fee_databox_send", row["id"], {
        "state": "returned_done" if ok else "returned_error", "returned_at": db.utcnow()})
    filing = db.query_one("SELECT * FROM stay_fee_filing WHERE id = ?", (row["filing_id"],))
    month = stay_fee.month_key(stay_fee_filing.period_anchor(filing)) if filing else ""
    path = f"/stay-fees/{row['apartment_id']}" + (f"?month={month}" if month else "")
    return _back(path, **({"msg": _flash(request, key)} if ok else {"err": _flash(request, key)}))


@router.get("/stay-fees/databox/done")
@router.post("/stay-fees/databox/done")
def databox_done(request: Request):
    return _land(request, True)


@router.get("/stay-fees/databox/error")
@router.post("/stay-fees/databox/error")
def databox_error(request: Request):
    return _land(request, False)
