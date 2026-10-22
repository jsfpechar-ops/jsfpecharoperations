# 0244: Property health check (idea O)

Status: todo
Depends on: 0243 | Base commit: after 0243 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The property overview's "Setup details" box shows eight tiles that say whether each wizard step was done once. It does not say whether the property works today. It becomes a live health check: one bordered row per thing that can break (calendar, guest link, police reports, business details, door codes when a lock is connected), each with one short sentence and, only when something is wrong, one button that opens the exact setting. When nothing is wrong the box shows "All set" and the rows fold away behind "Show the checks".

## 2. Context

- `_property_overview.html` shows the box (`section.panel.host-checklist[data-setup-status]`) only when the setup wizard card is not active. Keep that condition, the section's class, `data-setup-status`, the `.setup-status-head h2` and the `details.setup-readiness-help` (field-by-field list behind "?"): other tests read them.
- Live facts already exist: `readiness` (routes/admin.py `_readiness`: `report` items with `done`/`anchor`, `invite` items `operator`/`controller`), `feeds` (each has `active` and `last_status`, "error" when the last sync failed), `door_code` (None without a lock, else has `enabled`), `workflow.guest_used_link(id)`, `workflow.link_unused([apartment])`, and the `alert` table (`apartment_id`, `kind`, `resolved_at`).
- Settings anchors: `needs_you._SETUP_QUERY` maps an anchor to its settings section (`ubyport` → `view=settings&section=reporting`, `address`/`basics` → `view=settings&section=property`, `calendars` → `view=bookings`).
- Do not touch the setup wizard, the stay fee step or the Settings stay fee section (another thread is changing them). Do not touch `.host-property-grid` / `.host-property-card` (another thread). The health check has no stay fee row for that reason.
- Owner rules: visible borders, no explanatory paragraph outside the wizard (the old "Your setup at a glance." line goes), 44 px buttons, EN/CS/VI.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/property_health.py` | create | the checks (step 1) |
| `App/app/routes/admin.py` | edit | import + one context key (step 2) |
| `App/app/host_i18n.py` | edit | EN + CS strings (step 3) |
| `App/app/host_vi_i18n.py` | edit | VI strings (step 3) |
| `App/app/templates/_property_overview.html` | edit | the box (step 4) |
| `App/app/static/workflow.css` | edit | styles (step 5) |
| `App/app/templates/base.html` | edit | cache key (step 5) |
| `App/tests/static_versions.json` | edit | manifest refresh (step 5) |
| `docs/design/catalog.json` | edit | new classes (step 6) |
| `App/tests/test_property_health_0244.py` | create | tests (step 7) |
| `App/tests/test_onboarding_followup_browser.py` | edit | the overview assertions (step 8) |
| `docs/tasks/0244-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. Create `App/app/property_health.py` with exactly this content

