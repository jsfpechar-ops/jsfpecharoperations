"""/dev/ui: the living component catalog (docs/design/MASTER.md 11.3).

Admin only. It renders every v2 component from the real CSS so executors
screenshot against it; it reads no data and writes nothing.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from .. import auth, templating

router = APIRouter()

SKELETON_KINDS = ("list", "detail", "form", "settings")


@router.get("/dev/ui")
def dev_ui(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    if not account or account["role"] != "admin":
        return Response(status_code=404)
    kind = request.query_params.get("kind", "detail")
    return templating.render(
        request,
        "dev_ui.html",
        {"nav": "admin", "body_kind": kind if kind in SKELETON_KINDS else "detail", "skeleton_kinds": SKELETON_KINDS},
    )
