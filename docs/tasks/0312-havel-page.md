# 0312: The Havel page `/havel` (route, thread, composer, copy in en, cs, vi)

Status: todo
Depends on: 0311 | Base commit: 92646d3 plus the 0310–0311 commits | Branch: task/0312-havel-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the page `/havel`: a normal form that posts to `/havel`, re-renders the conversation (works without JavaScript), applies the limits and free local replies from the engine, shows the remaining-messages line, link buttons and the AI label, and can also answer with a thread fragment for the panel that 0313 adds. All Havel copy lands in `host_i18n.py` (en, cs) and `host_vi_i18n.py` (vi). Confirm cards come in 0314; until then an action reply ends in a link button to the normal form.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` sections 2, 9, 11, 17b (panel states), 17e (copy). Rules: AGENTS.md 6 (light mode), 7 (browser and geometry tests, screenshots), 9 (copy), MASTER 7.1 (buttons), 8 (tone), 10 (never do), 11.0 (layout guard: a new host page adds its route to `ROUTES`).

Repo facts, verified 2026-10-24:
- Engine (0311): `havel.Host(user_id, lang, device, properties, page, topic, read_keys)`, `havel.ask(host, history, message) -> Reply` (`kind` in answer, clarify, action, escalate, refuse, fail; `.text`, `.links` as `(label, url)`, `.action`, `.support_summary`), `havel.read_history / sign_history`, `havel.limit_state(uid)` (None or `paused`, `limit_burst`, `limit_week`, `limit_month`), `havel.remaining(uid) -> (n, period)`, `havel.record_message`, `havel.record_refusal`, `havel.record_stat`, `havel.local_reply(text) -> key or None`, `havel.MAX_MESSAGE_CHARS`, `havel.MAX_EXCHANGES`, `havel.PAGES`, `havel.page_url`. Exceptions from `ai`: `AIDisabled`, `AIBudgetError` (`.reason` `month` or `day`).
- Routers take CSRF as a dependency, `App/app/routes/cleaning.py` line 13:

```python
router = APIRouter(dependencies=[Depends(security.protect_host_post)])
```

- Rendering, `App/app/templating.py` line 561: `def render(request: Request, name: str, context: Optional[Dict[str, Any]] = None, status_code: int = 200):` adds `request`, `csrf_token`, `current_user`, `workspace_user`, flash from `?msg=`/`?err=`. The language is `request.state.lang`. Template globals include `t(key, **kw)`, `operator()` (with `.email`), `icon` via `{% from "_icons.html" import icon with context %}`, `ui_button` from `_ui.html`.
- The guide route pattern (`App/app/routes/admin.py` line 508): `@router.get("/guide")`, `guard = auth.require_login(request)`, `if guard: return guard`, then `render(...)`.
- `App/app/main.py` line 32: `from .routes import admin, cleaning as cleaning_routes, dev_ui, guest, invoices, legal, mail_unsubscribe, onboarding_wizard, stay_fees`; line 355: `app.include_router(cleaning_routes.router)`.
- `App/app/templates/guide.html` lines 1–7 show the page skeleton (`{% extends "host_page.html" %}`, `{% set nav = 'guide' %}`, `{% set body_kind = 'detail' %}`, blocks `title`, `page_title`, `meta`, `body`).
- `App/app/host_i18n.py`: the `STRINGS["en"]` block ends with the line `        "settings.archive_hint": "Restore archived stays, properties, and house-book entries.",` followed by `    },` and `    "cs": {`; the `STRINGS["cs"]` block ends with `        "settings.archive_hint": "Obnovte archivované pobyty, ubytování a záznamy domovní knihy.",` followed by `    },` and `}`.
- `App/app/host_vi_i18n.py`: the flat `STRINGS` dict ends with `    "stay_fees.pay.add_account": "Thêm tài khoản",` followed by `}`.
- `App/app/templates/base.html` line 26: `  <link rel="stylesheet" href="/static/host2.css?v=20261022-0289">`. A changed static file needs a new key and `cd App && .venv/bin/python tests/test_static_versions.py --write`.
- `App/tests/test_design_guardrails_browser.py` lines 34–47: `ROUTES.update({ ... "settings-account": "/settings", })`. The a11y guard reuses `ROUTES`.
- `docs/design/catalog.json`: keys `classes` (list), `hooks`, `enforced_templates`, `enforced_stylesheets` (`host2.css` is enforced: tokens only, no raw px except `0` and `1px`), `class_notes`. The lint is `python3 scripts/design_lint.py`.
- Test fixture: `from tests.test_submission_retry_cap import host as host` gives a signed-in `TestClient` (an admin with no property). `tests/ai_fake.py` (0310) gives `FakeClient`, `reply`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/havel.py | new | GET and POST `/havel` |
| App/app/templates/_icons.html | edit | the one new icon `message-circle-question` (step with the icon) |
| App/app/main.py | edit | import and include the router |
| App/app/templates/havel.html | new | the page |
| App/app/templates/_havel_thread.html | new | bubbles, links, support exit (reused by the panel, 0324) |
| App/app/templates/_havel_form.html | new | composer and hidden fields (reused by 0313 and 0324) |
| App/app/static/host2.css | append | thread, bubbles, composer |
| App/app/templates/base.html | edit | host2.css key |
| App/tests/static_versions.json | regenerate | `--write` |
| App/app/host_i18n.py | edit | `havel.*` en and cs |
| docs/design/catalog.json | edit | classes and enforced templates |
| docs/design/pages/havel.md | new | page file |
| App/tests/test_design_guardrails_browser.py | edit | `ROUTES["havel"]` |
| App/tests/test_havel_page.py | new | unit tests |
| docs/tasks/0312-report.md | new | report |

No other file may change.

## 4. Steps

Commit after each step: `0312 step k`.

1. **Copy, English.** In `App/app/host_i18n.py`, directly after the line `        "settings.archive_hint": "Restore archived stays, properties, and house-book entries.",` (the last key of `STRINGS["en"]`), insert:

```python
        # 0312: Havel, the AI support assistant (plan section 17e). "AI" is never dropped from the name.
        "havel.name": "Havel (AI)",
        "havel.title": "Havel (AI) · Support assistant",
        "havel.subtitle": "Support assistant",
        "havel.launcher": "Ask Havel (AI)",
        "havel.open_page": "Open as a page",
        "havel.close": "Close",
        "havel.intro": "Hello, I'm Havel, UbyHost's AI assistant. Pick a topic below or ask me how something works. I explain step by step, and nothing changes until you confirm it.",
        "havel.ai_note": "Havel is an AI and can make mistakes. Check every card before you confirm. Don't type passwords or guests' document numbers.",
        "havel.topics_title": "What do you need help with?",
        "havel.topic.stays": "Add or change a stay",
        "havel.topic.guest_link": "Guest link and PIN",
        "havel.topic.reporting": "Police reporting",
        "havel.topic.calendars": "Calendars (Airbnb, Booking)",
        "havel.topic.wrong": "Something is wrong",
        "havel.topic.back": "All topics",
        "havel.topic.ask": "Still need help? Ask Havel",
        "havel.topic.guide": "Read more in the guide",
        "havel.q.stays.add": "How do I add a stay by hand?",
        "havel.q.stays.change": "What can I change on a stay?",
        "havel.q.stays.cancelled": "A booking was cancelled or moved",
        "havel.q.guest_link.how": "How do guests register?",
        "havel.q.guest_link.where": "Where do I find the link and PIN?",
        "havel.q.guest_link.broken": "A guest says the link does not work",
        "havel.q.reporting.when": "When is a guest reported?",
        "havel.q.reporting.colours": "What do the colours mean?",
        "havel.q.reporting.czech": "Is a Czech guest reported?",
        "havel.q.calendars.connect": "How do I connect a calendar?",
        "havel.q.calendars.stale": "The calendar did not update",
        "havel.q.wrong.report": "A report failed or shows red",
        "havel.q.wrong.error": "I see an error or something is missing",
        "havel.placeholder": "Write your question here",
        "havel.send": "Send",
        "havel.writing": "Havel is writing…",
        "havel.you": "You",
        "havel.new": "New conversation",
        "havel.remaining_week": "%(n)s messages left this week",
        "havel.remaining_month": "%(n)s messages left this month",
        "havel.greeting": "Hello. Ask me how something works in UbyHost, or pick a topic above.",
        "havel.thanks": "You're welcome. I'm here if anything else comes up.",
        "havel.too_long": "Please keep your message under 600 characters.",
        "havel.error": "Something went wrong on our side. Please try again in a moment.",
        "havel.retry": "Try again",
        "havel.not_helped": "This didn't help",
        "havel.dont_know": "I don't know that, and I don't want to guess. I can forward your question to the UbyHost team. They usually reply within a few hours.",
        "havel.fallback": "I couldn't answer that just now. You can forward it to the UbyHost team. They usually reply within a few hours.",
        "havel.off": "Havel is unavailable right now. You can still write to support here.",
        "havel.limit_burst": "Let's take a short break. You can write again in a few minutes.",
        "havel.limit_week": "You've used this week's messages for Havel. They come back on Monday. The guide and support are always here.",
        "havel.limit_month": "You've used this month's messages for Havel. They come back on the 1st. The guide and support are always here.",
        "havel.paused": "I can only help with UbyHost, so I'll pause until Monday. Support is still here.",
        "havel.resting": "Havel is resting until tomorrow. You can still write to support here.",
        "havel.limit_turns": "Let's start a fresh conversation.",
        "havel.card.title_stay": "Add this stay?",
        "havel.card.title_cleaning": "Add this cleaning?",
        "havel.card.title_sync": "Refresh all calendars?",
        "havel.card.title_pin": "Make a new PIN?",
        "havel.card.title_link": "Guest link",
        "havel.card.confirm_stay": "Add stay",
        "havel.card.confirm_cleaning": "Add cleaning",
        "havel.card.confirm_sync": "Refresh calendars",
        "havel.card.confirm_pin": "Make a new PIN",
        "havel.card.change": "Change",
        "havel.card.cancel": "Cancel",
        "havel.card.nights": "%(n)s nights",
        "havel.card.guests": "%(n)s guests",
        "havel.card.pin": "PIN",
        "havel.card.copy_link": "Copy link",
        "havel.card.open_guest_links": "Open Guest links",
        "havel.card.overlap": "This overlaps another stay at this property.",
        "havel.card.pin_warning": "The current PIN stops working at once, also for guests who are registering now.",
        "havel.card.not_prepared": "I couldn't prepare this: %(reason)s",
        "havel.card.open_form": "Open the form",
        "havel.reason.property": "I'm not sure which property you mean.",
        "havel.reason.dates": "The dates aren't clear to me.",
        "havel.reason.no_calendar": "No calendar is connected yet.",
        "havel.reason.no_link": "This property has no guest link yet.",
        "havel.reason.archived": "This property is archived or switched off.",
        "havel.support.title": "Send to UbyHost support",
        "havel.support.add": "Anything to add?",
        "havel.support.send": "Send to support",
        "havel.support.sent": "Forwarded to the UbyHost team. They know about it and usually reply within a few hours.",
        "havel.support.replies_to": "Support replies to %(email)s",
        "havel.support.mailto": "E-mail support",
