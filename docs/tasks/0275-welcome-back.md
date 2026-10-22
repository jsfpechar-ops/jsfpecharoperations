# 0275: Welcome back line (S)

Status: todo
Depends on: 0274 | Base commit: 48c21b3 + 0270-0274 | Branch: claude/project-thread-4b2e7k (commit here, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A host who opens the dashboard after 14 days or more away sees one calm, dismissible line above "What needs you": "Welcome back! Since 3 Sep: 4 new stays came in. 9 guests were reported to the police." Hosts forget everything after setup; this tells them what happened without an email.

## 2. Context

- Owner rules: no email, no push, one line, dismissible, works without JavaScript (a plain form POST). Calm tone: neutral banner, never amber or red.
- Privacy: store only dates. Two settings rows per user account: `last_seen_<user id>` = `YYYY-MM-DD` of the last dashboard view, and `welcome_back_<user id>` = `<since YYYY-MM-DD>|<shown from YYYY-MM-DD>`. The line shows for at most 7 days after it first appears, then the row is cleared. Both rows are deleted with the workspace (retention.py).
- Counts exclude demo stays (`COALESCE(r.source, '') != 'demo'`) and use the workspace scope `db.null_safe_eq('a.owner_user_id')` exactly like the `feed_count` query in `App/app/routes/admin.py` (grep `null_safe_eq('a.owner_user_id')`).
- Reported = `guest.submit_state = 'sent'` (constant `reporting.SENT`) and `guest.submitted_at >= since`. New stays = `reservation.created_at >= since`. Timestamps are ISO strings, so `>=` against a `YYYY-MM-DD` string works.

Excerpt `App/app/routes/admin.py` (dashboard):

```
    owner_user_id = access.owner_id(request)
    apartments = access.apartments(request)
    today = deadlines.local_now().date()
```

and in its `render(` context:

```
            "link_unused": workflow.link_unused(apartments),
```

Excerpt `App/app/templates/dashboard.html`:

```
  {% set ny_lines = (needs_you.lines | rejectattr('kind', 'equalto', 'setup') | list) if banner_showing else needs_you.lines %}
  <div data-dashboard-refresh="stats">
```

Excerpt `App/app/retention.py`:

```
        cur.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))
```

Excerpt `App/app/routes/onboarding.py` (`@router.post("/onboarding/dismiss")`): copy its guard and redirect shape.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/welcome_back.py | create | `check()` and `dismiss()` |
| App/app/routes/admin.py | edit | call `check()`, pass `welcome_back` |
| App/app/routes/onboarding.py | edit | POST `/welcome-back/dismiss` |
| App/app/templates/dashboard.html | edit | the line |
| App/app/retention.py | edit | delete the two rows with the workspace |
| App/app/host_i18n.py | edit | EN + CS block |
| App/app/host_vi_i18n.py | edit | VI block |
| docs/design/catalog.json | edit | only if lint T3 asks |
| App/tests/test_welcome_back_0275.py | create | tests |

No other file may change.

## 4. Steps

**Step 1.** Create `App/app/welcome_back.py`:

```python
"""0275: one welcome-back line after 14 days away (idea S). Dates only."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from . import db, reporting

AWAY_DAYS = 14
SHOW_DAYS = 7


def _seen_key(user_id: int) -> str:
    return f"last_seen_{int(user_id)}"


def _line_key(user_id: int) -> str:
    return f"welcome_back_{int(user_id)}"


def _parse(value: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def check(user_id: Optional[int], owner_user_id: Optional[int], today: date) -> Optional[Dict[str, Any]]:
    """Record today's visit; return the line to show, or None."""
    if not user_id:
        return None
    last_seen = _parse(db.get_setting(_seen_key(user_id)))
    if last_seen != today:
        db.set_setting(_seen_key(user_id), today.isoformat())
    if last_seen and (today - last_seen).days >= AWAY_DAYS:
        db.set_setting(_line_key(user_id), f"{last_seen.isoformat()}|{today.isoformat()}")
    raw = db.get_setting(_line_key(user_id)) or ""
    since_raw, _, shown_raw = raw.partition("|")
    since, shown = _parse(since_raw), _parse(shown_raw)
    if not since or not shown:
        return None
    if (today - shown).days > SHOW_DAYS:
        dismiss(user_id)
        return None
    scope = db.null_safe_eq("a.owner_user_id")
    stays = db.query_one(
        "SELECT COUNT(*) AS n FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE {scope} AND COALESCE(r.source, '') != 'demo' AND r.created_at >= ?",
        (owner_user_id, since.isoformat()),
    )["n"]
    reported = db.query_one(
        "SELECT COUNT(*) AS n FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE {scope} AND COALESCE(r.source, '') != 'demo' "
        "AND g.submit_state = ? AND g.submitted_at >= ?",
        (owner_user_id, reporting.SENT, since.isoformat()),
    )["n"]
    return {"since": since.isoformat(), "stays": int(stays), "reported": int(reported)}


def dismiss(user_id: Optional[int]) -> None:
    if user_id:
        db.set_setting(_line_key(user_id), "")


def forget(cur, user_id: int) -> None:
    """Retention: drop both rows with the account's workspace."""
    cur.execute(
        "DELETE FROM settings WHERE key IN (?, ?)", (_seen_key(user_id), _line_key(user_id))
    )
```

Check first: `grep -n "def null_safe_eq" -A8 App/app/db.py` and confirm it takes one argument and adds one `?` placeholder. If it adds two placeholders, pass `owner_user_id` twice in both queries. Check `grep -n "^SENT" App/app/reporting.py`.

**Step 2.** `admin.py` dashboard: after `today = deadlines.local_now().date()` add:

```python
    # 0275: one welcome-back line after two weeks away.
    account = auth.current_user(request)
    welcome = welcome_back.check(account["id"] if account else None, owner_user_id, today)
```

add `welcome_back` to the `from .. import …` line of admin.py (check it is not shadowed: `grep -n "welcome_back" App/app/routes/admin.py` must be empty first), and in the render context after the `"link_unused"` line add `            "welcome_back": welcome,`.

**Step 3.** `routes/onboarding.py`, after the `onboarding_dismiss` function, add:

```python
@router.post("/welcome-back/dismiss")
async def welcome_back_dismiss(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    await request.form()
    account = auth.current_user(request)
    welcome_back.dismiss(account["id"] if account else None)
    return RedirectResponse("/", status_code=303)
```

and add `welcome_back` to its `from .. import …` line.

**Step 4.** `dashboard.html`: directly after the `{% set ny_lines = … %}` line insert:

```
  {% if welcome_back %}
  <div class="ui-banner ui-banner-neutral" role="status" data-welcome-back>
    <div class="grow"><strong>{{ t('welcome_back.title', date=welcome_back.since | date_short) }}</strong> {% if welcome_back.stays or welcome_back.reported %}{{ tp('welcome_back.stays', welcome_back.stays) }} {{ tp('welcome_back.reported', welcome_back.reported) }}{% else %}{{ t('welcome_back.quiet') }}{% endif %}</div>
    <form method="post" action="/welcome-back/dismiss" data-welcome-back-dismiss><input type="hidden" name="_csrf" value="{{ csrf_token }}">{{ ui_icon_button(t('a11y.dismiss_notification'), 'x', type='submit') }}</form>
  </div>
  {% endif %}
```

Check `ui_icon_button` is imported in dashboard.html (`grep -n "ui_icon_button" App/app/templates/dashboard.html | head -2`).

**Step 5.** `retention.py`: directly before `        cur.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))` add:

```python
        # 0275: the welcome-back dates (last dashboard visit) go with the account.
        welcome_back.forget(cur, owner_id)
```

and import `welcome_back` in retention.py's `from . import …` line (check for import cycles by running the tests).

**Step 6.** i18n, a `_WELCOME_0275_STRINGS` block after the last block in `host_i18n.py` (same shape as `_WIZARD_0272_STRINGS`):

| key | en | cs |
|---|---|---|
| welcome_back.title | Welcome back! Since %(date)s: | Vítejte zpět! Od %(date)s: |
| welcome_back.stays | %(count)s new stays came in. | přišlo %(count)s nových pobytů. |
| welcome_back.stays.one | 1 new stay came in. | přišel 1 nový pobyt. |
| welcome_back.stays.few | %(count)s new stays came in. | přišly %(count)s nové pobyty. |
| welcome_back.reported | %(count)s guests were reported to the police. | %(count)s hostů jsme nahlásili policii. |
| welcome_back.reported.one | 1 guest was reported to the police. | 1 hosta jsme nahlásili policii. |
| welcome_back.reported.few | %(count)s guests were reported to the police. | %(count)s hosty jsme nahlásili policii. |
| welcome_back.quiet | Nothing new came in. | Nic nového nepřišlo. |

VI `STRINGS.update` block in `host_vi_i18n.py`:

| key | vi |
|---|---|
| welcome_back.title | Chào mừng bạn trở lại! Từ %(date)s: |
| welcome_back.stays | Có %(count)s lượt lưu trú mới. |
| welcome_back.stays.one | Có 1 lượt lưu trú mới. |
| welcome_back.stays.few | Có %(count)s lượt lưu trú mới. |
| welcome_back.reported | Đã khai báo %(count)s khách cho cảnh sát. |
| welcome_back.reported.one | Đã khai báo 1 khách cho cảnh sát. |
| welcome_back.reported.few | Đã khai báo %(count)s khách cho cảnh sát. |
| welcome_back.quiet | Không có gì mới. |

**Step 7.** Run the design lint from the repo root; if T3 names a class, add it to the `legacy` list of `App/app/templates/dashboard.html` in `docs/design/catalog.json`.

**Step 8.** Create `App/tests/test_welcome_back_0275.py`. Unit-test `welcome_back.check` directly with an isolated DB like other unit tests do (find the fixture used by `tests/test_onboarding_wizard_survival.py` `host`; import `host` from there and use `host["client"]` for the HTTP tests). Tests:

1. `test_first_visit_no_line`: `check(uid, owner, date(2026, 10, 22))` returns None and stores `last_seen_<uid>`.
2. `test_after_14_days_line_then_7_days_gone`: set `last_seen_<uid>` to `2026-10-01`, `check(… date(2026, 10, 22))` returns `{"since": "2026-10-01", …}`; a call on `2026-10-25` still returns it; a call on `2026-10-30` returns None.
3. `test_13_days_no_line`.
4. `test_dashboard_shows_and_dismiss_clears`: with the HTTP client, find the signed-in account id (`db.query_one("SELECT id FROM user_account ORDER BY id LIMIT 1")` or from the fixture), set `last_seen_<id>` to 20 days ago, GET `/?lang=en` has `data-welcome-back` and "Welcome back!"; POST `/welcome-back/dismiss` with the CSRF token taken from the page (copy how other tests read `_csrf`, `grep -n "_csrf" tests/test_onboarding_wizard_survival.py | head -3`) returns 303; GET `/` no longer has `data-welcome-back`.
5. `test_counts_skip_demo`: a demo reservation (`source='demo'`) created after `since` is not counted.

## 5. Do not touch

needs_you.py, other dashboard sections, mail, push. No new dependency. Never push.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_welcome_back_0275.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_retention*.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_dashboard*.py -q --tb=short -x 2>&1 | tail -30`
- Repo root: `python3 scripts/design_lint.py 2>&1 | tail -3`

## 7. Acceptance

- [ ] Line shows after 14+ days away, for 7 days at most, never on a first visit.
- [ ] Dismiss works without JavaScript and the line does not return.
- [ ] Both settings rows are removed by workspace deletion.
- [ ] Tests and lint pass.

## 8. Stop and ask

Per TEMPLATE.

## 9. Report

`docs/tasks/0275-report.md` (600 tokens max), `Status: review`, commits `0275 step k`. Do not push.
