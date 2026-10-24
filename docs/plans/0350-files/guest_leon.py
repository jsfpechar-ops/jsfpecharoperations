"""0350: Leon (AI) endpoints behind the two guide doors (JSON; the chat UI is brief 0352).

Stay door: ``/l/{token}/{reservation_id}/guide/leon``, the same gate as the
stay guide (``_stay_gate``), level from ``booked_level``; one conversation per
stay. QR door: ``/g/{token}/leon``, the QR rate limit and token lookup
(``_qr_apartment``), always level "everyone"; one conversation per browser,
keyed by the HttpOnly ``ubyhost_leon`` cookie (random, set on the first POST).
Both: 404 while the guide is not live. POST takes the form field ``message``;
GET returns the conversation. Never log message text.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from .. import auth, db, guest_guide, leon, rate_limit, security
from ..leon import LEON_COOKIE
from .guest import _host_contact
from .guest_guide_view import HARDEN, _qr_apartment, _stay_gate, booked_level

router = APIRouter(dependencies=[Depends(security.protect_guest_post)])


def _json(body: Dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status_code, headers=HARDEN)


def _gone() -> JSONResponse:
    return _json({"error": "not_found"}, 404)


def _conversation(chat: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not chat:
        return {"messages": [], "open_questions": 0, "answering": False}
    open_row = db.query_one(
        "SELECT COUNT(*) AS n FROM guest_question WHERE chat_id = ? AND status = 'open'", (chat["id"],)
    )
    shown = [
        {"role": m["role"], "kind": m["kind"], "text": m["text"], "at": m["created_at"]}
        for m in leon.messages(int(chat["id"]))
    ]
    return {"messages": shown, "open_questions": int(open_row["n"]) if open_row else 0, "answering": leon.answering(chat)}


async def _answer(chat: Dict[str, Any], message: str, *, level: str, apartment, lang: str,
                  request: Request, client_id: str = "") -> Dict[str, Any]:
    host = _host_contact(apartment).get("name", "")
    result = await run_in_threadpool(
        leon.reply, chat, message, level=level, property_name=apartment["internal_name"] or "",
        host_name=host, address_key=rate_limit.client_key(request, "leon"), lang=lang,
        client_id=client_id or None,
    )
    return {"kind": result["kind"], "text": result["text"], "asked_host": result["question_id"] is not None}


# --- the stay door ---------------------------------------------------------------

@router.get("/l/{token}/{reservation_id}/guide/leon")
def stay_leon_history(token: str, reservation_id: int, request: Request):
    apartment, reservation, token, lang, early = _stay_gate(request, token, reservation_id)
    if early or not guest_guide.progress(apartment["id"])["live"]:
        return _gone()
    row = db.query_one("SELECT * FROM guest_chat WHERE door = 'stay' AND reservation_id = ?", (reservation["id"],))
    return _json(_conversation(dict(row) if row else None))


@router.post("/l/{token}/{reservation_id}/guide/leon")
async def stay_leon(token: str, reservation_id: int, request: Request, message: str = Form(""), client_id: str = Form("")):
    apartment, reservation, token, lang, early = _stay_gate(request, token, reservation_id)
    if early or not guest_guide.progress(apartment["id"])["live"]:
        return _gone()
    chat = leon.stay_chat(apartment["id"], reservation["id"], lang)
    body = await _answer(chat, message, level=booked_level(reservation), apartment=apartment, lang=lang,
                         request=request, client_id=client_id)
    return _json(body)


# --- the QR door -------------------------------------------------------------------

@router.get("/g/{token}/leon")
def qr_leon_history(token: str, request: Request):
    apartment, lang, early = _qr_apartment(request, token)
    if early or not guest_guide.progress(apartment["id"])["live"]:
        return _gone()
    cookie = request.cookies.get(LEON_COOKIE)
    row = None
    if leon.cookie_id_ok(cookie):
        row = db.query_one(
            "SELECT * FROM guest_chat WHERE door = 'qr' AND apartment_id = ? AND cookie_id = ?", (apartment["id"], cookie)
        )
    return _json(_conversation(dict(row) if row else None))


@router.post("/g/{token}/leon")
async def qr_leon(token: str, request: Request, message: str = Form(""), client_id: str = Form("")):
    apartment, lang, early = _qr_apartment(request, token)
    if early or not guest_guide.progress(apartment["id"])["live"]:
        return _gone()
    # Every QR post also counts as a QR page view, so one address cannot mint endless conversations.
    rate_limit.record("guide_qr", rate_limit.client_key(request, "guide_qr"))
    cookie = request.cookies.get(LEON_COOKIE)
    fresh = not leon.cookie_id_ok(cookie)
    if fresh:
        cookie = leon.new_cookie_id()
    chat = leon.qr_chat(apartment["id"], cookie, lang)
    # A QR sticker outlives every stay: everyone level only, and only the host's name.
    response = _json(await _answer(chat, message, level="everyone", apartment=apartment, lang=lang, request=request,
                                      client_id=client_id))
    if fresh:
        response.set_cookie(
            LEON_COOKIE, cookie, max_age=60 * 60 * 24 * leon.COOKIE_DAYS, httponly=True,
            samesite="lax", secure=auth.secure_cookies(), path=f"/g/{token}",
        )
    return response
