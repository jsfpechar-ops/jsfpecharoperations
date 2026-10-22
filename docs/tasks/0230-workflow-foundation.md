# 0230: Foolproof workflow round 1, foundation (module, copy, styles)

Status: todo
Depends on: none | Base commit: 80b5deb | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add one small module, `app/workflow.py`, that tells the five-step story of a stay (who does each step, where a stay is, when a stay appears on the guest link, whether a real guest has used the link yet), plus all round-1 copy in EN, CS and VI and one new stylesheet. Briefs 0231 to 0234 only use what this brief adds, so they stay small.

## 2. Context

- Ideas doc: "Foolproof host workflow: ideas" (Claude Doc), round 1 = I, A, B+Q, D, J. Owner decisions (2026-10-22): do NOT widen the guest-link window; outside the wizard no description walls ("?" tips, at most one short non-label sentence per page); Airbnb-like clarity; visible borders; WCAG 2.2 AA; light mode only.
- `app/routes/guest.py` `_visible_reservations` lists stays with `date_from` from today to today + `permalink_window_days` (`apartment["permalink_window_days"] or 1`), active, not archived, not demo. The new `link_window()` must give the same answer.
- Privacy (hard rule 2): the "a guest used the link" check reads only `reservation_claim` rows the app already stores. No new log, no new column, no new outbound request.
- Strings: `app/host_i18n.py` adds a block as `_NAME = {"en": {...}, "cs": {...}}` + `for _lang, _strings in _NAME.items(): STRINGS[_lang].update(_strings)`, placed before the line `STRINGS["vi"] = dict(_VI_STRINGS)`. Vietnamese goes at the end of `app/host_vi_i18n.py` as `STRINGS.update({...})`. Tests demand: EN and CS have the same keys; every VI key exists in EN with the same `%(name)s` placeholders. Plural keys ship as `base`, `base.one`, `base.few` in every language. No em dashes anywhere.
- Static files get a new `?v=` key (memory rule).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/workflow.py` | create | the module (step 1) |
| `App/app/templating.py` | edit | register 5 globals (step 2) |
| `App/app/host_i18n.py` | edit | EN + CS strings (step 3) |
| `App/app/host_vi_i18n.py` | edit | VI strings (step 4) |
| `App/app/static/workflow.css` | create | styles (step 5) |
| `App/app/templates/base.html` | edit | link the stylesheet (step 6) |
| `App/tests/test_workflow_0230.py` | create | tests (step 7) |
| `docs/tasks/0230-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. Create `App/app/workflow.py` with exactly this content

