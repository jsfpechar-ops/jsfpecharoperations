# 0534: property page on the v2 shell, part 1: shared form controls and the one-scroll page
Status: todo
Depends on: 0532/0533 (this branch), 0718 (merged) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Owner decision 2026-11-01 14:33: pages are rebuilt from the approved mockup's own HTML and CSS. Rebuild `/apartments/<id>` (editing branch of `App/app/templates/apartment_form.html`) like the mockup view `prop` in `docs/design/mockup/ubyhost-redesign-v2.html` (`grep -n 'data-v="prop"'`, about 25 lines; CSS lines ~51-63): crumb, h1, guest-link card, one column of `<details>` sections, a fixed save bar (Zrušit, Uložit). The preview aside and the phone layout come in 0535/0536. No JavaScript changes; the page must work without JS.

## 2. Context
- v2 opt-in exactly as `apartments.html` does it (top of file: `{% set v2 = true %}` and the empty blocks). Only `tokens.css` + `app2.css` load on v2, so every old class (`panel`, `field`, `hint`, `ui-btn*`, `ui-section`, `switch`, `err-text`) is unstyled there.
- Today the page has three views (Overview, Bookings, Settings: `data-property-views`, `data-property-view`, tabs) and settings groups (`data-settings-group`, `settings_section`). Agreed with the JS owner: one scroll page; each section a plain `<details>` that keeps its old `id`; remove the tabs, the section nav, `data-property-views/-view/-base` and `data-settings-group` wrappers. The JS owner then deletes `initPropertyViews` and `initInlineTiming` (not you).
- Sections, in this order (titles and one-line `<small>` from the mockup; new i18n keys `property_page.sec.<key>.title` / `.sub`, en/cs/vi in `App/app/host_i18n.py` and `App/app/host_vi_i18n.py`, cs text from the mockup):
  1. `basics` "Základní údaje" / "Název a adresa nemovitosti": the `settings_section == 'property'` group contents (basics, arrival-departure, address, notes; keep inner section ids).
  2. `police` "Cizinecká policie" / "Ubytovací zařízení a hlášení": the `reporting` group's `#ubyport` section and the `automation` group.
  3. `messages` "Automatické zprávy" / "Kdy se hostům pošle odkaz k registraci": the `guests` group.
  4. `lock` "Chytrý zámek" / "Kódy ke dveřím pro hosty": the `lock` group inside the form.
  5. `fee` "Poplatek z pobytu" / "Kolik se platí obci": `#stay-fee-settings`.
  6. `archive`: the existing archive section, last inside the form.
  All six live inside the existing settings `<form>` (one save). After the form: `calendars` "Kalendáře" / "Airbnb a Booking" holding `_property_calendars.html` (it has its own forms, so it cannot sit inside the settings form; this order is a known departure from the mockup), then the lock-account panel (`settings-lock-account`) if rendered, as its own details.
- Open state without JS: a section's `<details>` gets `open` when it holds the requested place: `settings_section` (property→basics, reporting→police or fee by anchor is unknown server-side, so open both police and fee for `reporting`; guests→messages; lock→lock; automation→police) or `property_view == 'bookings'` → calendars. With no view/section, open `basics` only (mockup).
- Keep from today: the guest-link card (0531 `.property-guest-link`; restyle it as the mockup card: `class="card guest-card"`, `<b>` title, `.sub` URL, the v2 copy button), the setup-continue card from `_property_overview.html` if `setup_progress` is shown (keep its markup), every form field, name, id and hidden input, the unsaved-changes reset button (`data-unsaved-reset`).
- Drop on this page: the tabs nav, the section nav, the overview health cards and readiness block (`_property_overview.html` stays on disk for 0535, which turns them into the preview aside; do not delete it).
- Save bar: the 0531 `.property-savebar` becomes mockup `.savebar` (fixed bottom right): `a.btn.ghost` Cancel (`/apartments`), the hidden reset button, `button.btn` Save, inside the form.
- Crumb: `<div class="crumb"><a href="/apartments">{{ t('nav.properties') or the sidebar label key }}</a> › {{ apartment.name }}</div>` then `<h1>`.
- Mockup page CSS to copy into a new 0534 block at the end of `App/app/static/app2.css`, scoped `body.v2`: `.form` (grid 1fr 300px; while no aside exists use one column: `grid-template-columns:minmax(0,1fr)` until 0535), `.crumb`, `details`, `summary` (+ marker and `:after` rules), `.fields`, `.savebar`, the `details .fields` animation only under `prefers-reduced-motion:no-preference`.
- NEW shared block (agreed with the Overview thread, you own it): `/* v2 form controls (shared, generic) */` near the shared rules in app2.css, `body.v2` scoped, no page selectors: `label` (block, 13px, `--ink2`), `input[type=text|number|email|password|tel|url|date|time|search]`, `select`, `textarea` with the mockup `.in` values (`margin-top:4px;border:1px solid #dcdcd7;border-radius:8px;padding:9px 10px;background:var(--s);color:var(--ink);font:inherit;width:100%;box-sizing:border-box`), focus uses the shell's focus ring (read how 0705-0718 style `:focus-visible`), `.hint` (12px `--ink3`), `.err-text` (`--bad`), checkbox and `[role=switch]` at 20 px with `accent-color:var(--acc)`, old `ui-btn ui-btn-secondary` / `ui-btn-compact` / `ui-btn-quiet` mapped to the mockup `.btn.ghost` / `.btn.sm` look, `.field` as a block with 12px bottom gap. Below 1024 px inputs, selects and buttons are at least 44 px tall. AA contrast for text and borders on controls (3:1 for the border).

