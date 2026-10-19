# 0148: phone dashboard, part 2: one PIN alert, one-line setup banner on phone

Status: todo
Depends on: 0147 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

Part 1 is [0147](0147-phone-dashboard-compact.md); run this only after `docs/tasks/0147-report.md` says review. Commit each step as `0148 step k`. Never push, never open a PR.

## 1. Objective

1. **Repeated alert.** The `guest_pin_rotated` host alert is raised once per property (`App/app/main.py`, `dedupe_key=f"guest_pin_rotated:{row['id']}"`), so a host with five properties reads the same card five times. Show it once, naming the affected properties in one line, linking to `/apartments`. Dismissing that one card dismisses all of them (otherwise the other four come back on the next page load).
2. **Setup banner on phone.** Below 768 px the attention banner's per-field list ("Review Flat: missing IDUB, Device code, ...") collapses to one line, "N properties need setup", with the existing "Finish setup" button. Desktop keeps the per-field list.

Grouping is done in the template. One Python change is unavoidable: the dismiss route must resolve every open `guest_pin_rotated` alert of the owner, not only the clicked one (`App/app/routes/admin.py`, `dismiss_alert`, the line `alerts.resolve_by_id(alert_id, user_dismissed=True)` at about line 4223).

## 2. Context

`App/app/templates/_host_alerts.html` (28 lines, included by `base.html` line 45) loops over `open_alerts`, a list of dicts with `id`, `kind`, `level`, `apartment_id`, `reservation_id`, `display_title`, `display_detail`. The same context always carries `apartments` (`templating.py` line 580, rows with `id` and `internal_name`), which the template uses for the property names. Jinja: `{% set _ = some_list.append(x) %}` inside a loop mutates the outer list; `{% for x in items if cond %}` filters.

The banner is built in `App/app/templates/dashboard.html` (enforced template: every class must be in `docs/design/catalog.json` hooks, no `style=`). Plural copy goes through `tp(base, n)` which picks `base.one`, `base.few` (2 to 4) or `base` (`host_i18n.plural_key`).

Anchors (verbatim, each occurs once in its file).

