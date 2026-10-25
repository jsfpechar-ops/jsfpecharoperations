"""Havel, the AI support assistant: the page /havel and the form it posts to.

Plan: docs/plans/havel-support-assistant.md sections 2, 9, 11 and 17. The same
form lives inside the panel (0324); with the header ``X-Havel: 1`` the POST
answers with the thread fragment instead of the page. Without JavaScript the
page simply re-renders. The engine (``app.havel``) decides what is safe to
show; this module only wires the form, the limits and the copy.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from .. import access, ai, auth, havel, host_i18n, security
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
            "support_summary": None, "card": None}
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
                  *, topic: str = "", page: str = "", return_to: str = "/havel", error: Optional[str] = None) -> Dict[str, Any]:
    state, remaining = _state(request, uid)
    payload, sig = havel.sign_history(uid, exchanges)
    return {
        "havel_items": items, "havel_state": state, "havel_remaining": remaining, "havel_error": error,
        "havel_history": payload, "havel_history_sig": sig, "havel_topic": topic, "havel_page": page,
        "havel_return_to": return_to, "havel_max": havel.MAX_MESSAGE_CHARS,
        "havel_fresh": len(exchanges) == 0,
    }


@router.get("/havel")
def havel_page(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    uid = int(auth.current_user(request)["id"])
    topic = re.sub(r"[^a-z_]", "", request.query_params.get("topic", ""))[:30]
    ctx = _page_context(request, uid, _thread(request, [], None), [], topic=topic, page="guide")
    return render(request, "havel.html", ctx)


@router.post("/havel")
async def havel_send(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    uid = int(auth.current_user(request)["id"])
    form = await request.form()
    message = str(form.get("message", "")).strip()
    exchanges = havel.read_history(uid, str(form.get("history", "")), str(form.get("history_sig", "")))
    topic = re.sub(r"[^a-z_]", "", str(form.get("topic", "")))[:30]
    page = str(form.get("page", ""))
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
        if key:
            reply_text = _t(request, key)
        elif len(exchanges) >= havel.MAX_EXCHANGES:
            reply_text = _t(request, "havel.limit_turns")
            exchanges = []
        elif not ai.enabled(havel.FEATURE):
            reply_text, support = _t(request, "havel.off"), True
        else:
            limit = havel.limit_state(uid)
            if limit:
                reply_text, support = _t(request, f"havel.{limit}"), True
                havel.record_stat("limit_hit")
            else:
                host = havel.Host(user_id=uid, lang=host_i18n.lang_from_request(request), device=device,
                                  properties=_properties(request), page=page, topic=topic)
                try:
                    reply = await run_in_threadpool(havel.ask, host, exchanges, message)
                except ai.AIDisabled:
                    reply_text, support = _t(request, "havel.off"), True
                except ai.AIBudgetError as exc:
                    reply_text, support = _t(request, "havel.off" if exc.reason == "month" else "havel.resting"), True
                else:
                    havel.record_message(uid)
                    if reply.kind == "refuse":
                        havel.record_refusal(uid)
                    if reply.kind == "fail":
                        reply_text, support = _t(request, "havel.dont_know"), True
                    else:
                        reply_text = reply.text
                        links = list(reply.links)
                        if reply.action:  # 0314 replaces this with the confirm card
                            page_id = ACTION_FALLBACK_PAGE[reply.action["type"]]
                            url = havel.page_url(page_id, reply.action.get("property_id"), host.property_ids)
                            links.append((_t(request, "havel.card.open_form"), url))
                        items.append(_item("havel", reply_text, links=links, support=reply.kind == "escalate",
                                           support_summary=reply.support_summary))
        if len(items) == 1:
            items.append(_item("havel", reply_text, support=support))
        if reply_text != _t(request, "havel.limit_turns"):
            exchanges.append({"host": message, "havel": reply_text})
        last = {"items": items}

    if fragment:
        ctx = _page_context(request, uid, last["items"] if last else [], exchanges, topic=topic, page=page,
                            return_to=return_to, error=error)
        ctx["havel_fragment"] = True
        return render(request, "_havel_thread.html", ctx)
    ctx = _page_context(request, uid, _thread(request, exchanges, last), exchanges, topic=topic, page=page,
                        return_to=return_to, error=error)
    return render(request, "havel.html", ctx)
