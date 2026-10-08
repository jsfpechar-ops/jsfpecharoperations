# 0011: Door code section on the property page

Status: todo
Depends on: 0010 | Base commit: after 0010 merges | Branch: task/0011-property-door-code-section
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

On an existing property's page, every host gets an optional "Door code" section (once the owner has switched the feature on): one tick box to switch door codes on, the lock, and the required check-in and check-out hours. Nothing issues codes yet (task 0012). The new-property form sees no change, and a host without TTLock only sees a one-line pointer to Settings.

## 2. Context

- Plan: `docs/plans/ttlock-door-codes.md` §2 (decisions 5, 5a, 5b) and §10 (the property sketch). Rule from `docs/HOST_APP_DESIGN.md` §6: optional features never block a first stay, so the section is edit-only, and errors redirect to a stable anchor.
- `config.DOOR_CODES_LIVE` (added by task 0012, which runs after this one): until it is on, only stays the host added by hand get a code. Use `getattr(config, "DOOR_CODES_LIVE", False)` here so this task does not depend on 0012.
- From task 0010 (`App/app/ttlock.py`): `allowed_for(owner_user_id)` (feature on and credentials set; there is no pilot list), `account_for(owner_user_id)`, `locks_of(account)` (items `lock_id`, `alias`, `battery`, `tz_offset_ms`, `key_end`). From 0008: `apartment.lock_provider`, `lock_id`, `checkin_hour`, `checkout_hour`; `config.DOOR_CODE_BUFFER_HOURS = 1`.
- Routes (`App/app/routes/admin.py`): GET `/apartments/{apartment_id}` is `apartment_detail` (renders `apartment_form.html`, near line 829). POST `/apartments/{apartment_id}` is `apartment_update`, which calls `_save_apartment_form(apartment_id, request, form)` (near line 883). That function ends with:
  ```
  db.update("apartment", apartment_id, payload)
  if credentials_changed:
      alerts.resolve(f"ubyport_auth_failed:{apartment_id}")
  db.audit("apartment_updated", f"id={apartment_id}")
  ```
  It returns `_back(f"/apartments/{apartment_id}#communication", err=_flash(request, "..."))` on an error and `None` on success.
- Template `App/app/templates/apartment_form.html`, all inside one `<form method="post" ...>` (no nested forms). Edit-mode cards (line 28):
  `{% for anchor, icon, key, hint in [('calendars', 'calendar', 'host.bookings', ''), ... ('address', 'property', 'host.property_details', '')] %}`.
  Edit-mode section nav: `<a href="#stay-fee-settings">{{ t('apartment.form.nav.stay_fee') }}</a>` (line 43). Sections are `<details class="panel property-section" id="...">` with a `<summary>`; selects use `<div class="field" style="max-width:320px"><label>…</label><select>…</select><div class="hint">…</div></div>`; tick boxes use `<div class="checkline"><input type="checkbox" …><label …>…</label></div>`.
- Host strings: `App/app/host_i18n.py` EN and CS, parity test `tests/test_host_i18n.py`. No em dashes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | Steps 1 and 2 |
| `App/app/templates/apartment_form.html` | edit | Step 3 |
| `App/app/host_i18n.py` | edit | Step 4 |
| `App/tests/test_property_door_code.py` | create | Step 5 |
| `App/tests/test_host_geometry.py` | edit | Step 6, one test |

No other file may change.

## 4. Steps

1. **Context.** In `apartment_detail`, add `door_code` to the render context:
   - `None` unless `ttlock.allowed_for(apartment["owner_user_id"])`.
   - Otherwise:
     ```python
     account = ttlock.account_for(apartment["owner_user_id"])
     locks = ttlock.locks_of(account) if account else []
     selected = next((l for l in locks if l["lock_id"] == apartment["lock_id"]), None)
     cin, cout = apartment["checkin_hour"], apartment["checkout_hour"]
     door_code = {
         "account": account,
         "locks": locks,
         "enabled": apartment["lock_provider"] == "ttlock",
         "lock_id": apartment["lock_id"],
         "checkin_hour": cin,
         "checkout_hour": cout,
         "tz_warning": bool(selected and selected["tz_offset_ms"] not in (None, 3600000)),
         "overlap": cin is not None and cout is not None and cin - cout < 2 * config.DOOR_CODE_BUFFER_HOURS,
         "buffer": config.DOOR_CODE_BUFFER_HOURS,
         "test_mode": not getattr(config, "DOOR_CODES_LIVE", False),
     }
     ```
