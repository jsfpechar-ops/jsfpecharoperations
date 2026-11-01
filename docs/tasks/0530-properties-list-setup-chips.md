# 0530: Properties page redesign, part 1: one table with green/red setup chips
Status: todo
Depends on: 0496 shell (merged) | Base commit: origin/main | Branch: task/0530-props-list
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Make the Properties list (`/apartments`, Czech title "Ubytování") follow the approved computer mockup (`/mnt/project-files/ux-redesign/ubyhost-redesign-v2.html`, view "props"), owner approved 2026-11-01: one table with the columns Name, Address, Setup, a "Copy link" button and the row menu. The Setup cell holds four chips, Police, Calendar, Lock, Stay fee: green = done, red = missing, grey = not used. Each chip is a link to the setting that fixes it. The second table ("property summaries": guest link, PIN, reporting timing) is removed; PIN and timing stay in each property's settings.

## 2. Context
- Route `apartments_list()` in `App/app/routes/admin.py` (line ~1183) builds `rows` (`apartment`, `issues`, `link_key`, `link_url`). Template `App/app/templates/apartments.html`.
- Chip rules (compute in the route, as `row["chips"]`, a list of 4 dicts `{"key", "state", "href"}`; state is `ok`, `bad` or `off`):
  - `police`: `bad` if `row["issues"]` is not empty or the property has an open alert of kind `ubyport_auth_failed` (one query for all the owner's properties: `SELECT apartment_id FROM alert WHERE owner_user_id = ? AND kind = 'ubyport_auth_failed' AND resolved_at IS NULL`); else `ok`. href `/apartments/<id>?view=settings&section=reporting#ubyport`.
  - `calendar`: `ok` if `feeds > 0` and no active feed has `last_status = 'error'`, else `bad`. Add a subquery `feed_errors` next to `feeds` in the list query (`... f.active = 1 AND f.last_status = 'error'`). href `/apartments/<id>?view=bookings#calendars`.
  - `lock`: `ok` if `apartment["lock_id"]` is set, else `off`. href `/apartments/<id>?view=settings&section=lock#door-code` when ok, else `/apartments/<id>?view=settings&section=property#basics`.
  - `fee`: `ok` if `stay_fee.is_active(apartment)` (already imported in admin.py as `stay_fee`), else `off` (the stay fee is optional: no rate = not used, grey). href `/apartments/<id>?view=settings&section=reporting#stay-fee-settings`.
- Badge classes exist in `App/app/static/host2.css` (line ~54): `ui-badge ui-badge-done` (green), `ui-badge-attention` (red), `ui-badge-neutral` (grey). Reuse them on `<a>` tags; do not add new badge colours.
- Copy button: macro `copy_inline(target_id, value, label)` in `_components.html` (line ~309).
- Address text: copy the expression `address_text` from `_property_overview.html` line 8.
- Translations: en and cs in `App/app/host_i18n.py`, vi in `App/app/host_vi_i18n.py`; existing `apartments.table.*` keys sit at line ~3380 (cs).
- Every new CSS class must be added to `docs/design/catalog.json` (the `classes` list and the description map), else `python3 scripts/design_lint.py` and CI fail.

## 3. Files
Edit `App/app/routes/admin.py` (apartments_list only), `App/app/templates/apartments.html`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/static/host2.css` (append at the end, plus its `?v=` key in `App/app/templates/base.html`), `App/tests/static_versions.json` (only via `--write`), `docs/design/catalog.json`. Create `App/tests/test_0530_properties_chips.py`. Screenshots `docs/tasks/screenshots-0530/`. Report `docs/tasks/0530-report.md`.

## 4. Steps
1. **Chips data.** In `apartments_list()` add the `feed_errors` subquery, the one alert query, and `row["chips"]` per rule above. Commit `0530 step 1`.
2. **Table.** In `apartments.html` replace the columns with: Name (`apartments.table.property`, keep the `property_identity` link and the inactive badge), Address (`apartments.table.address`), Setup (`apartments.table.setup`), a cell with `copy_inline('guest-url-' ~ apartment.id, row.link_url, t('common.copy_link'))` when `row.link_url` (else empty), and the existing actions cell (row_open + row menu, unchanged). The Setup cell: `<div class="property-setup-chips">` with one `<a class="ui-badge ui-badge-{done|attention|neutral}" data-setup-chip="{{ chip.key }}" data-state="{{ chip.state }}" href="{{ chip.href }}">{{ t('apartments.chip.' ~ chip.key) }}<span class="sr-only">: {{ t('apartments.chip_state.' ~ chip.state) }}</span></a>` per chip. Delete the whole `<section class="property-summaries">` block and its comment. Keep the empty states. Commit `0530 step 2`.
3. **Copy.** Keys: `apartments.table.address` en "Address", cs "Adresa", vi "Địa chỉ"; `apartments.chip.police` "Police"/"Policie"/"Công an"; `apartments.chip.calendar` "Calendar"/"Kalendář"/"Lịch"; `apartments.chip.lock` "Lock"/"Zámek"/"Khóa"; `apartments.chip.fee` "Stay fee"/"Poplatek"/"Phí lưu trú"; `apartments.chip_state.ok` "done"/"hotovo"/"xong"; `.bad` "missing"/"chybí"/"thiếu"; `.off` "not used"/"nepoužíváte"/"không dùng". Change the Setup header cs `apartments.table.setup` to "Nastavení" (en "Setup", vi keep). Remove keys that no template or Python file uses any more after step 2 (check each with `grep -rn` across `App/app` before removing): likely `apartments.table.entity`, `.calendars`, `.stays`, `apartments.setup.fix`, `.calendar`, `.ready`, `properties.summary.*`, `properties.inline.*`. Commit `0530 step 3`.
4. **CSS** (end of `host2.css`): `.host-workspace .property-setup-chips{display:flex;flex-wrap:wrap;gap:6px}` and `.host-workspace .property-setup-chips .ui-badge{text-decoration:none;margin:0}`. Add `property-setup-chips` to `docs/design/catalog.json`. Bump the `host2.css?v=` key, run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0530 step 4`.
5. **Test** `test_0530_properties_chips.py` (copy fixtures and login from `tests/test_properties_table_chips.py`): one property with full UbyPort fields, a working feed, `lock_id` set and a fee rate shows four `data-state="ok"` chips; a bare property shows police `bad`, calendar `bad`, lock `off`, fee `bad`; an open `ubyport_auth_failed` alert makes police `bad`; a feed with `last_status='error'` makes calendar `bad`; the page has no `property-summaries`; each chip href is the one in section 2. Commit `0530 step 5`.
6. Screenshots of `/apartments?lang=cs` at 1280 and 390 px into `docs/tasks/screenshots-0530/`. Commit `0530 step 6`.

## 5. Do not touch
Any JS file (`App/app/static/*.js`), the property detail page and its partials, the wizard (`setup_wizard/`), the row menu items, other routes. The JS that drove the removed inline timing form stays; the JS owner removes it. No new dependency, no migration.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0530_properties_chips.py tests/test_properties_table_chips.py tests/test_property_hub.py tests/test_host_ux_acceptance.py tests/test_no_dead_internal_links.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`, then the browser set `tests/test_0385_phone_card_open_browser.py tests/test_0284_states_browser.py tests/test_0285_rows_browser.py tests/test_host_list_page_layout_browser.py tests/test_onboarding_followup_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat origin/main` lists only section 3 files, plus tests changed under section 8.

## 8. Stop and ask
Standing rule: an existing test that asserts the removed columns, the old Setup badge text, or the property-summaries section may be updated (that assertion only) or, for `tests/test_properties_inline_controls_browser.py` which tests only the removed section, deleted; list each in the report. Stop if any other existing test changes result.

## 9. Report
`docs/tasks/0530-report.md`: Status, test and lint tails, `git diff --stat origin/main`, screenshot paths, deviations.