```python
"""0244 (idea O): the property's health check on its overview.

One row per thing that can break today: calendar, guest link, police
reports, business details, and door codes when a lock is connected. A row
that is fine says so in a few words; a row that is not gets one button to
the exact setting. It reads only facts the property page already loads,
plus open alerts.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from . import db, needs_you, workflow

_LOGIN_KINDS = {"ubyport_auth_failed"}
_FEED_KINDS = {"feed_error", "feed_incomplete", "feed_duplicate_uid", "feed_recurring_event"}


def _row(key: str, icon: str, state: str, text_key: str, action_key: str = "", href: str = "") -> Dict[str, str]:
    return {
        "key": key,
        "icon": icon,
        "state": state,  # ok | warn | bad | off
        "label_key": f"health.{key}",
        "text_key": text_key,
        "action_key": action_key,
        "href": href,
    }


def _open_kinds(apartment_id: int) -> set:
    rows = db.query(
        "SELECT kind FROM alert WHERE apartment_id = ? AND resolved_at IS NULL",
        (apartment_id,),
    )
    return {row["kind"] for row in rows}


def checks(
    apartment,
    feeds: Iterable[Any],
    readiness: Optional[Dict[str, Any]],
    door_code: Optional[Dict[str, Any]],
    *,
    open_kinds: Optional[set] = None,
    guest_used: Optional[bool] = None,
    link_due: Optional[bool] = None,
) -> List[Dict[str, str]]:
    """The rows, in a fixed order. The keyword arguments let tests skip the database."""
    apartment_id = apartment["id"]
    base = f"/apartments/{apartment_id}"
    if open_kinds is None:
        open_kinds = _open_kinds(apartment_id)
    rows = []

    active = [feed for feed in feeds or [] if feed["active"]]
    calendar_href = f"{base}?view=bookings#calendars"
    if any(feed["last_status"] == "error" for feed in active) or open_kinds & _FEED_KINDS:
        rows.append(_row("calendar", "calendar-days", "bad", "health.calendar.error", "health.calendar.fix", calendar_href))
    elif not active:
        rows.append(_row("calendar", "calendar-days", "warn", "health.calendar.none", "health.calendar.connect", calendar_href))
    else:
        rows.append(_row("calendar", "calendar-days", "ok", "health.calendar.ok"))

    if guest_used is None:
        guest_used = workflow.guest_used_link(apartment_id)
    if guest_used:
        rows.append(_row("guest_link", "external-link", "ok", "health.guest_link.ok"))
    else:
        if link_due is None:
            link_due = bool(workflow.link_unused([apartment]))
        if link_due:
            rows.append(_row(
                "guest_link", "external-link", "warn", "health.guest_link.unused", "health.guest_link.fix",
                f"{base}?view=settings&section=guests#communication",
            ))
        else:
            rows.append(_row("guest_link", "external-link", "off", "health.guest_link.waiting"))

    missing = [item for item in (readiness or {}).get("report", []) if not item["done"]]
    if open_kinds & _LOGIN_KINDS:
        rows.append(_row(
            "police", "send", "bad", "health.police.login", "health.police.fix_login",
            f"{base}?view=settings&section=reporting#ubyport",
        ))
    elif missing:
        anchor = missing[0]["anchor"]
        query = needs_you._SETUP_QUERY.get(anchor, "view=settings")
        rows.append(_row("police", "send", "bad", "health.police.missing", "health.police.fix", f"{base}?{query}#{anchor}"))
    else:
        rows.append(_row("police", "send", "ok", "health.police.ok"))

    business = [
        item for item in (readiness or {}).get("invite", [])
        if item["key"] in ("operator", "controller") and not item["done"]
    ]
    if business or "controller_missing" in open_kinds:
        rows.append(_row(
            "business", "receipt", "bad", "health.business.missing", "health.business.fix",
            f"{base}?view=settings&section=property#operator-picker",
        ))
    else:
        rows.append(_row("business", "receipt", "ok", "health.business.ok"))

    if door_code is not None:
        if door_code.get("enabled"):
            rows.append(_row("door", "key-round", "ok", "health.door.ok"))
        else:
            rows.append(_row("door", "key-round", "off", "health.door.off"))
    return rows


def to_fix(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """Rows that need the host: a red or amber row with a button."""
    return [row for row in rows if row["state"] in ("bad", "warn")]
```

Command: `cd App && .venv/bin/python -c "import app.property_health" 2>&1 | tail -5` → no output. Commit `0244 step 1`.

### Step 2. `routes/admin.py`

2a. Anchor (these exact lines, the import block):

```python
    property_setup,
    rate_limit,
```

Replace with:

```python
    property_health,
    property_setup,
    rate_limit,
```

2b. Anchor (exact line, in the function that renders `apartment_form.html` with `"readiness": readiness,`; it appears once with that indentation, check with `grep -n '            "readiness": readiness,' app/routes/admin.py`): `            "readiness": readiness,`

Replace with:

```python
            "readiness": readiness,
            # 0244: the live health check on the property overview.
            "health": property_health.checks(apartment, feeds, readiness, door_code),
```

If the grep finds more than one such line, stop and report the line numbers. Command: `cd App && .venv/bin/python -c "import app.routes.admin" 2>&1 | tail -5` → no output. Commit `0244 step 2`.

### Step 3. Strings

3a. `host_i18n.py`. Anchor (these exact lines):

```python
for _lang, _strings in _NEEDS_YOU_0240_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Insert directly AFTER them:

```python

