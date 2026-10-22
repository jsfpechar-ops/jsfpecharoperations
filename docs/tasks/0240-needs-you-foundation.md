# 0240: "What needs you", foundation (module, copy, styles) (idea N)

Status: todo
Depends on: 0239 | Base commit: after 0239 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `app/needs_you.py`, which turns what the dashboard already loads (stays, alerts, unfinished police setup, the paste check) into one ordered list of lines, each a bold subject, one plain sentence and one button to the exact fix. Add its copy in EN, CS and VI and its styles. Brief 0241 puts the card on the dashboard.

## 2. Context

- Idea N (owner, 2026-10-22): "One card listing only the things that need the host, each as a plain sentence with one button... When nothing needs them, it says so: 'Nothing needs you today. 3 stays are on track.' This replaces hunting through lists." Outside the wizard: no description walls; visible borders; WCAG 2.2 AA; light mode only; no em dashes.
- Rows come from `reporting.dashboard_rows()`: dicts with `reservation` (row with `id`, `internal_name`, `summary`, `source`, `date_from`, `date_to`, `automation_mode`), `progress` (`status` in awaiting_guest, incomplete, ready, awaiting_verification, failed, reported, not_required) and `urgency` (`overdue`, `urgent`, `soon`, `ok`, `future`). `reporting.queue_groups()` splits them into `needs_action`, `waiting`, `upcoming`, `completed`.
- Alert cards come from `alerts.present_many()`: dicts with `id`, `kind`, `level` (critical, warning, info), `display_title`, `display_detail`, `reservation_id`, `apartment_id`, and since 0239 `action_label_key`, `action_href`.
- Stay page anchors: `#now` (send button), `#guests`, `#stay-link` (the stay's own guest link).
- Strings pattern: see 0239 (block after `for _lang, _strings in _PLAIN_FIXES_0239_STRINGS.items():` in `host_i18n.py`; VI `STRINGS.update({...})` at the end of `host_vi_i18n.py`). Counted keys ship `base`, `base.one`, `base.few` in every language.
- Static files get a new `?v=` key (owner rule, `tests/test_static_versions.py` guards it).
- Every class a host template uses must be in `docs/design/catalog.json` `classes` with a `class_notes` entry (`tests/test_design_lint.py`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/needs_you.py` | create | the module (step 1) |
| `App/app/templating.py` | edit | register one global (step 2) |
| `App/app/host_i18n.py` | edit | EN + CS (step 3) |
| `App/app/host_vi_i18n.py` | edit | VI (step 4) |
| `App/app/static/workflow.css` | edit | styles (step 5) |
| `App/app/templates/base.html` | edit | new `?v=` (step 6) |
| `docs/design/catalog.json` | edit | classes + notes (step 7) |
| `App/tests/test_needs_you_0240.py` | create | tests (step 8) |
| `docs/tasks/0240-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. Create `App/app/needs_you.py` with exactly this content

```python
"""0240 (idea N): "What needs you", the one card at the top of the dashboard.

Each line is a bold subject, one plain sentence and one button that lands on
the exact fix. It gathers what used to be separate blocks on the dashboard:
the alert stack, the stays that need the host, unfinished police setup and
the paste reminder (0233). It reads only what the dashboard already loaded.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

from . import host_i18n, validation

_TONE_RANK = {"red": 0, "amber": 1, "grey": 2}
_ALERT_TONE = {"critical": "red", "warning": "amber", "info": "grey"}
_FINISHED = ("reported", "not_required")
_SEND = ("ready", "awaiting_verification")
_GUEST = ("awaiting_guest", "incomplete")
# The settings part of the page that holds each missing police field.
_SETUP_QUERY = {
    "basics": "view=settings&section=property",
    "address": "view=settings&section=property",
    "ubyport": "view=settings&section=reporting",
    "calendars": "view=bookings",
}


def _get(row, key: str, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _line(kind: str, tone: str, subject: str, text: str, action: str, href: str, **extra) -> Dict[str, Any]:
    return {
        "kind": kind,
        "tone": tone,
        "subject": subject,
        "text": text,
        "action": action,
        "href": href,
        "dismiss_id": extra.get("dismiss_id"),
        "stay_id": extra.get("stay_id"),
        "apartment_id": extra.get("apartment_id"),
    }


def _stay_name(reservation) -> str:
    """The same name the stay list uses: the typed label of a hand-made stay."""
    label = _get(reservation, "summary", "")
    if _get(reservation, "source", "") != "manual" or not str(label).strip():
        label = _get(reservation, "internal_name", "")
    dates = validation.fmt_date_range(_get(reservation, "date_from"), _get(reservation, "date_to"))
    return f"{label} · {dates}"


def stay_line(row: Dict[str, Any], lang: str, today: date) -> Optional[Dict[str, Any]]:
    """The line for one stay, or None while the stay is on track."""
    from . import demo  # local: demo imports many modules

    def t(key: str, **kwargs) -> str:
        return host_i18n.translate(lang, key, **kwargs)

    reservation = row["reservation"]
    status = row["progress"]["status"]
    if status in _FINISHED:
        return None
    stay_id = reservation["id"]
    subject = _stay_name(reservation)
    base = f"/reservations/{stay_id}?return_to=/"
    if status == "failed":
        return _line("stay", "red", subject, t("needs_you.stay.failed"), t("needs_you.action.fix"), base + "#guests", stay_id=stay_id)
    if row.get("urgency") == "overdue":
        if status in _SEND:
            return _line("stay", "red", subject, t("needs_you.stay.overdue"), t("needs_you.action.send"), base + "#now", stay_id=stay_id)
        return _line("stay", "red", subject, t("needs_you.stay.overdue"), t("needs_you.action.open"), base, stay_id=stay_id)
    if demo.is_demo_stay(reservation):
        return None
    if status in _SEND:
        # Automatic and scheduled reporting send by themselves: on track.
        if _get(reservation, "automation_mode", "manual") != "manual":
            return None
        return _line("stay", "amber", subject, t("needs_you.stay.ready"), t("needs_you.action.send"), base + "#now", stay_id=stay_id)
    arrival = validation.parse_iso_date(_get(reservation, "date_from", ""))
    if status in _GUEST and arrival is not None and arrival <= today + timedelta(days=1):
        if arrival < today:
            when = t("needs_you.when.arrived")
        elif arrival == today:
            when = t("needs_you.when.today")
        else:
            when = t("needs_you.when.tomorrow")
        key = "needs_you.stay.no_form" if status == "awaiting_guest" else "needs_you.stay.forms_missing"
        return _line("stay", "amber", subject, t(key, when=when), t("needs_you.action.send_link"), base + "#stay-link", stay_id=stay_id)
    return None


def build(
    rows: Iterable[Dict[str, Any]],
    queue: Dict[str, List[Dict[str, Any]]],
    cards: Iterable[Dict[str, Any]],
    missing_rows: Iterable[Dict[str, Any]],
    link_unused: Iterable[Any],
    lang: str,
    today: date,
) -> Dict[str, Any]:
    """{"lines": [...], "on_track": n}: red first, then amber, then grey."""

    def t(key: str, **kwargs) -> str:
        return host_i18n.translate(lang, key, **kwargs)

    lines: List[Dict[str, Any]] = []
    covered = set()
    for bucket in ("needs_action", "waiting", "upcoming"):
        for row in (queue or {}).get(bucket, []):
            stay_id = row["reservation"]["id"]
            if stay_id in covered:
                continue
            line = stay_line(row, lang, today)
            if line:
                covered.add(stay_id)
                lines.append(line)
    setup_alerts = set()
    pin_cards = [card for card in cards or [] if card.get("kind") == "guest_pin_rotated"]
    for card in cards or []:
        kind = card.get("kind") or ""
        if card.get("reservation_id") and card["reservation_id"] in covered:
            continue  # the stay's own line says it, with live numbers
        if kind == "apartment_setup" and card.get("apartment_id"):
            setup_alerts.add(card["apartment_id"])
        href = card.get("action_href") or ""
        action = t(card["action_label_key"]) if card.get("action_label_key") else ""
        if kind == "guest_pin_rotated":
            if card is not pin_cards[0]:
                continue
            if len(pin_cards) > 1:
                href, action = "/apartments", t("dashboard.setup.view_properties")
        lines.append(_line(
            "alert",
            _ALERT_TONE.get(card.get("level") or "", "amber"),
            card.get("display_title") or card.get("message") or "",
            card.get("display_detail") or card.get("detail") or "",
            action,
            href,
            dismiss_id=None if kind == "dates_changed_resign" else card.get("id"),
            stay_id=card.get("reservation_id"),
            apartment_id=card.get("apartment_id"),
        ))
    for row in missing_rows or []:
        apartment = row["apartment"]
        if apartment["id"] in setup_alerts or not row.get("missing"):
            continue
        # One short line, never the field-by-field list (owner, 2026-10-22):
        # the button opens the first missing field.
        first = row["missing"][0]["anchor"]
        lines.append(_line(
            "setup", "amber", apartment["internal_name"] or "",
            t("needs_you.setup"), t("needs_you.action.setup"),
            f"/apartments/{apartment['id']}?{_SETUP_QUERY.get(first, 'view=settings')}#{first}",
            apartment_id=apartment["id"],
        ))
    for apartment in link_unused or []:
        lines.append(_line(
            "paste", "amber", apartment["internal_name"] or "",
            t("needs_you.paste"), t("workflow.paste.open"),
            f"/apartments/{apartment['id']}?view=settings&section=guests#communication",
            apartment_id=apartment["id"],
        ))
    lines.sort(key=lambda line: _TONE_RANK.get(line["tone"], 1))
    on_track = sum(
        1 for row in rows or []
        if row["progress"]["status"] not in _FINISHED and row["reservation"]["id"] not in covered
    )
    return {"lines": lines, "on_track": on_track}
```

Command: `cd App && .venv/bin/python -c "import app.needs_you" 2>&1 | tail -3` → no output. Commit `0240 step 1`.

### Step 2. `templating.py`: register the global

Anchor (exact line): `templates.env.globals["next_stay_window"] = workflow.next_stay_window`

Insert directly AFTER it:

```python
# 0240: "What needs you" on the dashboard.
from . import needs_you  # noqa: E402

templates.env.globals["needs_you_build"] = needs_you.build
```

Commit `0240 step 2`.

### Step 3. `host_i18n.py`: EN + CS

Anchor (exact two lines):

```python
for _lang, _strings in _PLAIN_FIXES_0239_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Insert directly AFTER them:

```python

# 0240 (idea N): "What needs you".
_NEEDS_YOU_0240_STRINGS = {
    "en": {
        "needs_you.title": "What needs you",
        "needs_you.calm": "Nothing needs you today.",
        "needs_you.on_track": "%(count)s stays are on track.",
        "needs_you.on_track.one": "1 stay is on track.",
        "needs_you.on_track.few": "%(count)s stays are on track.",
        "needs_you.more": "Show %(count)s more",
        "needs_you.more.one": "Show 1 more",
        "needs_you.more.few": "Show %(count)s more",
        "needs_you.stay.failed": "The police did not accept the report.",
        "needs_you.stay.overdue": "The police deadline has passed.",
        "needs_you.stay.ready": "All guest forms are done. Send the police report.",
        "needs_you.stay.no_form": "The guest %(when)s and has not filled in the guest form.",
        "needs_you.stay.forms_missing": "The guest %(when)s and some guest forms are not finished.",
        "needs_you.when.today": "arrives today",
        "needs_you.when.tomorrow": "arrives tomorrow",
        "needs_you.when.arrived": "has arrived",
        "needs_you.setup": "Police details are missing, so no police report can go out yet.",
        "needs_you.paste": "No guest has used your guest link yet. Did you paste the guest message into Airbnb or Booking.com?",
        "needs_you.action.fix": "Fix the report",
        "needs_you.action.send": "Send the report",
        "needs_you.action.open": "Open the stay",
        "needs_you.action.send_link": "Send the guest link",
        "needs_you.action.setup": "Finish setup",
    },
    "cs": {
        "needs_you.title": "Co na vás čeká",
        "needs_you.calm": "Dnes na vás nic nečeká.",
        "needs_you.on_track": "%(count)s pobytů běží podle plánu.",
        "needs_you.on_track.one": "1 pobyt běží podle plánu.",
        "needs_you.on_track.few": "%(count)s pobyty běží podle plánu.",
        "needs_you.more": "Zobrazit dalších %(count)s",
        "needs_you.more.one": "Zobrazit další 1",
        "needs_you.more.few": "Zobrazit další %(count)s",
        "needs_you.stay.failed": "Policie hlášení nepřijala.",
        "needs_you.stay.overdue": "Lhůta pro hlášení policii už uplynula.",
        "needs_you.stay.ready": "Všechny formuláře hostů jsou hotové. Odešlete hlášení policii.",
        "needs_you.stay.no_form": "Host %(when)s a ještě nevyplnil formulář pro hosty.",
        "needs_you.stay.forms_missing": "Host %(when)s a některé formuláře hostů ještě nejsou hotové.",
        "needs_you.when.today": "přijede dnes",
        "needs_you.when.tomorrow": "přijede zítra",
        "needs_you.when.arrived": "už přijel",
        "needs_you.setup": "Chybí údaje pro policii, takže zatím nemůže odejít žádné hlášení.",
        "needs_you.paste": "Odkaz pro hosty zatím žádný host nepoužil. Vložili jste zprávu pro hosty do Airbnb nebo Booking.com?",
        "needs_you.action.fix": "Opravit hlášení",
        "needs_you.action.send": "Odeslat hlášení",
        "needs_you.action.open": "Otevřít pobyt",
        "needs_you.action.send_link": "Poslat odkaz hostovi",
        "needs_you.action.setup": "Dokončit nastavení",
    },
}
for _lang, _strings in _NEEDS_YOU_0240_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

### Step 4. `host_vi_i18n.py`: VI

Append at the very end of the file:

```python

# 0240 (idea N): "What needs you".
STRINGS.update({
    "needs_you.title": "Việc cần bạn",
    "needs_you.calm": "Hôm nay không có việc gì cần bạn.",
    "needs_you.on_track": "%(count)s lượt lưu trú đang đúng kế hoạch.",
    "needs_you.on_track.one": "1 lượt lưu trú đang đúng kế hoạch.",
    "needs_you.on_track.few": "%(count)s lượt lưu trú đang đúng kế hoạch.",
    "needs_you.more": "Xem thêm %(count)s",
    "needs_you.more.one": "Xem thêm 1",
    "needs_you.more.few": "Xem thêm %(count)s",
    "needs_you.stay.failed": "Cảnh sát không chấp nhận khai báo.",
    "needs_you.stay.overdue": "Đã quá hạn khai báo cảnh sát.",
    "needs_you.stay.ready": "Khách đã điền xong mọi biểu mẫu. Hãy gửi khai báo cảnh sát.",
    "needs_you.stay.no_form": "Khách %(when)s nhưng chưa điền biểu mẫu cho khách.",
    "needs_you.stay.forms_missing": "Khách %(when)s nhưng một số biểu mẫu cho khách chưa xong.",
    "needs_you.when.today": "đến hôm nay",
    "needs_you.when.tomorrow": "đến ngày mai",
    "needs_you.when.arrived": "đã đến",
    "needs_you.setup": "Còn thiếu thông tin cho cảnh sát nên chưa gửi được khai báo nào.",
    "needs_you.paste": "Chưa có khách nào dùng liên kết cho khách của bạn. Bạn đã dán tin nhắn cho khách vào Airbnb hoặc Booking.com chưa?",
    "needs_you.action.fix": "Sửa khai báo",
    "needs_you.action.send": "Gửi khai báo",
    "needs_you.action.open": "Mở lượt lưu trú",
    "needs_you.action.send_link": "Gửi liên kết cho khách",
    "needs_you.action.setup": "Hoàn tất thiết lập",
})
```

Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short 2>&1 | tail -5` → all pass. Commit `0240 steps 3-4`.

### Step 5. `workflow.css`: append at the end of the file

```css

/* 0240 (idea N): "What needs you". One bordered card, one bordered line per
   thing, a coloured left edge for how urgent it is (the words say it too). */
.needs-you { margin: 0 0 var(--space-5); padding: var(--space-4); border: 1px solid var(--border-strong); border-radius: var(--radius-lg); background: var(--surface); }
.needs-you > h2 { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); margin: 0 0 var(--space-3); font-size: var(--text-md); line-height: 1.3; }
.needs-you-list { display: grid; gap: var(--space-2); margin: 0; padding: 0; list-style: none; }
.needs-you-item { display: grid; grid-template-columns: minmax(0, 1fr); align-items: center; gap: var(--space-2); min-width: 0; padding: var(--space-3); border: 1px solid var(--border); border-left: 4px solid var(--amber); border-radius: var(--radius-md); background: var(--surface); }
.needs-you-item[data-tone="red"] { border-left-color: var(--red); }
.needs-you-item[data-tone="grey"] { border-left-color: var(--border-strong); }
.needs-you-copy { display: grid; gap: 2px; min-width: 0; }
.needs-you-copy strong { color: var(--ink); font-size: var(--text-sm); line-height: 1.35; overflow-wrap: anywhere; }
.needs-you-copy span { color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.4; overflow-wrap: anywhere; }
.needs-you-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); }
.needs-you-actions .ui-btn { min-height: 44px; }
.needs-you-dismiss { display: inline-flex; margin: 0; }
.needs-you-more { margin-top: var(--space-2); }
.needs-you-more > summary { display: inline-flex; align-items: center; min-height: 44px; cursor: pointer; font-weight: 600; }
.needs-you-more > .needs-you-list, .needs-you-how { margin-top: var(--space-2); }
.needs-you-how { display: grid; gap: var(--space-1); margin-bottom: 0; padding-left: var(--space-5); }
.needs-you-calm { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); margin: 0; color: var(--ink); }
.needs-you-calm svg { color: var(--green-700); }
.needs-you-calm span { color: var(--ink-secondary); }
.needs-you-more > summary:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
@media (min-width: 720px) {
  .needs-you-item { grid-template-columns: minmax(0, 1fr) auto; }
  .needs-you-actions { justify-content: flex-end; flex-wrap: nowrap; }
}
```

Commit `0240 step 5`.

### Step 6. `base.html`: new cache key

Anchor (exact line): `  <link rel="stylesheet" href="/static/workflow.css?v=20261022-0237">`

Replace with: `  <link rel="stylesheet" href="/static/workflow.css?v=20261022-0240">`

Command: `cd App && .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short 2>&1 | tail -5` → pass. Commit `0240 step 6`.

### Step 7. `docs/design/catalog.json`

Run from the repo root exactly:

```bash
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path("docs/design/catalog.json")
c = json.loads(p.read_text(encoding="utf-8"))
notes = {
    "needs-you": "0240 dashboard card 'What needs you': bordered, holds one line per thing that needs the host, or the calm line.",
    "needs-you-list": "0240 list of needs-you-item lines.",
    "needs-you-item": "0240 one line: subject, one sentence, one button; data-tone red/amber/grey sets the left edge colour.",
    "needs-you-copy": "0240 subject (strong) and sentence (span) of a needs-you-item.",
    "needs-you-actions": "0240 the button (and dismiss for alerts) of a needs-you-item.",
    "needs-you-dismiss": "0240 dismiss form for an alert line, same endpoint as the alert stack.",
    "needs-you-more": "0240 details that holds lines past the fifth, and the paste how-to.",
    "needs-you-how": "0240 paste how-to list inside needs-you-more.",
    "needs-you-calm": "0240 'Nothing needs you today' line with a tick.",
}
for name, note in notes.items():
    if name not in c["classes"]:
        c["classes"].append(name)
    c["class_notes"][name] = note
