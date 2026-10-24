# 0365 report

Status: review

Files changed: `App/tests/test_push_settings_browser.py`, `docs/tasks/0365-report.md`. No app file touched (Risk list: none).

Failures (8, all one cause):
- turning_alerts_on_sends_one_test (en/cs/vi), the_alerts_row_fits_wide_layouts (4), logging_out_turns_alerts_off: test environment, not stale and not an app bug. Playwright's old headless shell reports `Notification.permission === "denied"` even after `grant_permissions(["notifications"])` (Permissions API says granted), so pwa.js correctly paints the denied state. Fix: launch with `channel="chromium"` (new headless) unless `UBYHOST_BROWSER_EXECUTABLE` is set.
- CI-only: `SHOT_DIR` was hard-coded to `/mnt/project-files/...`; now `$UBYHOST_SHOTS_DIR` or the temp dir + `pwa-0227` (coordinator request).

Commands: push settings file, 11 passed, 0 skipped, twice; guardrails + a11y browser files, 14 passed.
No test skipped, deleted or loosened. 390 px screenshots are written by the test to the shots dir (no template/CSS change).
Owner steps: merge when CI is green; CI needs the full Chromium installed (`playwright install chromium` does it).

## Orchestrator review

Reviewed. The channel switch only applies to this file and only when no system browser is configured; CI installs full Chromium with `playwright install chromium`.