# 0244 (idea O): the property health check.
_HEALTH_0244_STRINGS = {
    "en": {
        "health.title": "Health check",
        "health.all_set": "All set",
        "health.show": "Show the checks",
        "health.to_fix": "%(count)s to fix",
        "health.to_fix.one": "1 to fix",
        "health.to_fix.few": "%(count)s to fix",
        "health.calendar": "Calendar",
        "health.calendar.ok": "Bookings come in by themselves.",
        "health.calendar.none": "No calendar connected. Add stays by hand or connect one.",
        "health.calendar.error": "The last calendar sync failed.",
        "health.calendar.fix": "Check the calendar",
        "health.calendar.connect": "Connect a calendar",
        "health.guest_link": "Guest link",
        "health.guest_link.ok": "A guest has used your link.",
        "health.guest_link.unused": "No guest has used your link yet.",
        "health.guest_link.waiting": "No guest could use it yet.",
        "health.guest_link.fix": "Open the guest message",
        "health.police": "Police reports",
        "health.police.ok": "Police details are complete.",
        "health.police.missing": "Police details are missing, so no report can go out.",
        "health.police.login": "The police system refused the login.",
        "health.police.fix": "Finish police setup",
        "health.police.fix_login": "Fix the police login",
        "health.business": "Business details",
        "health.business.ok": "Complete.",
        "health.business.missing": "Business details are missing.",
        "health.business.fix": "Add business details",
        "health.door": "Door codes",
        "health.door.ok": "Door codes go out by themselves.",
        "health.door.off": "Turned off.",
    },
    "cs": {
        "health.title": "Kontrola nastavení",
        "health.all_set": "Vše v pořádku",
        "health.show": "Zobrazit kontroly",
        "health.to_fix": "%(count)s k opravě",
        "health.to_fix.one": "1 k opravě",
        "health.to_fix.few": "%(count)s k opravě",
        "health.calendar": "Kalendář",
        "health.calendar.ok": "Rezervace se načítají samy.",
        "health.calendar.none": "Žádný kalendář není připojen. Pobyty přidávejte ručně, nebo kalendář připojte.",
        "health.calendar.error": "Poslední synchronizace kalendáře selhala.",
        "health.calendar.fix": "Zkontrolovat kalendář",
        "health.calendar.connect": "Připojit kalendář",
        "health.guest_link": "Odkaz pro hosty",
        "health.guest_link.ok": "Host už váš odkaz použil.",
        "health.guest_link.unused": "Váš odkaz zatím žádný host nepoužil.",
        "health.guest_link.waiting": "Zatím ho nemohl použít žádný host.",
        "health.guest_link.fix": "Otevřít zprávu pro hosty",
        "health.police": "Hlášení policii",
        "health.police.ok": "Údaje pro policii jsou kompletní.",
        "health.police.missing": "Chybí údaje pro policii, proto nemůže odejít žádné hlášení.",
        "health.police.login": "Policejní systém odmítl přihlášení.",
        "health.police.fix": "Dokončit nastavení pro policii",
        "health.police.fix_login": "Opravit přihlášení k policii",
        "health.business": "Údaje o podnikání",
        "health.business.ok": "Kompletní.",
        "health.business.missing": "Chybí údaje o podnikání.",
        "health.business.fix": "Doplnit údaje o podnikání",
        "health.door": "Kódy ke dveřím",
        "health.door.ok": "Kódy ke dveřím odcházejí samy.",
        "health.door.off": "Vypnuto.",
    },
}
for _lang, _strings in _HEALTH_0244_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

3b. `host_vi_i18n.py`: append at the very end of the file:

```python

# 0244 (idea O): the property health check.
STRINGS.update({
    "health.title": "Kiểm tra thiết lập",
    "health.all_set": "Mọi thứ đã sẵn sàng",
    "health.show": "Xem các mục kiểm tra",
    "health.to_fix": "%(count)s mục cần sửa",
    "health.to_fix.one": "1 mục cần sửa",
    "health.to_fix.few": "%(count)s mục cần sửa",
    "health.calendar": "Lịch",
    "health.calendar.ok": "Đặt phòng tự động được cập nhật.",
    "health.calendar.none": "Chưa kết nối lịch. Hãy thêm lượt lưu trú thủ công hoặc kết nối lịch.",
    "health.calendar.error": "Lần đồng bộ lịch gần nhất đã thất bại.",
    "health.calendar.fix": "Kiểm tra lịch",
    "health.calendar.connect": "Kết nối lịch",
    "health.guest_link": "Liên kết cho khách",
    "health.guest_link.ok": "Đã có khách dùng liên kết của bạn.",
    "health.guest_link.unused": "Chưa có khách nào dùng liên kết của bạn.",
    "health.guest_link.waiting": "Chưa có khách nào có thể dùng liên kết.",
    "health.guest_link.fix": "Mở tin nhắn cho khách",
    "health.police": "Khai báo cảnh sát",
    "health.police.ok": "Thông tin cho cảnh sát đã đầy đủ.",
    "health.police.missing": "Thiếu thông tin cho cảnh sát nên chưa thể gửi khai báo.",
    "health.police.login": "Hệ thống cảnh sát đã từ chối đăng nhập.",
    "health.police.fix": "Hoàn tất thiết lập cảnh sát",
    "health.police.fix_login": "Sửa đăng nhập cảnh sát",
    "health.business": "Thông tin doanh nghiệp",
    "health.business.ok": "Đầy đủ.",
    "health.business.missing": "Thiếu thông tin doanh nghiệp.",
    "health.business.fix": "Thêm thông tin doanh nghiệp",
    "health.door": "Mã cửa",
    "health.door.ok": "Mã cửa được gửi tự động.",
    "health.door.off": "Đã tắt.",
})
```

