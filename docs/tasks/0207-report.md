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

## Follow-up (step 9)

Step 9 a) and b) applied (one exact match each), committed as `0207 step 9` (0db03b4). Status stays `blocked`: one test still fails.

Commands (last lines):

1. `.venv/bin/python -m pytest tests/test_reporting_help_0097.py tests/test_smart_locks_page.py -q --tb=short` (From App/)
```
FAILED tests/test_smart_locks_page.py::test_after_connecting_three_essentials_and_every_tap_in_the_guide
1 failed, 18 passed, 1 warning in 14.94s
```
Failure: `tests/test_smart_locks_page.py:111`: `assert "Otevřete svůj zámek v TTLock." in cs` (the Czech `/apartments/…?view=settings&section=lock&lang=cs` page does not contain this string). Not caused by step 9 a): that edit changed only the guide-English assertion on line 106. The copy lives in `App/app/host_i18n.py` / `App/app/guide_i18n.py`, which the brief does not name. Not fixed here.

2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_ux_acceptance.py -q --tb=line -rs` (From App/)
```
12 passed, 1 warning in 116.48s (0:01:56)
```
0 skipped. Step 9 b) is covered by this run.

3. `python3 scripts/design_lint.py` (repo root)
```
design lint: OK
```

4. `python3 scripts/context_lint.py | grep -i error` (repo root)
```
(no output: no error lines)
```

Not run: `tests/test_onboarding_wizard_browser.py` (brief §6 item 5) was not in this follow-up's command list.

Evidence: working tree clean after the runs; no PNGs committed.

Left for the owner or the next session: fix the Czech copy assertion at `App/tests/test_smart_locks_page.py:111` (decide whether the copy or the assertion is wrong), then rerun the first command, then set Status to `review`.
