# 0148 report

Status: review

## Files changed
- App/app/host_i18n.py (setup-count keys, EN and CS)
- App/app/templates/dashboard.html (banner list plus one-line short form)
- docs/design/catalog.json (new hook classes)
- App/app/static/host2.css (phone rule for the short banner line)
- App/app/templates/_host_alerts.html (group guest_pin_rotated alerts into one card)
- App/app/routes/admin.py (dismiss resolves every open guest_pin_rotated alert of the owner)
- App/tests/test_dashboard_phone_browser.py (PIN card and banner assertions at 390 and 1280)
- docs/tasks/0148-evidence/calendar-phone-390-alert.png, calendar-phone-1280.png

## Commands (last lines)
- `python3 scripts/design_lint.py | tail -3`: `design lint: OK`
- `pytest tests/test_dashboard_phone_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_design_dashboard.py -q --tb=line -rs`: `6 passed, 1 warning in 40.28s` (0 skipped)
- `pytest tests -q -x --tb=short -k "alert or host_i18n or i18n_parity"`: `1 failed, 53 passed, 3623 deselected`. The failure is tests/test_endtoend.py::test_24, which needs an apartment created by earlier tests in its file; the -k filter deselects them, so it fails only under this filter.
- `pytest tests/test_endtoend.py -q --tb=short`: `28 passed`
- `pytest tests -q --tb=line -k "alert or host_i18n or i18n_parity"`: `1 failed, 135 passed` (same test_24 filter artifact)
- `App/.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 ...`: `All checks passed!`

## Screenshots
- 390 px: one PIN card naming Calendar home 1, 2 and 3, with a link to the properties page. The amber banner is one line, "3 properties need setup", with the Finish setup button.
- 1280 px: the banner lists the three properties with their missing fields, and the Finish setup button is on the right.

## Checklist (brief section 7)
- [x] design_lint OK after step 1
- [x] Phone, dashboard and design tests pass with 0 skipped; i18n keys added in both languages
- [x] One guest_pin_rotated card at 390 px, asserted by the test (dismiss-then-reload check in the test)
- [x] Screenshots committed

## Deviations
- Step 4 `-k` subset: test_24 fails under the filter only (see above). It passes when run in its file.
- No push, no PR, as instructed by the orchestrator. The owner opens the PR.
- Commit trailer uses Claude Haiku 5.5 (the executor's model), not the Opus line in the brief.

## Questions
None.

## Owner steps left
- Review and merge the branch with scripts/merge-pr-on-green.sh. Production deploy is manual.