p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
EOF
git diff --stat docs/design/catalog.json
```

The diff must touch only `docs/design/catalog.json` with about 18 added lines. If the diff rewrites the whole file (indentation or key order changed), run `git checkout docs/design/catalog.json` and instead add the 9 names by hand at the end of the `"classes"` list and the 9 notes at the end of `"class_notes"`, matching the existing formatting. Commit `0240 step 7`.

### Step 8. Create `App/tests/test_needs_you_0240.py` with exactly this content

```python
"""0240 (idea N): the lines of the "What needs you" card."""

from __future__ import annotations

from datetime import date, timedelta

from app import needs_you

TODAY = date(2026, 10, 22)


def _row(stay_id, status, *, days=0, urgency="future", mode="manual", source="airbnb"):
    start = TODAY + timedelta(days=days)
    return {
        "reservation": {
            "id": stay_id, "internal_name": "Loft", "summary": "", "source": source,
            "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
            "automation_mode": mode,
        },
        "progress": {"status": status},
        "urgency": urgency,
    }


def _build(rows, cards=(), missing=(), unused=(), lang="en"):
    queue = {"needs_action": list(rows), "waiting": [], "upcoming": []}
    return needs_you.build(rows, queue, list(cards), list(missing), list(unused), lang, TODAY)