Command: `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_i18n.py -q --tb=short 2>&1 | tail -10` → pass. Commit `0244 step 3`.

### Step 4. `_property_overview.html`: the box

Anchor (these exact lines):

```jinja
<section class="panel host-checklist" data-setup-status aria-labelledby="property-readiness-title">
  <header class="setup-status-head">
    <div><h2 id="property-readiness-title">{{ t('host.setup_details') }}</h2><p>{{ t('wizard.overview.status_note') }}</p></div>
    <span class="ui-badge ui-badge-{{ 'done' if readiness.invite_ready else 'neutral' }}" data-tone="{{ 'green' if readiness.invite_ready else 'grey' }}">{{ t('apartment.form.readiness.invite_ready') if readiness.invite_ready else t('wizard.overview.invite_pending') }}</span>
  </header>
```

Replace with:

```jinja
<section class="panel host-checklist" data-setup-status aria-labelledby="property-readiness-title">
  {%- set health_rows = health or [] -%}
  {%- set health_open = health_rows | selectattr('state', 'in', ['bad', 'warn']) | list -%}
  <header class="setup-status-head">
    <h2 id="property-readiness-title">{{ t('health.title') }}</h2>
    {% if health_open %}<span class="ui-badge ui-badge-action" data-tone="{{ 'red' if health_open | selectattr('state', 'equalto', 'bad') | list else 'amber' }}">{{ tp('health.to_fix', health_open | length) }}</span>
    {% else %}<span class="ui-badge ui-badge-done" data-tone="green">{{ t('health.all_set') }}</span>{% endif %}
  </header>
  {% set health_list %}
  <ul class="health-list">
    {% for row in health_rows %}
    <li class="health-row" data-health-check="{{ row.key }}" data-state="{{ row.state }}">
      <span class="health-icon" aria-hidden="true">{{ icon(row.icon, 20) }}</span>
      <div class="health-copy"><strong>{{ t(row.label_key) }}</strong><span>{{ t(row.text_key) }}</span></div>
      {% if row.href %}<a class="ui-btn ui-btn-secondary" href="{{ row.href }}">{{ t(row.action_key) }}</a>{% endif %}
    </li>
    {% endfor %}
  </ul>
  {% endset %}
  {% if health_open %}{{ health_list }}
  {% else %}<details class="health-all-set"><summary>{{ t('health.show') }}</summary>{{ health_list }}</details>{% endif %}
```

Then delete the old tile grid that follows: from the line `  {% set icons = {'property': 'house', 'calendar': 'calendar-days', 'guest_link': 'external-link', 'try_it': 'users', 'police': 'send', 'stay_fee': 'coins', 'door_lock': 'key-round', 'automation': 'refresh-cw'} %}` through its closing `  </ul>` (the line directly before `  <details class="setup-readiness-help">`). Keep `<details class="setup-readiness-help">` and everything after it.

Command: `cd App && grep -c 'setup-status-tile\|wizard.overview.status_note' app/templates/_property_overview.html` → `0`. Commit `0244 step 4`.

### Step 5. CSS and cache key

5a. Append to the end of `App/app/static/workflow.css`:

```css

/* 0244 (idea O): property health check. One bordered row per check; the
   left edge says how it is (the sentence says it too). */
.health-list { display: grid; gap: var(--space-2); margin: 0 0 var(--space-3); padding: 0; list-style: none; }
.health-row { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: var(--space-2) var(--space-3); min-width: 0; padding: var(--space-3); border: 1px solid var(--border); border-left: 4px solid var(--green-700); border-radius: var(--radius-md); background: var(--surface); }
.health-row[data-state="warn"] { border-left-color: var(--amber); }
.health-row[data-state="bad"] { border-left-color: var(--red); }
.health-row[data-state="off"] { border-left-color: var(--border-strong); }
.health-icon { display: inline-flex; color: var(--ink-secondary); }
.health-row[data-state="ok"] .health-icon { color: var(--green-700); }
.health-copy { display: grid; gap: 2px; min-width: 0; }
.health-copy strong { color: var(--ink); font-size: var(--text-sm); line-height: 1.35; overflow-wrap: anywhere; }
.health-copy span { color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.4; overflow-wrap: anywhere; }
.health-row > .ui-btn { grid-column: 1 / -1; justify-self: start; min-height: 44px; }
.health-all-set { margin: 0 0 var(--space-3); }
.health-all-set > summary { display: inline-flex; align-items: center; min-height: 44px; cursor: pointer; font-weight: 600; }
.health-all-set > summary:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
.health-all-set > .health-list { margin-top: var(--space-2); }
@media (min-width: 720px) {
  .health-row { grid-template-columns: auto minmax(0, 1fr) auto; }
  .health-row > .ui-btn { grid-column: auto; justify-self: end; }
}
```

5b. In `App/app/templates/base.html` replace `/static/workflow.css?v=20261022-0240` with `/static/workflow.css?v=20261022-0244`.

5c. Command: `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5 && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -5` → pass. Commit `0244 step 5` (workflow.css, base.html and tests/static_versions.json together).

### Step 6. `docs/design/catalog.json`

Add to the `classes` list, directly after `"needs-you-calm"`: `"health-list"`, `"health-row"`, `"health-icon"`, `"health-copy"`, `"health-all-set"`. Add to `class_notes`, directly after the `"needs-you-calm"` note (mind the commas, the file must stay valid JSON):

```json
    "health-list": "0244 property health check: list of health-row.",
    "health-row": "0244 one check: icon, name and one sentence, one button only when something is wrong; data-state ok/warn/bad/off sets the left edge colour.",
    "health-icon": "0244 the row's icon, green when the check is fine.",
    "health-copy": "0244 name (strong) and sentence (span) of a health-row.",
    "health-all-set": "0244 details that folds the rows away when nothing needs fixing."
```

Command: `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -5` → pass. Commit `0244 step 6`.

### Step 7. Create `App/tests/test_property_health_0244.py` with exactly this content

```python
"""0244: the property health check says what works today, with one fix button per problem."""

from __future__ import annotations

from app import db, property_health, property_setup
from tests.test_guest_links_bilingual import _apartment_id, host  # noqa: F401

APARTMENT = {"id": 7, "internal_name": "Flat", "active": 1}
READY = {"report": [{"key": "idub", "anchor": "ubyport", "done": True}],
         "invite": [{"key": "operator", "anchor": "basics", "done": True},
                    {"key": "controller", "anchor": "basics", "done": True}]}
FEED_OK = [{"active": 1, "last_status": "ok"}]


def _rows(**kwargs):
    defaults = {"feeds": FEED_OK, "readiness": READY, "door_code": None,
                "open_kinds": set(), "guest_used": True, "link_due": False}
    defaults.update(kwargs)
    return {row["key"]: row for row in property_health.checks(
        APARTMENT, defaults["feeds"], defaults["readiness"], defaults["door_code"],
        open_kinds=defaults["open_kinds"], guest_used=defaults["guest_used"], link_due=defaults["link_due"],
    )}


def test_a_healthy_property_needs_nothing():
    rows = _rows()
    assert list(rows) == ["calendar", "guest_link", "police", "business"]
    assert {row["state"] for row in rows.values()} == {"ok"}
    assert all(not row["href"] for row in rows.values())
    assert property_health.to_fix(rows.values()) == []


def test_each_problem_gets_one_button_to_the_exact_setting():
    missing = {"report": [{"key": "zip", "anchor": "address", "done": False}],
               "invite": [{"key": "operator", "anchor": "basics", "done": False}]}
    rows = _rows(feeds=[{"active": 1, "last_status": "error"}], readiness=missing,
                 guest_used=False, link_due=True)
    assert rows["calendar"]["state"] == "bad"
    assert rows["calendar"]["href"] == "/apartments/7?view=bookings#calendars"
    assert rows["guest_link"]["state"] == "warn"
    assert rows["guest_link"]["href"] == "/apartments/7?view=settings&section=guests#communication"
    assert rows["police"]["href"] == "/apartments/7?view=settings&section=property#address"
    assert rows["business"]["href"] == "/apartments/7?view=settings&section=property#operator-picker"
    assert len(property_health.to_fix(rows.values())) == 4


def test_a_refused_police_login_wins_over_complete_details():
    rows = _rows(open_kinds={"ubyport_auth_failed"})
    assert rows["police"]["state"] == "bad"
    assert rows["police"]["text_key"] == "health.police.login"
    assert rows["police"]["href"].endswith("section=reporting#ubyport")


def test_no_calendar_is_a_nudge_and_door_codes_show_only_with_a_lock():
    rows = _rows(feeds=[], guest_used=False, link_due=False, door_code={"enabled": False})
    assert rows["calendar"]["state"] == "warn"
    assert rows["guest_link"]["state"] == "off" and not rows["guest_link"]["href"]
    assert rows["door"]["state"] == "off" and not rows["door"]["href"]
    assert "door" not in _rows()


def test_the_overview_shows_the_health_check(host):  # noqa: F811
    apartment_id = _apartment_id()
    property_setup.finish(apartment_id)
    for lang, title in (("en", "Health check"), ("cs", "Kontrola nastavení"), ("vi", "Kiểm tra thiết lập")):
        page = host.get(f"/apartments/{apartment_id}?view=overview&lang={lang}").text
        assert title in page, lang
        assert 'data-health-check="police"' in page
        assert 'class="setup-status-tile' not in page
    assert db.query_one("SELECT id FROM apartment WHERE id = ?", (apartment_id,))
```