```python
"""0230: the five-step story of a stay, told the same way on every host page.

1 you paste the guest message (once), 2 the guest fills the form, 3 you get an
email, 4 the police report goes out (by the property's own option), 5 the guest
gets the confirmation email (and the door code when a lock is connected).
Also: when a stay appears on the property's guest link, and whether a real
guest has used the link yet. Reads only data the app already stores.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from . import claim, db, validation

TOTAL = 5

# reporting.reservation_progress()["status"] -> the step the stay is on.
_STATUS_STEP = {
    "awaiting_guest": 2,
    "incomplete": 2,
    "ready": 4,
    "awaiting_verification": 4,
    "failed": 4,
    "reported": 5,
}

_POLICE_KEYS = {
    "manual": "police_manual",
    "scheduled": "police_scheduled",
    "immediate": "police_immediate",
}


def _get(row, key: str, default=None):
    if row is None:
        return default
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _as_dict(row) -> Dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def has_door_code(apartment) -> bool:
    """Step 5 names the door code only when a TTLock lock is set for the property."""
    if _get(apartment, "lock_provider") != "ttlock":
        return False
    from . import ttlock  # local: ttlock pulls in the HTTP client

    return bool(ttlock.enabled())


def steps(apartment=None) -> List[Dict[str, Any]]:
    """The five steps, worded for this property's police option and lock.

    Without a property (the first wizard screen) step 4 stays generic.
    """
    police = _POLICE_KEYS.get(_get(apartment, "automation_mode", ""), "police") if apartment is not None else "police"
    finish = "finish_lock" if apartment is not None and has_door_code(apartment) else "finish"
    return [
        {"n": 1, "key": "paste", "who": "you_once"},
        {"n": 2, "key": "form", "who": "auto"},
        {"n": 3, "key": "email", "who": "auto"},
        {"n": 4, "key": police, "who": "you" if police == "police_manual" else "auto"},
        {"n": 5, "key": finish, "who": "auto"},
    ]


def step_number(status) -> Optional[int]:
    """The step a stay with this reporting status is on, or None (not reported)."""
    return _STATUS_STEP.get(status or "")


def journey(reservation, progress) -> Optional[Dict[str, Any]]:
    """Where one stay is in the five steps, for the tracker on the stay page."""
    status = _get(progress, "status")
    current = step_number(status)
    if current is None or _get(reservation, "status", "active") != "active" or _get(reservation, "archived_at"):
        return None
    view = _as_dict(
        db.query_one("SELECT * FROM apartment WHERE id = ?", (_get(reservation, "apartment_id"),))
    )
    mode = _get(reservation, "automation_mode")
    if mode:
        view["automation_mode"] = mode
    complete = status == "reported"
    rows = []
    for step in steps(view or None):
        if complete or step["n"] < current:
            state = "done"
        elif step["n"] == current:
            state = "current"
        else:
            state = "todo"
        rows.append({**step, "state": state})
    return {
        "current": current,
        "total": TOTAL,
        "complete": complete,
        "failed": status == "failed",
        "steps": rows,
    }


def _window_days(row) -> int:
    days = _get(row, "permalink_window_days")
    if days is None and _get(row, "apartment_id") is not None:
        apartment = db.query_one(
            "SELECT permalink_window_days FROM apartment WHERE id = ?", (row["apartment_id"],)
        )
        days = _get(apartment, "permalink_window_days")
    return int(days or 1)


def link_window(reservation, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """When this stay is listed on the property's guest link.

    {"state": "now"} while it is listed, {"state": "from", "opens": date} before,
    None for past, inactive, archived or demo stays. Same rule as
    routes/guest.py _visible_reservations: check-in from today to today + window.
    """
    if _get(reservation, "status", "active") != "active" or _get(reservation, "archived_at"):
        return None
    if _get(reservation, "source", "") == "demo":
        return None
    start = validation.parse_iso_date(_get(reservation, "date_from", ""))
    if not start:
        return None
    today = today or claim.prague_today()
    if start < today:
        return None
    opens = start - timedelta(days=_window_days(reservation))
    if opens <= today:
        return {"state": "now", "opens": today}
    return {"state": "from", "opens": opens}


def next_stay_window(apartment, today: Optional[date] = None) -> Dict[str, Any]:
    """The property's next real stay and the day it appears on the guest link."""
    today = today or claim.prague_today()
    days = _window_days(apartment)
    row = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND status = 'active' "
        "AND archived_at IS NULL AND COALESCE(source, '') != 'demo' AND date_from >= ? "
        "ORDER BY date_from LIMIT 1",
        (apartment["id"], today.isoformat()),
    )
    if row is None:
        return {"stay": None, "days": days, "window": None}
    stay = _as_dict(row)
    stay["permalink_window_days"] = days
    return {"stay": row, "days": days, "window": link_window(stay, today)}


def guest_used_link(apartment_id: int) -> bool:
    """0232: a real guest claimed a stay of this property (the only proof we store)."""
    row = db.query_one(
        "SELECT 1 AS hit FROM reservation r "
        "JOIN reservation_claim c ON c.reservation_id = r.id "
        "WHERE r.apartment_id = ? AND COALESCE(r.source, '') != 'demo' "
        "AND (c.state IN ('provisional', 'claimed') OR c.claimed_at IS NOT NULL) "
        "LIMIT 1",
        (apartment_id,),
    )
    return row is not None


def link_unused(apartments, today: Optional[date] = None) -> List[Any]:
    """Properties whose link a guest could have used by now, but no guest has.

    A stay must have reached the guest link since the property was added, so a
    new host is not nagged before any guest could have seen the message.
    """
    from . import demo  # local: demo imports many modules

    today = today or claim.prague_today()
    found = []
    for apartment in apartments or []:
        if not _get(apartment, "active", 1) or _get(apartment, "archived_at"):
            continue
        if not _get(apartment, "permalink_token") or demo.is_demo_apartment(apartment):
            continue
        added = str(_get(apartment, "created_at", ""))[:10] or "0000-00-00"
        horizon = (today + timedelta(days=_window_days(apartment))).isoformat()
        due = db.query_one(
            "SELECT 1 AS hit FROM reservation WHERE apartment_id = ? AND status = 'active' "
            "AND archived_at IS NULL AND COALESCE(source, '') != 'demo' "
            "AND date_from >= ? AND date_from <= ? LIMIT 1",
            (apartment["id"], added, horizon),
        )
        if due and not guest_used_link(apartment["id"]):
            found.append(apartment)
    return found
```

