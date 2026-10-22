# 0280: Short notifications: one line and a link to the fix

Status: todo
Depends on: none | Base commit: a6c532c | Branch: claude/project-thread-j2cl8a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every host notification becomes one short line (what and where) plus one link that opens the exact fix. Field lists, error strings and explanations leave the cards; the page the link opens already shows them. On pages other than the dashboard, only red alerts get their own line; everything else folds into one line that opens the dashboard card.

## 2. Context

Owner (2026-10-22, with a phone screenshot of a card listing `uby_idub: IDUB is required...; uby_mark: ...`): "Notifications are huge and overwhelming, I want the minimal but still urgent ... we don't need the whole description what is missing, they can just click it and it points them." Calm app: to-dos live in one place, the dashboard "What needs you" card; red only for real breakage.

Today a card is `display_title` + `display_detail` + action. `display_detail` is long for stored kinds (it falls back to the raw English log text, e.g. the field list). The short stay reasons ("Overdue by 7 days · 2/2") are good and stay.

`App/app/alerts.py`, end of `present()`:
```python
    row = dict(alert)
    kind = row.get("kind") or ""
    if kind in _COMPUTED_ALERT_KINDS:
        return _with_action(_present_computed(row, kind, lang, stays))
    return _with_action(_present_stored(row, kind, lang))
```

`App/app/needs_you.py` in `build()`:
```python
            card.get("display_title") or card.get("message") or "",
            card.get("display_detail") or card.get("detail") or "",
```