## 3. Files
Edit `App/app/templates/apartment_form.html`, `App/app/templates/_property_editor.html`, `App/app/templates/_property_calendars.html` (wrapper only if needed), `App/app/static/app2.css`, `App/app/templates/base.html` (app2 key), `App/tests/static_versions.json` (`--write`), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `docs/design/catalog.json`, `scripts/design_lint.py` (add the two templates to `V2_TEMPLATES` if the lint needs it, as 0532 did), `App/tests/v2_mockup.py` (one new PAGES entry `property`, path = the first seeded property's page, `view: "prop"`, selectors `.crumb`, `main h1`, `.guest-card`, `details`, `summary b`, `summary small`, `.savebar .btn`; `phone_view: None` until 0536, the way `menu` marks a missing view). Create `App/tests/test_0534_property_page_v2.py`. Report `docs/tasks/0534-report.md`, screenshots `docs/tasks/screenshots-0534/`.

## 4. Steps
1. Template: v2 opt-in, crumb, h1, guest card, details sections and open rules, save bar; remove tabs/views/groups wrappers. Commit `0534 step 1`.
2. i18n keys; remove keys that nothing uses any more (grep each across `App/app`). Commit `0534 step 2`.
3. CSS: shared form-controls block and the 0534 page block; key bump, `--write`; catalog. Commit `0534 step 3`.
4. Test `test_0534_property_page_v2.py` (fixtures from `tests/test_property_hub.py`): page is v2 (no `property-tabs`, no `data-property-view`); the seven/eight `details` exist in order with their ids; `?view=settings&section=lock` opens only `lock`; `?view=bookings` opens `calendars`; no view opens `basics`; a POST of the settings form still saves a field (reuse an existing save assertion); every old anchor id used by links in `App/app` (`#ubyport`, `#stay-fee-settings`, `#door-code`, `#basics`, `#address`, `#communication`, `#calendars`, `#automation`) still exists. Commit `0534 step 4`.
5. PAGES entry; run section 6 until green. Commit `0534 step 5`.
6. Screenshots of `/apartments/<id>?lang=cs` at 1280 and 1024 and the mockup `prop` view at 1280. Commit `0534 step 6`.

## 5. Do not touch
Any JS file, routes (`App/app/routes/*`), form field names and POST handling, the wizard (`setup_wizard/`), `_property_overview.html` content, other pages' templates, the 0532/0533 blocks, the 0710 comparison logic. No new dependency.

## 6. Commands (from `App/`; browser tests SKIP SILENTLY without the env vars)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then
`.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_property_hub.py tests/test_property_readiness.py tests/test_host_ux_acceptance.py tests/test_no_dead_internal_links.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rfs -p no:cacheprovider 2>&1 | tail -30`
then the browser tests that open a property page: `grep -l "/apartments/" tests/*browser*.py | head -20`, run them `-q --tb=short -rfs -p no:cacheprovider 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3`. Restore tracked PNGs a run rewrites outside `screenshots-0534/`. Known failures not yours: 0710 overview-768, properties-768, menu-320.

## 7. Acceptance
All pass, 0 skipped, except the known three. 0710 passes for `property` at 1024, 1280, 1440. Only section 3 files plus section 8 tests changed.

## 8. Stop and ask
Standing rule: an existing test that asserts the removed tabs, views, settings groups, section nav, overview health cards on the property page, or old class names there may be updated to the new markup (that assertion only; list each). A test that asserts JS behaviour of the removed views (`initPropertyViews`) may be deleted only if it tests nothing else; list it. Stop if a POST/save test fails, if an old link anchor no longer resolves, or if a test about another page fails.

## 9. Report
`docs/tasks/0534-report.md`: status, tails, diff stat, screenshot paths, deviations. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push.