Command: `cd App && .venv/bin/python -c "import app.workflow as w; print(len(w.steps()))" 2>&1 | tail -5` → prints `5`. Commit `0230 step 1`.

### Step 2. `App/app/templating.py`: register the globals

Anchor (exact line): `templates.env.globals["door_codes_enabled"] = _template_door_codes_enabled`

Insert directly after that line:

```python
# 0230: the five-step story, the same words on every host page.
from . import workflow  # noqa: E402

templates.env.globals["workflow_steps"] = workflow.steps
templates.env.globals["stay_journey"] = workflow.journey
templates.env.globals["journey_step"] = workflow.step_number
templates.env.globals["link_window"] = workflow.link_window
templates.env.globals["next_stay_window"] = workflow.next_stay_window
```

Command: `cd App && .venv/bin/python -c "from app.templating import templates; print('stay_journey' in templates.env.globals)" 2>&1 | tail -5` → `True`. Commit `0230 step 2`.

### Step 3. `App/app/host_i18n.py`: EN and CS strings

Anchor (exact line): `STRINGS["vi"] = dict(_VI_STRINGS)`

Insert directly BEFORE that line (keep one blank line between blocks):

```python
# 0230-0234: foolproof workflow round 1 (I, A, B+Q, D, J).
_WORKFLOW_0230_STRINGS = {
    "en": {
        "workflow.title": "How each stay works",
        "workflow.who.you_once": "You, once",
        "workflow.who.you": "You",
        "workflow.who.auto": "Automatic",
        "workflow.step.paste": "You paste the guest message into Airbnb or Booking.com",
        "workflow.step.form": "The guest fills in the guest form",
        "workflow.step.email": "You get an email",
        "workflow.step.police": "The police report goes out",
        "workflow.step.police_manual": "You press Send for the police report",
        "workflow.step.police_scheduled": "The police report goes out by itself after a short delay",
        "workflow.step.police_immediate": "The police report goes out at once",
        "workflow.step.finish": "The guest gets a confirmation email",
        "workflow.step.finish_lock": "The guest gets the door code and a confirmation email",
        "workflow.short.paste": "Guest message",
        "workflow.short.form": "Guest form",
        "workflow.short.email": "Your email",
        "workflow.short.police": "Police report",
        "workflow.short.police_manual": "Police report",
        "workflow.short.police_scheduled": "Police report",
        "workflow.short.police_immediate": "Police report",
        "workflow.short.finish": "Confirmation email",
        "workflow.short.finish_lock": "Door code and confirmation email",
        "workflow.step_of": "%(n)s of %(total)s",
        "workflow.journey.label": "Step %(n)s of %(total)s: %(step)s",
        "workflow.journey.complete": "All 5 steps done",
        "workflow.journey.state.done": "done",
        "workflow.journey.state.current": "now",
        "workflow.link.now": "On guest link now",
        "workflow.link.from": "On guest link from %(date)s",
        "workflow.link.next_stay": "Your next stay, %(stay)s, appears on your guest link from %(date)s.",
        "workflow.link.next_stay_now": "Your next stay, %(stay)s, is on your guest link now.",
        "workflow.link.no_stay": "A stay appears on your guest link %(count)s days before check-in.",
        "workflow.link.no_stay.one": "A stay appears on your guest link 1 day before check-in.",
        "workflow.link.no_stay.few": "A stay appears on your guest link %(count)s days before check-in.",
        "workflow.link.why": "Your guest link only lists stays that start soon, so another guest cannot pick this stay early. This guest's own link works now.",
        "workflow.link.copy_own": "Copy this guest's own link",
        "workflow.link.preview": "See what guests see today",
        "workflow.link.host_note": "Only you see this note. Your next stay, %(stay)s, appears here from %(date)s. Need it sooner? Send that guest their own link from the stay page.",
        "workflow.link.host_note_none": "Only you see this note. No upcoming stay yet. Stays appear here shortly before check-in.",
        "workflow.paste.title": "No guest has used your guest link yet",
        "workflow.paste.body": "Did you paste the guest message into Airbnb or Booking.com?",
        "workflow.paste.how": "How to paste it",
        "workflow.paste.airbnb": "Airbnb: add it as a scheduled message that goes out after each booking.",
        "workflow.paste.booking": "Booking.com: add it as a message template that is sent automatically.",
        "workflow.paste.direct": "Direct bookings: paste it into your booking confirmation.",
        "workflow.paste.open": "Open the guest message",
        "wizard.optional_suffix": " (optional)",
        "wizard.door_lock.question": "Do you have a smart lock?",
        "wizard.door_lock.no": "No smart lock",
        "wizard.door_lock.no_hint": "I hand over keys or use a key box",
        "wizard.door_lock.yes": "Yes, I have a TTLock lock",
        "wizard.door_lock.yes_hint": "With a gateway, so codes reach the lock online",
        "wizard.door_lock.other_brands": "Other brands are not supported yet.",
        "wizard.summary.status.not_needed": "Not needed",
        "why.door_lock": "With a TTLock smart lock, UbyHost makes a door code for each stay that works only during that stay. The guest gets it once everyone has registered, so you never hand over keys.",
    },
    "cs": {
        "workflow.title": "Jak probíhá každý pobyt",
        "workflow.who.you_once": "Vy, jednou",
        "workflow.who.you": "Vy",
        "workflow.who.auto": "Automaticky",
        "workflow.step.paste": "Vložíte zprávu pro hosty do Airbnb nebo Booking.com",
        "workflow.step.form": "Host vyplní formulář pro hosty",
        "workflow.step.email": "Přijde vám e-mail",
        "workflow.step.police": "Hlášení policii odejde",
        "workflow.step.police_manual": "Hlášení policii odešlete tlačítkem Odeslat",
        "workflow.step.police_scheduled": "Hlášení policii odejde samo po krátké prodlevě",
        "workflow.step.police_immediate": "Hlášení policii odejde hned",
        "workflow.step.finish": "Host dostane potvrzovací e-mail",
        "workflow.step.finish_lock": "Host dostane kód ke dveřím a potvrzovací e-mail",
        "workflow.short.paste": "Zpráva pro hosty",
        "workflow.short.form": "Formulář pro hosty",
        "workflow.short.email": "Váš e-mail",
        "workflow.short.police": "Hlášení policii",
        "workflow.short.police_manual": "Hlášení policii",
        "workflow.short.police_scheduled": "Hlášení policii",
        "workflow.short.police_immediate": "Hlášení policii",
        "workflow.short.finish": "Potvrzovací e-mail",
        "workflow.short.finish_lock": "Kód ke dveřím a potvrzovací e-mail",
        "workflow.step_of": "%(n)s z %(total)s",
        "workflow.journey.label": "Krok %(n)s z %(total)s: %(step)s",
        "workflow.journey.complete": "Všech 5 kroků hotovo",
        "workflow.journey.state.done": "hotovo",
        "workflow.journey.state.current": "teď",
        "workflow.link.now": "Na odkazu pro hosty už teď",
        "workflow.link.from": "Na odkazu pro hosty od %(date)s",
        "workflow.link.next_stay": "Váš další pobyt (%(stay)s) se na odkazu pro hosty objeví od %(date)s.",
        "workflow.link.next_stay_now": "Váš další pobyt (%(stay)s) je na odkazu pro hosty už teď.",
        "workflow.link.no_stay": "Pobyt se na odkazu pro hosty objeví %(count)s dní před příjezdem.",
        "workflow.link.no_stay.one": "Pobyt se na odkazu pro hosty objeví 1 den před příjezdem.",
        "workflow.link.no_stay.few": "Pobyt se na odkazu pro hosty objeví %(count)s dny před příjezdem.",
        "workflow.link.why": "Odkaz pro hosty ukazuje jen pobyty, které brzy začínají, aby si tento pobyt nevybral dřív jiný host. Vlastní odkaz tohoto hosta funguje už teď.",
        "workflow.link.copy_own": "Kopírovat vlastní odkaz hosta",
        "workflow.link.preview": "Co dnes uvidí hosté",
        "workflow.link.host_note": "Tuto poznámku vidíte jen vy. Váš další pobyt (%(stay)s) se tu objeví od %(date)s. Potřebujete to dřív? Pošlete hostovi jeho vlastní odkaz ze stránky pobytu.",
        "workflow.link.host_note_none": "Tuto poznámku vidíte jen vy. Zatím tu není žádný nadcházející pobyt. Pobyty se tu objeví krátce před příjezdem.",
        "workflow.paste.title": "Odkaz pro hosty zatím žádný host nepoužil",
        "workflow.paste.body": "Vložili jste zprávu pro hosty do Airbnb nebo Booking.com?",
        "workflow.paste.how": "Jak ji vložit",
        "workflow.paste.airbnb": "Airbnb: přidejte ji jako naplánovanou zprávu, která odejde po každé rezervaci.",
        "workflow.paste.booking": "Booking.com: přidejte ji jako šablonu zprávy, která se odešle automaticky.",
        "workflow.paste.direct": "Přímé rezervace: vložte ji do potvrzení rezervace.",
        "workflow.paste.open": "Otevřít zprávu pro hosty",
        "wizard.optional_suffix": " (nepovinné)",
        "wizard.door_lock.question": "Máte chytrý zámek?",
        "wizard.door_lock.no": "Nemám chytrý zámek",
        "wizard.door_lock.no_hint": "Klíče předávám osobně nebo přes schránku na klíče",
        "wizard.door_lock.yes": "Ano, mám zámek TTLock",
        "wizard.door_lock.yes_hint": "S bránou, aby kódy došly do zámku online",
        "wizard.door_lock.other_brands": "Jiné značky zatím nepodporujeme.",
        "wizard.summary.status.not_needed": "Není potřeba",
        "why.door_lock": "S chytrým zámkem TTLock vytvoří UbyHost každému pobytu vlastní vstupní kód, platný jen po dobu pobytu. Host ho dostane, jakmile se všichni zaregistrují, a vy nemusíte předávat klíče.",
    },
}
for _lang, _strings in _WORKFLOW_0230_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -5` → all pass. Commit `0230 step 3`.

