# 0123: Unified host workspace and property timing

Status: review
Depends on: none | Base commit: 7835b528cec95a1d7a25798e0002d28c0255f346 | Branch: feature/host-design0123-20261016
Executor: Luna executor | PR: #397
Report: docs/tasks/0123-host-design-report.md

## 1. Objective

Implement the owner-approved flat-white host workspace proposal in `docs/plans/0123-rework-proposal`, with real UbyHost logos/icons, compact calendar controls, stay-first lists, and one shared Properties source for check-in/check-out defaults.

## 2. Context and decisions

- Owner approved the revised proposal and implementation. Keep FastAPI/Jinja/plain JS, current routes/data/permissions, and system fonts.
- Main workspace white; warm color remains in the rail and small accents. Coral actions, near-black type, neutral dividers, centered 1080px lane, 216px rail.
- Keep existing Search, account/admin, language, environment, collapse/mobile drawer, dialogs, navigation, exports, filters, saved views, filing, restore/archive, invoices, receipts and door-code actions.
- Property hours are `apartment.checkin_hour` / `checkout_hour`; Properties settings and the Property wizard step own the one editable pair. Door lock and Cleaning show inherited values and link back to Properties.
- Cleaning legacy `checkout_time` / `checkin_time` values are retained without migration but do not override apartment hours. Explicit per-cleaning time/date adjustments remain valid.
- Manual reservation summary is safe as the stay label only for manual source; imported summaries and guest identities do not become new list content.

## 3. Files

Production UI: `App/app/static/host-design0123.css`; `App/app/templates/base.html`; `App/app/templates/dashboard.html`; `App/app/templates/reservations.html`; `App/app/templates/reservation_detail.html`; `App/app/templates/_components.html`; `App/app/templates/_dashboard_calendar.html`; `App/app/static/dashboard-calendar.js`; `App/app/static/dashboard-calendar.css`; `App/app/host_design_i18n.py`.
Shared timing: `App/app/templates/_property_editor.html`; `App/app/routes/admin.py`; `App/app/templates/cleaning_settings.html`; `App/app/routes/cleaning.py`; `App/app/cleaning.py`; `App/app/cleaning_i18n.py`; `App/app/templates/setup_wizard/property.html`; `App/app/templates/setup_wizard/door_lock.html`; `App/app/property_setup.py`.
Tests: `App/tests/test_dashboard_calendar_browser.py`; `App/tests/test_cleaning.py`; `App/tests/test_cleaning_browser.py`; `App/tests/test_host_wide_geometry_browser.py`; `App/tests/test_host_list_layouts_browser.py`; `App/tests/test_host_geometry.py`; `App/tests/test_lock_navigation_browser.py`; `App/tests/test_door_codes_safeguards.py`; `App/tests/test_onboarding_wizard_survival.py`; `App/tests/test_property_navigation_browser.py`; `App/tests/test_host_quiet_dashboard_browser.py`; `App/tests/test_onboarding_followup_browser.py`; `App/tests/test_overhaul.py`; `App/tests/test_signed_in_chrome.py`.
Docs/CI: `.github/workflows/ci.yml`; `docs/tasks/0123-host-design.md`; `docs/tasks/0123-host-design-report.md`; `docs/plans/0123-rework-proposal/README.md`; `docs/HOST_APP_DESIGN.md`; `docs/DESIGN.md`; `docs/context/status.md`; `docs/context/decisions.md`; `docs/context/known-issues.md`. CI changes are limited to adding an existing browser test if needed.

## 4. Steps

1. Replace the first-pass theme with a coherent host-only flat-white layer; retain real shell assets and working-lane/card breakpoints.
2. Flatten dashboard counts/calendar/queue and list/detail/property/cleaning surfaces without losing current controls or data hooks. Stay rows use safe manual label, full date range, property identity, guest/report facts and existing More actions.
3. Replace calendar button groups with native View (Auto/Calendar/Gantt) and Period (Month/Week/Year) selects mirroring current mode/scale, auto threshold, URL/storage and Settings behavior.
4. Edit property hours independently of TTLock state, validate before writes, preserve missing legacy form values and existing lock guards. Cleaning automatic availability uses property hours; old cleaning defaults remain stored but ignored. Preserve manual event adjustments and conflict checks.
5. Update focused browser/unit coverage and active design/context docs; keep screenshot evidence in existing CI uploads.

## 5. Do not touch

No public/guest/auth redesign, new backend search, data migration, dependency, share-policy, filing, permission, credential or TTLock issuance changes. No lock calls, main push, merge or deployment.

## 6. Commands

Run the full test suite and required zero-skip Chromium/geometry jobs through repository CI because the managed shell/browser environment is unavailable. Keep all existing assertions and screenshot uploads. Do not claim local browser results.

## 7. Acceptance

Flat-white work surfaces with real icons; readable EN/CS layouts at 360–2048px; working manual/Auto calendar behavior and every existing action; one Properties-owned hours pair used by TTLock and Cleaning; legacy cleaning values preserved; manual cleaning exceptions retained; full required CI with zero skipped browser cases.

## 8. Stop and ask

Stop only for a genuine schema, permission/security, missing-file, or required-scope blocker. Resolve routine visual and implementation choices autonomously.

## 9. Report

Use `docs/tasks/0123-host-design-report.md`, then mark this brief review. Link exact CI and screenshot evidence and state any remaining visual review limitation.
