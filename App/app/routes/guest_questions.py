"""Brief 0351: the host answers Leon's open questions.

Pages under the property's guest guide: a list of questions and one page per
question with the answer form. Every query goes through ``guest_guide._home``
(owner check, 404 for another host's property) and ``guest_handoff.get``
(the question must belong to that property). POSTs carry the CSRF token
(``security.protect_host_post`` on the router).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import auth, guest_guide, guest_handoff, security
from .admin_helpers import back, flash
from .guest_guide import _base, _home, _render

router = APIRouter(dependencies=[Depends(security.protect_host_post)])


def _page(request: Request, apartment, question, values=None, error: str = "", status_code: int = 200):
    return _render(
        request, "guest_question.html", status_code=status_code,
        apartment=apartment, question=question, values=values or {},
        error=error, topics=guest_guide.TOPICS,
        card_id=guest_handoff.card_for(question) if question["status"] == "answered" else None,
        max_chars=guest_handoff.MAX_ANSWER_CHARS,
    )


def _question(request: Request, apartment_id: int, question_id: int):
    apartment = _home(request, apartment_id)
    question = guest_handoff.get(apartment_id, question_id)
    if not question:
        raise HTTPException(404)
    return apartment, question


@router.get("/apartments/{apartment_id}/guide/questions")
def questions_index(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _home(request, apartment_id)
    guest_handoff.refresh_alert(apartment_id)
    rows = guest_handoff.questions(apartment_id)
    return _render(
        request, "guest_questions.html", apartment=apartment, questions=rows,
        open_count=sum(1 for r in rows if r["status"] == "open"),
    )


@router.get("/apartments/{apartment_id}/guide/questions/{question_id}")
def question_page(request: Request, apartment_id: int, question_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, question = _question(request, apartment_id, question_id)
    return _page(request, apartment, question)


@router.post("/apartments/{apartment_id}/guide/questions/{question_id}")
async def question_answer(request: Request, apartment_id: int, question_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, question = _question(request, apartment_id, question_id)
    form = await request.form()
    text = str(form.get("answer", ""))
    try:
        guest_handoff.answer(apartment_id, question_id, text)
    except guest_handoff.HandoffError as exc:
        return _page(request, apartment, question, values={"answer": text}, error=exc.key, status_code=422)
    return back(f"{_base(apartment_id)}/questions/{question_id}", msg=flash(request, "flash.guest_question.sent"))


@router.post("/apartments/{apartment_id}/guide/questions/{question_id}/dismiss")
def question_dismiss(request: Request, apartment_id: int, question_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _question(request, apartment_id, question_id)
    guest_handoff.dismiss(apartment_id, question_id)
    return back(f"{_base(apartment_id)}/questions", msg=flash(request, "flash.guest_question.dismissed"))


@router.post("/apartments/{apartment_id}/guide/questions/{question_id}/card")
async def question_card(request: Request, apartment_id: int, question_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, question = _question(request, apartment_id, question_id)
    form = await request.form()
    try:
        item_id = guest_handoff.add_to_guide(apartment_id, question_id, str(form.get("topic", "")))
    except (guest_handoff.HandoffError, guest_guide.GuideError) as exc:
        return _page(request, apartment, question, error=exc.key, status_code=422)
    return back(f"{_base(apartment_id)}/{item_id}", msg=flash(request, "flash.guest_question.card"))