### Step 4. `App/app/host_vi_i18n.py`: VI strings

Append at the very end of the file:

```python

# 0230-0234: foolproof workflow round 1.
STRINGS.update({
    "workflow.title": "Mỗi lượt lưu trú diễn ra thế nào",
    "workflow.who.you_once": "Bạn, một lần",
    "workflow.who.you": "Bạn",
    "workflow.who.auto": "Tự động",
    "workflow.step.paste": "Bạn dán tin nhắn cho khách vào Airbnb hoặc Booking.com",
    "workflow.step.form": "Khách điền biểu mẫu cho khách",
    "workflow.step.email": "Bạn nhận được email",
    "workflow.step.police": "Báo cáo cho công an được gửi đi",
    "workflow.step.police_manual": "Bạn bấm Gửi để gửi báo cáo cho công an",
    "workflow.step.police_scheduled": "Báo cáo cho công an tự gửi đi sau một khoảng chờ ngắn",
    "workflow.step.police_immediate": "Báo cáo cho công an được gửi ngay",
    "workflow.step.finish": "Khách nhận email xác nhận",
    "workflow.step.finish_lock": "Khách nhận mã cửa và email xác nhận",
    "workflow.short.paste": "Tin nhắn cho khách",
    "workflow.short.form": "Biểu mẫu cho khách",
    "workflow.short.email": "Email của bạn",
    "workflow.short.police": "Báo cáo công an",
    "workflow.short.police_manual": "Báo cáo công an",
    "workflow.short.police_scheduled": "Báo cáo công an",
    "workflow.short.police_immediate": "Báo cáo công an",
    "workflow.short.finish": "Email xác nhận",
    "workflow.short.finish_lock": "Mã cửa và email xác nhận",
    "workflow.step_of": "%(n)s / %(total)s",
    "workflow.journey.label": "Bước %(n)s / %(total)s: %(step)s",
    "workflow.journey.complete": "Đã xong cả 5 bước",
    "workflow.journey.state.done": "xong",
    "workflow.journey.state.current": "bây giờ",
    "workflow.link.now": "Đã có trên liên kết cho khách",
    "workflow.link.from": "Có trên liên kết cho khách từ %(date)s",
    "workflow.link.next_stay": "Lượt lưu trú tiếp theo của bạn (%(stay)s) sẽ hiện trên liên kết cho khách từ %(date)s.",
    "workflow.link.next_stay_now": "Lượt lưu trú tiếp theo của bạn (%(stay)s) đã có trên liên kết cho khách.",
    "workflow.link.no_stay": "Lượt lưu trú hiện trên liên kết cho khách %(count)s ngày trước ngày nhận phòng.",
    "workflow.link.no_stay.one": "Lượt lưu trú hiện trên liên kết cho khách 1 ngày trước ngày nhận phòng.",
    "workflow.link.no_stay.few": "Lượt lưu trú hiện trên liên kết cho khách %(count)s ngày trước ngày nhận phòng.",
    "workflow.link.why": "Liên kết cho khách chỉ hiện các lượt lưu trú sắp bắt đầu, để khách khác không thể chọn trước lượt này. Liên kết riêng của khách này dùng được ngay.",
    "workflow.link.copy_own": "Sao chép liên kết riêng của khách",
    "workflow.link.preview": "Xem khách thấy gì hôm nay",
    "workflow.link.host_note": "Chỉ bạn thấy ghi chú này. Lượt lưu trú tiếp theo (%(stay)s) sẽ hiện ở đây từ %(date)s. Cần sớm hơn? Hãy gửi cho khách liên kết riêng từ trang lượt lưu trú.",
    "workflow.link.host_note_none": "Chỉ bạn thấy ghi chú này. Chưa có lượt lưu trú sắp tới. Lượt lưu trú sẽ hiện ở đây ngay trước ngày nhận phòng.",
    "workflow.paste.title": "Chưa có khách nào dùng liên kết cho khách của bạn",
    "workflow.paste.body": "Bạn đã dán tin nhắn cho khách vào Airbnb hoặc Booking.com chưa?",
    "workflow.paste.how": "Cách dán",
    "workflow.paste.airbnb": "Airbnb: thêm làm tin nhắn đã lên lịch, gửi sau mỗi lượt đặt.",
    "workflow.paste.booking": "Booking.com: thêm làm mẫu tin nhắn được gửi tự động.",
    "workflow.paste.direct": "Đặt trực tiếp: dán vào xác nhận đặt phòng của bạn.",
    "workflow.paste.open": "Mở tin nhắn cho khách",
    "wizard.optional_suffix": " (không bắt buộc)",
    "wizard.door_lock.question": "Bạn có khóa thông minh không?",
    "wizard.door_lock.no": "Không có khóa thông minh",
    "wizard.door_lock.no_hint": "Tôi giao chìa khóa hoặc dùng hộp đựng chìa khóa",
    "wizard.door_lock.yes": "Có, tôi có khóa TTLock",
    "wizard.door_lock.yes_hint": "Có gateway, để mã đến khóa qua mạng",
    "wizard.door_lock.other_brands": "Hiện chưa hỗ trợ các hãng khác.",
    "wizard.summary.status.not_needed": "Không cần",
    "why.door_lock": "Với khóa thông minh TTLock, UbyHost tạo cho mỗi lượt lưu trú một mã cửa chỉ dùng được trong thời gian lưu trú. Khách nhận mã khi mọi người đã đăng ký xong, nên bạn không cần giao chìa khóa.",
})
```

Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_onboarding_why_0206.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -5` → all pass. Commit `0230 step 4`.

### Step 5. Create `App/app/static/workflow.css` with exactly this content

```css
/* 0230: foolproof workflow round 1. Strip (A), stay tracker (B), guest-link
   window (I), paste check (D), lock question (J). Bordered, light, AA. */

