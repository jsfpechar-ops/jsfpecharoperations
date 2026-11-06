# 0987: PR 790: property "?" in the h1, CI green, simpler stays copy, alert link check

Status: todo
Depends on: 0986 | Base commit: origin/codex/ux-remediation-handoff | Branch: codex/ux-remediation-handoff
Executor: Haiku 5.5 | Fits one session: 25 tool calls (at 21 calls stop and report).

## 1. Objective
Four fixes on the branch, most important first: (A) the property page "?" sits inside the title line as on main; (B) the 15 CI failures of job `test` on head 0ced2abf are gone; (C) the stays list loses the overdue note and gets main's first filter label; (D) the stay alert on `/settings` links to the stay as on main. Markup restoration, never a weakened assertion.

## 2. Context
- Owner decision (decisions.md, 0986): main's property header. 0986 step 3 (CSS only) failed because the shared partial `App/app/templates/partials/settings_back_header.html` on the branch renders a page help OUTSIDE the h1 (`help_is_page`). Main renders `{{ help }}` INSIDE the h1 in `<span class="tip-nowrap">` with the last word. The `page-help-wrap` macro in `_components.html` stays (popover fix, works inside the h1). Settings pages using this partial also return to main's look (intended).
- Owner on stays copy: "feels too AI and extra, we want simpler and intuitive". Keep the "Overdue" group heading (`stays.grp.overdue`).
- CI messages: test_0534 x2 `ValueError: substring not found`; test_design_dashboard `assert 2 == 1`; test_page_help_0277 x3 `AssertionError: dashboard`; test_signed_in_chrome expects `<span class="ph-hide">Dashboard`; test_host_redesign x2 `AssertionError: /`; test_ttlock_setup_0954 x4 `assert (None)`; two door-code tests (form action `/apartments/<id>/door-codes`). 0986 may have fixed some.
- Facts found by grep (verify before editing):
  - Dashboard branch line 49 of `App/app/templates/dashboard.html` (inside `.ov-title-row`): `<h1 class="hl... ph-hide">{{ t('dashboard.title') }}</h1><span class="ph-hide">{{ page_help('dashboard') }}</span><h1 class="hl... ph-only" aria-hidden="true">...</h1>`. Main (line 49): ONE `<h1 class="hl{{ ' done' if not ny_lines }}"><span class="ph-hide{{ ' cal-hide' if cal_view }}">{{ t('dashboard.title') }}{{ page_help('dashboard') }}</span><span class="ph-only">{% if cal_view %}{{ t('nav.calendar') }}{% elif ny_lines %}{{ tp('dashboard.ph.need', ny_lines | length) }}{% else %}{{ t('dashboard.ph.done') }}{% endif %}</span></h1>`. The branch has two h1 (the cause of `2 == 1`) and the help outside the `<span class="ph-hide">Dashboard`.
  - `property-detail` class: used by `App/tests/test_host_wide_geometry_browser.py` lines 58-59 (selector `.property-detail, .panel`) and `app2.css` ~2623 uses `.form.prop-form-single` (not property-detail). So the class is used by a test: do NOT remove it; update the test_0534 substring to the new markup.
  - Stays: `App/app/templates/reservations.html` lines 101-105 hold `overdue_scope` and `data-stays-overdue-note`; i18n keys `stays.scope.overdue_note` in `App/app/host_i18n.py` (en ~1243, cs ~3319) and `App/app/host_vi_i18n.py` ~1278. Label key `stays.chip.upcoming`: main "Upcoming & current" / cs "Nadcházející" / vi "Sắp tới và hiện tại" (uk: check whether it changed). Branch: "Upcoming, current & overdue" etc.
  - Tests pinning the removed copy: `App/tests/test_host_filter_panels_browser.py` (SCOPE_LABEL line 522, SCOPE_NOTE ~523, assertions ~613, ~619, geometry ~717-731 incl. `noteInside`), `App/tests/test_0285_rows_browser.py` line 33.
  - Alerts: `_host_alerts.html` line 29 wraps the whole card in `<a class="notification-link">` when `alert.action_href`; the "Open the stay" label `<small class="notification-action">` is hidden by `not (compact_page or ...)` on line 34 (compact_page is true on /settings). Main's label key is `notification.open_stay` (`app/alerts.py` 357).