def test_calm_when_nothing_needs_the_host():
    result = _build([_row(1, "awaiting_guest", days=10), _row(2, "ready", days=3, mode="scheduled")])
    assert result["lines"] == []
    assert result["on_track"] == 2


def test_each_stay_gets_one_plain_line_with_the_exact_button():
    rows = [
        _row(1, "failed", days=-2),
        _row(2, "ready", days=2),
        _row(3, "awaiting_guest", days=1),
        _row(4, "incomplete", days=-1, urgency="overdue"),
    ]
    lines = {line["stay_id"]: line for line in _build(rows)["lines"]}
    assert lines[1]["text"] == "The police did not accept the report." and lines[1]["href"].endswith("#guests")
    assert lines[2]["action"] == "Send the report" and lines[2]["href"].endswith("#now")
    assert lines[3]["text"] == "The guest arrives tomorrow and has not filled in the guest form."
    assert lines[3]["href"] == "/reservations/3?return_to=/#stay-link"
    assert lines[4]["tone"] == "red" and lines[4]["text"] == "The police deadline has passed."


def test_red_lines_come_first():
    rows = [_row(2, "ready", days=2), _row(1, "failed", days=-2)]
    tones = [line["tone"] for line in _build(rows)["lines"]]
    assert tones == sorted(tones, key=lambda tone: {"red": 0, "amber": 1, "grey": 2}[tone])