.workflow-block { margin: 0 0 var(--space-5); }
.workflow-block > h2 { margin: 0 0 var(--space-3); font-size: var(--text-md); }
.workflow-strip { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-2); margin: 0; padding: 0; list-style: none; }
.workflow-strip-step { display: flex; align-items: flex-start; gap: var(--space-3); min-width: 0; padding: var(--space-3) var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface); }
.workflow-strip-step.is-you { border-color: var(--brand); background: var(--brand-soft); }
.workflow-num { flex: 0 0 auto; display: inline-grid; place-items: center; width: 28px; height: 28px; border: 1px solid var(--border-strong); border-radius: 999px; background: var(--surface); color: var(--ink); font-size: var(--text-sm); font-weight: 700; line-height: 1; }
.workflow-strip-step.is-you .workflow-num { border-color: var(--brand-action); background: var(--brand-action); color: var(--on-brand); }
.workflow-strip-copy { display: grid; gap: var(--space-1); min-width: 0; }
.workflow-strip-label { color: var(--ink); font-size: var(--text-sm); line-height: 1.35; overflow-wrap: anywhere; }
.workflow-tag { justify-self: start; display: inline-flex; align-items: center; min-height: 22px; padding: 0 var(--space-2); border: 1px solid var(--border); border-radius: var(--radius-pill); background: var(--surface); color: var(--ink-secondary); font-size: var(--text-xs); font-weight: 600; white-space: nowrap; }
.workflow-strip-step.is-you .workflow-tag { border-color: var(--brand); color: var(--brand-ink); }
@media (min-width: 1100px) {
  .workflow-strip { grid-template-columns: repeat(5, minmax(0, 1fr)); }
  .workflow-strip-step { flex-direction: column; gap: var(--space-2); }
}

