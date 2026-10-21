# 0206 report: urgent alerts switch in Settings

Status: blocked (one layout check, see Deviations)

## Files changed (steps 1 to 6, one commit each)
- App/app/templates/settings.html (alerts row, device list)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (remove-confirm copy)
- App/app/static/pwa.js (push block; logout hook)
- App/app/templates/base.html, App/app/templates/auth_base.html (key 20261021-0206)
- App/tests/static_versions.json (regenerated, 33 files)
- App/tests/test_push_settings_browser.py (new)
- docs/tasks/0206-report.md, docs/tasks/0206-push-settings-ui.md (Status only)

## Commands (last 5 lines)
- `node --check App/app/static/pwa.js`: no output, exit 0
- `python3 scripts/design_lint.py`: `design lint: OK`
- `.venv/bin/python -m pytest tests/test_pwa.py ... tests/test_cookie_inventory.py -q --tb=short`: `63 passed, 2 warnings in 3.56s`
- `UBYHOST_REQUIRE_BROWSER=1 ... pytest tests/test_push_settings_browser.py tests/test_pwa_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q -rs`: `27 passed, 1 warning in 82.17s` (0 skipped)
- `python3 scripts/context_lint.py`: `context lint: OK`

## Acceptance (§7)
- [x] §6 passes, 0 skipped
- [x] 14 screenshots in /mnt/project-files/pwa/0206/, each viewed once; nothing cut off at 390 in en, cs, vi; labels fit
- [ ] On badge and the two buttons on one line at 1280 and 2000: not met (see below)
- [x] Only §3 files changed (pre-existing uncommitted docs edits in the tree were left alone, not committed)

## Deviations
- Step 7 layout check: at 1280 and 2000 px the On badge sits beside the row title, and "Send a test" and "Turn off" sit on a second row below the text. The brief asks for one line. The fix needs CSS, which §3 excludes, so I stopped per §4 step 7 and changed no CSS.
- Test command 1 was run without `-x`, so the known test_host_i18n.py failures would show. None occurred.
- No PR opened (invocation said not to).

## Questions
- Is the one-line badge-and-buttons layout required at 1280 and 2000? If yes, a CSS change to settings is needed (new brief).

## Owner steps left
- None from this brief.