Command: `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_property_health_0244.py -q --tb=short 2>&1 | tail -10` → pass. If only the last test fails because the box is not on the page (the wizard card shows instead), report the page's `setup-continue-card` presence and stop. Commit `0244 step 7`.

### Step 8. `test_onboarding_followup_browser.py`

Anchor (these exact lines):

```python
        assert status.locator(".setup-status-tile").count() == 8
        assert status.locator(".host-property-card").count() == 0
        assert status.locator(".setup-status-tile a").count() == 0
        assert not status.locator(".setup-readiness-help").evaluate("el => el.open")
        police = status.locator('[data-overview-setup-step="police"]')
        assert police.locator('[data-tone="amber"]').is_visible()
        assert police.locator('[data-tone="green"]').count() == 0
        tile = status.locator(".setup-status-tile").first
        color = tile.evaluate("el => getComputedStyle(el).backgroundColor")
        tile.hover()
        assert tile.evaluate("el => getComputedStyle(el).backgroundColor") == color
        assert tile.evaluate("el => getComputedStyle(el).cursor") == "default"
```

Replace with:

```python
        # 0244: a live health check, one bordered row per check, a button only on a problem.
        rows = status.locator(".health-row")
        assert rows.count() >= 4
        assert status.locator(".host-property-card").count() == 0
        assert not status.locator(".setup-readiness-help").evaluate("el => el.open")
        for index in range(rows.count()):
            row = rows.nth(index)
            state = row.get_attribute("data-state")
            assert row.locator("a.ui-btn").count() == (1 if state in ("bad", "warn") else 0), state
            assert row.evaluate("el => getComputedStyle(el).borderTopStyle") == "solid"
            for button in row.locator("a.ui-btn").all():
                assert button.bounding_box()["height"] >= 43.5
        police = status.locator('[data-health-check="police"]')
        assert police.count() == 1
```

and the screenshot name `f"40-overview-status-tiles-{lang}-{width}.png"` with `f"40-overview-health-{lang}-{width}.png"`.

Command: `cd App && PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_onboarding_followup_browser.py -q --tb=short 2>&1 | tail -10` → pass, 0 skipped. Commit `0244 step 8`.

## 5. Do not touch

Everything outside §3: the setup wizard, stay fee files, `.host-property-grid`, `host.css`, `alerts.py`.

## 6. Commands

From `App/` with `export PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw UBYHOST_REQUIRE_BROWSER=1`, `tests/test_alert_stack.py` first:

1. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_property_health_0244.py tests/test_host_i18n.py tests/test_static_versions.py tests/test_design_lint.py tests/test_property_form_nav.py tests/test_guest_links_bilingual.py -q --tb=short 2>&1 | tail -15`
2. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_onboarding_followup_browser.py tests/test_design_guardrails_browser.py tests/test_onboarding_wizard_browser.py -q --tb=short 2>&1 | tail -15`
3. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] §6 commands 1 and 2 pass with 0 skipped.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0244-report.md` (600 tokens at most) with the last lines of each command, and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/property_health.py` (two small queries per property page), `_property_overview.html` (the box), `workflow.css` plus cache key.

## Owner steps

None.