2. **Save.** In `_save_apartment_form`, before `db.update("apartment", apartment_id, payload)`, add a block that runs only when `form.get("door_code_section") == "1"` and `ttlock.allowed_for(<the apartment's owner_user_id>)` (read the apartment row the function already has; if it has none, fetch it with `db.query_one`):
   - Ticked (`form.get("door_codes") == "1"`):
     - `lock_id` must be one of `[l["lock_id"] for l in ttlock.locks_of(ttlock.account_for(owner_id))]`, else return `_back(f"/apartments/{apartment_id}#door-code", err=_flash(request, "flash.error.door_code_lock"))`.
     - `checkin_hour` and `checkout_hour` must both parse as integers 0 to 23, else `flash.error.door_code_hours`.
     - Then `payload.update({"lock_provider": "ttlock", "lock_id": lock_id, "checkin_hour": cin, "checkout_hour": cout})`.
   - Not ticked: `payload["lock_provider"] = None`. Keep `lock_id` and the hours, so ticking again is one click. Hours that were sent are still saved if they are valid integers 0 to 23.
   - An error returns before anything is written, so a failed save changes nothing.
   - After the existing `db.audit("apartment_updated", ...)`, write `db.audit("door_codes_on", f"apartment={apartment_id}")` or `db.audit("door_codes_off", f"apartment={apartment_id}")` only when `lock_provider` actually changed.
3. **Template.**
   - Cards: build the list with `{% set cards = [ ...the existing six tuples... ] %}`, then `{% if door_code %}{% set cards = cards + [('door-code', ICON, 'host.door_code', '')] %}{% endif %}`, and loop over `cards`. For `ICON`, use an existing `nav_icon` name (grep the macro); pick `key` or `lock` if one exists, else `property`. Inside the card, add `{% if anchor == 'door-code' %}<small>{{ t('apartment.form.door_code.on') if door_code.enabled else t('apartment.form.door_code.off') }}</small>{% endif %}`.
   - Section nav: after the `#stay-fee-settings` link, add `{% if door_code %}<a href="#door-code">{{ t('host.door_code') }}</a>{% endif %}`.
   - Section, right after the `stay-fee-settings` section's closing `</details>`, inside the main form, only `{% if editing and door_code %}`:
     ```
     <details class="panel property-section" id="door-code" {% if door_code.enabled %}open{% endif %}>
       <summary>{{ t('host.door_code') }}</summary>
       <input type="hidden" name="door_code_section" value="1">
       {% if not door_code.account %}
         <p class="small muted">{{ t('apartment.form.door_code.connect_first') }} <a href="/settings#settings-smart-locks">{{ t('settings.smart_locks.title') }}</a></p>
       {% else %}
         <p class="small muted" style="margin-top:-4px">{{ t('apartment.form.door_code.lede') }}</p>
         {% if door_code.test_mode %}<p class="small"><strong>{{ t('apartment.form.door_code.test_mode') }}</strong></p>{% endif %}
         <div class="checkline"><input type="checkbox" id="door_codes" name="door_codes" value="1" {% if door_code.enabled %}checked{% endif %}><label for="door_codes">{{ t('apartment.form.door_code.enable') }}</label></div>
         <div class="field" style="max-width:320px"><label for="lock_id">{{ t('apartment.form.door_code.lock') }}</label>
           <select id="lock_id" name="lock_id"><option value="">{{ t('apartment.form.door_code.choose') }}</option>
             {% for lock in door_code.locks %}<option value="{{ lock.lock_id }}" {% if lock.lock_id == door_code.lock_id %}selected{% endif %}>{{ lock.alias }} ({{ t('settings.smart_locks.lock_id', id=lock.lock_id) }})</option>{% endfor %}
           </select>
           {% if door_code.tz_warning %}<div class="hint"><strong>{{ t('settings.smart_locks.timezone_warning') }}</strong></div>{% endif %}
         </div>
         <div class="grid two">
           {% for name, value, label in [('checkin_hour', door_code.checkin_hour, 'apartment.form.door_code.checkin'), ('checkout_hour', door_code.checkout_hour, 'apartment.form.door_code.checkout')] %}
           <div class="field"><label for="{{ name }}">{{ t(label) }}</label>
             <select id="{{ name }}" name="{{ name }}"><option value="">{{ t('apartment.form.door_code.choose') }}</option>
               {% for h in range(24) %}<option value="{{ h }}" {% if value == h %}selected{% endif %}>{{ '%02d:00' % h }}</option>{% endfor %}
             </select></div>
           {% endfor %}
         </div>
         <p class="small">{{ t('apartment.form.door_code.margin', hours=door_code.buffer) }}</p>
         {% if door_code.overlap %}<p class="small"><strong>{{ t('apartment.form.door_code.overlap') }}</strong></p>{% endif %}
         <p class="small muted">{{ t('apartment.form.door_code.risk') }}</p>
       {% endif %}
     </details>
     ```
