"""Where the ISDS Odesílací brána sends the host back (brief 0239).

Public and outside the host CSRF dependency: ISDS may come back with a POST,
and the host's UbyHost session may have expired while they were in their data
box. The pages read nothing from the request and store nothing; UbyHost never
sees or keeps data-box login details.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..templating import render

router = APIRouter()


def _page(request: Request, ok: bool):
    # lang_next drops the query string, so nothing ISDS sends is echoed back.
    return render(request, "databox_return.html", {"ok": ok, "open_alerts": [], "lang_next": request.url.path})


@router.get("/stay-fees/databox/done")
@router.post("/stay-fees/databox/done")
def databox_done(request: Request):
    return _page(request, True)


@router.get("/stay-fees/databox/error")
@router.post("/stay-fees/databox/error")
def databox_error(request: Request):
    return _page(request, False)
