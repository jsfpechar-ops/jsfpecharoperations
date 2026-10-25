"""Havel, the AI support assistant: the page /havel and the form it posts to.

Plan: docs/plans/havel-support-assistant.md sections 2, 9, 11 and 17. The same
form lives inside the panel (0324); with the header ``X-Havel: 1`` the POST
answers with the thread fragment instead of the page. Without JavaScript the
page simply re-renders. The engine (``app.havel``) decides what is safe to
show; this module only wires the form, the limits and the copy.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from .. import (access, ai, auth, cleaning_i18n, config, db, havel, havel_actions, havel_topics, host_i18n, mail,
                mail_notify, rate_limit, security)
from . import dashboard_calendar
from ..templating import render

router = APIRouter(dependencies=[Depends(security.protect_host_post)])

# The hosting page's nav key (base.html) -> the page id Havel knows (havel.PAGES).
NAV_TO_PAGE = {
    "dashboard": "dashboard", "reservations": "stays", "submissions": "reports", "housebook": "housebook",
    "apartments": "properties", "cleaning": "cleaning", "stay_fees": "stay_fees", "invoices": "invoices",
    "settings": "settings", "guide": "guide", "entities": "business", "smart_locks": "smart_locks",
}
# Where an action reply points until the confirm cards arrive (0314).
ACTION_FALLBACK_PAGE = {"show_guest_link": "property_guests", "new_pin": "property_guests", "create_stay": "add_stay",
                        "create_cleaning": "cleaning", "sync_calendars": "dashboard"}
_STEP = re.compile(r"^\d{1,2}\.\s+")


def _t(request: Request, key: str, **kw: Any) -> str:
    return host_i18n.translate(host_i18n.lang_from_request(request), key, **kw)


def _properties(request: Request) -> List[Dict[str, Any]]:
    rows = access.apartments(request, "id, internal_name, addr_obec")
    return [{"id": int(r["id"]), "name": r["internal_name"] or f"#{r['id']}", "city": r["addr_obec"] or ""} for r in rows]


def _feed_count(apartment_id: int) -> int:
    row = db.query_one("SELECT COUNT(*) AS n FROM ical_feed WHERE apartment_id = ? AND active = 1", (apartment_id,))
    return int(row["n"]) if row else 0


def _card(request: Request, action: Dict[str, Any], return_to: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(card, None) or (None, reason sentence)."""
    rows = list(access.apartments(request, "*"))
    try:
        card = havel_actions.prepare(action, rows, date.today(), return_to=return_to,
                                     overlaps=dashboard_calendar.overlapping_count, feed_count=_feed_count)
    except havel_actions.NotPrepared as exc:
        return None, _t(request, "havel.card.not_prepared", reason=_t(request, f"havel.reason.{exc.reason}"))
    card["cleaning_words"] = cleaning_i18n.translator(host_i18n.lang_from_request(request))
    return card, None