.journey { margin: 0 0 var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
.journey > summary { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-3); min-height: 44px; padding: var(--space-2) var(--space-3); cursor: pointer; list-style: none; }
.journey > summary::-webkit-details-marker { display: none; }
.journey > summary::after { content: ""; width: 8px; height: 8px; margin-left: auto; border-right: 2px solid var(--ink-muted); border-bottom: 2px solid var(--ink-muted); transform: rotate(45deg); }
.journey[open] > summary::after { transform: rotate(-135deg); }
.journey-dots { display: flex; align-items: center; gap: 6px; margin: 0; padding: 0; list-style: none; }
.journey-dots li { width: 10px; height: 10px; border: 1.5px solid var(--border-strong); border-radius: 999px; background: var(--surface); }
.journey-dots li.is-done { border-color: var(--green-700); background: var(--green-700); }
.journey-dots li.is-current { width: 22px; border-color: var(--brand-action); background: var(--brand-action); }
.journey-label { color: var(--ink); font-size: var(--text-sm); font-weight: 600; }
.journey-steps { display: grid; gap: var(--space-2); margin: 0; padding: 0 var(--space-3) var(--space-3); list-style: none; }
.journey-steps li { display: flex; align-items: flex-start; gap: var(--space-2); color: var(--ink-secondary); font-size: var(--text-sm); }
.journey-steps li.is-current { color: var(--ink); font-weight: 600; }
.journey-steps .workflow-num { width: 24px; height: 24px; font-size: var(--text-xs); }
.journey-steps li.is-done .workflow-num { border-color: var(--green-700); background: var(--status-done-bg); color: var(--green-700); }
.journey-steps li.is-current .workflow-num { border-color: var(--brand-action); background: var(--brand-action); color: var(--on-brand); }

