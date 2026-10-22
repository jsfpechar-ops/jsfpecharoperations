# 0274: Finish moment (L) and the right finish button (M)

Status: todo
Depends on: 0273 | Base commit: 48c21b3 + 0270-0273 | Branch: claude/project-thread-4b2e7k (commit here, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The finish screen celebrates once (CSS confetti, never again on reload, none for reduced motion) with a clear headline, shows the five-step workflow picture, and its one button opens the page that matters next: the missing step, the property's stays, or the property. Today the button says "Go to my property" but opens the dashboard.

## 2. Context

- Celebration rules (owner, idea L): confetti only the first time the finish page is shown after setup finishes; reduced motion gets the static tick only; the animation ends by itself (it is 1.8 s); the banner has `role="status"` so a screen reader hears the headline. When something is still missing (police login waiting), no confetti and the headline says what is left.
- M rules: missing step first (status `waiting` or `todo` in `checklist`, in step order) → that wizard step; else a next stay exists → `/apartments/<id>?view=bookings`; else → `/apartments/<id>?view=overview`. The button label names the page. Button labels stay at 24 characters or fewer in every language.
- Calendar sync interval is `config.ICAL_POLL_MINUTES`.
- `next_stay_window(apartment)` is a Jinja global returning `{"stay", "days", "window"}`; `date_short` is a filter. Copy the exact expression from `App/app/templates/setup_wizard/guest_link.html` line with `workflow.link.next_stay_now` (grep it).

Excerpt `App/app/property_setup.py` (the `load` return and `_save`):

```
    return {
        "steps": normalised,
        "finished": bool(state.get("finished")),
        "hidden": bool(state.get("hidden")),
        "legacy": bool(state.get("legacy")),
    }
```

```
            {
                "steps": state["steps"],
                "finished": bool(state["finished"]),
                "hidden": bool(state.get("hidden")),
                "legacy": bool(state.get("legacy")),
            },
```

Excerpt `App/app/routes/onboarding_wizard.py` in `_wizard_context`:

```
        "checklist": property_setup.checklist(
```

Current `App/app/templates/setup_wizard/done.html` is 34 lines: a `ui-banner setup-wizard-celebrate` with 12 confetti `<i>`, an h2 `wizard.done.title`, the checklist `<ul class="setup-wizard-checklist host-property-grid">…</ul>`, and the actions block with `<a class="ui-btn ui-btn-primary" href="/">{{ t('wizard.done.go') }}</a>`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/property_setup.py | edit | `celebrated` flag + `celebrate_once()` |
| App/app/routes/onboarding_wizard.py | edit | `celebrate` and `ical_poll_minutes` in context |
| App/app/templates/setup_wizard/done.html | edit | banner, strip, note, button |
| App/app/static/wizard.css | edit | celebrate styles (append) |
| App/app/templates/base.html | edit | wizard.css key to `20261022-0274` |
| App/app/host_i18n.py | edit | EN + CS block |
| App/app/host_vi_i18n.py | edit | VI block |
| docs/design/catalog.json | edit | legacy classes for done.html |
| App/tests/static_versions.json | regenerate | |
| App/tests/test_finish_moment_0274.py | create | tests |

No other file may change.

## 4. Steps

**Step 1.** `property_setup.py`: in the `load` return dict add `"celebrated": bool(state.get("celebrated")),` after the `legacy` line; in `_save` add `"celebrated": bool(state.get("celebrated")),` after its `legacy` line. After `def finish(...)` add:

```python
def celebrate_once(apartment_id: int) -> bool:
    """0274: True the first time the finished wizard's finish page is shown."""
    state = load(apartment_id)
    if not state or not state["finished"] or state.get("celebrated"):
        return False
    state["celebrated"] = True
    _save(apartment_id, state)
    return True
```

**Step 2.** `onboarding_wizard.py`, in the `ctx = {` dict of `_wizard_context`, directly before the line `        "checklist": property_setup.checklist(`, insert:

```python
        # 0274: confetti once, the first time the finish page is shown.
        "celebrate": property_setup.celebrate_once(apartment_id) if step == "done" else False,
        "ical_poll_minutes": config.ICAL_POLL_MINUTES,
```

**Step 3.** Replace the whole of `done.html` with:

```
{% extends "setup_wizard/_layout.html" %}
{% from "_components.html" import nav_icon with context %}
{% from "_workflow.html" import workflow_strip with context %}
{% set missing_row = checklist | selectattr('status', 'in', ['waiting', 'todo']) | first %}
{% set link_next = next_stay_window(apartment) %}
{% block wizard_content %}
<div class="ui-banner setup-wizard-celebrate{{ ' is-partial' if missing_row }}" role="status" data-setup-celebrate="{{ 'partial' if missing_row else 'done' }}">
  {% if celebrate and not missing_row %}<span class="setup-wizard-confetti" aria-hidden="true">{% for n in range(12) %}<i></i>{% endfor %}</span>{% endif %}
  <span class="setup-wizard-celebrate-mark" aria-hidden="true">{{ '!' if missing_row else '✓' }}</span>
  <div class="grow setup-wizard-celebrate-copy">
    <strong class="setup-wizard-celebrate-title">{{ t('wizard.done.almost') if missing_row else t('wizard.done.all_set') }}</strong>
    <span>{{ (t('wizard.done.left.police') if missing_row.key == 'police' else t('wizard.done.left.step')) if missing_row else t('wizard.done.all_set_text') }}</span>
  </div>
</div>
{{ workflow_strip(apartment) }}
<h2 class="setup-wizard-section-title">{{ t('wizard.done.title') }}</h2>
{% set icons = {'property': 'property', 'calendar': 'calendar', 'guest_link': 'link', 'try_it': 'users', 'police': 'report', 'stay_fee': 'coins', 'door_lock': 'lock', 'automation': 'automation'} %}
```

then copy the existing `<ul class="setup-wizard-checklist host-property-grid">` … `</ul>` block unchanged (read it from git: `git show HEAD:App/app/templates/setup_wizard/done.html | sed -n '/<ul class="setup-wizard-checklist/,/<\/ul>/p'`), then:

```
{% if not missing_row %}
<p class="setup-wizard-instruction" data-finish-note>{% if link_next.stay and link_next.window and link_next.window.state == 'now' %}{{ t('workflow.link.next_stay_now', stay=link_next.stay.date_from | date_short) }}{% elif link_next.stay and link_next.window %}{{ t('workflow.link.next_stay', stay=link_next.stay.date_from | date_short, date=link_next.window.opens.isoformat() | date_short) }}{% elif wizard_facts.feeds %}{{ t('wizard.done.note_sync', minutes=ical_poll_minutes) }}{% else %}{{ t('wizard.done.note_no_calendar') }}{% endif %}</p>
{% endif %}
{% endblock %}
{% block wizard_actions %}
<span></span>
{% if missing_row %}
<a class="ui-btn ui-btn-primary" href="/apartments/{{ apartment.id }}/setup/{{ missing_row.key }}" data-finish-go="fix">{{ t('wizard.done.fix.police') if missing_row.key == 'police' else t('wizard.done.fix.step') }}</a>
{% elif link_next.stay %}
<a class="ui-btn ui-btn-primary" href="/apartments/{{ apartment.id }}?view=bookings" data-finish-go="stays">{{ t('wizard.done.go_stays') }}</a>
{% else %}
<a class="ui-btn ui-btn-primary" href="/apartments/{{ apartment.id }}?view=overview" data-finish-go="property">{{ t('wizard.done.go_property') }}</a>
{% endif %}
{% endblock %}
```

Check `wizard_facts` has `feeds`: `grep -n '"feeds"' App/app/admin*.py App/app/routes/admin.py | head -3`. If the key differs, STOP.

**Step 4.** Append to `App/app/static/wizard.css`:

```
/* 0274: finish moment (L). Confetti lives in host2.css (12 pieces, reduced-motion hidden). */
.host-workspace .setup-wizard-celebrate { display: flex; align-items: center; gap: var(--space-3); min-height: 96px; padding: var(--space-5); }
.host-workspace .setup-wizard-celebrate-mark { position: relative; flex: 0 0 auto; display: inline-grid; place-items: center; width: 44px; height: 44px; border: 1px solid var(--green-300); border-radius: var(--radius-pill); background: var(--surface); color: var(--green-700); font-size: var(--text-lg); font-weight: 700; }
.host-workspace .setup-wizard-celebrate-copy { position: relative; display: grid; gap: var(--space-1); min-width: 0; }
.host-workspace .setup-wizard-celebrate-title { color: var(--ink); font-size: var(--text-lg); line-height: 1.25; overflow-wrap: anywhere; }
.host-workspace .setup-wizard-celebrate.is-partial { background: var(--amber-bg); border-color: var(--amber-300); }
.host-workspace .setup-wizard-celebrate.is-partial .setup-wizard-celebrate-mark { border-color: var(--amber-300); color: var(--amber-700); }
.host-workspace .setup-wizard-celebrate .setup-wizard-confetti i { animation-duration: 2s; }
```

Change the wizard.css link in `base.html` to `?v=20261022-0274`.

**Step 5.** i18n. In `host_i18n.py`, after the `_WIZARD_0273_STRINGS` loop, add a `_FINISH_0274_STRINGS` block in the same shape:

| key | en | cs |
|---|---|---|
| wizard.done.all_set | You're all set! | Hotovo, vše je nastavené! |
| wizard.done.all_set_text | Your guests can now register on their own. | Hosté se teď můžou registrovat sami. |
| wizard.done.almost | Almost there: one thing left. | Skoro hotovo: zbývá jedna věc. |
| wizard.done.left.police | Add your police login and reports go out by themselves. | Doplňte přihlášení do Ubyportu a hlášení půjdou sama. |
| wizard.done.left.step | Finish the step below and you are done. | Dokončete krok níže a máte hotovo. |
| wizard.done.fix.police | Add your police login | Doplnit údaje Ubyportu |
| wizard.done.fix.step | Finish setup | Dokončit nastavení |
| wizard.done.go_stays | Open my stays | Otevřít moje pobyty |
| wizard.done.go_property | Open my property | Otevřít ubytování |
| wizard.done.note_sync | Your stays appear on the property page within %(minutes)s minutes, once your calendar syncs. | Pobyty se objeví u ubytování do %(minutes)s minut, jakmile se kalendář synchronizuje. |
| wizard.done.note_no_calendar | No calendar is connected yet. You can add stays by hand on the property page. | Zatím není připojený žádný kalendář. Pobyty můžete přidat ručně u ubytování. |

Append to `host_vi_i18n.py` a `STRINGS.update({...})` block with:

| key | vi |
|---|---|
| wizard.done.all_set | Xong rồi! |
| wizard.done.all_set_text | Giờ khách có thể tự đăng ký. |
| wizard.done.almost | Sắp xong: còn một việc. |
| wizard.done.left.police | Thêm thông tin đăng nhập cảnh sát, khai báo sẽ tự gửi đi. |
| wizard.done.left.step | Hoàn tất bước bên dưới là xong. |
| wizard.done.fix.police | Thêm đăng nhập cảnh sát |
| wizard.done.fix.step | Hoàn tất thiết lập |
| wizard.done.go_stays | Mở các lượt lưu trú |
| wizard.done.go_property | Mở chỗ ở của tôi |
| wizard.done.note_sync | Các lượt lưu trú sẽ hiện ở trang chỗ ở trong vòng %(minutes)s phút, khi lịch được đồng bộ. |
| wizard.done.note_no_calendar | Chưa kết nối lịch nào. Bạn có thể tự thêm lượt lưu trú ở trang chỗ ở. |

**Step 6.** `catalog.json`: add to the `legacy` list of `"App/app/templates/setup_wizard/done.html"`: `setup-wizard-celebrate`, `setup-wizard-confetti`, `setup-wizard-celebrate-mark`, `setup-wizard-celebrate-copy`, `setup-wizard-celebrate-title`, `setup-wizard-instruction`, `ui-banner`, `grow` (only those not already in `classes`, `hooks` or the list; the lint tells you). Run `python3 scripts/design_lint.py` from the repo root until OK.

**Step 7.** From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.

**Step 8.** Create `App/tests/test_finish_moment_0274.py`, importing `host` and `_full_apartment` from `tests.test_onboarding_wizard_survival` like `tests/test_wizard_friendly_0273.py` does. A helper `_finish(client, apt_id, *, wait_police)` walks the wizard in the new order by posting to `/apartments/{id}/setup`: `("calendar","skip")`, then police `("police","wait")` only when `wait_police` (otherwise the property from `_full_apartment` already has a complete police login; check `property_setup.load(apt_id)` reaches automation), then save automation with a POST to `/apartments/{id}/automation-timing` data `{"automation_mode": "manual", "submit_after_hours": "24", "setup_step": "automation", "return_to": f"/apartments/{id}/setup/stay_fee"}`, then `("stay_fee","skip")`, `("door_lock","none")` only if the page `/setup/door_lock` returns 200, `("guest_link","done")`, `("try_it","skip")`. Use `monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)` to keep it simple. Tests:

1. `test_confetti_once`: finish without waiting; first GET `/setup/done?lang=en` contains `setup-wizard-confetti` and `data-setup-celebrate="done"` and the EN `wizard.done.all_set` text; second GET does not contain `setup-wizard-confetti`.
2. `test_missing_police_goes_to_police`: finish with `wait_police=True`, and blank the police login first like `test_finish_setup_with_police_credentials_deferred` does (copy its `UPDATE apartment SET uby_idub = ''…` statement). GET done: contains `data-setup-celebrate="partial"`, no `setup-wizard-confetti`, and `href="/apartments/{id}/setup/police"` with `data-finish-go="fix"`.
3. `test_no_stays_goes_to_property`: finish; done page has `data-finish-go="property"` and `?view=overview`, never `href="/"` as the primary button.
4. `test_next_stay_goes_to_stays`: insert a reservation for the property 5 days from today (copy the `db.insert("reservation", …)` shape from an existing test: `grep -n 'db.insert(\s*"reservation"' -A12 tests/test_onboarding_wizard_survival.py | head -20`), finish; done page has `data-finish-go="stays"` and `?view=bookings` and `data-finish-note`.
5. `test_labels_short`: for en, cs, vi the four button keys translate to 24 characters or fewer.

## 5. Do not touch

host2.css (its confetti rules stay), other wizard templates, routes other than the two lines in step 2. Never push.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_finish_moment_0274.py tests/test_wizard_friendly_0273.py tests/test_onboarding_wizard_survival.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`
- Repo root: `python3 scripts/design_lint.py 2>&1 | tail -3` ends `design lint: OK`.

## 7. Acceptance

- [ ] Confetti on the first finish view only; partial finish shows amber "Almost there" and no confetti.
- [ ] The finish button goes to the missing step, the stays, or the property; never `/`.
- [ ] Tests and lint pass.

## 8. Stop and ask

Per TEMPLATE.

## 9. Report

`docs/tasks/0274-report.md` (600 tokens max), `Status: review`, commits `0274 step k`. Do not push.