Anchor A, `App/app/host_i18n.py`, English block:
```
        "dashboard.missing_banner.and_more": "and %(count)s more",
```
Anchor B, `App/app/host_i18n.py`, Czech block:
```
        "dashboard.missing_banner.and_more": "a %(count)s dalších",
```
Anchor C, `App/app/templates/dashboard.html` (seven lines):
```
  {% set missing_text %}
    {% for row in missing_report_display %}
    <span class="dashboard-missing-line"><strong>{{ property_identity(row.apartment.id, row.apartment.internal_name, true) }}</strong>: {{ t('dashboard.missing_banner.missing') }}
      {% for item in row.missing %}<a href="/apartments/{{ row.apartment.id }}?{{ anchor_query.get(item.anchor, 'view=settings') }}#{{ item.anchor }}">{{ t('apartment.form.readiness.item.' ~ item.key) }}</a>{% if not loop.last %}, {% endif %}{% endfor %}</span>
    {% endfor %}
    {% if missing_report_more %}<a href="/apartments">{{ t('dashboard.missing_banner.and_more', count=missing_report_more) }}</a>{% endif %}
  {% endset %}
```
Anchor D, `docs/design/catalog.json`:
```
"dashboard-missing-line", "ui-table-wrap", "is-overdue"]
```
Anchor E, `App/app/routes/admin.py` (three lines):
```
    alerts.resolve_by_id(alert_id, user_dismissed=True)
    if request.headers.get("x-requested-with") == "fetch":
        return Response(status_code=204)
```
Anchor F, `App/tests/test_dashboard_phone_browser.py` (created by 0147):
```
                # 0148: alerts and banner (390)
```
and
```
                # 0148: alerts and banner (1280)
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/host_i18n.py | edit | six keys, Anchors A and B (step 1) |
| App/app/templates/dashboard.html | edit | Anchor C (step 1) |
| docs/design/catalog.json | edit | Anchor D (step 1) |
| App/app/static/host2.css | edit | append (step 1) |
| App/app/templates/_host_alerts.html | rewrite | whole file (step 2) |
| App/app/routes/admin.py | edit | Anchor E (step 2) |
| App/tests/test_dashboard_phone_browser.py | edit | Anchor F (step 3) |
| docs/tasks/0148-report.md, docs/tasks/0148-evidence/ | create | step 5 |

No other file may change.

## 4. Steps

1. Banner. Below Anchor A add:
   ```
           "dashboard.setup.properties": "%(count)s properties need setup",
           "dashboard.setup.properties.one": "1 property needs setup",
           "dashboard.setup.properties.few": "%(count)s properties need setup",
   ```
   Below Anchor B add:
   ```
           "dashboard.setup.properties": "%(count)s ubytování potřebuje dokončit nastavení",
           "dashboard.setup.properties.one": "1 ubytování potřebuje dokončit nastavení",
           "dashboard.setup.properties.few": "%(count)s ubytování potřebují dokončit nastavení",
   ```
   Replace Anchor C with:
   ```
     {% set missing_text %}
       <span class="dashboard-missing-list">
       {% for row in missing_report_display %}
       <span class="dashboard-missing-line"><strong>{{ property_identity(row.apartment.id, row.apartment.internal_name, true) }}</strong>: {{ t('dashboard.missing_banner.missing') }}
         {% for item in row.missing %}<a href="/apartments/{{ row.apartment.id }}?{{ anchor_query.get(item.anchor, 'view=settings') }}#{{ item.anchor }}">{{ t('apartment.form.readiness.item.' ~ item.key) }}</a>{% if not loop.last %}, {% endif %}{% endfor %}</span>
       {% endfor %}
       {% if missing_report_more %}<a href="/apartments">{{ t('dashboard.missing_banner.and_more', count=missing_report_more) }}</a>{% endif %}
       </span>
       <span class="dashboard-missing-short">{{ tp('dashboard.setup.properties', missing_report_display | length + missing_report_more) }}</span>
     {% endset %}
   ```
   Replace Anchor D with:
   ```
   "dashboard-missing-line", "dashboard-missing-list", "dashboard-missing-short", "ui-table-wrap", "is-overdue"]
   ```
   Append to the end of `App/app/static/host2.css`:
   ```
   /* 0148: setup banner is one line on phone */
   .host-workspace .dashboard-missing-short { display: none; }
   @media (max-width: 767px) {
     .host-workspace .dashboard-missing-list { display: none; }
     .host-workspace .dashboard-missing-short { display: inline; }
   }
   ```
   `python3 scripts/design_lint.py | tail -3` must print OK. Commit `0148 step 1`.

2. Alerts. Replace the whole content of `App/app/templates/_host_alerts.html` with:
   ```
   {% if open_alerts %}
   {% set pin_alerts = open_alerts | selectattr('kind', 'equalto', 'guest_pin_rotated') | list %}
   {% set pin_ids = pin_alerts | map(attribute='apartment_id') | list %}
   {% set pin_names = [] %}
   {% for apartment in apartments | default([]) if apartment.id in pin_ids %}{% set _ = pin_names.append(apartment.internal_name) %}{% endfor %}
   <aside class="notification-stack" data-host-alerts aria-label="{{ t('a11y.notifications') }}" aria-live="polite">
     {% for alert in open_alerts if alert.kind != 'guest_pin_rotated' or alert.id == pin_alerts[0].id %}
       {% set grouped = alert.kind == 'guest_pin_rotated' and pin_alerts | length > 1 %}
       <article class="notification-bubble {{ alert.level }}" data-notification{% if grouped %} data-notification-group="guest_pin_rotated"{% endif %}>
         {% if alert.reservation_id %}
           <a class="notification-link" href="/reservations/{{ alert.reservation_id }}">
         {% elif grouped %}
           <a class="notification-link" href="/apartments">
         {% elif alert.apartment_id %}
           <a class="notification-link" href="/apartments/{{ alert.apartment_id }}">
         {% else %}
           <div class="notification-link">
         {% endif %}
             <span class="notification-icon" aria-hidden="true">!</span>
             <span class="grow">
               <strong>{{ alert.display_title or alert.message }}</strong>
               {% if grouped %}<small>{{ pin_names | join(', ') }}. {{ alert.display_detail or alert.detail }}</small>
               {% elif alert.display_detail or alert.detail %}<small>{{ alert.display_detail or alert.detail }}</small>{% endif %}
               {% if alert.reservation_id %}<small class="notification-action">{{ t('notification.open_stay') }}</small>
               {% elif grouped %}<small class="notification-action">{{ t('dashboard.setup.view_properties') }}</small>
               {% elif alert.apartment_id %}<small class="notification-action">{{ t('notification.open_property') }}</small>{% endif %}
             </span>
         {% if alert.reservation_id or alert.apartment_id %}</a>{% else %}</div>{% endif %}
         {% if alert.kind != 'dates_changed_resign' %}
         <form method="post" action="/alerts/{{ alert.id }}/dismiss" data-notification-dismiss>
           <button type="submit" aria-label="{{ t('a11y.dismiss_notification') }}">&times;</button>
         </form>
         {% endif %}
       </article>
     {% endfor %}
   </aside>
   {% endif %}
   ```
   Replace Anchor E with:
   ```
       alerts.resolve_by_id(alert_id, user_dismissed=True)
       if row["kind"] == "guest_pin_rotated":
           # One card stands for every property whose PIN was rotated (0148).
           for other in alerts.open_alerts(row["owner_user_id"]):
               if other["kind"] == "guest_pin_rotated":
                   alerts.resolve_by_id(other["id"], user_dismissed=True)
       if request.headers.get("x-requested-with") == "fetch":
           return Response(status_code=204)
   ```
   Commit `0148 step 2`.

3. Test. In `App/tests/test_dashboard_phone_browser.py` add after the import block (below the `from tests.test_dashboard_calendar_browser import (...)` statement):
   ```python
   from app import alerts, db


   def seed_pin_alerts(ws):
       for property_id in ws["properties"]:
           alerts.raise_alert(
               "warning", "guest_pin_rotated", "The guest link PIN was replaced with a new six-digit PIN.",
               detail="Four-digit PINs are no longer accepted.", dedupe_key=f"guest_pin_rotated:{property_id}",
               apartment_id=property_id, owner_user_id=ws["owner"],
           )
       return [db.query_one("SELECT internal_name FROM apartment WHERE id = ?", (pid,))["internal_name"] for pid in ws["properties"]]
   ```
   Replace the first Anchor F line (390) with:
   ```
                   names = seed_pin_alerts(calendar_workspace)
                   page.reload()
                   pin_cards = page.locator("[data-notification]", has_text="PIN")
                   assert pin_cards.count() == 1
                   assert pin_cards.first.get_attribute("data-notification-group") == "guest_pin_rotated"
                   for name in names:
                       assert name in pin_cards.first.inner_text(), name
                   assert pin_cards.first.locator('a[href="/apartments"]').count() == 1
                   short = page.locator(".dashboard-missing-short")
                   assert short.is_visible()
                   assert short.inner_text().strip() == "3 properties need setup", short.inner_text()
                   assert not page.locator(".dashboard-missing-list").first.is_visible()
                   assert page.locator(".ui-banner-attention .ui-btn").count() == 1
                   shot(page, "phone-390-alert")
                   pin_cards.first.locator("[data-notification-dismiss] button").click()
                   page.wait_for_timeout(500)
                   page.reload()
                   assert page.locator("[data-notification]", has_text="PIN").count() == 0
   ```
   Replace the second Anchor F line (1280) with:
   ```
                   assert page.locator(".dashboard-missing-list").first.is_visible()
                   assert not page.locator(".dashboard-missing-short").is_visible()
                   assert page.locator(".dashboard-missing-line").count() == 3
   ```
   (The fixture's three properties have no UbyPort details, so the banner always shows with three lines.) Commit `0148 step 3`.

4. Run, from `App/`:
   `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_SHOTS_DIR=/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0148 .venv/bin/python -m pytest tests/test_dashboard_phone_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_design_dashboard.py -q --tb=line -rs 2>&1 | tail -15`
   then `.venv/bin/python -m pytest tests -q -x --tb=short -k "alert or host_i18n or i18n_parity" 2>&1 | tail -10`.
   Expected: pass, 0 skipped. Then `App/.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 App/app/routes/admin.py App/tests/test_dashboard_phone_browser.py | tail -3`.

5. Open `calendar-phone-390-alert.png` and `calendar-phone-1280.png` from the shots dir. Confirm by eye: at 390 one PIN card naming three properties, and the amber banner is one sentence plus the "Finish setup" button; at 1280 the banner lists the three properties with their missing fields. Copy both to `docs/tasks/0148-evidence/`. Write `docs/tasks/0148-report.md` (Status, pytest tails, what you saw, evidence paths). Commit `0148 report` with `git add docs/tasks/0148-report.md docs/tasks/0148-evidence`.

## 5. Do not touch

`dashboard-calendar.js`, `dashboard-calendar.css`, `_dashboard_calendar.html`, `alerts.py`, `main.py`, `app.css`, `host.css`.

## 6. Commands

As in steps 1, 4 and 5. Every command ends with `| tail -N`.

## 7. Acceptance

- [ ] `design_lint.py` prints OK after step 1 (new classes are in the catalog hooks).
- [ ] Step 4 passes, 0 skipped; both i18n languages have the three new keys.
- [ ] One `guest_pin_rotated` card at any width; dismissing it leaves none after reload.
- [ ] Step 5 confirmed in the report with both screenshots committed.

## 8. Stop and ask

Stop if an anchor is not found verbatim, if `apartments` is undefined in the alert template (the names line comes out empty: report it, do not add Python), or if a test fails twice. Report the assertion verbatim and set Status: blocked.

## 9. Report

As in step 5.