## 3. Files
- `App/app/templates/partials/settings_back_header.html`, `App/app/static/app2.css`, `App/app/templates/base.html`, `App/tests/static_versions.json` (generated), `docs/design/catalog.json` (only if a class is added)
- `App/app/templates/dashboard.html`, `App/app/templates/_property_editor.html`, `App/app/templates/reservations.html`, `App/app/templates/_host_alerts.html`
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` (and the uk file only if the label differs from main)
- Tests named in step 3 to 6 (pins and markup substrings only), `App/tests/v2_mockup.py` (pins only)
- `docs/tasks/0987-report.md`, `docs/tasks/screenshots-0987/`

## 4. Steps
1. Setup: `git fetch origin main codex/ux-remediation-handoff 2>&1 | tail -3; git checkout -B codex/ux-remediation-handoff origin/codex/ux-remediation-handoff 2>&1 | tail -3`. Then from `App/` ONE call, record which still fail: `.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_design_dashboard.py tests/test_door_code_missing_times_0397.py tests/test_door_code_one_lock_one_property.py tests/test_host_redesign.py tests/test_page_help_0277.py tests/test_signed_in_chrome.py tests/test_ttlock_setup_0954.py -q --tb=line 2>&1 | tail -30`.
2. A. Header partial. Replace the file `App/app/templates/partials/settings_back_header.html` with main's: `git show origin/main:App/app/templates/partials/settings_back_header.html > App/app/templates/partials/settings_back_header.html`. Check `git diff --stat | tail -3` shows only this file. Then list the callers first: `grep -rln "airbnb-header" App/app/templates | head -20`. In `app2.css` the rules at `grep -n "airbnb-header>.page-help\|airbnb-header:has(>.page-help" App/app/static/app2.css` (lines ~1845-1847, 2379) positioned the outside help. Delete them only if no template other than the partial emits a `.airbnb-header` child `.page-help`/`.page-help-wrap` (the partial no longer does, so they are dead); list the callers in the report. Commit `0987 step 2`.
3. B1. Dashboard: in `dashboard.html` line 49 keep the branch's `.ov-title-row` wrapper and the calendar branch (`{% if cal_view %}...{% else %}`), but in the else branch put main's single h1 (see Context) instead of the two h1 plus the `ph-hide` span. Then `grep -n "ov-title-row\|ph-hide.*hl" App/app/static/app2.css | cut -c1-160 | head` to see CSS that expected the old markup; leave it unless a test fails. Run the B command from step 1 for `tests/test_design_dashboard.py tests/test_page_help_0277.py tests/test_signed_in_chrome.py tests/test_host_redesign.py -q --tb=short 2>&1 | tail -30`. If `test_host_redesign` still fails read its assertion (one read) and restore the missing markup, not the test. Commit `0987 step 3`.
4. B2. test_0534 x2: `grep -n "prop-form-single" App/tests/test_0534_property_page_v2.py | cut -c1-150`. Change the searched substring from `<div class="form prop-form-single">` to `<div class="form prop-form-single property-detail">` (markup pin: `property-detail` is used by test_host_wide_geometry_browser, so the class stays). Run that test file. Commit `0987 step 4`.
5. B3. Lock tab: for the ttlock x4 and door-code x2 tests, read the failing assertion lines (`--tb=short`, `tail -30`, one test at a time at most). Compare: `git show origin/main:App/app/templates/_property_editor.html | grep -n "door-codes\|lock-" | cut -c1-170` against `grep -n "door-codes\|lock-" App/app/templates/_property_editor.html | cut -c1-170`. Restore the missing markup, ids or form action `/apartments/{{ apartment.id }}/door-codes` from main (the branch keeps `#lock-setup-state`, `#lock-connected-off`, `#lock-unavailable`; keep them). Rerun those four files. Commit `0987 step 5`. If more than 6 calls are spent here: stop, go to step 6, and say so in the report.
6. C. Stays copy. (a) `reservations.html`: delete lines 101-105 (the `overdue_scope` namespace, its `if`/`for` block and the `data-stays-overdue-note` paragraph); `grep -n "overdue_scope" App/app/templates/reservations.html` must print nothing. (b) i18n: set `stays.chip.upcoming` back to main's text in en, cs, vi (and uk if it changed): `git show origin/main:App/app/host_i18n.py | grep -n "stays.chip.upcoming"`. Delete `stays.scope.overdue_note` from the three files (grep shows no other reference after (a)). Keep `stays.grp.overdue`. (c) Tests: `test_0285_rows_browser.py` line 33 label to `Upcoming &amp; current`; in `test_host_filter_panels_browser.py` set SCOPE_LABEL to main's texts, delete the SCOPE_NOTE dict only if nothing else uses it, delete only the assertions on the note (`data-stays-overdue-note` at ~613 and ~619, `noteInside` at ~717-731); keep the overdue stay still-visible assertions. Say in the report which assertions were deleted. Run `.venv/bin/python -m pytest tests/test_0285_rows_browser.py tests/test_host_filter_panels_browser.py -k "stays or overdue or scope or rows" -q --tb=short -rs 2>&1 | tail -30` (0 skipped). Commit `0987 step 6`.
7. D. Alert: the whole card IS a link (`<a class="notification-link">` wraps `<strong>` title, so the accessible name is the title text), but the visible "Open the stay" line is hidden on compact pages. Restore it: in `_host_alerts.html` line 34 change the condition to `{% if alert.action_label_key and not (alert.id in held.outside) %}`; then compare 390 px `/settings` in the screenshots. If layout-lint or a `compact_page` test fails (grep `compact_page` in App/tests, at most one grep), revert this line and report: "alert is a full-card link with title as accessible name; label hidden by compact_page by design". One line in the report either way. Commit `0987 step 7`.
8. E. Cache and catalog. Only if `app2.css` changed in step 2: `sed -i -E 's#(/static/app2\.css\?v=)[^"]*#\120261106-0987#' App/app/templates/base.html 2>&1 | tail -30`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. New CSS class: none expected; if one is added put it in `docs/design/catalog.json` (classes and class_notes). Then `python3 scripts/design_lint.py | tail -3`. Commit `0987 step 8`.
9. F. Verification (below, section 6). Geometry pins (`v2_mockup.py` `overview:.hl`, property title pins) change only to the measured value, only where main's markup was restored, comment `# 0987: main markup restored`.
10. Screenshots and report: copy `property-detail-configured-390.png`, `stays-390.png`, `settings-390.png`, `dashboard-390.png` (names as in `ls /tmp/shots-0987/layout-lint/ | grep 390 | head -40`) into `docs/tasks/screenshots-0987/`. Write `docs/tasks/0987-report.md`: `Status: review` only if every command is green, else `blocked` with `Done: steps 1 to k. Left: ...`. Set this brief's Status to match. Commit `0987: PR 790 CI green, property help in h1, simpler stays copy`, `git push -u origin codex/ux-remediation-handoff 2>&1 | tail -3` (no force, never main, no PR).