.link-window { display: inline-flex; align-items: center; gap: var(--space-1); color: var(--ink-secondary); font-size: var(--text-xs); }
.link-window.is-later { color: var(--amber-700); font-weight: 600; }
.link-window-line { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-1); margin: var(--space-1) 0 0; }
.link-window-note { margin: var(--space-2) 0 0; }

.paste-check { display: grid; gap: var(--space-2); margin: 0 0 var(--space-4); padding: var(--space-4); border: 1px solid var(--border-strong); border-left: 4px solid var(--amber); border-radius: var(--radius-md); background: var(--surface); }
.paste-check h2 { margin: 0; font-size: var(--text-md); }
.paste-check p { margin: 0; }
.paste-check summary { display: inline-flex; align-items: center; min-height: 44px; cursor: pointer; font-weight: 600; }
.paste-check ul { display: grid; gap: var(--space-1); margin: 0 0 var(--space-2); padding-left: var(--space-5); }
.paste-check-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }

.lock-choice { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-3); margin: var(--space-3) 0; }
.lock-choice-form { margin: 0; }
.lock-choice-option { display: grid; gap: var(--space-1); width: 100%; min-height: 88px; padding: var(--space-4); border: 1.5px solid var(--border-strong); border-radius: var(--radius-lg); background: var(--surface); color: var(--ink); font: inherit; text-align: left; cursor: pointer; list-style: none; }
.lock-choice-option::-webkit-details-marker { display: none; }
.lock-choice-option:hover { border-color: var(--ink); background: var(--surface-hover); }
.lock-choice-option strong { font-size: var(--text-md); }
.lock-choice-option span { color: var(--ink-secondary); font-size: var(--text-sm); }
.lock-choice-yes[open] > .lock-choice-option { border-color: var(--brand-action); box-shadow: 0 0 0 1px var(--brand-action); }
.lock-choice-yes > .setup-wizard-lock-panel { margin-top: var(--space-3); }
.lock-choice-note { margin: 0; color: var(--ink-secondary); font-size: var(--text-sm); }
@media (min-width: 720px) {
  .lock-choice { grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
  .lock-choice-yes[open] { grid-column: 1 / -1; }
}

.journey > summary:focus-visible,
.lock-choice-option:focus-visible,
.paste-check summary:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
```

Command: `test -s App/app/static/workflow.css && echo ok` → `ok`. Commit `0230 step 5`.

### Step 6. `App/app/templates/base.html`: link the stylesheet

Anchor (exact line): `  <link rel="stylesheet" href="/static/host2.css?v=20261021-0418m">`

Insert directly after it:

```html
  <link rel="stylesheet" href="/static/workflow.css?v=20261022-0230">
```

Command: `grep -c "workflow.css?v=20261022-0230" App/app/templates/base.html` → `1`. Commit `0230 step 6`.

### Step 7. Create `App/tests/test_workflow_0230.py` with exactly this content

```python
"""0230: the five-step story, the guest-link window and the paste check."""

from __future__ import annotations

from datetime import date

from app import db, workflow
from app.main import app  # noqa: F401  (creates the test database schema)

TODAY = date(2026, 11, 10)


def test_steps_follow_the_police_option_and_name_who_acts():
    manual = workflow.steps({"automation_mode": "manual", "lock_provider": None})
    assert [s["n"] for s in manual] == [1, 2, 3, 4, 5]
    assert manual[0]["who"] == "you_once"
    assert manual[3] == {"n": 4, "key": "police_manual", "who": "you"}
    assert workflow.steps({"automation_mode": "scheduled"})[3]["who"] == "auto"
    assert workflow.steps(None)[3]["key"] == "police"
    assert workflow.steps(None)[4]["key"] == "finish"


def test_status_maps_to_one_step():
    assert workflow.step_number("awaiting_guest") == 2
    assert workflow.step_number("incomplete") == 2
    assert workflow.step_number("ready") == 4
    assert workflow.step_number("failed") == 4
    assert workflow.step_number("reported") == 5
    assert workflow.step_number("not_required") is None


def _stay(date_from, **extra):
    row = {"status": "active", "archived_at": None, "source": "airbnb",
           "date_from": date_from, "permalink_window_days": 2}
    row.update(extra)
    return row


def test_link_window_matches_the_guest_picker_rule():
    assert workflow.link_window(_stay("2026-11-12"), TODAY) == {"state": "now", "opens": TODAY}
    later = workflow.link_window(_stay("2026-11-20"), TODAY)
    assert later == {"state": "from", "opens": date(2026, 11, 18)}
    assert workflow.link_window(_stay("2026-11-09"), TODAY) is None
    assert workflow.link_window(_stay("2026-11-20", source="demo"), TODAY) is None
    assert workflow.link_window(_stay("2026-11-20", status="cancelled"), TODAY) is None


def _apartment(token):
    entity = db.insert("legal_entity", {"name": "Workflow 0230 s.r.o.", "created_at": db.utcnow()})
    return db.insert("apartment", {
        "legal_entity_id": entity, "internal_name": "Workflow flat", "permalink_token": token,
        "active": 1, "permalink_window_days": 2, "created_at": "2026-11-01T08:00:00",
    })


def _reservation(apartment_id, date_from, uid):
    return db.insert("reservation", {
        "apartment_id": apartment_id, "uid": uid, "date_from": date_from, "date_to": "2026-11-30",
        "status": "active", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def test_paste_check_shows_until_a_guest_claims_a_stay():
    apartment_id = _apartment("workflow0230token")
    try:
        row = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        assert workflow.link_unused([row], TODAY) == []  # no stay reached the link yet
        reservation_id = _reservation(apartment_id, "2026-11-11", "wf0230-a")
        assert [r["id"] for r in workflow.link_unused([row], TODAY)] == [apartment_id]
        db.insert("reservation_claim", {
            "reservation_id": reservation_id, "state": "claimed", "token_version": 0,
            "claimed_at": db.utcnow(), "created_at": db.utcnow(), "updated_at": db.utcnow(),
        })
        assert workflow.guest_used_link(apartment_id) is True
        assert workflow.link_unused([row], TODAY) == []
    finally:
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))


def test_strings_exist_in_every_host_language():
    from app import host_i18n

    for lang in ("en", "cs", "vi"):
        for key in ("workflow.title", "workflow.link.from", "workflow.paste.title",
                    "wizard.door_lock.question", "wizard.summary.status.not_needed"):
            assert host_i18n.STRINGS[lang].get(key), (lang, key)
```

Command: `cd App && .venv/bin/python -m pytest tests/test_workflow_0230.py -q --tb=short -x 2>&1 | tail -15` → 6 passed. If an insert fails with `NOT NULL constraint failed: <table>.<column>`, add that one column with a plain test value to the insert in the test (only in this test file) and rerun once. Commit `0230 step 7`.

## 5. Do not touch

Everything outside §3. `App/app/routes/guest.py` (0231 changes it). No migration, no new dependency, no em dash.

## 6. Commands

1. `cd App && .venv/bin/python -m pytest tests/test_workflow_0230.py tests/test_host_i18n.py tests/test_onboarding_why_0206.py tests/test_no_em_dashes.py -q --tb=short 2>&1 | tail -15`
2. `cd .. && python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] `app/workflow.py` exists and the 6 new tests pass.
- [ ] `tests/test_host_i18n.py` passes (EN/CS parity, VI placeholders).
- [ ] `base.html` links `workflow.css?v=20261022-0230` once.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0230-report.md` (600 tokens at most) with: `git diff --stat`, each command with its last 5 lines, §7 ticked, deviations, questions. Set `Status: review`. Do not push and do not open a PR (the orchestrator does that for all of round 1).

## Risk list (for the reviewer)

`App/app/workflow.py` (SQL, privacy), `App/app/host_i18n.py`.

## Owner steps

None for this brief. Deploy notes come with the round-1 PR.