def blocks(text: str) -> List[Dict[str, Any]]:
    """Paragraphs and numbered steps as blocks, so steps render as a real list."""
    out: List[Dict[str, Any]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if _STEP.match(line):
            if not out or out[-1]["kind"] != "ol":
                out.append({"kind": "ol", "items": []})
            out[-1]["items"].append(_STEP.sub("", line))
        else:
            out.append({"kind": "p", "text": line})
    return out


def _item(role: str, text: str, **extra: Any) -> Dict[str, Any]:
    item = {"role": role, "text": text, "blocks": blocks(text), "links": [], "support": False,
            "support_summary": None, "next": [], "card": None}
    item.update(extra)
    return item


def _thread(request: Request, exchanges: List[Dict[str, str]], last: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = [_item("havel", _t(request, "havel.intro"))]
    for exchange in exchanges[:-1] if last else exchanges:
        items.append(_item("host", exchange["host"]))
        items.append(_item("havel", exchange["havel"]))
    if last:
        items.extend(last["items"])
    return items


def _state(request: Request, uid: int) -> Tuple[Optional[str], str]:
    """(state, remaining line). state is None, 'off' or a limit key suffix."""
    n, period = havel.remaining(uid)
    line = _t(request, f"havel.remaining_{period}", n=n)
    if not ai.enabled(havel.FEATURE):
        return "off", line
    return havel.limit_state(uid), line


def _page_context(request: Request, uid: int, items: List[Dict[str, Any]], exchanges: List[Dict[str, str]],
                  *, topic: str = "", q: str = "", page: str = "", return_to: str = "/havel",
                  error: Optional[str] = None) -> Dict[str, Any]:
    state, remaining = _state(request, uid)
    payload, sig = havel.sign_history(uid, exchanges)
    nav = next((k for k, v in NAV_TO_PAGE.items() if v == page), "")
    ids = [p["id"] for p in _properties(request)]
    return {
        "havel_items": items, "havel_state": state, "havel_remaining": remaining, "havel_error": error,
        "havel_history": payload, "havel_history_sig": sig, "havel_topic": topic, "havel_q": q, "havel_page": page,
        "havel_return_to": return_to, "havel_max": havel.MAX_MESSAGE_CHARS,
        "havel_fresh": len(exchanges) == 0,
        "havel_topics": havel_topics.ordered(nav), "havel_topic_data": havel_topics.topic(topic) if topic else None,
        "havel_answer": havel_topics.answer(host_i18n.lang_from_request(request), topic, q) if topic and q else None,
        "havel_show_topics": len(exchanges) == 0 and not items,
        "havel_support_to": mail.mask_email(str((auth.current_user(request) or {"email": ""})["email"] or "")),
        "havel_support_blocked": havel.support_blocked(uid),
        "pages": havel.PAGES,
        "page_url": lambda page_id: havel.page_url(page_id, ids[0] if ids else None, ids),
    }


def _clean_id(value: str) -> str:
    return re.sub(r"[^a-z_]", "", value)[:30]


@router.get("/havel")
def havel_page(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    uid = int(auth.current_user(request)["id"])
    topic = _clean_id(request.query_params.get("topic", ""))
    q = _clean_id(request.query_params.get("q", ""))
    if topic not in havel_topics.TOPIC_IDS:
        topic, q = "", ""
    page = NAV_TO_PAGE.get(request.query_params.get("page", ""), "guide")
    ctx = _page_context(request, uid, [], [], topic=topic, q=q, page=page,
                        return_to=security.safe_local_path(request.query_params.get("return_to", ""), "/havel"))
    if request.headers.get("x-havel") == "1":
        ctx["havel_fragment"] = True
        return render(request, "_havel_fragment.html", ctx)
    return render(request, "havel.html", ctx)


def _forward(request: Request, uid: int, message: str, exchanges: List[Dict[str, str]], page: str,
             reason: str) -> bool:
    """0333: a limit was hit, so the host's message goes to support instead of the model.

    False when the weekly support cap is used up; the caller then shows the limit text.
    """
    if havel.support_blocked(uid):
        return False
    account = auth.current_user(request)
    workspace = auth.workspace_user(request) or account
    mail_notify.havel_support(
        user_id=uid, account_email=str(account["email"] or ""),
        workspace=str(workspace["display_name"] or workspace["username"] or ""),
        lang=host_i18n.lang_from_request(request), page=page,
        summary=f"Havel limit reached ({reason}). The host's message below was forwarded without an AI answer.",
        note=message, turns=[exchange["host"] for exchange in exchanges][-4:],
    )
    rate_limit.record("havel_support", str(uid))
    havel.record_stat("support_forwarded")
    return True


@router.post("/havel")
async def havel_send(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    uid = int(auth.current_user(request)["id"])
    form = await request.form()
    message = str(form.get("message", "")).strip()
    exchanges = havel.read_history(uid, str(form.get("history", "")), str(form.get("history_sig", "")))
    topic = _clean_id(str(form.get("topic", "")))
    q = _clean_id(str(form.get("q", "")))
    if topic not in havel_topics.TOPIC_IDS:
        topic, q = "", ""
    page = str(form.get("page", ""))
    page = NAV_TO_PAGE.get(page, page)
    page = page if page in havel.PAGES else ""
    device = "phone" if form.get("device") == "phone" else "computer"
    return_to = security.safe_local_path(str(form.get("return_to", "")), "/havel")
    fragment = request.headers.get("x-havel") == "1"
    if form.get("reset") == "1":
        exchanges = []
    error = None
    last: Optional[Dict[str, Any]] = None

    if message and len(message) > havel.MAX_MESSAGE_CHARS:
        error = _t(request, "havel.too_long")
    elif message:
        items = [_item("host", message)]
        key = havel.local_reply(message)
        support = False
        forward, prior = "", exchanges
        if key:
            reply_text = _t(request, key)
        elif len(exchanges) >= havel.MAX_EXCHANGES:
            forward = "conversation"
            reply_text = _t(request, "havel.limit_turns")
            exchanges = []
        elif not ai.enabled(havel.FEATURE):
            reply_text, support = _t(request, "havel.off"), True
        else:
            limit = havel.limit_state(uid)
            if limit:
                reply_text, support = _t(request, f"havel.{limit}"), True
                havel.record_stat("limit_hit")
                forward = limit if limit in ("limit_week", "limit_month") else ""
            else:
                host = havel.Host(user_id=uid, lang=host_i18n.lang_from_request(request), device=device,
                                  properties=_properties(request), page=page, topic=topic, read_keys=havel_topics.read_keys(topic, q))
                try:
                    reply = await run_in_threadpool(havel.ask, host, exchanges, message)
                except ai.AIDisabled:
                    reply_text, support = _t(request, "havel.off"), True
                except ai.AIBudgetError as exc:
                    reply_text, support = _t(request, "havel.off" if exc.reason == "month" else "havel.resting"), True
                    forward = "budget_" + exc.reason
                else:
                    havel.record_message(uid)
                    if reply.kind in ("escalate", "fail"):
                        havel.record_gap(host_i18n.lang_from_request(request), page, reply.kind, message)
                    if reply.kind == "refuse":
                        havel.record_refusal(uid)
                    if reply.kind == "fail":
                        reply_text, support = _t(request, "havel.dont_know"), True
                    else:
                        reply_text = reply.text
                        links = list(reply.links)
                        card = None
                        if reply.action:
                            card, not_prepared = _card(request, reply.action, return_to)
                            if not_prepared:
                                reply_text = f"{reply_text}\n{not_prepared}".strip()
                                page_id = ACTION_FALLBACK_PAGE[reply.action["type"]]
                                url = havel.page_url(page_id, reply.action.get("property_id"), host.property_ids)
                                links.append((_t(request, "havel.card.open_form"), url))
                        items.append(_item("havel", reply_text, links=links, support=reply.kind == "escalate",
                                           support_summary=reply.support_summary, card=card, next=reply.next,
                                           not_helped=reply.kind in ("answer", "clarify")))
        if forward and _forward(request, uid, message, prior, page, forward):
            reply_text, support = _t(request, "havel.forwarded"), False
        if len(items) == 1:
            items.append(_item("havel", reply_text, support=support))
        if reply_text != _t(request, "havel.limit_turns"):
            exchanges.append({"host": message, "havel": reply_text})
        last = {"items": items}

    if fragment:
        ctx = _page_context(request, uid, last["items"] if last else [], exchanges, topic=topic, q=q, page=page,
                            return_to=return_to, error=error)
        ctx["havel_fragment"] = True
        return render(request, "_havel_fragment.html", ctx)
    ctx = _page_context(request, uid, _thread(request, exchanges, last), exchanges, topic=topic, q=q, page=page,
                        return_to=return_to, error=error)
    return render(request, "havel.html", ctx)


@router.post("/havel/support")
async def havel_support(request: Request):
    """Plan section 8: the host's one tap sends the summary to UbyHost support."""
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    uid = int(account["id"])
    form = await request.form()
    exchanges = havel.read_history(uid, str(form.get("history", "")), str(form.get("history_sig", "")))
    page = str(form.get("page", ""))
    page = page if page in havel.PAGES else ""
    return_to = security.safe_local_path(str(form.get("return_to", "")), "/havel")
    summary = str(form.get("summary", "")).strip()[: havel.MAX_SUMMARY_CHARS]
    note = str(form.get("note", "")).strip()[: havel.MAX_MESSAGE_CHARS]
    items = _thread(request, exchanges, None)
    if havel.support_blocked(uid):
        items.append(_item("havel", _t(request, "havel.support.limit", email=config.OPERATOR_EMAIL)))
    elif not summary and not note:
        items.append(_item("havel", _t(request, "havel.support.empty"), support=True))
    else:
        workspace = auth.workspace_user(request) or account
        mail_notify.havel_support(
            user_id=uid, account_email=str(account["email"] or ""),
            workspace=str(workspace["display_name"] or workspace["username"] or ""),
            lang=host_i18n.lang_from_request(request), page=page, summary=summary, note=note,
            turns=[exchange["host"] for exchange in exchanges][-4:],
        )
        rate_limit.record("havel_support", str(uid))
        havel.record_stat("support_sent")
        items.append(_item("havel", _t(request, "havel.support.sent")))
    ctx = _page_context(request, uid, items, exchanges, page=page, return_to=return_to)
    return render(request, "havel.html", ctx)


NOT_HELPED_PER_DAY = 5


@router.post("/havel/not-helped")
async def havel_not_helped(request: Request):
    """"This didn't help": the last question (from the signed history) goes to the gap log."""
    guard = auth.require_login(request)
    if guard:
        return guard
    uid = int(auth.current_user(request)["id"])
    form = await request.form()
    exchanges = havel.read_history(uid, str(form.get("history", "")), str(form.get("history_sig", "")))
    page = str(form.get("page", ""))
    page = page if page in havel.PAGES else ""
    question = exchanges[-1]["host"] if exchanges else ""
    if question and not rate_limit.blocked("havel_gap", str(uid), NOT_HELPED_PER_DAY, 86400):
        rate_limit.record("havel_gap", str(uid))
        havel.record_gap(host_i18n.lang_from_request(request), page, "not_helped", question)
        havel.record_stat("not_helped")
    items = _thread(request, exchanges, None)
    items.append(_item("havel", _t(request, "havel.not_helped_ack"), support=True, support_summary=question))
    return render(request, "havel.html", _page_context(request, uid, items, exchanges, page=page))
