# 0195: Door lock account lives in each property's Door lock tab

Status: done
Depends on: none | Base commit: fea8bee | Branch: claude/project-thread-xo8dql
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The "Digital door lock" account panel (connect TTLock, share admin, check connection, lock list) is shown on the Properties list page under the property table. Josef wants it gone from there: hosts open Properties, pick a property, and find everything about the lock in that property's **Door lock** tab.

## 2. Context

- `App/app/templates/apartments.html` lines 148-152 render the panel:
  ```
  {% if smart_locks_enabled %}
  <h2 id="smart-locks-title">{{ t('smart_locks.title') }}</h2>
  <p class="ui-sub">{{ t('smart_locks.lede') }}</p>
  {% include "_smart_locks_panel.html" %}
  {% endif %}
  ```
  and `App/app/routes/admin.py` (properties list route, ~line 1153) passes `**_smart_lock_panel_context(request)`.
- `_smart_lock_panel_context(request)` (admin.py ~line 494) builds the panel context and sets `"return_to": "/smart-locks"`.
- `GET /smart-locks` (admin.py ~line 524) redirects to `/apartments#smart-locks-list|how`.
- `_smart_locks_url(return_to, section)` (admin.py ~line 150): when `return_to` starts with `/apartments/` it currently goes to `/smart-locks?return_to=...#anchor` (a page that no longer exists, it just redirects).
- `App/app/templates/_property_editor.html` lines 201-245: the lock group `<div class="property-settings-group ..." data-settings-group="lock" id="settings-lock">` sits INSIDE the big `<form id="property-settings-form">` (closes at line 371). When there is no account / no locks it shows a link to `/smart-locks?return_to=...`. The panel has its own `<form>`s, so it must NOT be placed inside the settings form (nested forms are invalid).
- Tab switching in `App/app/static/app.js` ~line 1973 toggles `is-active` on **every** `[data-settings-group]` inside the root, so a second element with `data-settings-group="lock"` placed after `</form>` shows and hides together with the lock tab.
- The property page route renders `apartment_form.html` with `"door_code": door_code` (admin.py ~line 1768-1780). `door_code` is None when the owner may not use locks.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/apartments.html | edit | delete the smart-locks block (lines 148-152) |
| App/app/routes/admin.py | edit | list route stops passing panel context; property route passes it; `/smart-locks` GET and `_smart_locks_url` land on the property lock tab |
| App/app/templates/_property_editor.html | edit | replace the two `/smart-locks?...` links with nothing; after `</form>` add the panel in a lock group |
| App/app/guide_i18n.py | edit | `guide.door_codes.step1` EN + CS wording |
| App/tests/test_smart_locks_page.py | edit | follow the new locations |

No other file may change.

## 4. Steps

1. `apartments.html`: delete the `{% if smart_locks_enabled %} ... {% endif %}` block (5 lines). Leave the comment after it.
2. `admin.py` properties list route: remove `**_smart_lock_panel_context(request),` from the `apartments.html` render.
3. `admin.py` property page route (the one rendering `apartment_form.html` with `"door_code": door_code`): add, only when `door_code` is not None,
   `**({**_smart_lock_panel_context(request), "return_to": f"/apartments/{apartment_id}?view=settings&section=lock"} if door_code is not None else {}),`
   (keys must not clash: `_smart_lock_panel_context` returns `account`, `locks` etc. Check the render dict for an existing key named `account` — it exists (`payments.czech_account_parts`). So instead pass the panel context under one key: `"lock_panel": {...}` and in the template use `{% with %}` (step 5).)
4. `admin.py`:
   - `_smart_locks_url`: if `return_to.startswith("/apartments/")` return `f"{return_to.split('#')[0]}#{anchor}"`; else return `f"/apartments#{anchor}"` (unchanged).
   - `GET /smart-locks`: if the owner has at least one active property (use `access.apartments(request)`, first row with `active`), redirect 303 to `/apartments/{id}?view=settings&section=lock#<anchor>` where anchor is `smart-locks-list` if an account exists else `smart-locks-how`; with no property redirect to `/apartments` (no anchor).
5. `_property_editor.html`:
   - In the lock group, replace the `{% if not door_code.account %} ... {% elif not door_code.locks %} ... {% else %}` branch so that the first two branches show only their `<p class="ui-sub">` sentence (delete the two `<a ... href="/smart-locks?...">` buttons). Keep the `{% else %}` branch unchanged.
   - Directly after the settings form's closing `</form>` (line 371), add:
     ```
     {% if door_code and lock_panel and lock_panel.smart_locks_enabled %}
     <div class="property-settings-group{% if settings_section == 'lock' %} is-active{% endif %}" data-settings-group="lock" id="settings-lock-account">
       <section class="panel property-section ui-section" id="smart-locks">
         <h3 class="property-section-title">{{ t('smart_locks.title') }}</h3>
         <p class="ui-sub">{{ t('smart_locks.lede') }}</p>
         {% with account=lock_panel.account, receiver=lock_panel.receiver, locks=lock_panel.locks, fetched_at=lock_panel.fetched_at, reauth=lock_panel.reauth, return_to=lock_panel.return_to, properties_using=lock_panel.properties_using %}
         {% include "_smart_locks_panel.html" %}
         {% endwith %}
       </section>
     </div>
     {% endif %}
     ```
     If the settings form shows its sticky save bar from a wrapper, this block must sit after it, still inside the same tab root that app.js searches (check with the browser in step 7).
6. `guide_i18n.py`: EN `'In UbyHost open Properties, pick the property, then the Door lock tab.'`; CS `'V UbyHost otevřete Ubytování, vyberte ubytování a otevřete záložku Zámek.'` (check the CS tab label `property_nav.group.lock` in host_i18n.py and use that exact word).
7. Tests: update `tests/test_smart_locks_page.py` so it asserts the panel is NOT on `/apartments` and IS on `/apartments/<id>?view=settings&section=lock`; redirects from `/smart-locks/refresh` with an `/apartments/<id>` return_to now land on `/apartments/<id>...#smart-locks-...`; lines ~189/192 no longer expect `/smart-locks?return_to=` links. Keep every other assertion.

## 5. Do not touch

`_smart_locks_panel.html`, CSS, JS, ttlock.py, door_codes.py. Hard rules: privacy first, no new dependency, never push.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_smart_locks_page.py tests/test_door_code*.py tests/test_ttlock*.py tests/test_property_hub.py tests/test_lock_navigation_browser.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] `/apartments` has no "Digital door lock" heading.
- [ ] `/apartments/<id>?view=settings&section=lock` shows the lock settings and the account panel; the panel's buttons post and come back to that tab.
- [ ] Tests above pass.

## 8. Stop and ask

If an excerpt is not found, or a test outside the list fails, stop and report. Do not commit; the orchestrator commits.

## 9. Report

[0195-report.md](0195-report.md)
