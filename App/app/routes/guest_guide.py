"""0342: the host's guest guide pages: the card list and one card's editor.

The data and every rule about it live in ``app.guest_guide``; these routes only
check the property belongs to the host, call it, and redirect.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from .. import access, auth, config, guest_guide, guest_guide_import, guest_handoff, guest_guide_merge, guide_photos, guide_token, payments, security, templating
from .admin_helpers import back, flash
from .. import ai, guide_translate  # 0353: the host usage line

router = APIRouter(dependencies=[Depends(security.protect_host_post)])
PRIVATE = {"Cache-Control": "no-store"}


def _home(request: Request, apartment_id: int) -> Dict[str, Any]:
    row = access.apartment(request, apartment_id)
    if not row or row["archived_at"]:
        raise HTTPException(404)
    return dict(row)


def _base(apartment_id: int) -> str:
    return f"/apartments/{apartment_id}/guide"


def _render(request: Request, name: str, status_code: int = 200, **values):
    context = {"nav": "apartments", "visibility": guest_guide.VISIBILITY, **values}
    response = templating.render(request, name, context, status_code=status_code)
    response.headers.update(PRIVATE)
    return response


def _card(request: Request, apartment, item, values, error: str = "", status_code: int = 200):
    return _render(
        request, "guest_guide_card.html", status_code=status_code,
        apartment=apartment, item=item, values=values, error=error,
        photos=guide_photos.photos(apartment["id"], item["id"]),
        max_photos=guide_photos.MAX_PER_ITEM,
    )


def _next_open(apartment_id: int, after_id: int) -> Optional[int]:
    """The next card in guest order that still needs the host, wrapping around."""
    rows = guest_guide.items(apartment_id)
    ids = [r["id"] for r in rows]
    start = ids.index(after_id) + 1 if after_id in ids else 0
    for row in rows[start:] + rows[:start]:
        if row["id"] != after_id and row["state"] in ("missing", "check"):
            return row["id"]
    return None


@router.get("/apartments/{apartment_id}/guide")
def guide_index(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    guest_guide.ensure_defaults(apartment)
    guide_token.ensure(apartment_id)
    rows = guest_guide.items(apartment_id)
    groups = [(topic, [r for r in rows if r["topic"] == topic]) for topic in guest_guide.TOPICS]
    return _render(
        request,
        "guest_guide.html",
        apartment=apartment,
        groups=[(topic, cards) for topic, cards in groups if cards],
        topics=guest_guide.TOPICS,
        must_have=guest_guide.MUST_HAVE,
        progress=guest_guide.progress(apartment_id),
        next_id=_next_open(apartment_id, 0),
        import_on=guest_guide_import.enabled(),
        import_left=guest_guide_import.imports_left(apartment_id),
        import_busy=guest_guide_import.in_progress(apartment_id),
        imports=guest_guide_import.imports(apartment_id),
        import_drafts=guest_guide_merge.drafted_count(apartment_id),
        questions_open=guest_handoff.open_count(apartment_id),
        usage=guide_translate.usage(apartment_id, ai.today().replace(day=1).isoformat()),
    )


@router.post("/apartments/{apartment_id}/guide/cards")
async def guide_add(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    try:
        item_id = guest_guide.add_custom(apartment_id, str(form.get("topic", "")), str(form.get("title", "")))
    except guest_guide.GuideError as exc:
        return back(_base(apartment_id), err=flash(request, exc.key))
    return back(f"{_base(apartment_id)}/{item_id}")


@router.post("/apartments/{apartment_id}/guide/import")
async def guide_import(request: Request, apartment_id: int):
    """Queue one Booking or Airbnb import (brief 0347). Must stay above the {item_id} routes."""
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    try:
        guest_guide_import.request_import(apartment_id, str(form.get("url", ""))[:guest_guide_import.MAX_URL_LENGTH])
    except guest_guide_import.GuideImportError as exc:
        return back(f"{_base(apartment_id)}#import", err=flash(request, exc.key))
    return back(f"{_base(apartment_id)}#import", msg=flash(request, "flash.guest_guide.import_queued"))


def _guest_url(apartment_id: int) -> str:
    return f"{config.PUBLIC_BASE_URL}/g/{guide_token.ensure(apartment_id)}"


@router.get("/apartments/{apartment_id}/guide/qr")
def guide_qr(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    url = _guest_url(apartment_id)
    return _render(
        request, "guest_guide_qr.html", apartment=apartment, guest_url=url,
        qr=payments.qr_data_uri(url), progress=guest_guide.progress(apartment_id),
    )


@router.get("/apartments/{apartment_id}/guide/qr.png")
def guide_qr_png(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    return Response(
        guide_token.qr_png(_guest_url(apartment_id)),
        media_type="image/png",
        headers={**PRIVATE, "Content-Disposition": 'attachment; filename="guest-guide-qr.png"'},
    )


@router.post("/apartments/{apartment_id}/guide/qr/rotate")
def guide_qr_rotate(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    guide_token.rotate(apartment_id)
    return back(f"{_base(apartment_id)}/qr", msg=flash(request, "flash.guest_guide.qr_rotated"))


@router.get("/apartments/{apartment_id}/guide/{item_id}")
def guide_card(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    item = guest_guide.get(apartment_id, item_id)
    if not item:
        raise HTTPException(404)
    return _card(request, apartment, item, item)


@router.post("/apartments/{apartment_id}/guide/{item_id}")
async def guide_card_save(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    item = guest_guide.get(apartment_id, item_id)
    if not item:
        raise HTTPException(404)
    form = await request.form()
    fields = {name: form.get(name, "") for name in guest_guide.LIMITS if name in form}
    fields["visibility"] = form.get("visibility", item["visibility"])
    try:
        guest_guide.save(apartment_id, item_id, fields)
    except guest_guide.GuideError as exc:
        values = {**item, **{k: str(v) for k, v in fields.items()}}
        return _card(request, apartment, item, values, error=exc.key, status_code=422)
    if form.get("then") == "next":
        next_id = _next_open(apartment_id, item_id)
        if next_id:
            return back(f"{_base(apartment_id)}/{next_id}", msg=flash(request, "flash.guest_guide.saved"))
    return back(_base(apartment_id), msg=flash(request, "flash.guest_guide.saved"))


@router.post("/apartments/{apartment_id}/guide/{item_id}/skip")
async def guide_card_skip(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    try:
        guest_guide.skip(apartment_id, item_id, skipped=form.get("skip") == "1")
    except guest_guide.GuideError:
        raise HTTPException(404) from None
    return back(_base(apartment_id))


@router.post("/apartments/{apartment_id}/guide/{item_id}/delete")
def guide_card_delete(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    item = guest_guide.get(apartment_id, item_id)
    if not item or item["kind"] != "custom":
        raise HTTPException(404)
    for photo in guide_photos.photos(apartment_id, item_id):
        guide_photos.delete(apartment_id, item_id, photo["id"])
    guest_guide.delete_custom(apartment_id, item_id)
    return back(_base(apartment_id), msg=flash(request, "flash.guest_guide.deleted"))


@router.post("/apartments/{apartment_id}/guide/{item_id}/photos")
async def guide_photo_add(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if not guest_guide.get(apartment_id, item_id):
        raise HTTPException(404)
    card_url = f"{_base(apartment_id)}/{item_id}"
    form = await request.form()
    upload = form.get("photo")
    if upload is None or not hasattr(upload, "read"):
        return back(card_url, err=flash(request, "flash.error.guide_photo_type"))
    content = await upload.read(guide_photos.MAX_UPLOAD_BYTES + 1)
    try:
        # Decoding and shrinking a phone photo is CPU work; keep it off the event loop.
        await run_in_threadpool(guide_photos.add, apartment_id, item_id, content, upload.content_type or "")
    except guest_guide.GuideError as exc:
        return back(card_url, err=flash(request, exc.key))
    return back(card_url, msg=flash(request, "flash.guest_guide.photo_added"))


@router.get("/apartments/{apartment_id}/guide/{item_id}/photos/{photo_id}")
def guide_photo_file(request: Request, apartment_id: int, item_id: int, photo_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    photo = guide_photos.get(apartment_id, item_id, photo_id)
    path = guide_photos.path_for(photo) if photo else None
    if not path or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/apartments/{apartment_id}/guide/{item_id}/photos/{photo_id}/delete")
def guide_photo_delete(request: Request, apartment_id: int, item_id: int, photo_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if not guide_photos.delete(apartment_id, item_id, photo_id):
        raise HTTPException(404)
    return back(f"{_base(apartment_id)}/{item_id}", msg=flash(request, "flash.guest_guide.photo_deleted"))