## 5. Do not touch
Any other template or CSS, `_components.html` (`page-help-wrap` macro stays), `App/app/*.py` other than the i18n files named, migrations, `main`. No test assertion changes other than the substring/label pins and the note assertions named in steps 4, 6, 9.

## 6. Commands
From `App/`, each ending `2>&1 | tail -30` (last pytest one `| tail -15`):
```
ruff check app tests tools --select E9,F63,F7,F82,F401,F841
.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_design_dashboard.py tests/test_door_code_missing_times_0397.py tests/test_door_code_one_lock_one_property.py tests/test_host_redesign.py tests/test_page_help_0277.py tests/test_signed_in_chrome.py tests/test_ttlock_setup_0954.py -q --tb=line
.venv/bin/python -m pytest tests -q -x --ignore-glob='*browser*' -p no:cacheprovider
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots-0987 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_0786_settings_geometry_browser.py tests/test_host_property_controls_browser.py -q --tb=short -x -rs
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots-0987 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "propert or overview or stays or settings" -q --tb=short -rs
```
Owner allows the one non-browser full run (third command) for this brief: CI's `test` job runs exactly that and was red. From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v ^WARN | tail -3` (OK) and `python3 scripts/design_lint.py | tail -3`.

## 7. Acceptance
- [ ] 390 px property page: "?" right after the name inside the title line, not on its own line
- [ ] step-1 test command: 0 failed; non-browser full run green; ruff clean
- [ ] browser commands: 0 failed, 0 skipped
- [ ] stays list: no overdue note, first filter label as on main, "Overdue" group heading kept
- [ ] stay alert on /settings: "Open the stay" visible (or the one-line reason in the report)
- [ ] cache key `20261106-0987` (if css changed), static_versions regenerated, context_lint and design_lint OK
- [ ] four 390 screenshots in `docs/tasks/screenshots-0987/`, report written, pushed

## 8. Stop and ask
- An anchor or main range does not match what this brief prints.
- A test fails twice, or only passes if an assertion is weakened.
- Restoring main's partial breaks a settings page geometry test that a pin change cannot explain.
- The non-browser full run shows failures outside the 15 named ones.
At 21 tool calls stop and report: commit, write the report with `Status: blocked`, `Done: steps 1 to k. Left: steps k+1 to 10.` Push what is committed.

## 9. Report
`docs/tasks/0987-report.md`, 600 tokens at most: files changed, last 5 lines of each section 6 command, section 7 ticked, per-screenshot sentence (what you saw at 390), callers of `airbnb-header` listed, pins changed (old, new), deleted note assertions, alert one-liner, deviations, questions.