def test_an_alert_for_a_stay_with_its_own_line_is_not_repeated():
    rows = [_row(1, "failed", days=-2)]
    cards = [
        {"id": 7, "kind": "submission_stuck", "level": "warning", "reservation_id": 1, "display_title": "x",
         "display_detail": "y", "action_label_key": "notification.action.guests", "action_href": "/reservations/1#guests"},
        {"id": 8, "kind": "feed_error", "level": "warning", "apartment_id": 5, "display_title": "Calendar 'A' could not be read.",
         "display_detail": "d", "action_label_key": "notification.action.calendar", "action_href": "/apartments/5?view=bookings#calendars"},
    ]
    lines = _build(rows, cards)["lines"]
    assert [line["kind"] for line in lines] == ["stay", "alert"]
    assert lines[1]["action"] == "Check the calendar" and lines[1]["dismiss_id"] == 8


def test_setup_and_paste_lines_name_the_property():
    missing = [{"apartment": {"id": 5, "internal_name": "Loft"}, "missing": [{"key": "ubyport", "anchor": "ubyport"}]}]
    unused = [{"id": 6, "internal_name": "Studio"}]
    lines = _build([], missing=missing, unused=unused, lang="cs")["lines"]
    assert lines[0]["subject"] == "Loft" and lines[0]["href"] == "/apartments/5?view=settings&section=reporting#ubyport"
    assert lines[0]["text"] == "Chybí údaje pro policii, takže zatím nemůže odejít žádné hlášení."
    assert lines[1]["subject"] == "Studio" and lines[1]["href"].endswith("#communication")


def test_demo_stays_never_ask_to_send():
    assert _build([_row(1, "ready", days=2, source="demo")])["lines"] == []
```

Command: `cd App && .venv/bin/python -m pytest tests/test_needs_you_0240.py -q --tb=short -x 2>&1 | tail -15` → 6 passed. Commit `0240 step 8`.

## 5. Do not touch

Everything outside §3. No new query, column or outbound request (privacy, hard rule 2). `reporting.py` and `alerts.py` stay as they are.

## 6. Commands

1. `cd App && .venv/bin/python -m pytest tests/test_needs_you_0240.py tests/test_host_i18n.py tests/test_static_versions.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -15`
2. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] All tests in §6 pass.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0240-report.md` (600 tokens at most) and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/needs_you.py` (which stays count as "on track"), the catalog diff.

## Owner steps

None.
