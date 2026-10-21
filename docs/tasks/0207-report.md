# 0207 report

Status: blocked
Branch: claude/project-thread-cf47ju | Base: 40b1947 (brief commit)

## Files changed

- docs/design/catalog.json: five classes registered, five class notes added (formatting kept, diff is additions only)
- App/app/static/host2.css: `border-radius: 2px` to `var(--radius-xs)`; `.required-legend` `font-size: 14px` to `var(--text-sm)` (note: `--text-sm` is 13px, not 14px, as the brief asked)
- App/app/templates/base.html: host2.css key `20261021-0204` to `20261021-0207`
- App/tests/static_versions.json: regenerated with `--write` (32 files)
- App/app/host_i18n.py: Czech `apartment.form.ubyport.mark_hint` text changed (exact anchor, one match)
- App/tests/test_smart_locks_page.py: three TTLock essentials lines replaced (exact anchor, one match)
- App/tests/test_onboarding_wizard_browser.py: `#uby_ws_password` fill added (anchor found once, followed by the `.err-text` assert)

## Commands (last lines)

1. `python3 scripts/design_lint.py`: `design lint: OK`
2. `pytest tests/test_design_lint.py tests/test_dev_ui.py tests/test_design_ui_macros.py tests/test_static_versions.py`: `15 passed`
3. `python3 scripts/context_lint.py`: FAIL, `ERROR docs/tasks/0207-design-lint-for-onboarding-fixes.md: missing section '## 5. Do not touch'`. The brief itself lacks that section. Warnings about other briefs are unrelated to this change.
4. `pytest tests/test_reporting_help_0097.py tests/test_smart_locks_page.py -x`: `1 failed, 5 passed`. Failing test: `test_smart_locks_page.py::test_after_connecting_three_essentials_and_every_tap_in_the_guide`, assertion `'Tap Recipient and paste the name' in guide`. That text is `smart_locks.s6` in host_i18n.py, which the brief did not change. Not fixed: picking the right guide wording would be a guess. Not checked on main.
5. Browser run `test_onboarding_wizard_browser.py test_host_ux_acceptance.py` (UBYHOST_REQUIRE_BROWSER=1): `1 failed, 81 passed`, 0 skipped. Failing test: `test_host_ux_acceptance.py::test_each_property_setting_has_exactly_one_editable_control_in_the_whole_host`, message `property-overview: setting has no editor ['city_en']`. Not checked on main; not fixed.

## Step 8 (360 px tab overflow)

- main (2f043c8): FAILS, `(360, 'en', 'settings', {'scroll': 360, 'vw': 360, 'bad': ['Reporting & fees', 'Door lock', 'Automation'], 'tabsScroll': True, ...})`
- branch: FAILS with the same assertion and the same three bad tabs.
- It is pre-existing on main, so not this PR's regression. Not fixed, per the brief.

## Deviations

- Steps 1 to 8 applied as written. Each step has its own commit (`0207 step k`). Report is committed separately.
- Test command 4 and test command 5 each have one failing test (above). Brief §8 asks to stop after a second failure. I did not try a fix, so status is blocked.
- Tool-call budget reached before the failing tests were investigated further.
- Evidence PNGs written by the browser run were restored or removed; nothing under docs/tasks/*-evidence is committed.
- No push, no PR, main untouched.

## Questions

1. Smart locks test: should the guide key `smart_locks.s6` / guide wording be updated, or should the test's expected guide words change? Owner or orchestrator decision.
2. `test_each_property_setting_has_exactly_one_editable_control_in_the_whole_host`: is `city_en` a regression from 0205, or a known gap? Needs a check on main.
3. Brief §5 is missing `## 5. Do not touch` and makes context lint fail.

## Owner steps left

- Decide questions 1 to 3 above, then re-run the failing commands 4 and 5.
- Confirm whether the 360 px tab overflow is tracked as its own brief (it fails on main).
