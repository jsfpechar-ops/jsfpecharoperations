# 0531: Properties page redesign, part 2: property page guest-link card and save bar
Status: todo
Depends on: none (runs beside 0530) | Base commit: origin/main | Branch: task/0531-property-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Bring one property's page (`/apartments/<id>`) closer to the approved computer mockup (`/mnt/project-files/ux-redesign/ubyhost-redesign-v2.html`, view "prop"), owner approved 2026-11-01, without touching JavaScript: (a) an "Odkaz pro hosty" card at the top of the page with the guest link and one Copy button; (b) the settings Save row becomes a save bar fixed to the bottom right of the screen (Cancel, then Save); (c) settings sections use the mockup card geometry. The Overview / Bookings / Settings tabs and the settings section links stay (the JS owner changes them later).

## 2. Context
- Page: `App/app/templates/apartment_form.html` includes `_property_overview.html`, `_property_calendars.html`, `_property_editor.html`. The guest link URL is the template variable `permalink` (used in `_property_overview.html` with `copy_inline`).
- Save row: `<div class="actions host-property-save">` near the end of the form in `_property_editor.html` (line ~364): Save (primary), discard (`data-unsaved-reset`, hidden until a change, JS-driven: keep the attribute), "Back to list" link.
- Sections: `section.panel.property-section.ui-section` in `_property_editor.html`.
- CSS goes at the end of `App/app/static/host.css` (link with `?v=` key in `App/app/templates/base.html`). Design tokens: `grep -n -- '--radius\|--line\|--surface\|--space-' App/app/static/host.css | head -20`.
- Every new CSS class must be added to `docs/design/catalog.json` (the `classes` list and the description map), else `python3 scripts/design_lint.py` and CI fail.

## 3. Files
Edit `App/app/templates/apartment_form.html`, `App/app/templates/_property_overview.html`, `App/app/templates/_property_editor.html`, `App/app/static/host.css` (append), `App/app/templates/base.html` (the `host.css?v=` key only), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/tests/static_versions.json` (only via `--write`), `docs/design/catalog.json`. Create `App/tests/test_0531_property_page.py`. Screenshots `docs/tasks/screenshots-0531/`. Report `docs/tasks/0531-report.md`.

## 4. Steps
1. **Guest-link card.** In `apartment_form.html`, in the editing branch, before the `<nav class="ui-tabs property-tabs">`, add `<section class="panel property-guest-link" aria-labelledby="property-guest-link-title"><div><h2 id="property-guest-link-title">{{ t('property_page.guest_link.title') }}</h2><p class="ui-sub mono">{{ permalink }}</p></div>{{ copy_inline('property-guest-url', permalink, t('common.copy_link')) }}</section>` only when `permalink`. In `_property_overview.html` remove the copy action from the guest-links card (the `copy_inline('overview-guest-url', ...)` div), keep the card. Copy: `property_page.guest_link.title` en "Guest link", cs "Odkaz pro hosty", vi "Liên kết cho khách". Commit `0531 step 1`.
2. **Save bar.** In `_property_editor.html` change the save row to `<div class="actions host-property-save property-savebar">` with, in this order: the "Back to list" link relabelled `t('common.cancel')` (keep href `/apartments`), the hidden discard button unchanged, and the Save button last. Commit `0531 step 2`.
3. **CSS** (end of `host.css`, real token names, fallbacks as in the mockup):
   `.host-workspace .property-guest-link{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px;margin-bottom:12px;border-radius:12px}` `.host-workspace .property-guest-link h2{font-size:15px;margin:0}` `.host-workspace .property-guest-link .ui-sub{margin:2px 0 0;overflow-wrap:anywhere}`;
   `.host-workspace .property-savebar{position:sticky;bottom:0;display:flex;justify-content:flex-end;gap:8px;padding:12px 0;background:var(--surface-page, #f6f6f4);border-top:1px solid var(--border, #ebebe7);z-index:5}`;
   `.host-workspace .property-section.ui-section{border-radius:12px}`.
   At max-width 640px the savebar buttons fill the width (`flex:1`). Add `property-guest-link` and `property-savebar` to `docs/design/catalog.json`. Bump `host.css?v=`, run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0531 step 3`.
4. **Test** `test_0531_property_page.py` (copy fixtures and login from `tests/test_property_hub.py`): the page has `property-guest-link` with the permalink and one `data-copy="property-guest-url"` button; the overview no longer has `overview-guest-url`; in the settings form the save row has class `property-savebar` and its last button is the submit Save; a POST of the form still saves (reuse an existing save assertion). Commit `0531 step 4`.
5. Screenshots of `/apartments/<id>?lang=cs` (overview view) and `?view=settings` at 1280 and 390 px into `docs/tasks/screenshots-0531/`. Commit `0531 step 5`.

## 5. Do not touch
Any JS file, the tabs and section links, `_property_calendars.html`, the wizard (`setup_wizard/`), `apartments.html`, any route or Python file other than the two i18n files. No new dependency, no migration.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0531_property_page.py tests/test_property_hub.py tests/test_host_ux_acceptance.py tests/test_no_dead_internal_links.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`, then the browser tests that open a property page: `ls tests/*browser*.py | xargs grep -l "/apartments/" | head -8`, run those with `-q --tb=short -x -rs 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat origin/main` lists only section 3 files, plus tests changed under section 8.

## 8. Stop and ask
Standing rule: an existing test that asserts the moved overview copy button, the "Back to list" label or the old save-row order may be updated (that assertion only); list each in the report. Stop if any other existing test changes result, or if the sticky save bar covers a field at 390 px.

## 9. Report
`docs/tasks/0531-report.md`: Status, test and lint tails, `git diff --stat origin/main`, screenshot paths, deviations.