4. **Strings** (EN and CS):

   | Key | EN | CS |
   |---|---|---|
   | `host.door_code` | Door code | Kód ke dveřím |
   | `apartment.form.door_code.on` | On | Zapnuto |
   | `apartment.form.door_code.off` | Off | Vypnuto |
   | `apartment.form.door_code.connect_first` | Connect a TTLock account first: | Nejdřív připojte účet TTLock: |
   | `apartment.form.door_code.lede` | When every guest on a stay is registered, UbyHost creates a TTLock code for the stay and sends it to the guest, with you in copy. | Jakmile jsou zaregistrováni všichni hosté pobytu, UbyHost vytvoří kód TTLock pro daný pobyt a pošle ho hostovi, vám v kopii. |
   | `apartment.form.door_code.test_mode` | Test mode: only stays you add by hand get a door code. Guests from booking calendars get none yet. | Testovací režim: kód ke dveřím dostanou jen pobyty, které přidáte ručně. Hosté z rezervačních kalendářů zatím žádný nedostanou. |
   | `apartment.form.door_code.enable` | Send guests a door code | Posílat hostům kód ke dveřím |
   | `apartment.form.door_code.lock` | Lock | Zámek |
   | `apartment.form.door_code.choose` | Choose | Vyberte |
   | `apartment.form.door_code.checkin` | Check-in from | Příjezd od |
   | `apartment.form.door_code.checkout` | Check-out until | Odjezd do |
   | `apartment.form.door_code.margin` | Codes work from %(hours)s hour before check-in to %(hours)s hour after check-out, so a slightly wrong lock clock never locks a guest out. | Kódy fungují od %(hours)s hodiny před příjezdem do %(hours)s hodiny po odjezdu, takže mírně nepřesné hodiny zámku hosta nikdy nezamknou venku. |
   | `apartment.form.door_code.overlap` | With these times, the leaving guest's code still works when the next guest arrives. | S těmito časy funguje kód odjíždějícího hosta ještě při příjezdu dalšího. |
   | `apartment.form.door_code.risk` | Anyone with this property's guest link and PIN can register for an upcoming stay and receive its door code. Change the PIN from time to time. | Kdokoli s odkazem pro hosty a PINem tohoto ubytování se může zaregistrovat k nadcházejícímu pobytu a dostat jeho kód ke dveřím. PIN čas od času změňte. |
   | `flash.error.door_code_lock` | Choose a lock from the list. | Vyberte zámek ze seznamu. |
   | `flash.error.door_code_hours` | Choose the check-in and check-out hour. | Vyberte hodinu příjezdu a odjezdu. |
5. **Tests** (`App/tests/test_property_door_code.py`), with `login_as` and the host and property setup from `tests/test_property_form_save.py`. Monkeypatch the feature on (`config.DOOR_CODES_ENABLED`, `TTLOCK_CLIENT_ID`, `TTLOCK_CLIENT_SECRET`) and seed a `lock_account` with `locks_json` of two locks. Each test posts the full form the way `test_property_form_save.py` does, plus the door-code fields. Tests:
   - `test_section_absent_when_the_feature_is_off` (`id="door-code"` missing).
   - `test_section_absent_on_the_new_property_form`.
   - `test_section_asks_to_connect_first_without_an_account`.
   - `test_enabling_saves_lock_and_hours` (columns read back `ttlock`, the lock id, 15, 11; audit `door_codes_on`).
   - `test_enabling_without_hours_is_refused_and_saves_nothing` (an unrelated field changed in the same post is not saved either).
   - `test_a_lock_outside_the_list_is_refused`.
   - `test_unticking_turns_codes_off_and_keeps_the_settings` (`lock_provider` NULL, `lock_id` and hours kept; audit `door_codes_off`).
   - `test_overlap_warning_shows_for_tight_turnover` (check-out 11, check-in 12).
   - `test_timezone_warning_shows_for_a_lock_off_prague_time`.
   - `test_test_mode_line_shows_until_live` (shown by default; hidden with `config.DOOR_CODES_LIVE = True` set through `monkeypatch.setattr(config, "DOOR_CODES_LIVE", True, raising=False)`).
   - `test_saving_other_fields_leaves_door_code_settings_alone` (a post without `door_code_section` keeps the four columns as they were).
6. **Geometry.** In `App/tests/test_host_geometry.py` add `test_door_code_section_fits(base, width)` for 360, 390 and 1280, same style as task 0010's test: feature on, account seeded, property with door codes on, open `/apartments/<id>?lang=en#door-code`, open the `<details>`, assert no horizontal overflow and that both hour selects have the same height. Save a screenshot of the section at each width to `docs/tasks/0011-shots/`.

## 5. Do not touch

Everything outside §3. `_apartment_payload` (the create path) stays unchanged. No scheduler, guest page or mail change.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (all pass), and `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_geometry.py -q -rs` (0 skipped). From the repo root: `python3 scripts/context_lint.py` (last line `context lint: OK`).

## 7. Acceptance

- [ ] The 11 tests in step 5 and the geometry test pass. All existing `tests/test_property_*.py` tests pass unchanged. Host geometry: 0 skipped.
- [ ] Screenshots at 360, 390 and 1280 px in `docs/tasks/0011-shots/`.
- [ ] `git diff --stat` shows only the files in §3 plus the screenshots.

## 8. Stop and ask

Stop, and write the report, if:

- a name or excerpt in §2 is not found;
- `_save_apartment_form` has no apartment row to read the owner from and fetching it changes behaviour;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0011-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/routes/admin.py` (`_save_apartment_form` block)
- `App/app/templates/apartment_form.html` (cards list and the section)

## Owner steps

After deploy: open each pilot property, tick **Send guests a door code**, pick the lock, set check-in and check-out, and save. Nothing is sent until task 0012 is live.