`App/app/templates/_host_alerts.html` is the stack shown on every page except the dashboard (`dashboard.html` sets `hide_alert_stack` when the host has properties). Its whole current content is in §4 step 3 (old). `open_alerts` there is the output of `alerts.present_many` (cards with `kind`, `level` in critical/warning/info, `display_title`, `action_href`, `action_label_key`, `id`, `apartment_id`, `reservation_id`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/alerts.py | edit | add `display_reason` |
| App/app/needs_you.py | edit | alert line text = `display_reason` |
| App/app/templates/_host_alerts.html | rewrite | red lines + one summary line |
| App/app/host_i18n.py | edit | shorter titles (script), 3 new keys EN/CS |
| App/app/host_vi_i18n.py | edit | shorter titles (script), 3 new keys VI |
| App/tests/test_alert_stack.py | edit | stack tests follow the new design |
| App/tests/test_0280_short_notifications.py | new | guards |
| docs/context/decisions.md | append | one line |

No other file may change. If another existing test fails because it asserted the old long copy or the old stack (for example `test_notification_copy.py`, `test_needs_you_0240.py`, `test_needs_you_dashboard_0241.py`, `test_alert_language.py`), update only the asserted string or count to the new design and list it under Deviations.

## 4. Steps

1. **Shorter titles.** From `App/`: `.venv/bin/python /mnt/project-files/notify-sign/tools/apply_0280_copy.py 2>&1 | tail -3`. Expected: `replaced 57` (it rewrites existing values in place, asserting each old value occurs once). Commit `0280 step 1`.

2. **`display_reason`.** In `App/app/alerts.py`, above `def present(`, add:
```python
# 0280: the one short line a card may show under its title. Only the live stay
# reasons are short enough; every other detail stays on the page the card opens.
_REASON_KINDS = frozenset({"deadline", "guest_incomplete_checkin", "headcount_mismatch"})


def _with_reason(card: Dict[str, Any]) -> Dict[str, Any]:
    card["display_reason"] = (
        card.get("display_detail") or "" if card.get("kind") in _REASON_KINDS else ""
    )
    return card
```
and change the two returns at the end of `present()` to `return _with_reason(_with_action(...))` (same inner calls). In `App/app/needs_you.py` replace the line `card.get("display_detail") or card.get("detail") or "",` with `card.get("display_reason") or "",`. Commit `0280 step 2`.

3. **Stack.** Replace the whole of `App/app/templates/_host_alerts.html` with:
```jinja
{#- 0280: off the dashboard, only red alerts get a line of their own, each one
    short line plus the link to its fix. Everything else is one line that opens
    the dashboard's "What needs you" card. -#}
{% if open_alerts %}
{% set red = open_alerts | selectattr('level', 'equalto', 'critical') | list %}
{% set rest = open_alerts | rejectattr('level', 'equalto', 'critical') | list %}
{% set rest_pin = rest | selectattr('kind', 'equalto', 'guest_pin_rotated') | list %}
{% set rest_count = (rest | rejectattr('kind', 'equalto', 'guest_pin_rotated') | list | length) + (1 if rest_pin else 0) %}
{% set lines = red + (rest if rest_count == 1 else []) %}
<aside class="notification-stack" data-host-alerts aria-label="{{ t('a11y.notifications') }}" aria-live="polite">
  {% for alert in lines if alert.kind != 'guest_pin_rotated' or alert.id == (rest_pin[0].id if rest_pin else alert.id) %}
    <article class="notification-bubble {{ alert.level }}" data-notification>
      {% if alert.action_href %}<a class="notification-link" href="{{ alert.action_href }}">{% else %}<div class="notification-link">{% endif %}
        <span class="notification-icon" aria-hidden="true">!</span>
        <span class="grow">
          <strong>{{ alert.display_title or alert.message }}</strong>
          {% if alert.display_reason %}<small>{{ alert.display_reason }}</small>{% endif %}
          {% if alert.action_label_key %}<small class="notification-action">{{ t(alert.action_label_key) }}</small>{% endif %}
        </span>
      {% if alert.action_href %}</a>{% else %}</div>{% endif %}
      {% if alert.kind != 'dates_changed_resign' %}
      <form method="post" action="/alerts/{{ alert.id }}/dismiss" data-notification-dismiss>
        <button type="submit" aria-label="{{ t('a11y.dismiss_notification') }}">&times;</button>
      </form>
      {% endif %}
    </article>
  {% endfor %}
  {% if rest_count > 1 %}
    <article class="notification-bubble {{ rest[0].level }}" data-notification-summary>
      <a class="notification-link" href="/#needs-action">
        <span class="notification-icon" aria-hidden="true">!</span>
        <span class="grow">
          <strong>{{ t('notification.summary.more' if red else 'notification.summary.count', n=rest_count) }}</strong>
          <small class="notification-action">{{ t('notification.summary.open') }}</small>
        </span>
      </a>
    </article>
  {% endif %}
</aside>
{% endif %}
```
Commit `0280 step 3`.

4. **Strings.** In `App/app/host_i18n.py`, directly above the line `STRINGS["vi"] = dict(_VI_STRINGS)`, add:
```python
# 0280: the one line that stands for several alerts off the dashboard.
_SUMMARY_0280_STRINGS = {
    "en": {
        "notification.summary.count": "%(n)s alerts need you",
        "notification.summary.more": "%(n)s more alerts",
        "notification.summary.open": "Open the dashboard",
    },
    "cs": {
        "notification.summary.count": "Upozornění k vyřízení: %(n)s",
        "notification.summary.more": "Další upozornění: %(n)s",
        "notification.summary.open": "Otevřít přehled",
    },
}
for _lang, _strings in _SUMMARY_0280_STRINGS.items():
    STRINGS[_lang].update(_strings)

```
At the end of `App/app/host_vi_i18n.py` add:
```python

# 0280: the one line that stands for several alerts off the dashboard.
STRINGS.update({
    "notification.summary.count": "%(n)s cảnh báo cần bạn xử lý",
    "notification.summary.more": "Thêm %(n)s cảnh báo",
    "notification.summary.open": "Mở trang tổng quan",
})
```
(Check with `tail -12 App/app/host_vi_i18n.py` that the 0245 block ends the same way and uses `STRINGS.update`; if not, STOP.) Commit `0280 step 4`.

5. **Tests.** In `App/tests/test_alert_stack.py` the stack tests assumed one card per alert. Update them to the new design, keeping their names: four `warning` alerts on `/reservations` give 1 `data-notification-summary` with `href="/#needs-action"` and 0 `data-notification` cards; two warnings give the summary (not two cards); one warning alone gives its own card; the Czech test asserts the Czech summary text `Upozornění k vyřízení: 3`; the critical tests stay as they are. Then write `App/tests/test_0280_short_notifications.py` with these tests (reuse the `host` fixture and `_alert` helper pattern from `test_alert_stack.py` by copying them, not importing):
   - `test_setup_alert_never_lists_fields`: raise an `apartment_setup` warning whose `detail` is `"uby_idub: IDUB is required"`; GET `/` dashboard and `/reservations` (EN): `uby_idub` is in neither page.
   - `test_titles_and_push_bodies_are_short`: for `en`, `cs`, `vi`, every key matching `notification\.[a-z_]+\.title` or `push\.msg\.` has at most 60 characters after removing `%(name)s` placeholders.
   - `test_reason_only_for_stay_kinds`: `alerts.present({"kind": "mail_failed", "detail": "x", ...minimal fields}, "en")["display_reason"] == ""`.
   - `test_red_alert_keeps_its_own_line`: one `critical` + three `warning` alerts: `/reservations` shows 1 `data-notification` card and the summary text `3 more alerts`.
   Commit `0280 step 5`.

6. **Decision line.** Append to `docs/context/decisions.md`: `- 2026-10-22 Notifications are one short line plus the link to the fix; no field lists or error text on cards. Off the dashboard only red alerts get a line, the rest is one summary line to the dashboard (owner).` Commit `0280 step 6`.

## 5. Do not touch

`alerts.raise_alert` callers and stored `detail` (the log keeps it), mail templates, `push.py`, CSS. Hard rules 2, 6, 9.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_0280_short_notifications.py tests/test_alert_stack.py tests/test_needs_you_0240.py tests/test_needs_you_dashboard_0241.py tests/test_notification_copy.py tests/test_alert_language.py tests/test_deadlines.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short 2>&1 | tail -15` (skip a file that does not exist)
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] No card on `/` or `/reservations` shows a field list or raw error text.
- [ ] Off the dashboard: red alerts one line each; other alerts one summary line to `/#needs-action` (one lone alert shows itself).
- [ ] All tests in §6 pass.
- [ ] Screenshot at 390 px of `/reservations` with demo data: `shots.py --new-app $PWD --out /mnt/project-files/notify-sign/0280 --pages /reservations,/ --widths 390` (tool in `/mnt/project-files/design-reset/tools/`).

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0280-report.md`, as in TEMPLATE §9.

## Risk list (for the reviewer)

`_host_alerts.html`, `alerts.py`, `needs_you.py`, the edited tests.

## Owner steps

1. After deploy, open any page other than the dashboard on your phone: you should see at most one line per red alert and one grey/amber line "N alerts need you".