```

   Command: `cd App && .venv/bin/python -c "from app import host_i18n as h; print(h.translate('en','havel.remaining_week', n=7), '|', h.translate('en','havel.card.title_pin'))"`. Expected: `7 messages left this week | Make a new PIN?`.

2. **Copy, Czech.** In `App/app/host_i18n.py`, directly after the line `        "settings.archive_hint": "Obnovte archivované pobyty, ubytování a záznamy domovní knihy.",` (the last key of `STRINGS["cs"]`), insert:

```python
        # 0312: Havel (plan section 17e).
        "havel.name": "Havel (AI)",
        "havel.title": "Havel (AI) · Asistent podpory",
        "havel.subtitle": "Asistent podpory",
        "havel.launcher": "Zeptat se Havla (AI)",
        "havel.open_page": "Otevřít jako stránku",
        "havel.close": "Zavřít",
        "havel.intro": "Dobrý den, jsem Havel, AI asistent UbyHostu. Vyberte si téma níže nebo se zeptejte, jak něco funguje. Vysvětlím to krok za krokem a nic se nezmění, dokud to nepotvrdíte.",
        "havel.ai_note": "Havel je umělá inteligence a může se splést. Každou kartu si před potvrzením zkontrolujte. Nepište sem hesla ani čísla dokladů hostů.",
        "havel.topics_title": "S čím potřebujete pomoct?",
        "havel.topic.stays": "Přidat nebo změnit pobyt",
        "havel.topic.guest_link": "Odkaz pro hosty a PIN",
        "havel.topic.reporting": "Hlášení na policii",
        "havel.topic.calendars": "Kalendáře (Airbnb, Booking)",
        "havel.topic.wrong": "Něco nefunguje",
        "havel.topic.back": "Všechna témata",
        "havel.topic.ask": "Potřebujete víc? Zeptejte se Havla",
        "havel.topic.guide": "Více v nápovědě",
        "havel.q.stays.add": "Jak přidám pobyt ručně?",
        "havel.q.stays.change": "Co můžu u pobytu změnit?",
        "havel.q.stays.cancelled": "Rezervace byla zrušena nebo přesunuta",
        "havel.q.guest_link.how": "Jak se hosté registrují?",
        "havel.q.guest_link.where": "Kde najdu odkaz a PIN?",
        "havel.q.guest_link.broken": "Host říká, že odkaz nefunguje",
        "havel.q.reporting.when": "Kdy se host hlásí?",
        "havel.q.reporting.colours": "Co znamenají barvy?",
        "havel.q.reporting.czech": "Hlásí se český host?",
        "havel.q.calendars.connect": "Jak připojím kalendář?",
        "havel.q.calendars.stale": "Kalendář se neaktualizoval",
        "havel.q.wrong.report": "Hlášení selhalo nebo je červené",
        "havel.q.wrong.error": "Vidím chybu nebo něco chybí",
        "havel.placeholder": "Sem napište svou otázku",
        "havel.send": "Odeslat",
        "havel.writing": "Havel píše…",
        "havel.you": "Vy",
        "havel.new": "Nový rozhovor",
        "havel.remaining_week": "Tento týden zbývá zpráv: %(n)s",
        "havel.remaining_month": "Tento měsíc zbývá zpráv: %(n)s",
        "havel.greeting": "Dobrý den. Zeptejte se, jak něco v UbyHostu funguje, nebo vyberte téma výše.",
        "havel.thanks": "Rádo se stalo. Kdyby bylo cokoli dalšího, jsem tu.",
        "havel.too_long": "Zprávu prosím zkraťte pod 600 znaků.",
        "havel.error": "Něco se nepovedlo na naší straně. Zkuste to prosím za chvíli znovu.",
        "havel.retry": "Zkusit znovu",
        "havel.not_helped": "Nepomohlo to",
        "havel.dont_know": "To nevím a nechci hádat. Můžu vaši otázku předat týmu UbyHostu. Obvykle odpoví do několika hodin.",
        "havel.fallback": "Teď jsem na to nedokázal odpovědět. Můžete to předat týmu UbyHostu. Obvykle odpoví do několika hodin.",
        "havel.off": "Havel teď není k dispozici. Podpoře můžete napsat tady.",
        "havel.limit_burst": "Dáme si krátkou pauzu. Za pár minut můžete psát dál.",
        "havel.limit_week": "Zprávy pro Havla na tento týden jste vyčerpali. Vrátí se v pondělí. Nápověda a podpora jsou tu pořád.",
        "havel.limit_month": "Zprávy pro Havla na tento měsíc jste vyčerpali. Vrátí se 1. dne v měsíci. Nápověda a podpora jsou tu pořád.",
        "havel.paused": "Můžu pomáhat jen s UbyHostem, tak si dám pauzu do pondělí. Podpora je tu pořád.",
        "havel.resting": "Havel odpočívá do zítřka. Podpoře můžete napsat tady.",
        "havel.limit_turns": "Začneme nový rozhovor.",
        "havel.card.title_stay": "Přidat tento pobyt?",
        "havel.card.title_cleaning": "Přidat tento úklid?",
        "havel.card.title_sync": "Obnovit všechny kalendáře?",
        "havel.card.title_pin": "Vytvořit nový PIN?",
        "havel.card.title_link": "Odkaz pro hosty",
        "havel.card.confirm_stay": "Přidat pobyt",
        "havel.card.confirm_cleaning": "Přidat úklid",
        "havel.card.confirm_sync": "Obnovit kalendáře",
        "havel.card.confirm_pin": "Vytvořit nový PIN",
        "havel.card.change": "Změnit",
        "havel.card.cancel": "Zrušit",
        "havel.card.nights": "Nocí: %(n)s",
        "havel.card.guests": "Hostů: %(n)s",
        "havel.card.pin": "PIN",
        "havel.card.copy_link": "Kopírovat odkaz",
        "havel.card.open_guest_links": "Otevřít Odkazy pro hosty",
        "havel.card.overlap": "Překrývá se s jiným pobytem v tomto ubytování.",
        "havel.card.pin_warning": "Současný PIN přestane platit okamžitě, i pro hosty, kteří se právě registrují.",
        "havel.card.not_prepared": "Tohle jsem nemohl připravit: %(reason)s",
        "havel.card.open_form": "Otevřít formulář",
        "havel.reason.property": "Nevím jistě, které ubytování myslíte.",
        "havel.reason.dates": "Nejsou mi jasná data.",
        "havel.reason.no_calendar": "Zatím není připojený žádný kalendář.",
        "havel.reason.no_link": "Toto ubytování zatím nemá odkaz pro hosty.",
        "havel.reason.archived": "Toto ubytování je archivované nebo vypnuté.",
        "havel.support.title": "Poslat podpoře UbyHostu",
        "havel.support.add": "Chcete něco doplnit?",
        "havel.support.send": "Poslat podpoře",
        "havel.support.sent": "Předáno týmu UbyHostu. Vědí o tom a obvykle odpoví do několika hodin.",
        "havel.support.replies_to": "Podpora odpoví na %(email)s",
        "havel.support.mailto": "Napsat podpoře e-mail",
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -5`. Expected: pass (en and cs parity holds: both blocks have the same 83 keys).

3. **Copy, Vietnamese.** Moved to brief 0325 (`host_vi_i18n` falls back to en until it ships). Nothing to do here.

4. **Route.** Create `App/app/routes/havel.py`:

```python
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
    return host_i18n.translate(request.state.lang, key, **kw)


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
                host = havel.Host(user_id=uid, lang=request.state.lang, device=device,
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
```

   Then in `App/app/main.py` change the import line

```python
from .routes import admin, cleaning as cleaning_routes, dev_ui, guest, invoices, legal, mail_unsubscribe, onboarding_wizard, stay_fees
```

   to

```python
from .routes import admin, cleaning as cleaning_routes, dev_ui, guest, havel as havel_routes, invoices, legal, mail_unsubscribe, onboarding_wizard, stay_fees
```

   and directly after `app.include_router(cleaning_routes.router)` add `app.include_router(havel_routes.router)`.

   Command: `cd App && .venv/bin/python -c "from app.main import app; print([r.path for r in app.routes if r.path == '/havel'])"`. Expected: `['/havel', '/havel']`.

5. **Templates.** Create `App/app/templates/havel.html`:

```jinja
{% extends "host_page.html" %}
{% set nav = 'guide' %}
{% set body_kind = 'detail' %}
{% block title %}{{ t('havel.title') }}{% endblock %}
{% block page_title %}{{ t('havel.name') }}{% endblock %}
{% block meta %}{{ t('havel.subtitle') }}{% endblock %}
{% block body %}
<section class="ui-section havel-page" data-havel-page>
  <div class="havel-thread" role="log" aria-live="polite" data-havel-thread>
    {% include "_havel_thread.html" %}
  </div>
  {% include "_havel_form.html" %}
</section>
{% endblock %}
```

   Create `App/app/templates/_havel_thread.html` (the panel in 0324 includes the same file):

```jinja
{#- 0312: Havel's thread. Host bubbles right, Havel bubbles left with the AI label.
    Numbered steps render as a list. Links are buttons under the bubble; a card
    (0314) sits under the bubble, never inside it. -#}
{% from "_icons.html" import icon with context %}
{% for item in havel_items %}
  {% if item.role == 'host' %}
  <div class="havel-msg havel-msg-host"><span class="sr-only">{{ t('havel.you') }}: </span>
    <div class="havel-bubble">{% for b in item.blocks %}<p>{{ b.text if b.kind == 'p' else b['items'] | join(' ') }}</p>{% endfor %}</div>
  </div>
  {% else %}
  <div class="havel-msg havel-msg-havel" tabindex="-1">
    <div class="havel-who"><span class="havel-avatar" aria-hidden="true">{{ icon('message-circle-question', 16) }}</span><span class="havel-name">{{ t('havel.name') }}</span></div>
    <div class="havel-bubble">
      {% for b in item.blocks %}{% if b.kind == 'ol' %}<ol>{% for step in b['items'] %}<li>{{ step }}</li>{% endfor %}</ol>{% else %}<p>{{ b.text }}</p>{% endif %}{% endfor %}
    </div>
    {% if item.card %}{% include "_havel_card.html" %}{% endif %}
    {% if item.links or item.support %}
    <div class="havel-links">
      {% for label, url in item.links %}<a class="ui-btn ui-btn-secondary ui-btn-compact" href="{{ url }}">{{ label }}{{ icon('chevron-right', 16) }}</a>{% endfor %}
      {% if item.support and operator().email %}<a class="ui-btn ui-btn-secondary ui-btn-compact" href="mailto:{{ operator().email }}{% if item.support_summary %}?body={{ item.support_summary | urlencode }}{% endif %}">{{ icon('send', 16) }}{{ t('havel.support.mailto') }}</a>{% endif %}
    </div>
    {% endif %}
  </div>
  {% endif %}
{% endfor %}
{% if havel_fragment %}<div hidden data-havel-state data-history="{{ havel_history }}" data-sig="{{ havel_history_sig }}" data-remaining="{{ havel_remaining }}" data-state="{{ havel_state or '' }}"{% if havel_error %} data-error="{{ havel_error }}"{% endif %}></div>{% endif %}
```

   `_havel_card.html` does not exist yet; the include is guarded by `item.card`, which is always `None` until 0314. Jinja only resolves an include when the branch runs, so the page renders.

   Create `App/app/templates/_havel_form.html`:

```jinja
{#- 0312: the composer. Hidden fields carry the signed history, the hosting page,
    the device (set by havel.js in 0324) and the quick-help topic. -#}
<form method="post" action="/havel" class="havel-composer" data-havel-form>
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="history" value="{{ havel_history }}" data-havel-history>
  <input type="hidden" name="history_sig" value="{{ havel_history_sig }}" data-havel-sig>
  <input type="hidden" name="page" value="{{ havel_page }}">
  <input type="hidden" name="device" value="computer" data-havel-device>
  <input type="hidden" name="topic" value="{{ havel_topic }}" data-havel-topic>
  <input type="hidden" name="return_to" value="{{ havel_return_to }}">
  {% if havel_state %}
  <p class="havel-meta">{{ t('havel.' ~ havel_state) }}</p>
  {% else %}
  <label for="havel-message" class="sr-only">{{ t('havel.placeholder') }}</label>
  <textarea id="havel-message" name="message" rows="2" maxlength="{{ havel_max }}" placeholder="{{ t('havel.placeholder') }}" required{% if havel_error %} aria-invalid="true" aria-describedby="havel-error"{% endif %}></textarea>
  {% if havel_error %}<p id="havel-error" class="havel-error">{{ havel_error }}</p>{% endif %}
  <div class="havel-actions">
    <p class="havel-meta">{{ havel_remaining }}</p>
    {% if not havel_fresh %}<button class="ui-btn ui-btn-quiet" type="submit" name="reset" value="1" formnovalidate>{{ t('havel.new') }}</button>{% endif %}
    <button class="ui-btn ui-btn-primary" type="submit" data-havel-send>{{ t('havel.send') }}</button>
  </div>
  {% endif %}
  <p class="havel-meta havel-note">{{ t('havel.ai_note') }}</p>
</form>
```

   The icon `message-circle-question` does not exist yet. In `App/app/templates/_icons.html`, directly after the line that starts `  'users': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>` (the last icon; it has no trailing comma), add a comma to that line's end and then this line:

```
  'message-circle-question': '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>'
```

   (Lucide `message-circle-question`, the same family as the other icons.) Add `App/app/templates/_icons.html` to your report's file list; it is allowed here as the one icon the plan names (17a).

   Command: `cd App && .venv/bin/python -c "from app.main import app" && grep -c "message-circle-question" app/templates/_icons.html`. Expected: no error, `1`.

6. **CSS.** Append to the very end of `App/app/static/host2.css`:

```css

/* 0312: Havel (AI) thread, bubbles, composer (plan 17b). Tokens only. */
.host-workspace .havel-thread { display: flex; flex-direction: column; gap: var(--space-3); }
.host-workspace .havel-msg { display: flex; flex-direction: column; max-width: 85%; }
.host-workspace .havel-msg-host { align-self: flex-end; align-items: flex-end; }
.host-workspace .havel-msg-havel { align-self: flex-start; align-items: flex-start; }
.host-workspace .havel-msg:focus { outline: none; }
.host-workspace .havel-msg:focus-visible .havel-bubble { box-shadow: var(--focus-ring-2); }
.host-workspace .havel-who { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1); color: var(--ink-2); font-size: var(--size-13); font-weight: 600; }
.host-workspace .havel-avatar { display: inline-flex; align-items: center; justify-content: center; width: var(--space-6); height: var(--space-6); border-radius: var(--radius-pill); background: var(--accent-soft); color: var(--accent-ink); }
.host-workspace .havel-bubble { padding: var(--space-3) var(--space-4); border-radius: var(--radius-4); font-size: var(--size-15); line-height: 1.5; color: var(--ink); }
.host-workspace .havel-msg-host .havel-bubble { background: var(--surface-2); border-bottom-right-radius: var(--radius-1); }
.host-workspace .havel-msg-havel .havel-bubble { background: var(--surface); border: 1px solid var(--line); border-bottom-left-radius: var(--radius-1); }
.host-workspace .havel-bubble p { margin: 0; }
.host-workspace .havel-bubble p + p, .host-workspace .havel-bubble p + ol, .host-workspace .havel-bubble ol + p { margin-top: var(--space-2); }
.host-workspace .havel-bubble ol { margin: 0; padding-left: var(--space-5); }
.host-workspace .havel-bubble li + li { margin-top: var(--space-1); }
.host-workspace .havel-links { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.host-workspace .havel-composer { display: flex; flex-direction: column; gap: var(--space-2); margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid var(--line); }
.host-workspace .havel-composer textarea { width: 100%; box-sizing: border-box; min-height: calc(var(--control-h) * 2); padding: var(--space-3); border: 1px solid var(--input-border); border-radius: var(--input-radius); font: inherit; font-size: var(--size-15); color: var(--ink); background: var(--surface); resize: vertical; }
.host-workspace .havel-composer textarea:focus-visible { outline: 0; border-color: var(--accent); box-shadow: var(--focus-ring-2); }
.host-workspace .havel-actions { display: flex; align-items: center; justify-content: flex-end; gap: var(--space-2); flex-wrap: wrap; }
.host-workspace .havel-actions .havel-meta { margin: 0 auto 0 0; }
.host-workspace .havel-meta { margin: 0; font-size: var(--size-13); color: var(--ink-3); }
.host-workspace .havel-note { font-size: var(--size-12); }
.host-workspace .havel-error { margin: 0; font-size: var(--size-13); color: var(--danger); }
```

   Then the cache key: `sed -i 's/host2.css?v=20261022-0289"/host2.css?v=20261024-0312"/' App/app/templates/base.html && grep -c 'host2.css?v=20261024-0312"' App/app/templates/base.html` (expected `1`), then `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`.

7. **Catalog, page file, guard route.** Save as `/tmp/claude-0/s/cat0312.py` and run from the repo root with `python3 /tmp/claude-0/s/cat0312.py 2>&1 | tail -3`:

```python
import json
from pathlib import Path

p = Path("docs/design/catalog.json")
c = json.loads(p.read_text(encoding="utf-8"))
new = ["havel-page", "havel-thread", "havel-msg", "havel-msg-host", "havel-msg-havel", "havel-who", "havel-avatar",
       "havel-name", "havel-bubble", "havel-links", "havel-composer", "havel-actions", "havel-meta", "havel-note",
       "havel-error", "havel-card", "havel-card-facts", "havel-card-warning", "havel-card-link", "havel-card-pin",
       "havel-topics", "havel-topic", "havel-answer", "havel-dialog", "havel-head", "havel-head-text", "havel-counter",
       "havel-writing"]
c["classes"] += [k for k in new if k not in c["classes"]]
for t in ["App/app/templates/havel.html", "App/app/templates/_havel_thread.html", "App/app/templates/_havel_form.html"]:
    if t not in c["enforced_templates"]:
        c["enforced_templates"].append(t)
c["class_notes"]["havel-*"] = "0312-0314: Havel (AI) support assistant: thread, bubbles, composer, cards, topics, panel (plan section 17)."
p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("catalog ok", len(c["classes"]))
```

   If `class_notes` is not a dict, skip that line and note it. Create `docs/design/pages/havel.md`:

```markdown
# Page: Havel (AI) (`/havel`, templates `havel.html`, `_havel_thread.html`, `_havel_form.html`)

Master version: 2.0.0. Adds only; never overrides MASTER.md. Plan: docs/plans/havel-support-assistant.md section 17.

- Identity: nav `guide`, body_kind `detail`, title `havel.title`, page title `havel.name`, meta `havel.subtitle`, no back link.
- Header: no actions, no tabs; the composer's Send is the page's one primary.
- Body: one `ui-section`: the thread (`role="log"`) with host and Havel bubbles, compact secondary link buttons and a confirm card (0314) under a Havel bubble; the composer (textarea 600 chars, remaining-messages line, quiet New conversation when a conversation exists, primary Send, the AI note). Off or over a limit: the limit sentence replaces the textarea; the support exit stays.
- Empty state: the quick-help topics (0313); never a blank box.
- Tests: `test_havel_page.py`, `test_havel_browser.py` (0324), `test_design_guardrails_browser.py` (`ROUTES["havel"]`); screenshots 390 and 1280.
```

   In `App/tests/test_design_guardrails_browser.py`, directly after the line `    "settings-account": "/settings",` insert `    "havel": "/havel",`.

   Command: `python3 scripts/design_lint.py 2>&1 | tail -5`. Expected: no finding for the havel templates or `host2.css`.

8. **Tests.** Create `App/tests/test_havel_page.py`:

```python
"""0312: the Havel page works as a plain form, applies the limits and shows only checked text."""
from __future__ import annotations

import re

import pytest

from app import ai, config, db, havel, rate_limit
from tests.ai_fake import FakeClient, reply
from tests.test_submission_retry_cap import host as host  # noqa: F401

ANSWER = {"kind": "answer", "reply": "Open Stays.\n1. Tap Add stay.\n2. Pick the dates.", "sources": ["guide.stays.body"],
          "links": [{"page": "add_stay", "property_id": None}], "action": None, "support_summary": None}


def _csrf(page: str) -> str:
    return re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)


def _post(client, data, headers=None):
    page = client.get("/havel").text
    form = {"_csrf": _csrf(page), "history": "", "history_sig": "", "page": "dashboard", "device": "phone", "topic": ""}
    form.update(data)
    return client.post("/havel", data=form, headers=headers or {})


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    db.init_db()
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    yield
    ai.set_client_for_tests(None)


def test_page_renders_in_every_language_with_the_ai_label(host):
    for lang in ("en", "cs", "vi"):
        page = host.get(f"/havel?lang={lang}").text
        assert "Havel (AI)" in page and "havel." not in page.replace("/havel", ""), lang
        assert 'data-havel-thread' in page and 'name="message"' in page and 'name="history_sig"' in page


def test_greeting_is_answered_locally_and_not_counted(host):
    fake = FakeClient([])
    ai.set_client_for_tests(fake)
    page = _post(host, {"message": "Hello"}).text
    assert "Ask me how something works" in page and fake.calls == []
    uid = db.query_one("SELECT id FROM user_account WHERE username = ?", ("retry-cap-admin",))
    assert rate_limit._count("havel_week", str(db.query_one("SELECT id FROM user_account ORDER BY id LIMIT 1", ())["id"]), 10 ** 6) == 0 or uid is None


def test_answer_renders_steps_links_and_signed_history(host):
    ai.set_client_for_tests(FakeClient([reply(ANSWER)]))
    page = _post(host, {"message": "How do I add a stay?"}).text
    assert "<ol><li>Tap Add stay.</li><li>Pick the dates.</li></ol>" in page
    assert 'href="/reservations?new=1"' in page
    history = re.search(r'name="history" value="([^"]*)"', page).group(1)
    sig = re.search(r'name="history_sig" value="([^"]*)"', page).group(1)
    assert "How do I add a stay?" in history.replace("&#34;", '"').replace("&quot;", '"') and len(sig) == 64
    assert "messages left this week" in page or "messages left this month" in page


def test_fragment_header_returns_only_the_thread(host):
    ai.set_client_for_tests(FakeClient([reply(ANSWER)]))
    res = _post(host, {"message": "How do I add a stay?"}, headers={"X-Havel": "1"})
    assert res.status_code == 200
    assert "<html" not in res.text and "data-havel-state" in res.text and "havel-msg-host" in res.text


def test_off_limit_and_failure_show_the_fixed_sentences(host, monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    page = _post(host, {"message": "How do I add a stay?"}).text
    assert "Havel is unavailable right now" in page
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    ai.set_client_for_tests(FakeClient([reply(text="{broken")]))
    page = _post(host, {"message": "How do I add a stay?"}).text
    assert "I don't know that, and I don't want to guess" in page
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: "limit_week")
    page = _post(host, {"message": "Again?"}).text
    assert "They come back on Monday" in page and 'name="message"' not in page


def test_too_long_is_refused_without_a_call(host):
    fake = FakeClient([])
    ai.set_client_for_tests(fake)
    page = _post(host, {"message": "x" * 601}).text
    assert "under 600 characters" in page and fake.calls == []
```

   Then simplify the second test: delete the two `uid`/`assert rate_limit._count(...)` lines and instead assert `db.query_one("SELECT COUNT(*) AS n FROM rate_limit_event WHERE scope = 'havel_week'", ())["n"] == 0`.

   Command: `cd App && .venv/bin/python -m pytest tests/test_havel_page.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

9. **Browser guard and screenshots** (rule 7), from `App/` with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`:

```
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -k "every_host_page" tests/test_a11y_guard_browser.py -k havel -q --tb=short -x -rs -p no:cacheprovider 2>&1 | tail -30
```

   Expected: pass, 0 skipped. Then take the screenshots of `/havel` at 390 and 1280 with the existing harness (`tests/browser_support.py`, as `test_host_wide_geometry_browser.py` does) and save them as `docs/tasks/screenshots-0312/havel-390.png` and `havel-1280.png`; look at each once.

## 5. Do not touch

Anything not in section 3 (plus `_icons.html` for the one icon). No topics (0313), no launcher, panel or JavaScript (0324), no cards (0314), no vi copy (0325), no mail (0319). AGENTS.md rules 6, 7, 9; MASTER 10.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`)

```
.venv/bin/python -m pytest tests/test_havel_page.py tests/test_havel_engine.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -k "every_host_page" tests/test_a11y_guard_browser.py -k havel -q --tb=short -x -rs -p no:cacheprovider 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py 2>&1 | tail -5 && python3 scripts/context_lint.py 2>&1 | tail -3
```

## 7. Acceptance

- [ ] `/havel` renders in en, cs and vi (vi falls back to en) with "Havel (AI)" in the title and no raw `havel.` keys.
- [ ] A greeting and an over-long message never reach the fake client; an answer renders steps as `<ol>`, link buttons and a 64-character history signature.
- [ ] `X-Havel: 1` returns the thread fragment with `data-havel-state`.
- [ ] Off, limit and guardrail failure show the fixed sentences and the e-mail support exit.
- [ ] Layout guard and a11y guard pass for `/havel`, 0 skipped; screenshots at 390 and 1280 saved and looked at.
- [ ] en and cs have the same `havel.*` keys (vi: 0325); no em dash; `host2.css` key bumped; design lint clean.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: `request.state.lang` is not set on the request (then use `host_i18n.normalise_language(request.query_params.get("lang") or "")` only after asking), the catalog script fails, the layout guard reports a Havel finding you cannot fix inside `havel.html` or the appended CSS.

## 9. Report

`docs/tasks/0312-report.md` (600 tokens at most), `Status: review`, with the two screenshot paths and what you checked on them (composer row at 390: textarea full width, Send 44 px, meta line wraps under; 1280: thread inside the lane, bubbles at most 85%). Do not push.

## Risk list (for the reviewer)

`App/app/routes/havel.py` (every branch records or skips limits correctly; `reset`; fragment), `_havel_thread.html` (all text goes through autoescape; `mailto:` only with `operator().email`), the i18n blocks (parity), `host2.css` (tokens only).

## Owner steps

1. On staging, after deploy, open `/havel` signed in: you should see Havel's intro bubble and the composer, and "Havel is unavailable right now" after sending a question (the feature is still off). Tap "E-mail support" once to see your mail app open.
