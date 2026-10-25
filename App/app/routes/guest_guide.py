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
from .. import db, guide_facts, host_i18n, leon
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
    import_left = guest_guide_import.imports_left(apartment_id)  # 0403
    import_busy = guest_guide_import.in_progress(apartment_id)
    import_drafts = guest_guide_merge.drafted_count(apartment_id)
    import_first = guest_guide_import.enabled() and (import_left > 0 or import_busy or import_drafts > 0)  # 0403
    return _render(
        request,
        "guest_guide.html",
        apartment=apartment,
        groups=[(topic, cards) for topic, cards in groups if cards],
        topics=guest_guide.TOPICS,
        must_have=guest_guide.MUST_HAVE,
        progress=guest_guide.progress(apartment_id),
        next_id=_next_open(apartment_id, 0),
        quick_next=guide_facts.next_step(apartment_id),
        leon_offer=ai.enabled_for_property(leon.FEATURE, apartment_id),  # 0376
        leon_state=leon.host_state(apartment, bool(guest_guide.progress(apartment_id)["live"])),  # 0396
        import_on=guest_guide_import.enabled(),
        import_left=import_left,
        import_busy=import_busy,
        import_sources=guest_guide_import.sources_left(apartment_id),  # 0403
        import_first=import_first,  # 0403
        imports=guest_guide_import.imports(apartment_id),
        import_drafts=import_drafts,
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


def leon_card_state(apartment) -> Optional[str]:
    """0396: the Leon card on the property overview; None where Leon is not offered."""
    if not ai.enabled_for_property(leon.FEATURE, apartment["id"]):
        return None
    live = bool(guest_guide.progress(apartment["id"])["live"]) if apartment["leon_enabled"] else False
    return leon.host_state(apartment, live)


def _leon_utc(value: Optional[str]) -> str:
    return f"{value[:16].replace('T', ' ')} UTC" if value else ""


@router.get("/apartments/{apartment_id}/leon")
def leon_page(request: Request, apartment_id: int):
    """0396: the host's Leon (AI) page: what Leon does, the warnings, the terms accepted."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    if not ai.enabled_for_property(leon.FEATURE, apartment_id):
        raise HTTPException(404)
    progress = guest_guide.progress(apartment_id)
    accepted = None
    if apartment["leon_terms_accepted_by"]:
        accepted = db.query_one("SELECT email FROM user_account WHERE id = ?", (apartment["leon_terms_accepted_by"],))
    return _render(
        request, "leon_settings.html", apartment=apartment,
        state=leon.host_state(apartment, bool(progress["live"])), live=bool(progress["live"]),
        accepted_at=_leon_utc(apartment["leon_terms_accepted_at"]),
        accepted_by=accepted["email"] if accepted else "",
    )


@router.post("/apartments/{apartment_id}/leon")
async def leon_save(request: Request, apartment_id: int):
    """0396: the host switches Leon (AI) on after ticking the current terms, or off (always allowed)."""
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    page = f"/apartments/{apartment_id}/leon"
    if form.get("action") == "off":
        db.execute("UPDATE apartment SET leon_enabled = 0 WHERE id = ?", (apartment_id,))
        db.audit("leon_switched_off", f"apartment={apartment_id}")
        return back(page, msg=flash(request, "flash.guest_guide.leon_off"))
    if form.get("action") == "on":
        if not ai.enabled_for_property(leon.FEATURE, apartment_id):
            raise HTTPException(404)
        if form.get("terms") != "1":
            return back(page, err=flash(request, "flash.error.leon_terms"))
        account = auth.current_user(request)
        db.execute(
            "UPDATE apartment SET leon_enabled = 1, leon_terms_version = ?, leon_terms_accepted_at = ?, "
            "leon_terms_accepted_by = ? WHERE id = ?",
            (leon.LEON_TERMS_VERSION, db.utcnow(), account["id"] if account else None, apartment_id),
        )
        db.audit("leon_terms_accepted", f"apartment={apartment_id} version={leon.LEON_TERMS_VERSION}")
        return back(page, msg=flash(request, "flash.guest_guide.leon_on"))
    return back(page)


@router.post("/apartments/{apartment_id}/guide/import")
async def guide_import(request: Request, apartment_id: int):
    """Queue one Booking or Airbnb import (brief 0347). Must stay above the {item_id} routes."""
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    form = await request.form()
    cap = guest_guide_import.MAX_URL_LENGTH
    urls = [str(form.get(name, ""))[:cap] for name in ("booking_url", "airbnb_url", "url")]
    target = f"/apartments/{apartment_id}/leon/setup/import" if form.get("next") == "leon" else f"{_base(apartment_id)}#import"
    try:
        guest_guide_import.request_imports(apartment_id, urls)
    except guest_guide_import.GuideImportError as exc:
        return back(target, err=flash(request, exc.key))
    return back(target, msg=flash(request, "flash.guest_guide.import_queued"))


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


@router.get("/apartments/{apartment_id}/guide/quick")
def guide_quick(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    return back(f"{_base(apartment_id)}/quick/{guide_facts.next_step(apartment_id) or 'done'}")


@router.get("/apartments/{apartment_id}/guide/quick/done")
def guide_quick_done(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    guest_guide.ensure_defaults(apartment)
    lang = host_i18n.lang_from_request(request)
    lines = guide_facts.lines(apartment_id, lang)
    rows = guest_guide.items(apartment_id)
    answered = [
        (host_i18n.translate(lang, f"guest_guide.kind.{r['kind']}.title"), " ".join(lines[r["kind"]]))
        for r in rows if r["kind"] in lines
    ]
    return _render(
        request, "guest_guide_quick_done.html", apartment=apartment, answered=answered,
        open_cards=[r for r in rows if r["state"] in ("missing", "check")],
        progress=guest_guide.progress(apartment_id), next_id=_next_open(apartment_id, 0),
        first_step=guide_facts.STEPS[0],
    )


@router.get("/apartments/{apartment_id}/guide/quick/{step}")
def guide_quick_step(request: Request, apartment_id: int, step: str):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    if step not in guide_facts.STEPS:
        raise HTTPException(404)
    index = guide_facts.STEPS.index(step)
    return _render(
        request, "guest_guide_quick.html", apartment=apartment, step=step,
        step_index=index + 1, step_total=len(guide_facts.STEPS), last=index == len(guide_facts.STEPS) - 1,
        facts=guide_facts.step_fields(apartment_id, step),
    )


@router.post("/apartments/{apartment_id}/guide/quick/{step}")
async def guide_quick_save(request: Request, apartment_id: int, step: str):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if step not in guide_facts.STEPS:
        raise HTTPException(404)
    form = await request.form()
    if form.get("skip"):
        guide_facts.mark_seen(apartment_id, step)
    else:
        guide_facts.save_step(apartment_id, step, form)
    index = guide_facts.STEPS.index(step) + 1
    following = guide_facts.STEPS[index] if index < len(guide_facts.STEPS) else "done"
    return back(f"{_base(apartment_id)}/quick/{following}")


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


@router.post("/apartments/{apartment_id}/guide/{item_id}/discard")
def guide_card_discard(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if not guest_guide.discard_draft(apartment_id, item_id):
        raise HTTPException(404)
    return back(f"{_base(apartment_id)}/{item_id}", msg=flash(request, "flash.guest_guide.discarded"))


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
